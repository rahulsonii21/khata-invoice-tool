"""
Portable, ORM-based export/import of every row in every table, as JSON.

Why this exists: the app's backup previously only included a database dump
when running on SQLite (local dev), with a comment claiming Supabase's
Postgres handles its own backups in production. That claim was wrong -
Supabase's FREE TIER (which this app runs on) provides zero automatic
backups. Daily backups and point-in-time recovery are Pro-plan-only
features. This means production had no real database backup at all until
this file existed.

This uses SQLAlchemy directly rather than pg_dump/psql, so it works
identically regardless of whether the database is SQLite or Postgres, with
no external binary dependency to install or version-match.
"""
from datetime import datetime, date
from sqlalchemy.orm import Session

from . import models

# Tables in dependency order (children before parents doesn't matter for
# export, but restore needs parents first so foreign keys resolve).
_EXPORT_ORDER = [
    "company_settings", "parties", "invoices", "payments",
    "suppliers", "purchases", "purchase_payments",
]

_MODEL_BY_TABLE = {
    "company_settings": models.CompanySettings,
    "parties": models.Party,
    "invoices": models.Invoice,
    "payments": models.Payment,
    "suppliers": models.Supplier,
    "purchases": models.Purchase,
    "purchase_payments": models.PurchasePayment,
}


def _serialize_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "value"):  # Enum members (InvoiceStatus, PaymentMode)
        return value.value
    return value


def _row_to_dict(row) -> dict:
    columns = row.__table__.columns.keys()
    return {col: _serialize_value(getattr(row, col)) for col in columns}


def export_all_data(db: Session) -> dict:
    """Returns a JSON-serializable dict: {table_name: [row_dict, ...]}."""
    data = {}
    for table_name in _EXPORT_ORDER:
        model = _MODEL_BY_TABLE[table_name]
        rows = db.query(model).all()
        data[table_name] = [_row_to_dict(r) for r in rows]
    return data


def _deserialize_row(table_name: str, row_dict: dict) -> dict:
    """Converts ISO date/datetime strings back to date/datetime objects for
    the columns that need it, based on the model's actual column types."""
    model = _MODEL_BY_TABLE[table_name]
    result = dict(row_dict)
    for col in model.__table__.columns:
        value = result.get(col.name)
        if value is None:
            continue
        type_name = type(col.type).__name__
        if type_name == "Date" and isinstance(value, str):
            result[col.name] = date.fromisoformat(value)
        elif type_name == "DateTime" and isinstance(value, str):
            result[col.name] = datetime.fromisoformat(value)
    return result


def restore_all_data(db: Session, data: dict) -> dict:
    """
    Replaces all current data with the backup's data. This is destructive by
    design - restoring a backup means going back to that point in time, not
    merging it with whatever exists now. The caller (API endpoint) is
    responsible for requiring explicit confirmation before calling this.

    Returns a summary dict of how many rows were restored per table.
    """
    summary = {}

    # Delete in reverse order (children before parents) to respect FK constraints
    for table_name in reversed(_EXPORT_ORDER):
        model = _MODEL_BY_TABLE[table_name]
        db.query(model).delete()
    db.flush()

    # Insert in forward order (parents before children)
    for table_name in _EXPORT_ORDER:
        model = _MODEL_BY_TABLE[table_name]
        rows = data.get(table_name, [])
        for row_dict in rows:
            clean = _deserialize_row(table_name, row_dict)
            db.add(model(**clean))
        summary[table_name] = len(rows)
        db.flush()

    db.commit()
    return summary
