from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _create_company_and_adopt_orphaned_data(db: Session, name: str) -> "models.Company":
    """Creates a new company and claims every row across every table that
    currently has no company_id at all (data from before multi-tenancy
    existed). Shared between the bootstrap registration path and the
    self-healing login path below - both situations are "this data
    unambiguously belongs to whoever is claiming it now"."""
    company = models.Company(name=name)
    db.add(company)
    db.flush()

    for model in [
        models.Party, models.Invoice, models.Payment,
        models.Supplier, models.Purchase, models.PurchasePayment,
        models.CompanySettings,
    ]:
        db.query(model).filter(model.company_id.is_(None)).update(
            {"company_id": company.id}, synchronize_session=False
        )

    return company


@router.get("/status")
def auth_status():
    """Unauthenticated - lets the frontend know whether to show a login
    screen at all. False until at least one account exists anywhere."""
    return {"required": auth.is_auth_required()}


@router.post("/login")
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    if not auth.is_auth_required():
        return {"token": None, "required": False}

    user = auth.authenticate(db, payload.username, payload.password)
    if not user:
        raise HTTPException(401, "Incorrect username or password")

    company_id = auth.get_active_company_id(db, user)
    if not company_id:
        # Self-healing repair, not a hard failure: this happens for an
        # account created by an EARLIER version of this app, from before
        # multi-tenancy existed - back then there was no concept of a
        # "company" at all, so accounts like this have no membership row.
        # Rather than lock the person out permanently, fix it on the spot:
        # give them their own company now (reusing an orphaned
        # CompanySettings name if one exists, since that's very likely
        # their real, already-configured business), and claim any
        # pre-existing orphaned data into it, exactly like the bootstrap
        # registration flow does for the very first account.
        orphaned_settings = db.query(models.CompanySettings).filter(
            models.CompanySettings.company_id.is_(None)
        ).first()
        company_name = (orphaned_settings.company_name if orphaned_settings and orphaned_settings.company_name
                         else f"{user.display_name}'s Company")

        company = _create_company_and_adopt_orphaned_data(db, company_name)
        db.add(models.CompanyMembership(user_id=user.id, company_id=company.id))
        db.commit()
        company_id = company.id

    company = db.query(models.Company).filter(models.Company.id == company_id).first()

    return {
        "token": auth.create_token(user, company_id),
        "required": True,
        "display_name": user.display_name,
        "company_name": company.name if company else None,
        "is_platform_admin": user.is_platform_admin,
    }


@router.post("/register", response_model=schemas.UserOut)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    """
    Signup is invite-only, not open self-registration - two paths:

    1. Bootstrap: zero accounts exist anywhere yet. Open, no invite needed -
       this IS how the very first account (and first company) gets created.
       That account becomes a platform admin automatically.
    2. Everyone else: requires a valid, unused, unexpired invite_token.
       - If the invite has no company_id: redeemer names a brand NEW company
         and becomes its first (and, so far, only) member.
       - If the invite has a company_id: redeemer joins that EXISTING
         company with full access, alongside whoever's already there.
    """
    existing = db.query(models.AppUser).filter(models.AppUser.username == payload.username).first()
    if existing:
        raise HTTPException(409, "That username is already taken")

    is_bootstrap = not auth.is_auth_required()

    if is_bootstrap:
        if not payload.company_name:
            raise HTTPException(422, "Company name is required")

        user = models.AppUser(
            username=payload.username,
            display_name=payload.display_name,
            password_hash=auth.hash_password(payload.password),
            is_platform_admin=True,
        )
        db.add(user)
        db.flush()

        # This deployment may already have real data from before multi-tenancy
        # existed (parties, invoices, company settings, etc. all created with
        # no company_id at all, back when there was only ever one business).
        # Since this is the very first company ever created here, every
        # orphaned row unambiguously belongs to it - claim all of it now
        # rather than leaving it invisible/orphaned once company scoping
        # kicks in for every query from this point forward.
        company = _create_company_and_adopt_orphaned_data(db, payload.company_name)

        db.add(models.CompanyMembership(user_id=user.id, company_id=company.id))

        db.commit()
        db.refresh(user)

        auth.refresh_auth_required_cache(db)
        return user

    # Not bootstrap - a valid invite is mandatory
    if not payload.invite_token:
        raise HTTPException(401, "An invite is required to create an account")

    invite = db.query(models.Invite).filter(models.Invite.token == payload.invite_token).first()
    if not invite:
        raise HTTPException(404, "Invite not found - check the link and try again")
    if invite.used_at is not None:
        raise HTTPException(410, "This invite has already been used")
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(410, "This invite has expired")

    user = models.AppUser(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=auth.hash_password(payload.password),
        is_platform_admin=False,
    )
    db.add(user)
    db.flush()

    if invite.company_id:
        company_id = invite.company_id
    else:
        if not payload.company_name:
            raise HTTPException(422, "Company name is required")
        company = models.Company(name=payload.company_name)
        db.add(company)
        db.flush()
        company_id = company.id

    db.add(models.CompanyMembership(user_id=user.id, company_id=company_id))

    invite.used_by_user_id = user.id
    invite.used_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    auth.refresh_auth_required_cache(db)
    return user


@router.post("/invites", response_model=schemas.InviteOut)
def create_invite(payload: schemas.InviteCreate, request: Request, db: Session = Depends(get_db)):
    """
    Two kinds, depending on for_new_company:
    - True: invite to start a fresh, separate business - platform-admin only
      (signup is invite-only, so this is the gate on who can onboard
      entirely new companies onto this deployment).
    - False (default): invite to join the CALLER's own current company with
      full access - any existing member can do this for their own company
      (e.g. Rahul inviting his father into Vrindavan Organics).
    """
    user_id = auth.get_current_user_id(request)
    if not user_id:
        raise HTTPException(401, "Not authenticated")

    if payload.for_new_company:
        if not auth.is_current_user_platform_admin(request):
            raise HTTPException(403, "Only a platform admin can invite someone to start a new company")
        company_id = None
    else:
        company_id = auth.get_current_company_id(request)
        if not company_id:
            raise HTTPException(400, "You're not currently in a company")

    invite = models.Invite(
        token=auth.generate_invite_token(),
        company_id=company_id,
        created_by_user_id=user_id,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


@router.get("/invites", response_model=List[schemas.InviteOut])
def list_invites(request: Request, db: Session = Depends(get_db)):
    """Invites created by the current user, so they can see which links are
    still unused vs already redeemed."""
    user_id = auth.get_current_user_id(request)
    if not user_id:
        raise HTTPException(401, "Not authenticated")
    return (
        db.query(models.Invite)
        .filter(models.Invite.created_by_user_id == user_id)
        .order_by(models.Invite.created_at.desc())
        .all()
    )


@router.get("/users", response_model=List[schemas.UserOut])
def list_company_users(request: Request, db: Session = Depends(get_db)):
    """Everyone in the CURRENT user's company - not a global user list,
    since other companies' members shouldn't be visible to you at all."""
    company_id = auth.get_current_company_id(request)
    if not company_id:
        raise HTTPException(400, "You're not currently in a company")

    user_ids = [
        m.user_id for m in
        db.query(models.CompanyMembership).filter(models.CompanyMembership.company_id == company_id).all()
    ]
    return db.query(models.AppUser).filter(models.AppUser.id.in_(user_ids)).order_by(models.AppUser.created_at).all()


@router.delete("/users/{user_id}")
def deactivate_user(user_id: str, request: Request, db: Session = Depends(get_db)):
    """Deactivates rather than deletes - keeps their name attached to
    whatever they've already added/edited, rather than leaving those
    references pointing at a vanished account. Only removes them from the
    CALLER's own company context (doesn't touch other companies they might
    separately belong to, though that's rare in practice)."""
    company_id = auth.get_current_company_id(request)
    if not company_id:
        raise HTTPException(400, "You're not currently in a company")

    membership = (
        db.query(models.CompanyMembership)
        .filter(models.CompanyMembership.user_id == user_id, models.CompanyMembership.company_id == company_id)
        .first()
    )
    if not membership:
        raise HTTPException(404, "That person isn't in your company")

    user = db.query(models.AppUser).filter(models.AppUser.id == user_id).first()

    active_count = (
        db.query(models.CompanyMembership)
        .join(models.AppUser, models.AppUser.id == models.CompanyMembership.user_id)
        .filter(models.CompanyMembership.company_id == company_id, models.AppUser.is_active == True)  # noqa: E712
        .count()
    )
    if active_count <= 1 and user.is_active:
        raise HTTPException(400, "Can't remove the last active person in this company - you'd lock everyone out")

    user.is_active = False
    db.commit()
    auth.refresh_auth_required_cache(db)
    return {"ok": True}
