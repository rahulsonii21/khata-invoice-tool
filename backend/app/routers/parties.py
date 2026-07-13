from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, selectinload
from typing import List

from .. import models, schemas, auth
from ..database import get_db
from ..audit import log_change

router = APIRouter(prefix="/api/parties", tags=["parties"])


@router.get("", response_model=List[schemas.PartyOut])
def list_parties(request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    parties = (
        db.query(models.Party)
        .options(selectinload(models.Party.invoices).selectinload(models.Invoice.payments))
        .filter(models.Party.company_id == company_id)
        .order_by(models.Party.name)
        .all()
    )
    return [_to_out(p) for p in parties]


@router.get("/match/search")
def match_party(request: Request, name: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """
    Fuzzy-matches a party name (typically from OCR extraction) against
    existing parties, so the review screen can suggest "did you mean X?"
    instead of creating duplicate parties for the same party written
    slightly differently (e.g. OCR variance, Hindi vs Hinglish spelling).
    """
    company_id = auth.get_current_company_id(request)
    rows = (
        db.query(models.Party.id, models.Party.name)
        .filter(models.Party.company_id == company_id)
        .all()
    )
    scored = [
        {
            "party_id": row.id,
            "name": row.name,
            "score": SequenceMatcher(None, name.lower().strip(), row.name.lower().strip()).ratio(),
        }
        for row in rows
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [s for s in scored if s["score"] >= 0.55][:5]


@router.get("/{party_id}", response_model=schemas.PartyOut)
def get_party(party_id: str, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    party = (
        db.query(models.Party)
        .options(selectinload(models.Party.invoices).selectinload(models.Invoice.payments))
        .filter(models.Party.id == party_id, models.Party.company_id == company_id)
        .first()
    )
    if not party:
        raise HTTPException(404, "Party not found")
    return _to_out(party)


@router.post("", response_model=schemas.PartyOut)
def create_party(payload: schemas.PartyCreate, request: Request, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["created_by"] = auth.get_current_username(request)
    data["company_id"] = auth.get_current_company_id(request)
    party = models.Party(**data)
    db.add(party)
    db.commit()
    db.refresh(party)
    return _to_out(party)


@router.put("/{party_id}", response_model=schemas.PartyOut)
def update_party(party_id: str, payload: schemas.PartyUpdate, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    party = db.query(models.Party).filter(models.Party.id == party_id, models.Party.company_id == company_id).first()
    if not party:
        raise HTTPException(404, "Party not found")

    changed_by = auth.get_current_username(request) or payload.changed_by
    updates = payload.model_dump(exclude={"changed_by"}, exclude_unset=True)
    for field, new_value in updates.items():
        old_value = getattr(party, field)
        if old_value != new_value:
            log_change(db, "party", party.id, field, old_value, new_value, changed_by)
            setattr(party, field, new_value)

    db.commit()
    db.refresh(party)
    return _to_out(party)


@router.delete("/{party_id}")
def delete_party(party_id: str, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    party = db.query(models.Party).filter(models.Party.id == party_id, models.Party.company_id == company_id).first()
    if not party:
        raise HTTPException(404, "Party not found")
    db.delete(party)
    db.commit()
    return {"ok": True}


def _to_out(party: models.Party) -> schemas.PartyOut:
    return schemas.PartyOut(
        id=party.id,
        name=party.name,
        phone=party.phone,
        gstin=party.gstin,
        address=party.address,
        city=party.city,
        pincode=party.pincode,
        email=party.email,
        notes=party.notes,
        created_at=party.created_at,
        created_by=party.created_by,
        total_invoiced=party.total_invoiced,
        total_received=party.total_received,
        outstanding=party.outstanding,
    )
