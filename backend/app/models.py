import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Float, Date, DateTime, ForeignKey, Text, Enum as SAEnum, Boolean
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
    address = Column(Text, nullable=True)
    city = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    email = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)  # display name of whoever created it, or None if auth wasn't active

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
    party_id = Column(UUID(as_uuid=False), ForeignKey("parties.id"), nullable=False, index=True)
    invoice_number = Column(String, nullable=True)
    invoice_date = Column(Date, nullable=True, index=True)
    due_date = Column(Date, nullable=True, index=True)
    amount = Column(Float, nullable=False, default=0.0)
    gst_amount = Column(Float, nullable=True)
    raw_image_url = Column(String, nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    remarks = Column(Text, nullable=True)
    shipped_by = Column(String, nullable=True)
    vehicle_number = Column(String, nullable=True)
    driver_contact = Column(String, nullable=True)
    is_generated = Column(Boolean, default=False)  # True if created via the bill generator, not OCR/manual
    items_json = Column(Text, nullable=True)  # stores the item breakdown for generated bills, so they're re-editable
    cgst_pct = Column(Float, nullable=True)
    sgst_pct = Column(Float, nullable=True)
    igst_pct = Column(Float, nullable=True)
    status = Column(SAEnum(InvoiceStatus), default=InvoiceStatus.unpaid)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)  # display name of whoever created it, or None if auth wasn't active

    party = relationship("Party", back_populates="invoices")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments)

    @property
    def outstanding(self):
        return self.amount - self.total_paid

    @property
    def is_overdue(self):
        if self.outstanding <= 0 or not self.due_date:
            return False
        return self.due_date < date.today()

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
    invoice_id = Column(UUID(as_uuid=False), ForeignKey("invoices.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=False, default=date.today)
    mode = Column(SAEnum(PaymentMode), default=PaymentMode.other)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)  # display name of whoever created it, or None if auth wasn't active
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
    details, used as the letterhead on PDF statements and generated bills."""
    __tablename__ = "company_settings"

    id = Column(String, primary_key=True, default="default")
    company_name = Column(String, nullable=True)
    gstin = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    phone = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    bank_ifsc = Column(String, nullable=True)
    bank_account_number = Column(String, nullable=True)
    default_credit_days = Column(Float, nullable=True)  # auto-fills due_date on new invoices when set
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Purchase ledger (payables) - the mirror image of Party/Invoice/Payment
# above, but for what THIS business owes its suppliers, rather than what
# customers owe this business. Kept as separate tables rather than adding a
# "direction" flag to Party/Invoice - safer (zero risk of touching the
# existing, working customer-side code) at the cost of some duplication.
# ---------------------------------------------------------------------------
class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=True)
    gstin = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    email = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)  # display name of whoever created it, or None if auth wasn't active

    purchases = relationship("Purchase", back_populates="supplier", cascade="all, delete-orphan")

    @property
    def total_purchased(self):
        return sum(p.amount for p in self.purchases)

    @property
    def total_paid(self):
        return sum(pay.amount for p in self.purchases for pay in p.payments)

    @property
    def outstanding(self):
        return self.total_purchased - self.total_paid


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    supplier_id = Column(UUID(as_uuid=False), ForeignKey("suppliers.id"), nullable=False, index=True)
    purchase_number = Column(String, nullable=True)  # the supplier's own bill/invoice number
    purchase_date = Column(Date, nullable=True, index=True)
    due_date = Column(Date, nullable=True, index=True)
    amount = Column(Float, nullable=False, default=0.0)
    gst_amount = Column(Float, nullable=True)
    raw_image_url = Column(String, nullable=True)  # photo of the supplier's bill
    ocr_confidence = Column(Float, nullable=True)
    remarks = Column(Text, nullable=True)
    status = Column(SAEnum(InvoiceStatus), default=InvoiceStatus.unpaid)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)  # display name of whoever created it, or None if auth wasn't active

    supplier = relationship("Supplier", back_populates="purchases")
    payments = relationship("PurchasePayment", back_populates="purchase", cascade="all, delete-orphan")

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments)

    @property
    def outstanding(self):
        return self.amount - self.total_paid

    @property
    def is_overdue(self):
        if self.outstanding <= 0 or not self.due_date:
            return False
        return self.due_date < date.today()

    def refresh_status(self):
        paid = self.total_paid
        if paid <= 0:
            self.status = InvoiceStatus.unpaid
        elif paid < self.amount:
            self.status = InvoiceStatus.partially_paid
        else:
            self.status = InvoiceStatus.paid


class PurchasePayment(Base):
    __tablename__ = "purchase_payments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    purchase_id = Column(UUID(as_uuid=False), ForeignKey("purchases.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=False, default=date.today)
    mode = Column(SAEnum(PaymentMode), default=PaymentMode.other)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)  # display name of whoever created it, or None if auth wasn't active
    edited_at = Column(DateTime, nullable=True)

    purchase = relationship("Purchase", back_populates="payments")


class AppUser(Base):
    """
    A real per-person account, replacing the old single-shared-PIN model.
    Everyone has equal permissions by design (this is a small trusted team,
    not an org needing role-based access control) - the point of separate
    accounts is purely accountability: knowing WHO added or changed a given
    invoice/payment/party, which the audit log (audit.py) already tracks via
    a changed_by field that used to just say the generic string "user" for
    everyone. Now it carries the real logged-in person's name.
    """
    __tablename__ = "app_users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    username = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
