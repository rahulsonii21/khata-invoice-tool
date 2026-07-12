from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas, auth
from ..database import get_db
from ..audit import log_change

router = APIRouter(prefix="/api/invoices/{invoice_id}/payments", tags=["payments"])
standalone_router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("", response_model=List[schemas.PaymentOut])
def list_payments(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return invoice.payments


@router.post("", response_model=schemas.PaymentOut)
def add_payment(invoice_id: str, payload: schemas.PaymentCreate, request: Request, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    data = payload.model_dump()
    data["created_by"] = auth.get_current_username(request)
    payment = models.Payment(invoice_id=invoice_id, **data)
    db.add(payment)
    db.flush()  # so invoice.payments reflects the new row

    invoice.refresh_status()
    db.commit()
    db.refresh(payment)
    return payment


@standalone_router.put("/{payment_id}", response_model=schemas.PaymentOut)
def update_payment(payment_id: str, payload: schemas.PaymentUpdate, request: Request, db: Session = Depends(get_db)):
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(404, "Payment not found")

    changed_by = auth.get_current_username(request) or payload.changed_by
    updates = payload.model_dump(exclude={"changed_by"}, exclude_unset=True)
    for field, new_value in updates.items():
        old_value = getattr(payment, field)
        if old_value != new_value:
            log_change(db, "payment", payment.id, field, old_value, new_value, changed_by)
            setattr(payment, field, new_value)

    if updates:
        payment.edited_at = datetime.utcnow()

    payment.invoice.refresh_status()
    db.commit()
    db.refresh(payment)
    return payment


@standalone_router.delete("/{payment_id}")
def delete_payment(payment_id: str, db: Session = Depends(get_db)):
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(404, "Payment not found")
    invoice = payment.invoice
    db.delete(payment)
    db.flush()
    invoice.refresh_status()
    db.commit()
    return {"ok": True}
