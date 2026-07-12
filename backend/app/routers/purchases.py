from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional

from .. import models, schemas, auth
from ..database import get_db
from ..audit import log_change

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


@router.get("", response_model=List[schemas.PurchaseOut])
def list_purchases(
    supplier_id: Optional[str] = Query(None),
    status: Optional[models.InvoiceStatus] = Query(None),
    month: Optional[str] = Query(None, description="YYYY-MM, filters by purchase_date"),
    db: Session = Depends(get_db),
):
    q = db.query(models.Purchase).options(selectinload(models.Purchase.payments))
    if supplier_id:
        q = q.filter(models.Purchase.supplier_id == supplier_id)
    if status:
        q = q.filter(models.Purchase.status == status)
    if month:
        from datetime import datetime
        import calendar
        year, mon = (int(x) for x in month.split("-"))
        last_day = calendar.monthrange(year, mon)[1]
        q = q.filter(
            models.Purchase.purchase_date >= datetime(year, mon, 1).date(),
            models.Purchase.purchase_date <= datetime(year, mon, last_day).date(),
        )
    purchases = q.order_by(models.Purchase.purchase_date.desc().nullslast()).all()
    return [_to_out(p) for p in purchases]


@router.get("/{purchase_id}", response_model=schemas.PurchaseOut)
def get_purchase(purchase_id: str, db: Session = Depends(get_db)):
    purchase = (
        db.query(models.Purchase)
        .options(selectinload(models.Purchase.payments))
        .filter(models.Purchase.id == purchase_id)
        .first()
    )
    if not purchase:
        raise HTTPException(404, "Purchase not found")
    return _to_out(purchase)


@router.post("", response_model=schemas.PurchaseOut)
def create_purchase(payload: schemas.PurchaseCreate, request: Request, db: Session = Depends(get_db)):
    supplier = db.query(models.Supplier).filter(models.Supplier.id == payload.supplier_id).first()
    if not supplier:
        raise HTTPException(404, "Supplier not found - create the supplier first")

    data = payload.model_dump()
    data["created_by"] = auth.get_current_username(request)
    purchase = models.Purchase(**data)
    purchase.refresh_status()
    db.add(purchase)
    db.commit()
    db.refresh(purchase)
    return _to_out(purchase)


@router.put("/{purchase_id}", response_model=schemas.PurchaseOut)
def update_purchase(purchase_id: str, payload: schemas.PurchaseUpdate, request: Request, db: Session = Depends(get_db)):
    purchase = db.query(models.Purchase).filter(models.Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(404, "Purchase not found")

    changed_by = auth.get_current_username(request) or payload.changed_by
    updates = payload.model_dump(exclude={"changed_by"}, exclude_unset=True)
    for field, new_value in updates.items():
        old_value = getattr(purchase, field)
        if old_value != new_value:
            log_change(db, "purchase", purchase.id, field, old_value, new_value, changed_by)
            setattr(purchase, field, new_value)

    purchase.refresh_status()
    db.commit()
    db.refresh(purchase)
    return _to_out(purchase)


@router.delete("/{purchase_id}")
def delete_purchase(purchase_id: str, db: Session = Depends(get_db)):
    purchase = db.query(models.Purchase).filter(models.Purchase.id == purchase_id).first()
    if not purchase:
        raise HTTPException(404, "Purchase not found")
    db.delete(purchase)
    db.commit()
    return {"ok": True}


def _to_out(purchase: models.Purchase) -> schemas.PurchaseOut:
    return schemas.PurchaseOut(
        id=purchase.id,
        supplier_id=purchase.supplier_id,
        purchase_number=purchase.purchase_number,
        purchase_date=purchase.purchase_date,
        due_date=purchase.due_date,
        is_overdue=purchase.is_overdue,
        amount=purchase.amount,
        gst_amount=purchase.gst_amount,
        raw_image_url=purchase.raw_image_url,
        ocr_confidence=purchase.ocr_confidence,
        remarks=purchase.remarks,
        status=purchase.status,
        created_at=purchase.created_at,
        created_by=purchase.created_by,
        total_paid=purchase.total_paid,
        outstanding=purchase.outstanding,
        payments=[schemas.PurchasePaymentOut.model_validate(p) for p in purchase.payments],
    )
