from datetime import datetime
import calendar
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional

from .. import models, storage
from ..database import get_db
from .. import export as export_lib

router = APIRouter(prefix="/api/export", tags=["export"])


def _month_bounds(month: str):
    """month: 'YYYY-MM' -> (first_day, last_day) as date objects."""
    year, mon = (int(x) for x in month.split("-"))
    last_day = calendar.monthrange(year, mon)[1]
    return datetime(year, mon, 1).date(), datetime(year, mon, last_day).date()


def _month_label(month: str) -> str:
    year, mon = (int(x) for x in month.split("-"))
    return datetime(year, mon, 1).strftime("%B %Y")


def _get_month_invoices(db: Session, month: str, party_id: Optional[str] = None):
    """Returns list of (party, invoices) tuples for the given month, optionally
    scoped to a single party. Invoices without a set invoice_date are excluded
    since they can't be placed in a specific month."""
    start, end = _month_bounds(month)

    party_query = db.query(models.Party)
    if party_id:
        party_query = party_query.filter(models.Party.id == party_id)
    parties = party_query.order_by(models.Party.name).all()

    result = []
    for party in parties:
        invoices = (
            db.query(models.Invoice)
            .filter(
                models.Invoice.party_id == party.id,
                models.Invoice.invoice_date >= start,
                models.Invoice.invoice_date <= end,
            )
            .order_by(models.Invoice.invoice_date)
            .all()
        )
        result.append((party, invoices))
    return result


@router.get("/monthly/summary-pdf")
def export_monthly_summary(
    month: str = Query(..., description="YYYY-MM"),
    party_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    party_invoice_pairs = _get_month_invoices(db, month, party_id)

    company_settings = db.query(models.CompanySettings).filter(models.CompanySettings.id == "default").first()
    logo_bytes = None
    if company_settings and company_settings.logo_url:
        logo_bytes = storage.get_cached_logo_bytes(company_settings.logo_url)

    pdf_bytes = export_lib.generate_monthly_summary_pdf(
        _month_label(month), party_invoice_pairs, company_settings, logo_bytes
    )
    filename = f"sales_summary_{month}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/monthly/detailed-excel")
def export_monthly_detailed_excel(
    month: str = Query(..., description="YYYY-MM"),
    party_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    party_invoice_pairs = _get_month_invoices(db, month, party_id)
    xlsx_bytes = export_lib.generate_excel_export(party_invoice_pairs)
    filename = f"sales_detail_{month}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/monthly/bills-pdf")
def export_monthly_bills_pdf(
    month: str = Query(..., description="YYYY-MM"),
    party_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    party_invoice_pairs = _get_month_invoices(db, month, party_id)

    # Flatten to a single chronological list across all included parties,
    # since bills from different parties on the same day should still
    # interleave by date, not be grouped by party.
    all_invoices = []
    for party, invoices in party_invoice_pairs:
        for inv in invoices:
            all_invoices.append((inv, party.name))
    all_invoices.sort(key=lambda x: x[0].invoice_date or datetime.min.date())

    invoices_with_images = []
    for inv, party_name in all_invoices:
        image_bytes = storage.read_image_bytes(inv.raw_image_url) if inv.raw_image_url else None
        invoices_with_images.append((inv, party_name, image_bytes))

    pdf_bytes = export_lib.generate_combined_bills_pdf(invoices_with_images)
    filename = f"bills_{month}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


# ---------------------------------------------------------------------------
# Purchase ledger (payables) monthly reports - mirror the sales-side ones above
# ---------------------------------------------------------------------------
def _get_month_purchases(db: Session, month: str, supplier_id: Optional[str] = None):
    start, end = _month_bounds(month)

    supplier_query = db.query(models.Supplier)
    if supplier_id:
        supplier_query = supplier_query.filter(models.Supplier.id == supplier_id)
    suppliers = supplier_query.order_by(models.Supplier.name).all()

    result = []
    for supplier in suppliers:
        purchases = (
            db.query(models.Purchase)
            .filter(
                models.Purchase.supplier_id == supplier.id,
                models.Purchase.purchase_date >= start,
                models.Purchase.purchase_date <= end,
            )
            .order_by(models.Purchase.purchase_date)
            .all()
        )
        result.append((supplier, purchases))
    return result


class _InvoiceLike:
    """Adapter so the existing generate_combined_bills_pdf (written for
    Invoice objects) can be reused as-is for Purchase objects, which have
    the same shape but different attribute names (purchase_date vs
    invoice_date, etc). Avoids touching or duplicating that function."""
    def __init__(self, date, number, amount):
        self.invoice_date = date
        self.invoice_number = number
        self.amount = amount


@router.get("/monthly/purchase-summary-pdf")
def export_monthly_purchase_summary(
    month: str = Query(..., description="YYYY-MM"),
    supplier_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    supplier_purchase_pairs = _get_month_purchases(db, month, supplier_id)

    company_settings = db.query(models.CompanySettings).filter(models.CompanySettings.id == "default").first()
    logo_bytes = None
    if company_settings and company_settings.logo_url:
        logo_bytes = storage.get_cached_logo_bytes(company_settings.logo_url)

    pdf_bytes = export_lib.generate_monthly_purchase_summary_pdf(
        _month_label(month), supplier_purchase_pairs, company_settings, logo_bytes
    )
    filename = f"purchase_summary_{month}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/monthly/purchase-detailed-excel")
def export_monthly_purchase_detailed_excel(
    month: str = Query(..., description="YYYY-MM"),
    supplier_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    supplier_purchase_pairs = _get_month_purchases(db, month, supplier_id)
    xlsx_bytes = export_lib.generate_purchase_excel_export(supplier_purchase_pairs)
    filename = f"purchase_detail_{month}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/monthly/purchase-bills-pdf")
def export_monthly_purchase_bills_pdf(
    month: str = Query(..., description="YYYY-MM"),
    supplier_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    supplier_purchase_pairs = _get_month_purchases(db, month, supplier_id)

    all_purchases = []
    for supplier, purchases in supplier_purchase_pairs:
        for pu in purchases:
            all_purchases.append((pu, supplier.name))
    all_purchases.sort(key=lambda x: x[0].purchase_date or datetime.min.date())

    purchases_with_images = []
    for pu, supplier_name in all_purchases:
        image_bytes = storage.read_image_bytes(pu.raw_image_url) if pu.raw_image_url else None
        adapted = _InvoiceLike(pu.purchase_date, pu.purchase_number, pu.amount)
        purchases_with_images.append((adapted, supplier_name, image_bytes))

    pdf_bytes = export_lib.generate_combined_bills_pdf(purchases_with_images)
    filename = f"purchase_bills_{month}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
