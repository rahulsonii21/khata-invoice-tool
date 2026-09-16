"""
Phase 1 Lekha AI tools - read-only only. Every one of these calls into
existing business logic (the same queries the Dashboard, Stock screen,
etc. already use) rather than reimplementing anything. No tool here
writes to the database - that's deliberately a later phase, once the
read path is proven out.

Every function takes (db, company_id) plus its own arguments, and
company_id is ALWAYS supplied by the caller (the chat endpoint, which
derives it from the authenticated session) - never accepted as a
parameter from Gemini's function-call arguments. This is the same
tenant-isolation rule the rest of the app follows.
"""
from sqlalchemy.orm import selectinload

from .. import models
from ..routers.dashboard import compute_summary
from ..routers.stock import compute_low_stock_items, _to_out as stock_item_to_out


def search_party(db, company_id, query: str) -> dict:
    """Finds parties (customers) by name or phone, fuzzy on name."""
    q = f"%{query.strip()}%"
    matches = (
        db.query(models.Party)
        .filter(models.Party.company_id == company_id)
        .filter((models.Party.name.ilike(q)) | (models.Party.phone.ilike(q)))
        .limit(10)
        .all()
    )
    return {
        "count": len(matches),
        "parties": [
            {
                "id": p.id,
                "name": p.name,
                "phone": p.phone,
                "outstanding": p.outstanding,
            }
            for p in matches
        ],
    }


def get_party_balance(db, company_id, party_name: str) -> dict:
    """Outstanding balance for a specific party, matched by name. If more
    than one party matches, returns all of them so the agent can ask
    which one rather than guessing."""
    matches = (
        db.query(models.Party)
        .filter(models.Party.company_id == company_id)
        .filter(models.Party.name.ilike(f"%{party_name.strip()}%"))
        .all()
    )
    if not matches:
        return {"found": False, "message": f"No party found matching '{party_name}'"}
    if len(matches) > 1:
        return {
            "found": False,
            "ambiguous": True,
            "matches": [{"id": p.id, "name": p.name} for p in matches],
            "message": "More than one party matches - ask the user which one they mean.",
        }
    p = matches[0]
    overdue_invoices = [inv for inv in p.invoices if inv.is_overdue]
    return {
        "found": True,
        "party_name": p.name,
        "outstanding": p.outstanding,
        "overdue_amount": sum(inv.outstanding for inv in overdue_invoices),
        "overdue_invoice_count": len(overdue_invoices),
    }


def get_business_summary(db, company_id) -> dict:
    """Overall totals - receivables, payables, overdue - the same numbers
    shown on the Dashboard."""
    s = compute_summary(db, company_id)
    return {
        "total_outstanding_receivable": s["total_outstanding"],
        "total_overdue_receivable": s["total_overdue"],
        "overdue_invoice_count": s["overdue_count"],
        "top_overdue_parties": s["top_overdue_parties"],
        "total_payable_to_suppliers": s["total_payable"],
        "total_payable_overdue": s["total_payable_overdue"],
    }


def get_stock(db, company_id, item_name: str) -> dict:
    """Current stock for an item, broken down by location, matched by
    name. Same ambiguity handling as get_party_balance."""
    matches = (
        db.query(models.Item)
        .options(selectinload(models.Item.stock_entries).selectinload(models.ItemStock.location))
        .filter(models.Item.company_id == company_id)
        .filter(models.Item.name.ilike(f"%{item_name.strip()}%"))
        .all()
    )
    if not matches:
        return {"found": False, "message": f"No item found matching '{item_name}'"}
    if len(matches) > 1:
        return {
            "found": False,
            "ambiguous": True,
            "matches": [{"id": i.id, "name": i.name} for i in matches],
            "message": "More than one item matches - ask the user which one they mean.",
        }
    out = stock_item_to_out(matches[0])
    return {
        "found": True,
        "item_name": out.name,
        "unit": out.unit,
        "total_quantity": out.total_quantity,
        "by_location": [{"location": s.location_name, "quantity": s.quantity} for s in out.stock_by_location],
        "is_low_stock": out.is_low_stock,
    }


def get_low_stock_items(db, company_id) -> dict:
    """Every item currently below its reorder threshold."""
    items = compute_low_stock_items(db, company_id)
    return {
        "count": len(items),
        "items": [{"name": i.name, "unit": i.unit, "total_quantity": i.total_quantity} for i in items],
    }


def calculate(db, company_id, expression: str) -> dict:
    """
    A safe, deterministic calculator - Gemini describes what to compute in
    plain arithmetic (numbers, + - * / % parentheses only), this evaluates
    it exactly rather than trusting the model's own arithmetic. This is
    NOT a general invoice/GST calculator yet (that needs the same rate
    structure Generate Bill uses, which is a later phase) - it's a
    general-purpose safety net for "what's 5% of 2 lakh" type questions.
    """
    import re
    allowed = re.fullmatch(r"[0-9+\-*/%.() \t]+", expression)
    if not allowed:
        return {"error": "Only plain arithmetic (numbers and + - * / % ( )) is supported."}
    try:
        # eval is safe here ONLY because the regex above has already
        # rejected anything that isn't digits/operators/parens/whitespace -
        # no names, no attribute access, no calls are possible.
        result = eval(expression, {"__builtins__": {}}, {})
    except Exception as e:
        return {"error": f"Could not evaluate that: {e}"}
    return {"expression": expression, "result": result}
