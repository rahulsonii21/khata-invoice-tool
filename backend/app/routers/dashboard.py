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
        "party_count": len(parties),
        "top_outstanding_parties": top_outstanding,
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
            }
            for inv in recent_invoices
        ],
    }
