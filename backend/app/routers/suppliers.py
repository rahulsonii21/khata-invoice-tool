from difflib import SequenceMatcher
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, selectinload
from typing import List

from .. import models, schemas, auth
from ..database import get_db
from ..audit import log_change

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("", response_model=List[schemas.SupplierOut])
def list_suppliers(request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    suppliers = (
        db.query(models.Supplier)
        .options(selectinload(models.Supplier.purchases).selectinload(models.Purchase.payments))
        .filter(models.Supplier.company_id == company_id)
        .order_by(models.Supplier.name)
        .all()
    )
    return [_to_out(s) for s in suppliers]


@router.get("/match/search")
def match_supplier(request: Request, name: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """Fuzzy-matches a supplier name, same idea as the customer-party version -
    helps avoid creating duplicate suppliers from OCR spelling variance."""
    company_id = auth.get_current_company_id(request)
    rows = (
        db.query(models.Supplier.id, models.Supplier.name)
        .filter(models.Supplier.company_id == company_id)
        .all()
    )
    scored = [
        {
            "supplier_id": row.id,
            "name": row.name,
            "score": SequenceMatcher(None, name.lower().strip(), row.name.lower().strip()).ratio(),
        }
        for row in rows
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [s for s in scored if s["score"] >= 0.55][:5]


@router.get("/{supplier_id}", response_model=schemas.SupplierOut)
def get_supplier(supplier_id: str, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    supplier = (
        db.query(models.Supplier)
        .options(selectinload(models.Supplier.purchases).selectinload(models.Purchase.payments))
        .filter(models.Supplier.id == supplier_id, models.Supplier.company_id == company_id)
        .first()
    )
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    return _to_out(supplier)


@router.post("", response_model=schemas.SupplierOut)
def create_supplier(payload: schemas.SupplierCreate, request: Request, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["created_by"] = auth.get_current_username(request)
    data["company_id"] = auth.get_current_company_id(request)
    supplier = models.Supplier(**data)
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return _to_out(supplier)


@router.put("/{supplier_id}", response_model=schemas.SupplierOut)
def update_supplier(supplier_id: str, payload: schemas.SupplierUpdate, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    supplier = db.query(models.Supplier).filter(
        models.Supplier.id == supplier_id, models.Supplier.company_id == company_id
    ).first()
    if not supplier:
        raise HTTPException(404, "Supplier not found")

    changed_by = auth.get_current_username(request) or payload.changed_by
    updates = payload.model_dump(exclude={"changed_by"}, exclude_unset=True)
    for field, new_value in updates.items():
        old_value = getattr(supplier, field)
        if old_value != new_value:
            log_change(db, "supplier", supplier.id, field, old_value, new_value, changed_by)
            setattr(supplier, field, new_value)

    db.commit()
    db.refresh(supplier)
    return _to_out(supplier)


@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: str, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    supplier = db.query(models.Supplier).filter(
        models.Supplier.id == supplier_id, models.Supplier.company_id == company_id
    ).first()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    db.delete(supplier)
    db.commit()
    return {"ok": True}


def _to_out(supplier: models.Supplier) -> schemas.SupplierOut:
    return schemas.SupplierOut(
        id=supplier.id,
        name=supplier.name,
        phone=supplier.phone,
        gstin=supplier.gstin,
        address=supplier.address,
        city=supplier.city,
        pincode=supplier.pincode,
        email=supplier.email,
        notes=supplier.notes,
        created_at=supplier.created_at,
        created_by=supplier.created_by,
        total_purchased=supplier.total_purchased,
        total_paid=supplier.total_paid,
        outstanding=supplier.outstanding,
    )
