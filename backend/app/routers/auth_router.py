from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
def auth_status():
    """Unauthenticated - lets the frontend know whether to show a login
    screen at all. False until at least one account has been created."""
    return {"required": auth.is_auth_required()}


@router.post("/login")
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    if not auth.is_auth_required():
        return {"token": None, "required": False}

    user = auth.authenticate(db, payload.username, payload.password)
    if not user:
        raise HTTPException(401, "Incorrect username or password")

    return {
        "token": auth.create_token(user),
        "required": True,
        "display_name": user.display_name,
    }


@router.post("/register", response_model=schemas.UserOut)
def register(payload: schemas.UserRegister, request: Request, db: Session = Depends(get_db)):
    """
    Creates a new account. Behaves differently depending on whether any
    accounts already exist:
    - Zero accounts (fresh install / nobody's set this up yet): open,
      no login needed - this IS how the very first account gets created.
    - One or more accounts already exist: the request must already be
      authenticated (the AuthMiddleware enforces this automatically, since
      is_auth_required() becomes true the moment the first account exists) -
      any logged-in person can add another, since everyone has equal
      permissions here by design.
    """
    existing = db.query(models.AppUser).filter(models.AppUser.username == payload.username).first()
    if existing:
        raise HTTPException(409, "That username is already taken")

    user = models.AppUser(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=auth.hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    auth.refresh_auth_required_cache(db)

    return user


@router.get("/users", response_model=List[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.AppUser).order_by(models.AppUser.created_at).all()


@router.delete("/users/{user_id}")
def deactivate_user(user_id: str, db: Session = Depends(get_db)):
    """Deactivates rather than deletes - keeps their name attached to
    whatever they've already added/edited in the audit log and on records,
    rather than leaving those references pointing at a vanished account."""
    user = db.query(models.AppUser).filter(models.AppUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    active_count = db.query(models.AppUser).filter(models.AppUser.is_active == True).count()  # noqa: E712
    if active_count <= 1 and user.is_active:
        raise HTTPException(400, "Can't remove the last active account - you'd lock yourself out")

    user.is_active = False
    db.commit()
    auth.refresh_auth_required_cache(db)
    return {"ok": True}
