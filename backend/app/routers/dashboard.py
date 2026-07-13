from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, selectinload
from typing import List

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_summary(request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)

    # Eager-load invoices + payments once; every computed property below
    # (total_invoiced, outstanding, is_overdue, etc.) then works off data
    # already in memory instead of firing a fresh query per party/invoice.
    parties = (
        db.query(models.Party)
        .options(selectinload(models.Party.invoices).selectinload(models.Invoice.payments))
        .filter(models.Party.company_id == company_id)
        .all()
    )

    total_invoiced = sum(p.total_invoiced for p in parties)
    total_received = sum(p.total_received for p in parties)
    total_outstanding = total_invoiced - total_received

    top_outstanding = sorted(
        [{"party_id": p.id, "name": p.name, "outstanding": p.outstanding} for p in parties],
        key=lambda x: x["outstanding"],
        reverse=True,
    )[:5]

    # Reuse the same already-loaded parties/invoices instead of a second
    # separate query for "all invoices" (which the previous version did).
    overdue_by_party = {}
    total_overdue = 0
    overdue_count = 0
    for party in parties:
        for inv in party.invoices:
            if inv.is_overdue:
                total_overdue += inv.outstanding
                overdue_count += 1
                bucket = overdue_by_party.setdefault(
                    party.id, {"party_id": party.id, "name": party.name, "amount": 0, "count": 0}
                )
                bucket["amount"] += inv.outstanding
                bucket["count"] += 1
    top_overdue = sorted(overdue_by_party.values(), key=lambda x: x["amount"], reverse=True)[:5]

    recent_payments = (
        db.query(models.Payment)
        .options(selectinload(models.Payment.invoice).selectinload(models.Invoice.party))
        .filter(models.Payment.company_id == company_id)
        .order_by(models.Payment.created_at.desc())
        .limit(10)
        .all()
    )
    recent_invoices = (
        db.query(models.Invoice)
        .options(selectinload(models.Invoice.party), selectinload(models.Invoice.payments))
        .filter(models.Invoice.company_id == company_id)
        .order_by(models.Invoice.created_at.desc())
        .limit(10)
        .all()
    )

    # --- Payables (purchase ledger) - mirrors everything above, for what
    # this business owes suppliers rather than what customers owe it. ---
    suppliers = (
        db.query(models.Supplier)
        .options(selectinload(models.Supplier.purchases).selectinload(models.Purchase.payments))
        .filter(models.Supplier.company_id == company_id)
        .all()
    )
    total_purchased = sum(s.total_purchased for s in suppliers)
    total_paid_to_suppliers = sum(s.total_paid for s in suppliers)
    total_payable = total_purchased - total_paid_to_suppliers

    top_payable = sorted(
        [{"supplier_id": s.id, "name": s.name, "outstanding": s.outstanding} for s in suppliers],
        key=lambda x: x["outstanding"],
        reverse=True,
    )[:5]

    payable_overdue_by_supplier = {}
    total_payable_overdue = 0
    payable_overdue_count = 0
    for supplier in suppliers:
        for purchase in supplier.purchases:
            if purchase.is_overdue:
                total_payable_overdue += purchase.outstanding
                payable_overdue_count += 1
                bucket = payable_overdue_by_supplier.setdefault(
                    supplier.id, {"supplier_id": supplier.id, "name": supplier.name, "amount": 0, "count": 0}
                )
                bucket["amount"] += purchase.outstanding
                bucket["count"] += 1
    top_payable_overdue = sorted(payable_overdue_by_supplier.values(), key=lambda x: x["amount"], reverse=True)[:5]

    return {
        "total_invoiced": total_invoiced,
        "total_received": total_received,
        "total_outstanding": total_outstanding,
        "total_overdue": total_overdue,
        "overdue_count": overdue_count,
        "party_count": len(parties),
        "top_outstanding_parties": top_outstanding,
        "top_overdue_parties": top_overdue,
        "total_purchased": total_purchased,
        "total_paid_to_suppliers": total_paid_to_suppliers,
        "total_payable": total_payable,
        "total_payable_overdue": total_payable_overdue,
        "payable_overdue_count": payable_overdue_count,
        "supplier_count": len(suppliers),
        "top_payable_suppliers": top_payable,
        "top_payable_overdue_suppliers": top_payable_overdue,
        "recent_payments": [
            {
                "id": pay.id,
                "invoice_id": pay.invoice_id,
                "amount": pay.amount,
                "payment_date": pay.payment_date,
                "party_name": pay.invoice.party.name,
            }
            for pay in recent_payments
        ],
        "recent_invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": inv.amount,
                "party_name": inv.party.name,
                "status": inv.status,
                "is_overdue": inv.is_overdue,
            }
            for inv in recent_invoices
        ],
    }
