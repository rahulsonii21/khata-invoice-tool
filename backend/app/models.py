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
    company_id = Column(String, nullable=True, index=True)  # no real FK constraint - see note above Company class
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
    company_id = Column(String, nullable=True, index=True)  # no real FK constraint - see note above Company class
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
    stock_links = relationship("InvoiceStockLink", cascade="all, delete-orphan")

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
    company_id = Column(String, nullable=True, index=True)  # no real FK constraint - see note above Company class
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
    """One row per company (business details used as the letterhead on PDF
    statements and generated bills) - was a fixed singleton row (id='default')
    before multi-tenancy; now keyed by company_id instead, one row per
    business using this deployment."""
    __tablename__ = "company_settings"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(String, nullable=True, unique=True, index=True)  # no real FK constraint - see note above Company class
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
    company_id = Column(String, nullable=True, index=True)  # no real FK constraint - see note above Company class
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
    company_id = Column(String, nullable=True, index=True)  # no real FK constraint - see note above Company class
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
    company_id = Column(String, nullable=True, index=True)  # no real FK constraint - see note above Company class
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
    A real per-person account. Can belong to one or more companies (see
    CompanyMembership) - in practice almost everyone belongs to exactly one,
    but the data model supports more (e.g. someone helping run two separate
    businesses).
    """
    __tablename__ = "app_users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    username = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    # Platform-level (not company-level) permission: can this person create
    # an invite for someone to start a brand NEW, separate company. Only the
    # very first account ever created on this deployment gets this - signup
    # is invite-only, so this gates who can onboard entirely new businesses,
    # as opposed to just adding a teammate to a company that already exists
    # (any member of a company can do that for their OWN company).
    is_platform_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Company(Base):
    """
    A fully separate business using this deployment - its own parties,
    invoices, suppliers, purchases, company settings, all isolated from
    every other company. This is what makes the app multi-tenant: many
    independent businesses can use the same running instance, each seeing
    only their own data.
    """
    __tablename__ = "companies"

    # Native UUID, matching how this table was actually created in
    # production via create_all() when multi-tenancy first launched -
    # alongside CompanyMembership and Invite, all UUID together from day
    # one, never touched by a migration. The 7 OTHER tables below (parties,
    # invoices, payments, suppliers, purchases, purchase_payments,
    # company_settings) are different: their company_id was retrofitted
    # onto tables that already existed, via a plain ALTER TABLE ADD COLUMN
    # VARCHAR - not through create_all() - so those really are VARCHAR in
    # the real database and their models correctly declare String. This
    # table is not one of those, and declaring it as String was actually
    # the mistake that caused the login endpoint to start crashing right
    # after that fix shipped - confirmed by precisely reproducing the real
    # production schema history against a real local Postgres instance:
    # attempting a fresh create_all() with Company.id as String, while
    # company_memberships.company_id (created earlier, still UUID) already
    # existed, failed with the exact same class of foreign-key type error
    # this whole investigation has been chasing.
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CompanyMembership(Base):
    """
    Which people belong to which company. Everyone has equal ('full')
    access within a company they're a member of - no in-company roles by
    design (small trusted teams, not orgs needing granular permissions).
    """
    __tablename__ = "company_memberships"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("app_users.id"), nullable=False, index=True)
    # UUID here, NOT String like the retrofitted tables below - this table
    # was created fresh via create_all() alongside Company itself, both as
    # native UUID from day one. Never touched by an ALTER TABLE migration,
    # so its real column type in production was never mismatched and never
    # needed changing.
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Invite(Base):
    """
    Signup is invite-only, not open self-registration. Two kinds of invite:
    - company_id is NULL: redeeming this creates a brand new, separate
      company (the redeemer names it and becomes its first member). Only
      platform admins can create these right now.
    - company_id is SET: redeeming this adds the person as a full member of
      that EXISTING company (e.g. Rahul inviting his father into Vrindavan
      Organics). Any existing member of a company can create one of these,
      for their own company.
    """
    __tablename__ = "invites"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    token = Column(String, nullable=False, unique=True, index=True)
    # UUID here, NOT String - same reasoning as CompanyMembership.company_id
    # above: this table was created fresh alongside Company, never migrated.
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=True)
    created_by_user_id = Column(UUID(as_uuid=False), ForeignKey("app_users.id"), nullable=False)
    used_by_user_id = Column(UUID(as_uuid=False), ForeignKey("app_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)


class StockLocation(Base):
    """
    A physical place stock actually sits - a shop counter, a godown, etc.
    Deliberately just a name, nothing more, for now: no address, no manager,
    no capacity - the whole point of starting simple is not building fields
    nobody asked for yet. Company-scoped like everything else, so one
    business's locations are never visible to another's.
    """
    __tablename__ = "stock_locations"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Item(Base):
    """
    Something you actually stock (a fertilizer, a seed variety, etc) -
    separate from Party/Invoice entirely, since an item isn't a customer or
    a bill, it's a physical thing sitting in one or more locations. unit is
    deliberately a free-text label ("bag", "kg", "litre") rather than a
    fixed list - whatever actually matches how a given item is counted,
    with no forced conversion math between units.
    """
    __tablename__ = "items"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    unit = Column(String, nullable=True)
    # Alert threshold for the TOTAL across every location combined, not
    # per-location - confirmed directly: what actually matters is "am I
    # about to run out overall", not one specific godown dipping low while
    # the others are fine.
    reorder_threshold = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)

    stock_entries = relationship("ItemStock", back_populates="item", cascade="all, delete-orphan")

    @property
    def total_quantity(self):
        return sum(s.quantity for s in self.stock_entries)

    @property
    def is_low_stock(self):
        if self.reorder_threshold is None:
            return False
        return self.total_quantity < self.reorder_threshold


class ItemStock(Base):
    """
    How much of one item sits at one location, right now. One row per
    (item, location) pair - created lazily the first time a quantity is
    actually set for that combination, rather than pre-creating a row for
    every item at every location whether it's ever used there or not.
    """
    __tablename__ = "item_stock"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    item_id = Column(UUID(as_uuid=False), ForeignKey("items.id"), nullable=False, index=True)
    location_id = Column(UUID(as_uuid=False), ForeignKey("stock_locations.id"), nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    item = relationship("Item", back_populates="stock_entries")
    location = relationship("StockLocation")


class InvoiceStockLink(Base):
    """
    Records that a specific quantity of a specific item, at a specific
    location, was deducted because of a specific invoice - not just the
    deduction itself (which just updates ItemStock directly), but a
    traceable record OF that deduction. This is what makes it possible to
    correctly give the stock back if the invoice is later deleted, rather
    than the deduction being a one-way, unreversible side effect.
    """
    __tablename__ = "invoice_stock_links"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    invoice_id = Column(UUID(as_uuid=False), ForeignKey("invoices.id"), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=False), ForeignKey("items.id"), nullable=False)
    location_id = Column(UUID(as_uuid=False), ForeignKey("stock_locations.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
