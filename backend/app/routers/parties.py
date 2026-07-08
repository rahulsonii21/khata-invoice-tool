from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas
from ..database import get_db
from ..audit import log_change

router = APIRouter(prefix="/api/parties", tags=["parties"])


@router.get("", response_model=List[schemas.PartyOut])
def list_parties(db: Session = Depends(get_db)):
    parties = db.query(models.Party).order_by(models.Party.name).all()
    return [_to_out(p) for p in parties]


@router.get("/match/search")
def match_party(name: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """
    Fuzzy-matches a party name (typically from OCR extraction) against
    existing parties, so the review screen can suggest "did you mean X?"
    instead of creating duplicate parties for the same party written
    slightly differently (e.g. OCR variance, Hindi vs Hinglish spelling).
    """
    parties = db.query(models.Party).all()
    scored = [
        {
            "party_id": p.id,
            "name": p.name,
            "score": SequenceMatcher(None, name.lower().strip(), p.name.lower().strip()).ratio(),
        }
        for p in parties
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    # Only return plausible matches; below ~0.55 similarity it's noise
    return [s for s in scored if s["score"] >= 0.55][:5]


@router.get("/{party_id}", response_model=schemas.PartyOut)
def get_party(party_id: str, db: Session = Depends(get_db)):
    party = db.query(models.Party).filter(models.Party.id == party_id).first()
    if not party:
        raise HTTPException(404, "Party not found")
    return _to_out(party)


@router.post("", response_model=schemas.PartyOut)
def create_party(payload: schemas.PartyCreate, db: Session = Depends(get_db)):
    party = models.Party(**payload.model_dump())
    db.add(party)
    db.commit()
    db.refresh(party)
    return _to_out(party)


@router.put("/{party_id}", response_model=schemas.PartyOut)
def update_party(party_id: str, payload: schemas.PartyUpdate, db: Session = Depends(get_db)):
    party = db.query(models.Party).filter(models.Party.id == party_id).first()
    if not party:
        raise HTTPException(404, "Party not found")

    changed_by = payload.changed_by
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
def delete_party(party_id: str, db: Session = Depends(get_db)):
    party = db.query(models.Party).filter(models.Party.id == party_id).first()
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
        notes=party.notes,
        created_at=party.created_at,
        total_invoiced=party.total_invoiced,
        total_received=party.total_received,
        outstanding=party.outstanding,
    )
