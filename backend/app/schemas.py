from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .models import InvoiceStatus, PaymentMode


# ---------- Party ----------
class PartyCreate(BaseModel):
    name: str = Field(min_length=1)
    phone: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be blank")
        return stripped


class PartyUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    changed_by: Optional[str] = None


class PartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    phone: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None
    total_invoiced: float = 0
    total_received: float = 0
    outstanding: float = 0


# ---------- Payment ----------
class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    payment_date: date
    mode: PaymentMode = PaymentMode.other
    remarks: Optional[str] = None


class PaymentUpdate(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0)
    payment_date: Optional[date] = None
    mode: Optional[PaymentMode] = None
    remarks: Optional[str] = None
    changed_by: Optional[str] = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    invoice_id: str
    amount: float
    payment_date: date
    mode: PaymentMode
    remarks: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None
    edited_at: Optional[datetime] = None


# ---------- Invoice ----------
class InvoiceCreate(BaseModel):
    party_id: str
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    amount: float = Field(gt=0)
    gst_amount: Optional[float] = None
    raw_image_url: Optional[str] = None
    ocr_confidence: Optional[float] = None
    remarks: Optional[str] = None
    shipped_by: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_contact: Optional[str] = None


class InvoiceUpdate(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    amount: Optional[float] = Field(default=None, gt=0)
    gst_amount: Optional[float] = None
    remarks: Optional[str] = None
    shipped_by: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_contact: Optional[str] = None
    changed_by: Optional[str] = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    party_id: str
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    is_overdue: bool = False
    amount: float
    gst_amount: Optional[float] = None
    raw_image_url: Optional[str] = None
    ocr_confidence: Optional[float] = None
    remarks: Optional[str] = None
    shipped_by: Optional[str] = None
    vehicle_number: Optional[str] = None
    driver_contact: Optional[str] = None
    is_generated: bool = False
    items_json: Optional[str] = None
    cgst_pct: Optional[float] = None
    sgst_pct: Optional[float] = None
    igst_pct: Optional[float] = None
    status: InvoiceStatus
    created_at: datetime
    created_by: Optional[str] = None
    total_paid: float = 0
    outstanding: float = 0
    payments: List[PaymentOut] = []


# ---------- OCR extraction ----------
class OCRExtractRequest(BaseModel):
    image_base64: str
    mime_type: str = "image/jpeg"


class OCRExtractResult(BaseModel):
    party_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    amount: Optional[float] = None
    gst_amount: Optional[float] = None
    gstin: Optional[str] = None
    confidence: Optional[float] = None
    raw_text: Optional[str] = None
    image_url: Optional[str] = None


# ---------- Company settings ----------
class CompanySettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    logo_url: Optional[str] = None
    bank_name: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_account_number: Optional[str] = None
    default_credit_days: Optional[float] = None


class CompanySettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    company_name: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    logo_url: Optional[str] = None
    bank_name: Optional[str] = None
    bank_ifsc: Optional[str] = None
    bank_account_number: Optional[str] = None
    default_credit_days: Optional[float] = None


# ---------- Purchase ledger (suppliers/purchases/purchase payments) ----------
class SupplierCreate(BaseModel):
    name: str = Field(min_length=1)
    phone: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name cannot be blank")
        return stripped


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    changed_by: Optional[str] = None


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    phone: Optional[str] = None
    gstin: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None
    total_purchased: float = 0
    total_paid: float = 0
    outstanding: float = 0


class PurchasePaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    payment_date: date
    mode: PaymentMode = PaymentMode.other
    remarks: Optional[str] = None


class PurchasePaymentUpdate(BaseModel):
    amount: Optional[float] = Field(default=None, gt=0)
    payment_date: Optional[date] = None
    mode: Optional[PaymentMode] = None
    remarks: Optional[str] = None
    changed_by: Optional[str] = None


class PurchasePaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    purchase_id: str
    amount: float
    payment_date: date
    mode: PaymentMode
    remarks: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None
    edited_at: Optional[datetime] = None


class PurchaseCreate(BaseModel):
    supplier_id: str
    purchase_number: Optional[str] = None
    purchase_date: Optional[date] = None
    due_date: Optional[date] = None
    amount: float = Field(gt=0)
    gst_amount: Optional[float] = None
    raw_image_url: Optional[str] = None
    ocr_confidence: Optional[float] = None
    remarks: Optional[str] = None


class PurchaseUpdate(BaseModel):
    purchase_number: Optional[str] = None
    purchase_date: Optional[date] = None
    due_date: Optional[date] = None
    amount: Optional[float] = Field(default=None, gt=0)
    gst_amount: Optional[float] = None
    remarks: Optional[str] = None
    changed_by: Optional[str] = None


class PurchaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    supplier_id: str
    purchase_number: Optional[str] = None
    purchase_date: Optional[date] = None
    due_date: Optional[date] = None
    is_overdue: bool = False
    amount: float
    gst_amount: Optional[float] = None
    raw_image_url: Optional[str] = None
    ocr_confidence: Optional[float] = None
    remarks: Optional[str] = None
    status: InvoiceStatus
    created_at: datetime
    created_by: Optional[str] = None
    total_paid: float = 0
    outstanding: float = 0
    payments: List[PurchasePaymentOut] = []


# ---------- User accounts ----------
class UserRegister(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=4)

    @field_validator("username")
    @classmethod
    def username_shape(cls, v):
        cleaned = v.strip().lower()
        if not cleaned.replace("_", "").replace(".", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, dots and underscores")
        return cleaned


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    display_name: str
    is_active: bool
    created_at: datetime
