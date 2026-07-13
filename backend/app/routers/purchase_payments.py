from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas, auth
from ..database import get_db
from ..audit import log_change

router = APIRouter(prefix="/api/purchases/{purchase_id}/payments", tags=["purchase_payments"])
standalone_router = APIRouter(prefix="/api/purchase-payments", tags=["purchase_payments"])


@router.get("", response_model=List[schemas.PurchasePaymentOut])
def list_purchase_payments(purchase_id: str, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    purchase = db.query(models.Purchase).filter(
        models.Purchase.id == purchase_id, models.Purchase.company_id == company_id
    ).first()
    if not purchase:
        raise HTTPException(404, "Purchase not found")
    return purchase.payments


@router.post("", response_model=schemas.PurchasePaymentOut)
def add_purchase_payment(purchase_id: str, payload: schemas.PurchasePaymentCreate, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    purchase = db.query(models.Purchase).filter(
        models.Purchase.id == purchase_id, models.Purchase.company_id == company_id
    ).first()
    if not purchase:
        raise HTTPException(404, "Purchase not found")

    data = payload.model_dump()
    data["created_by"] = auth.get_current_username(request)
    data["company_id"] = company_id
    payment = models.PurchasePayment(purchase_id=purchase_id, **data)
    db.add(payment)
    db.flush()

    purchase.refresh_status()
    db.commit()
    db.refresh(payment)
    return payment


@standalone_router.put("/{payment_id}", response_model=schemas.PurchasePaymentOut)
def update_purchase_payment(payment_id: str, payload: schemas.PurchasePaymentUpdate, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    payment = db.query(models.PurchasePayment).filter(
        models.PurchasePayment.id == payment_id, models.PurchasePayment.company_id == company_id
    ).first()
    if not payment:
        raise HTTPException(404, "Payment not found")

    changed_by = auth.get_current_username(request) or payload.changed_by
    updates = payload.model_dump(exclude={"changed_by"}, exclude_unset=True)
    for field, new_value in updates.items():
        old_value = getattr(payment, field)
        if old_value != new_value:
            log_change(db, "purchase_payment", payment.id, field, old_value, new_value, changed_by)
            setattr(payment, field, new_value)

    if updates:
        payment.edited_at = datetime.utcnow()

    payment.purchase.refresh_status()
    db.commit()
    db.refresh(payment)
    return payment


@standalone_router.delete("/{payment_id}")
def delete_purchase_payment(payment_id: str, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    payment = db.query(models.PurchasePayment).filter(
        models.PurchasePayment.id == payment_id, models.PurchasePayment.company_id == company_id
    ).first()
    if not payment:
        raise HTTPException(404, "Payment not found")
    purchase = payment.purchase
    db.delete(payment)
    db.flush()
    purchase.refresh_status()
    db.commit()
    return {"ok": True}
