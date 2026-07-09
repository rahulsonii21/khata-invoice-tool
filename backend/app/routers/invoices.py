from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from .. import models, schemas
from ..database import get_db
from ..audit import log_change

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.get("", response_model=List[schemas.InvoiceOut])
def list_invoices(
    party_id: Optional[str] = Query(None),
    status: Optional[models.InvoiceStatus] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(models.Invoice)
    if party_id:
        q = q.filter(models.Invoice.party_id == party_id)
    if status:
        q = q.filter(models.Invoice.status == status)
    invoices = q.order_by(models.Invoice.invoice_date.desc().nullslast()).all()
    return [_to_out(i) for i in invoices]


@router.get("/{invoice_id}", response_model=schemas.InvoiceOut)
def get_invoice(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return _to_out(invoice)


@router.post("", response_model=schemas.InvoiceOut)
def create_invoice(payload: schemas.InvoiceCreate, db: Session = Depends(get_db)):
    party = db.query(models.Party).filter(models.Party.id == payload.party_id).first()
    if not party:
        raise HTTPException(404, "Party not found - create the party first")

    data = payload.model_dump()

    # Auto-fill due_date from the company's default credit terms, if the
    # caller didn't specify one explicitly and we have both an invoice date
    # and a configured default.
    if not data.get("due_date") and data.get("invoice_date"):
        company = db.query(models.CompanySettings).filter(models.CompanySettings.id == "default").first()
        if company and company.default_credit_days:
            from datetime import timedelta
            data["due_date"] = data["invoice_date"] + timedelta(days=int(company.default_credit_days))

    invoice = models.Invoice(**data)
    invoice.refresh_status()
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return _to_out(invoice)


@router.put("/{invoice_id}", response_model=schemas.InvoiceOut)
def update_invoice(invoice_id: str, payload: schemas.InvoiceUpdate, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    changed_by = payload.changed_by
    updates = payload.model_dump(exclude={"changed_by"}, exclude_unset=True)
    for field, new_value in updates.items():
        old_value = getattr(invoice, field)
        if old_value != new_value:
            log_change(db, "invoice", invoice.id, field, old_value, new_value, changed_by)
            setattr(invoice, field, new_value)

    invoice.refresh_status()
    db.commit()
    db.refresh(invoice)
    return _to_out(invoice)


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    db.delete(invoice)
    db.commit()
    return {"ok": True}


def _to_out(invoice: models.Invoice) -> schemas.InvoiceOut:
    return schemas.InvoiceOut(
        id=invoice.id,
        party_id=invoice.party_id,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        is_overdue=invoice.is_overdue,
        amount=invoice.amount,
        gst_amount=invoice.gst_amount,
        raw_image_url=invoice.raw_image_url,
        ocr_confidence=invoice.ocr_confidence,
        remarks=invoice.remarks,
        shipped_by=invoice.shipped_by,
        vehicle_number=invoice.vehicle_number,
        driver_contact=invoice.driver_contact,
        is_generated=invoice.is_generated or False,
        items_json=invoice.items_json,
        cgst_pct=invoice.cgst_pct,
        sgst_pct=invoice.sgst_pct,
        igst_pct=invoice.igst_pct,
        status=invoice.status,
        created_at=invoice.created_at,
        total_paid=invoice.total_paid,
        outstanding=invoice.outstanding,
        payments=[schemas.PaymentOut.model_validate(p) for p in invoice.payments],
    )
