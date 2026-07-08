import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Float, Date, DateTime, ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base
import enum


def gen_uuid():
    return str(uuid.uuid4())


class InvoiceStatus(str, enum.Enum):
    unpaid = "unpaid"
    partially_paid = "partially_paid"
    paid = "paid"


class PaymentMode(str, enum.Enum):
    cash = "cash"
    upi = "upi"
    bank = "bank"
    cheque = "cheque"
    other = "other"


class Party(Base):
    __tablename__ = "parties"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=True)
    gstin = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoices = relationship("Invoice", back_populates="party", cascade="all, delete-orphan")

    @property
    def total_invoiced(self):
        return sum(inv.amount for inv in self.invoices)

    @property
    def total_received(self):
        return sum(p.amount for inv in self.invoices for p in inv.payments)

    @property
    def outstanding(self):
        return self.total_invoiced - self.total_received


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    party_id = Column(UUID(as_uuid=False), ForeignKey("parties.id"), nullable=False)
    invoice_number = Column(String, nullable=True)
    invoice_date = Column(Date, nullable=True)
    amount = Column(Float, nullable=False, default=0.0)
    gst_amount = Column(Float, nullable=True)
    raw_image_url = Column(String, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    remarks = Column(Text, nullable=True)
    status = Column(SAEnum(InvoiceStatus), default=InvoiceStatus.unpaid)
    created_at = Column(DateTime, default=datetime.utcnow)

    party = relationship("Party", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments)

    @property
    def outstanding(self):
        return self.amount - self.total_paid

    def refresh_status(self):
        paid = self.total_paid
        if paid <= 0:
            self.status = InvoiceStatus.unpaid
        elif paid < self.amount:
            self.status = InvoiceStatus.partially_paid
        else:
            self.status = InvoiceStatus.paid


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    invoice_id = Column(UUID(as_uuid=False), ForeignKey("invoices.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=False, default=date.today)
    mode = Column(SAEnum(PaymentMode), default=PaymentMode.other)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)

    invoice = relationship("Invoice", back_populates="payments")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    record_type = Column(String, nullable=False)  # "invoice" | "payment" | "party"
    record_id = Column(String, nullable=False)
    field_changed = Column(String, nullable=False)
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    changed_by = Column(String, nullable=True)  # "user" or "father" - simple text tag
    changed_at = Column(DateTime, default=datetime.utcnow)


class CompanySettings(Base):
    """Singleton table (always id='default') holding the user's own business
    details, used as the letterhead on PDF statements."""
    __tablename__ = "company_settings"

    id = Column(String, primary_key=True, default="default")
    company_name = Column(String, nullable=True)
    gstin = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
