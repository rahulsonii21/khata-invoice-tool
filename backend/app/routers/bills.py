from datetime import datetime, date as date_type
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, schemas, storage, bill_generator
from ..database import get_db

router = APIRouter(prefix="/api/bills", tags=["bills"])


class BillItem(BaseModel):
    description: str
    qty_label: str = ""
    rate: Optional[float] = None
    amount: float


class GenerateBillRequest(BaseModel):
    party_id: str
    bill_number: Optional[str] = None
    bill_date: Optional[str] = None  # YYYY-MM-DD
    items: List[BillItem]
    cgst_pct: float = 0
    sgst_pct: float = 0
    igst_pct: float = 0
    shipped_by: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_contact: Optional[str] = None


@router.post("/generate")
def generate_bill(payload: GenerateBillRequest, db: Session = Depends(get_db)):
    party = db.query(models.Party).filter(models.Party.id == payload.party_id).first()
    if not party:
        raise HTTPException(404, "Party not found")

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
            company["logo_bytes"] = storage.read_image_bytes(company_row.logo_url)

    bill_date_display = payload.bill_date
    if payload.bill_date:
        try:
            d = datetime.strptime(payload.bill_date, "%Y-%m-%d").date()
            bill_date_display = d.strftime("%d-%m-%Y")
        except ValueError:
            pass

    try:
        image_bytes = bill_generator.generate_bill_image(
            company=company,
            party_name=party.name,
            bill_number=payload.bill_number,
            bill_date=bill_date_display,
            items=[item.model_dump() for item in payload.items],
            cgst_pct=payload.cgst_pct,
            sgst_pct=payload.sgst_pct,
            igst_pct=payload.igst_pct,
            party_gstin=party.gstin,
            party_address=party.address,
            party_city=party.city,
            party_pincode=party.pincode,
            party_phone=party.phone,
            shipped_by=payload.shipped_by,
            vehicle_number=payload.vehicle_number,
            driver_contact=payload.driver_contact,
        )
    except Exception as e:
        raise HTTPException(500, f"Bill generation failed: {e}")

    try:
        image_url = storage.save_generated_bill(image_bytes)
    except Exception as e:
        raise HTTPException(502, f"Could not save generated bill: {e}")

    total_amount = sum(item.amount for item in payload.items)
    grand_total = total_amount * (1 + (payload.cgst_pct + payload.sgst_pct + payload.igst_pct) / 100)

    invoice = models.Invoice(
        party_id=party.id,
        invoice_number=payload.bill_number,
        invoice_date=datetime.strptime(payload.bill_date, "%Y-%m-%d").date() if payload.bill_date else None,
        amount=grand_total,
        gst_amount=grand_total - total_amount if (payload.cgst_pct or payload.sgst_pct or payload.igst_pct) else None,
        raw_image_url=image_url,
        shipped_by=payload.shipped_by,
        vehicle_number=payload.vehicle_number,
        driver_contact=payload.driver_contact,
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
