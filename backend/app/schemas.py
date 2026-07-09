from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from .models import InvoiceStatus, PaymentMode


# ---------- Party ----------
class PartyCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    gstin: Optional[str] = None
    notes: Optional[str] = None


class PartyUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    gstin: Optional[str] = None
    notes: Optional[str] = None
    changed_by: Optional[str] = None


class PartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    phone: Optional[str] = None
    gstin: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    total_invoiced: float = 0
    total_received: float = 0
    outstanding: float = 0


# ---------- Payment ----------
class PaymentCreate(BaseModel):
    amount: float
    payment_date: date
    mode: PaymentMode = PaymentMode.other
    remarks: Optional[str] = None


class PaymentUpdate(BaseModel):
    amount: Optional[float] = None
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
    edited_at: Optional[datetime] = None


# ---------- Invoice ----------
class InvoiceCreate(BaseModel):
    party_id: str
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    amount: float
    gst_amount: Optional[float] = None
    raw_image_url: Optional[str] = None
    ocr_confidence: Optional[float] = None
    remarks: Optional[str] = None


class InvoiceUpdate(BaseModel):
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    amount: Optional[float] = None
    gst_amount: Optional[float] = None
    remarks: Optional[str] = None
    changed_by: Optional[str] = None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    party_id: str
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    amount: float
    gst_amount: Optional[float] = None
    raw_image_url: Optional[str] = None
    ocr_confidence: Optional[float] = None
    remarks: Optional[str] = None
    status: InvoiceStatus
    created_at: datetime
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
