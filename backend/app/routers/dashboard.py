from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    parties = db.query(models.Party).all()

    total_invoiced = sum(p.total_invoiced for p in parties)
    total_received = sum(p.total_received for p in parties)
    total_outstanding = total_invoiced - total_received

    top_outstanding = sorted(
        [{"party_id": p.id, "name": p.name, "outstanding": p.outstanding} for p in parties],
        key=lambda x: x["outstanding"],
        reverse=True,
    )[:5]

    all_invoices = db.query(models.Invoice).all()
    overdue_invoices = [inv for inv in all_invoices if inv.is_overdue]
    total_overdue = sum(inv.outstanding for inv in overdue_invoices)

    overdue_by_party = {}
    for inv in overdue_invoices:
        overdue_by_party.setdefault(inv.party_id, {"party_id": inv.party_id, "name": inv.party.name, "amount": 0, "count": 0})
        overdue_by_party[inv.party_id]["amount"] += inv.outstanding
        overdue_by_party[inv.party_id]["count"] += 1
    top_overdue = sorted(overdue_by_party.values(), key=lambda x: x["amount"], reverse=True)[:5]

    recent_payments = (
        db.query(models.Payment)
        .order_by(models.Payment.created_at.desc())
        .limit(10)
        .all()
    )
    recent_invoices = (
        db.query(models.Invoice)
        .order_by(models.Invoice.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "total_invoiced": total_invoiced,
        "total_received": total_received,
        "total_outstanding": total_outstanding,
        "total_overdue": total_overdue,
        "overdue_count": len(overdue_invoices),
        "party_count": len(parties),
        "top_outstanding_parties": top_outstanding,
        "top_overdue_parties": top_overdue,
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
