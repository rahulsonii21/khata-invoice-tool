from sqlalchemy.orm import Session
from . import models


def log_change(db: Session, record_type: str, record_id: str, field: str,
                old_value, new_value, changed_by: str = None):
    entry = models.AuditLog(
        record_type=record_type,
        record_id=str(record_id),
        field_changed=field,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        changed_by=changed_by,
    )
    db.add(entry)
