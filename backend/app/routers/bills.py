import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, storage, bill_generator
from ..database import get_db

router = APIRouter(prefix="/api/bills", tags=["bills"])


class BillItem(BaseModel):
    description: str
    qty_label: str = ""
    rate: Optional[float] = None
    amount: float
    hsn_code: Optional[str] = None


class GenerateBillRequest(BaseModel):
    party_id: str
    bill_number: Optional[str] = None
    bill_date: Optional[str] = None  # YYYY-MM-DD
    due_date: Optional[str] = None  # YYYY-MM-DD
    items: List[BillItem]
    cgst_pct: float = 0
    sgst_pct: float = 0
    igst_pct: float = 0
    shipped_by: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_contact: Optional[str] = None


class RegenerateBillRequest(BaseModel):
    bill_number: Optional[str] = None
    bill_date: Optional[str] = None
    due_date: Optional[str] = None
    items: List[BillItem]
    cgst_pct: float = 0
    sgst_pct: float = 0
    igst_pct: float = 0
    shipped_by: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_contact: Optional[str] = None


def _build_company_dict(db: Session) -> dict:
    company_row = db.query(models.CompanySettings).filter(models.CompanySettings.id == "default").first()
    company = {}
    if company_row:
        company = {
            "company_name": company_row.company_name,
            "gstin": company_row.gstin,
            "address": company_row.address,
            "phone": company_row.phone,
            "bank_name": company_row.bank_name,
            "bank_ifsc": company_row.bank_ifsc,
            "bank_account_number": company_row.bank_account_number,
        }
        if company_row.logo_url:
            company["logo_bytes"] = storage.get_cached_logo_bytes(company_row.logo_url)
    return company


def _render_bill(company, party, bill_number, bill_date, items, cgst_pct, sgst_pct, igst_pct,
                  shipped_by, vehicle_number, driver_contact) -> bytes:
    bill_date_display = bill_date
    if bill_date:
        try:
            d = datetime.strptime(bill_date, "%Y-%m-%d").date()
            bill_date_display = d.strftime("%d-%m-%Y")
        except ValueError:
            pass

    return bill_generator.generate_bill_image(
        company=company,
        party_name=party.name,
        bill_number=bill_number,
        bill_date=bill_date_display,
        items=[item.model_dump() if hasattr(item, "model_dump") else item for item in items],
        cgst_pct=cgst_pct,
        sgst_pct=sgst_pct,
        igst_pct=igst_pct,
        party_gstin=party.gstin,
        party_address=party.address,
        party_city=party.city,
        party_pincode=party.pincode,
        party_phone=party.phone,
        shipped_by=shipped_by,
        vehicle_number=vehicle_number,
        driver_contact=driver_contact,
    )


@router.post("/generate")
def generate_bill(payload: GenerateBillRequest, db: Session = Depends(get_db)):
    party = db.query(models.Party).filter(models.Party.id == payload.party_id).first()
    if not party:
        raise HTTPException(404, "Party not found")

    company = _build_company_dict(db)

    try:
        image_bytes = _render_bill(
            company, party, payload.bill_number, payload.bill_date, payload.items,
            payload.cgst_pct, payload.sgst_pct, payload.igst_pct,
            payload.shipped_by, payload.vehicle_number, payload.driver_contact,
        )
    except Exception as e:
        raise HTTPException(500, f"Bill generation failed: {e}")

    try:
        image_url = storage.save_generated_bill(image_bytes)
    except Exception as e:
        raise HTTPException(502, f"Could not save generated bill: {e}")

    total_amount = sum(item.amount for item in payload.items)
    grand_total = total_amount * (1 + (payload.cgst_pct + payload.sgst_pct + payload.igst_pct) / 100)

    invoice_date = datetime.strptime(payload.bill_date, "%Y-%m-%d").date() if payload.bill_date else None
    due_date = datetime.strptime(payload.due_date, "%Y-%m-%d").date() if payload.due_date else None
    if not due_date and invoice_date:
        company_row = db.query(models.CompanySettings).filter(models.CompanySettings.id == "default").first()
        if company_row and company_row.default_credit_days:
            from datetime import timedelta
            due_date = invoice_date + timedelta(days=int(company_row.default_credit_days))

    invoice = models.Invoice(
        party_id=party.id,
        invoice_number=payload.bill_number,
        invoice_date=invoice_date,
        due_date=due_date,
        amount=grand_total,
        gst_amount=grand_total - total_amount if (payload.cgst_pct or payload.sgst_pct or payload.igst_pct) else None,
        raw_image_url=image_url,
        shipped_by=payload.shipped_by,
        vehicle_number=payload.vehicle_number,
        driver_contact=payload.driver_contact,
        is_generated=True,
        items_json=json.dumps([item.model_dump() for item in payload.items]),
        cgst_pct=payload.cgst_pct,
        sgst_pct=payload.sgst_pct,
        igst_pct=payload.igst_pct,
    )
    invoice.refresh_status()
    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return {
        "invoice_id": invoice.id,
        "image_url": image_url,
        "amount": grand_total,
    }


@router.put("/{invoice_id}/regenerate")
def regenerate_bill(invoice_id: str, payload: RegenerateBillRequest, db: Session = Depends(get_db)):
    """Re-renders an existing generated bill's image with edited items/details,
    and updates the same invoice record (rather than creating a new one)."""
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    if not invoice.is_generated:
        raise HTTPException(400, "This invoice wasn't created by the bill generator, so it can't be regenerated")

    party = db.query(models.Party).filter(models.Party.id == invoice.party_id).first()
    if not party:
        raise HTTPException(404, "Party not found")

    company = _build_company_dict(db)

    try:
        image_bytes = _render_bill(
            company, party, payload.bill_number, payload.bill_date, payload.items,
            payload.cgst_pct, payload.sgst_pct, payload.igst_pct,
            payload.shipped_by, payload.vehicle_number, payload.driver_contact,
        )
    except Exception as e:
        raise HTTPException(500, f"Bill regeneration failed: {e}")

    try:
        image_url = storage.save_generated_bill(image_bytes)
    except Exception as e:
        raise HTTPException(502, f"Could not save regenerated bill: {e}")

    total_amount = sum(item.amount for item in payload.items)
    grand_total = total_amount * (1 + (payload.cgst_pct + payload.sgst_pct + payload.igst_pct) / 100)

    invoice.invoice_number = payload.bill_number
    invoice.invoice_date = datetime.strptime(payload.bill_date, "%Y-%m-%d").date() if payload.bill_date else None
    invoice.due_date = datetime.strptime(payload.due_date, "%Y-%m-%d").date() if payload.due_date else None
    invoice.amount = grand_total
    invoice.gst_amount = grand_total - total_amount if (payload.cgst_pct or payload.sgst_pct or payload.igst_pct) else None
    invoice.raw_image_url = image_url
    invoice.shipped_by = payload.shipped_by
    invoice.vehicle_number = payload.vehicle_number
    invoice.driver_contact = payload.driver_contact
    invoice.items_json = json.dumps([item.model_dump() for item in payload.items])
    invoice.cgst_pct = payload.cgst_pct
    invoice.sgst_pct = payload.sgst_pct
    invoice.igst_pct = payload.igst_pct
    invoice.refresh_status()

    db.commit()
    db.refresh(invoice)

    return {
        "invoice_id": invoice.id,
        "image_url": image_url,
        "amount": grand_total,
    }
