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


def list_sales_invoices(db, company_id, party_name: str = None, month: str = None) -> dict:
    """
    Lists sales invoices, optionally filtered by party name and/or month
    (YYYY-MM) - reuses the exact same filtering the real Invoices list
    screen uses. Capped at 50 results (most recent first) so a broad
    query doesn't dump the entire ledger into the conversation.
    """
    import calendar
    from datetime import date as date_cls
    from sqlalchemy.orm import selectinload

    query = db.query(models.Invoice).options(selectinload(models.Invoice.payments)).filter(
        models.Invoice.company_id == company_id
    )

    if party_name:
        matches = (
            db.query(models.Party)
            .filter(models.Party.company_id == company_id)
            .filter(models.Party.name.ilike(f"%{party_name.strip()}%"))
            .all()
        )
        if not matches:
            return {"error": f"No party found matching '{party_name}'"}
        if len(matches) > 1:
            return {
                "ambiguous": True,
                "matches": [{"id": p.id, "name": p.name} for p in matches],
                "message": "More than one party matches - ask the user which one they mean.",
            }
        query = query.filter(models.Invoice.party_id == matches[0].id)

    if month:
        try:
            year, mon = (int(x) for x in month.split("-"))
            last_day = calendar.monthrange(year, mon)[1]
            query = query.filter(
                models.Invoice.invoice_date >= date_cls(year, mon, 1),
                models.Invoice.invoice_date <= date_cls(year, mon, last_day),
            )
        except (ValueError, AttributeError):
            return {"error": "month must be in YYYY-MM format, e.g. 2026-05"}

    invoices = query.order_by(models.Invoice.invoice_date.desc().nullslast()).limit(50).all()
    return {
        "count": len(invoices),
        "total_amount": sum(inv.amount for inv in invoices),
        "invoices": [
            {
                "party_name": inv.party.name if inv.party else None,
                "date": str(inv.invoice_date) if inv.invoice_date else None,
                "amount": inv.amount,
                "outstanding": inv.outstanding,
                "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
            }
            for inv in invoices
        ],
    }


def list_purchase_invoices(db, company_id, supplier_name: str = None, month: str = None) -> dict:
    """
    Lists purchase invoices (what's owed to suppliers), optionally
    filtered by supplier name and/or month (YYYY-MM) - the payable-side
    mirror of list_sales_invoices, reusing the same filtering the real
    Purchases list screen uses.
    """
    import calendar
    from datetime import date as date_cls
    from sqlalchemy.orm import selectinload

    query = db.query(models.Purchase).options(selectinload(models.Purchase.payments)).filter(
        models.Purchase.company_id == company_id
    )

    if supplier_name:
        matches = (
            db.query(models.Supplier)
            .filter(models.Supplier.company_id == company_id)
            .filter(models.Supplier.name.ilike(f"%{supplier_name.strip()}%"))
            .all()
        )
        if not matches:
            return {"error": f"No supplier found matching '{supplier_name}'"}
        if len(matches) > 1:
            return {
                "ambiguous": True,
                "matches": [{"id": s.id, "name": s.name} for s in matches],
                "message": "More than one supplier matches - ask the user which one they mean.",
            }
        query = query.filter(models.Purchase.supplier_id == matches[0].id)

    if month:
        try:
            year, mon = (int(x) for x in month.split("-"))
            last_day = calendar.monthrange(year, mon)[1]
            query = query.filter(
                models.Purchase.purchase_date >= date_cls(year, mon, 1),
                models.Purchase.purchase_date <= date_cls(year, mon, last_day),
            )
        except (ValueError, AttributeError):
            return {"error": "month must be in YYYY-MM format, e.g. 2026-05"}

    purchases = query.order_by(models.Purchase.purchase_date.desc().nullslast()).limit(50).all()
    return {
        "count": len(purchases),
        "total_amount": sum(p.amount for p in purchases),
        "purchases": [
            {
                "supplier_name": p.supplier.name if p.supplier else None,
                "date": str(p.purchase_date) if p.purchase_date else None,
                "amount": p.amount,
                "outstanding": p.outstanding,
                "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            }
            for p in purchases
        ],
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


# ---------- Phase 2: write actions ----------
#
# Every write action is split into a propose_* tool (checks for problems,
# validates, but writes NOTHING) and a confirm_* tool (does the actual
# write) - the system prompt requires the agent to call propose_*, show
# the user exactly what it's about to do, and wait for an explicit yes
# before ever calling confirm_*. confirm_* re-validates its arguments
# through the exact same Pydantic rules the real API endpoints use
# (phone format, name not blank, etc), so even if the model restates the
# details slightly wrong when confirming, invalid data still can't get
# through - it fails validation instead of silently creating something
# wrong.

def propose_create_party(db, company_id, name: str, phone: str = None, gstin: str = None,
                          address: str = None, city: str = None, notes: str = None) -> dict:
    """Checks for a likely-duplicate party BEFORE proposing creation - if
    Vyapar/myBillBook-style close-name matches exist, surfaces them instead
    of silently creating a second party for someone already in the system."""
    from .. import schemas
    from pydantic import ValidationError

    existing = db.query(models.Party).filter(models.Party.company_id == company_id).all()
    close_matches = [p for p in existing if _names_similar(p.name, name)]
    if close_matches:
        return {
            "duplicate_warning": True,
            "requires_confirmation": False,
            "existing_matches": [{"id": p.id, "name": p.name, "phone": p.phone} for p in close_matches],
            "message": "A similarly-named party already exists - ask the user whether they meant this existing one, or genuinely want a new, separate party.",
        }

    try:
        validated = schemas.PartyCreate(name=name, phone=phone, gstin=gstin, address=address, city=city, notes=notes)
    except ValidationError as e:
        return {"error": _first_validation_message(e)}

    return {
        "requires_confirmation": True,
        "action": "create_party",
        "args": validated.model_dump(),
        "summary": f"Create a new party '{validated.name}'" + (f" (phone {validated.phone})" if validated.phone else "") + "?",
    }


def confirm_create_party(db, company_id, name: str, phone: str = None, gstin: str = None,
                          address: str = None, city: str = None, notes: str = None) -> dict:
    """Actually creates the party - only ever called after the user has
    explicitly confirmed a propose_create_party summary."""
    from .. import schemas
    from pydantic import ValidationError

    try:
        validated = schemas.PartyCreate(name=name, phone=phone, gstin=gstin, address=address, city=city, notes=notes)
    except ValidationError as e:
        return {"error": _first_validation_message(e)}

    party = models.Party(**validated.model_dump(), company_id=company_id, created_by="Lekha AI")
    db.add(party)
    db.commit()
    db.refresh(party)
    return {"created": True, "party_id": party.id, "party_name": party.name}


def propose_create_invoice(db, company_id, party_name: str, amount: float,
                            invoice_date: str = None, due_date: str = None) -> dict:
    """Resolves the party by name first (with the same ambiguity handling
    as get_party_balance) and validates the amount, before ever proposing
    the actual write."""
    matches = (
        db.query(models.Party)
        .filter(models.Party.company_id == company_id)
        .filter(models.Party.name.ilike(f"%{party_name.strip()}%"))
        .all()
    )
    if not matches:
        return {"error": f"No party found matching '{party_name}' - create the party first, or check the spelling."}
    if len(matches) > 1:
        return {
            "requires_confirmation": False,
            "ambiguous": True,
            "matches": [{"id": p.id, "name": p.name} for p in matches],
            "message": "More than one party matches - ask the user which one they mean.",
        }
    if amount <= 0:
        return {"error": "Amount must be greater than zero."}

    party = matches[0]
    return {
        "requires_confirmation": True,
        "action": "create_invoice",
        "args": {"party_id": party.id, "amount": amount, "invoice_date": invoice_date, "due_date": due_date},
        "summary": f"Create an invoice of ₹{amount:,.0f} for {party.name}" + (f" dated {invoice_date}" if invoice_date else "") + "?",
    }


def confirm_create_invoice(db, company_id, party_id: str, amount: float,
                            invoice_date: str = None, due_date: str = None) -> dict:
    """Actually creates the invoice - only ever called after explicit
    confirmation, and always with the exact party_id a propose_ step
    already resolved (never re-searching by name here)."""
    from .. import schemas
    from pydantic import ValidationError

    party = db.query(models.Party).filter(models.Party.id == party_id, models.Party.company_id == company_id).first()
    if not party:
        return {"error": "That party no longer matches this company - please search again."}

    try:
        validated = schemas.InvoiceCreate(party_id=party_id, amount=amount, invoice_date=invoice_date, due_date=due_date)
    except ValidationError as e:
        return {"error": _first_validation_message(e)}

    data = validated.model_dump()
    data.pop("stock_items", None)
    invoice = models.Invoice(**data, company_id=company_id, created_by="Lekha AI")
    invoice.refresh_status()
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return {"created": True, "invoice_id": invoice.id, "party_name": party.name, "amount": invoice.amount}


def _names_similar(a: str, b: str) -> bool:
    """Simple, dependency-free closeness check: same after lowering case
    and stripping whitespace, or one is fully contained in the other.
    Good enough to catch 'Ramesh Traders' vs 'ramesh traders ' or
    'Ramesh' vs 'Ramesh Traders' - not a fuzzy-typo matcher, deliberately
    conservative so it doesn't block genuinely different parties."""
    a_norm = " ".join(a.lower().split())
    b_norm = " ".join(b.lower().split())
    return a_norm == b_norm or a_norm in b_norm or b_norm in a_norm


def _first_validation_message(e) -> str:
    errors = e.errors()
    if errors:
        return errors[0].get("msg", str(e))
    return str(e)


def _resolve_item_and_locations(db, company_id, item_name: str, from_location_name: str, to_location_name: str):
    """Shared name-resolution for both propose and confirm stock-transfer
    tools - looks up the item and both locations by name, with the same
    'ambiguous, ask the user' handling as every other tool. Returns
    (item, from_location, to_location, error_dict_or_None)."""
    item_matches = (
        db.query(models.Item)
        .filter(models.Item.company_id == company_id)
        .filter(models.Item.name.ilike(f"%{item_name.strip()}%"))
        .all()
    )
    if not item_matches:
        return None, None, None, {"error": f"No item found matching '{item_name}'"}
    if len(item_matches) > 1:
        return None, None, None, {
            "ambiguous": True,
            "matches": [{"id": i.id, "name": i.name} for i in item_matches],
            "message": "More than one item matches - ask the user which one they mean.",
        }

    def _find_location(name):
        matches = (
            db.query(models.StockLocation)
            .filter(models.StockLocation.company_id == company_id)
            .filter(models.StockLocation.name.ilike(f"%{name.strip()}%"))
            .all()
        )
        return matches

    from_matches = _find_location(from_location_name)
    if not from_matches:
        return None, None, None, {"error": f"No location found matching '{from_location_name}'"}
    if len(from_matches) > 1:
        return None, None, None, {
            "ambiguous": True,
            "matches": [{"id": l.id, "name": l.name} for l in from_matches],
            "message": f"More than one location matches '{from_location_name}' - ask the user which one they mean.",
        }

    to_matches = _find_location(to_location_name)
    if not to_matches:
        return None, None, None, {"error": f"No location found matching '{to_location_name}'"}
    if len(to_matches) > 1:
        return None, None, None, {
            "ambiguous": True,
            "matches": [{"id": l.id, "name": l.name} for l in to_matches],
            "message": f"More than one location matches '{to_location_name}' - ask the user which one they mean.",
        }

    return item_matches[0], from_matches[0], to_matches[0], None


def propose_stock_transfer(db, company_id, item_name: str, from_location_name: str, to_location_name: str, quantity: float) -> dict:
    """Resolves the item and both locations by name, checks enough stock is
    actually available at the source, but transfers NOTHING yet."""
    from ..routers.stock import _to_out

    item, from_loc, to_loc, error = _resolve_item_and_locations(db, company_id, item_name, from_location_name, to_location_name)
    if error:
        return error

    if from_loc.id == to_loc.id:
        return {"error": "Source and destination can't be the same place."}
    if quantity <= 0:
        return {"error": "Quantity must be greater than zero."}

    out = _to_out(item)
    available = next((s.quantity for s in out.stock_by_location if s.location_id == from_loc.id), 0)
    if quantity > available:
        return {"error": f"Only {available} {out.unit or ''} available at {from_loc.name} - can't transfer {quantity}."}

    return {
        "requires_confirmation": True,
        "action": "transfer_stock",
        "args": {"item_id": item.id, "from_location_id": from_loc.id, "to_location_id": to_loc.id, "quantity": quantity},
        "summary": f"Transfer {quantity} {out.unit or ''} of {item.name} from {from_loc.name} to {to_loc.name}?",
    }


def confirm_stock_transfer(db, company_id, item_id: str, from_location_id: str, to_location_id: str, quantity: float) -> dict:
    """Actually performs the transfer - reuses the exact same
    apply_stock_transfer function the real /transfer API endpoint uses,
    so this is never a second implementation of the transfer rules."""
    from ..routers.stock import apply_stock_transfer, StockTransferError, _to_out

    try:
        item = apply_stock_transfer(db, company_id, item_id, from_location_id, to_location_id, quantity)
    except StockTransferError as e:
        return {"error": str(e)}

    out = _to_out(item)
    return {"transferred": True, "item_name": out.name, "quantity": quantity, "new_totals": [
        {"location": s.location_name, "quantity": s.quantity} for s in out.stock_by_location
    ]}


def draft_payment_reminder(db, company_id, party_name: str) -> dict:
    """
    Drafts a payment reminder message for a party - does NOT send anything
    (there's no server-side WhatsApp sending in this app, and there won't
    be without Meta's paid Business API). This just prepares the message
    text; the frontend turns it into a WhatsApp link the user taps to
    actually send, the same way every other WhatsApp feature in the app
    already works.
    """
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

    party = matches[0]
    if party.outstanding <= 0:
        return {"found": True, "has_outstanding": False, "party_name": party.name, "message": f"{party.name} has no outstanding balance - nothing to remind them about."}

    if not party.phone:
        return {
            "found": True,
            "has_outstanding": True,
            "can_send": False,
            "party_name": party.name,
            "outstanding": party.outstanding,
            "message": f"{party.name} owes ₹{party.outstanding:,.0f}, but has no phone number saved, so a WhatsApp reminder can't be prepared - add one to their party details first.",
        }

    draft_text = (
        f"Namaste {party.name} ji, aapke account mein ₹{party.outstanding:,.0f} payment pending hai. "
        f"Kripya convenient time par payment arrange kar dein. Dhanyavaad."
    )
    return {
        "found": True,
        "has_outstanding": True,
        "can_send": True,
        "party_name": party.name,
        "phone": party.phone,
        "outstanding": party.outstanding,
        "draft_message": draft_text,
    }
