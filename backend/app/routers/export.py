from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, storage
from ..database import get_db
from .. import export as export_lib

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/party/{party_id}/pdf")
def export_party_pdf(party_id: str, db: Session = Depends(get_db)):
    party = db.query(models.Party).filter(models.Party.id == party_id).first()
    if not party:
        raise HTTPException(404, "Party not found")

    invoices = (
        db.query(models.Invoice)
        .filter(models.Invoice.party_id == party_id)
        .order_by(models.Invoice.invoice_date)
        .all()
    )

    company_settings = db.query(models.CompanySettings).filter(models.CompanySettings.id == "default").first()
    logo_bytes = None
    if company_settings and company_settings.logo_url:
        logo_bytes = storage.get_cached_logo_bytes(company_settings.logo_url)

    pdf_bytes = export_lib.generate_party_statement_pdf(party, invoices, company_settings, logo_bytes)
    filename = f"{party.name.replace(' ', '_')}_statement_{datetime.now().strftime('%Y%m%d')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/party/{party_id}/excel")
def export_party_excel(party_id: str, db: Session = Depends(get_db)):
    party = db.query(models.Party).filter(models.Party.id == party_id).first()
    if not party:
        raise HTTPException(404, "Party not found")

    invoices = (
        db.query(models.Invoice)
        .filter(models.Invoice.party_id == party_id)
        .order_by(models.Invoice.invoice_date)
        .all()
    )

    xlsx_bytes = export_lib.generate_excel_export([(party, invoices)])
    filename = f"{party.name.replace(' ', '_')}_data_{datetime.now().strftime('%Y%m%d')}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/all/excel")
def export_all_excel(db: Session = Depends(get_db)):
    parties = db.query(models.Party).order_by(models.Party.name).all()

    parties_with_invoices = [
        (
            party,
            db.query(models.Invoice)
            .filter(models.Invoice.party_id == party.id)
            .order_by(models.Invoice.invoice_date)
            .all(),
        )
        for party in parties
    ]

    xlsx_bytes = export_lib.generate_excel_export(parties_with_invoices)
    filename = f"all_parties_data_{datetime.now().strftime('%Y%m%d')}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
