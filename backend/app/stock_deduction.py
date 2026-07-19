"""
Auto-deducts stock when a sale happens - shared by every place an invoice
gets created (Generate Bill, manual entry, OCR review), so the exact same
rules apply everywhere rather than three separate implementations quietly
drifting apart.

Deliberately only applies from a fixed date forward (confirmed directly:
based on the invoice's own date, not when it happens to be entered into the
app) - retroactively deducting stock for invoices from before this existed
would be working from numbers that were never actually being tracked,
producing results that look precise but aren't real.

Deliberately does NOT block a sale if there isn't "enough" stock recorded -
the sale already happened in real life; the bill still needs to go out.
Letting the count go negative is a useful, visible signal that the
recorded stock needs a real recount, not something to prevent after the
fact.
"""
from datetime import date

from . import models

AUTO_DEDUCT_START_DATE = date(2026, 8, 1)


def should_auto_deduct(invoice_date) -> bool:
    if not invoice_date:
        return False
    return invoice_date >= AUTO_DEDUCT_START_DATE


def apply_stock_deduction(db, invoice, stock_items, company_id):
    """
    stock_items: list of SoldStockLine (item_id, location_id, quantity).
    Silently does nothing if the invoice's date is before the cutoff, or if
    no stock_items were given at all - callers don't need to check
    should_auto_deduct themselves first.
    """
    if not stock_items or not should_auto_deduct(invoice.invoice_date):
        return

    for line in stock_items:
        item = db.query(models.Item).filter(
            models.Item.id == line.item_id, models.Item.company_id == company_id
        ).first()
        location = db.query(models.StockLocation).filter(
            models.StockLocation.id == line.location_id, models.StockLocation.company_id == company_id
        ).first()
        if not item or not location:
            continue  # a stale/mismatched reference shouldn't block the actual sale from saving

        entry = db.query(models.ItemStock).filter(
            models.ItemStock.item_id == line.item_id, models.ItemStock.location_id == line.location_id
        ).first()
        if not entry:
            entry = models.ItemStock(item_id=line.item_id, location_id=line.location_id, quantity=0)
            db.add(entry)
        entry.quantity -= line.quantity

        db.add(models.InvoiceStockLink(
            invoice_id=invoice.id, item_id=line.item_id, location_id=line.location_id, quantity=line.quantity
        ))


def reverse_stock_deduction(db, invoice):
    """Called before deleting an invoice - gives back whatever it had
    deducted, so deleting a sale doesn't leave stock permanently short."""
    links = db.query(models.InvoiceStockLink).filter(models.InvoiceStockLink.invoice_id == invoice.id).all()
    for link in links:
        entry = db.query(models.ItemStock).filter(
            models.ItemStock.item_id == link.item_id, models.ItemStock.location_id == link.location_id
        ).first()
        if entry:
            entry.quantity += link.quantity
