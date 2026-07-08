"""
Free, fully local OCR using Tesseract - no API key, no quota, no cost.

Three stages:
1. Preprocessing (OpenCV) - grayscale, upscale, denoise, adaptive threshold.
   Tesseract's accuracy is very sensitive to image quality, so this step
   matters more than it might seem.
2. Raw text extraction (Tesseract, Hindi+English combined, using the
   higher-accuracy "best" LSTM models rather than the default fast ones).
3. Structured field parsing - Tesseract only returns raw text, it has no
   concept of "this is the amount" vs "this is the invoice number". This
   stage applies invoice-specific patterns (keywords, regex, and targeted
   character-confusion fixes for alphanumeric codes like GSTIN, where OCR
   commonly confuses 1/l/I and 0/O) to pull out the fields the app needs.
"""
import re
import io
import cv2
import numpy as np
import pytesseract
from PIL import Image

LANG = "hin+eng"

# Keywords that tend to precede the actual invoice total, checked in order
# of specificity (grand total is more reliable than a bare "total" line,
# which might refer to a subtotal). Includes common Hindi/Hinglish variants.
TOTAL_KEYWORDS = [
    "grand total", "net amount", "net payable", "total amount",
    "कुल राशि", "grand total", "amount payable", "total",
]
DATE_PATTERN = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
GSTIN_PATTERN = re.compile(r"\b([0-9OolI]{2}[A-Za-z0-9OolI]{10}[A-Za-z0-9OolI]{3})\b")
AMOUNT_PATTERN = re.compile(r"(?:rs\.?|inr|₹)\s*([0-9OolI,]+(?:\.[0-9]{1,2})?)", re.IGNORECASE)
INVOICE_NO_PATTERN = re.compile(
    r"(?:invoice\s*no\.?|inv\s*no\.?|bill\s*no\.?)\s*[:\-]?\s*[^A-Za-z0-9]*([A-Za-z0-9][A-Za-z0-9\-/]*)",
    re.IGNORECASE,
)


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        # Fall back to PIL for formats OpenCV might not decode directly (e.g. some HEIC/webp)
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Upscale small images - Tesseract wants ~300 DPI equivalent; phone photos
    # of a full invoice are often too low-resolution per character.
    h, w = gray.shape
    if max(h, w) < 1800:
        scale = 1800 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )
    return thresh


def extract_raw_text(image_bytes: bytes) -> str:
    processed = preprocess_image(image_bytes)
    pil_img = Image.fromarray(processed)
    # psm 4: assume a single column of text of variable sizes - fits most
    # invoice layouts better than the fully-automatic default.
    config = "--psm 4"
    return pytesseract.image_to_string(pil_img, lang=LANG, config=config)


def _fix_alphanumeric_confusion(code: str) -> str:
    """GSTIN and similar codes follow known digit/letter position rules.
    OCR commonly swaps 1/l/I and 0/O in these codes. Since we know GSTIN's
    fixed format (2 digits, 5 letters, 4 digits, 1 letter, 1 digit, 1 letter/digit,
    'Z', 1 alphanumeric), we can correct position-by-position rather than guessing."""
    if len(code) != 15:
        return code
    digit_positions = {0, 1, 7, 8, 9, 10, 12}
    fixed = list(code)
    for i in digit_positions:
        if fixed[i] in "oOlI":
            fixed[i] = "0" if fixed[i] in "oO" else "1"
    return "".join(fixed)


def _clean_amount(raw: str) -> float | None:
    cleaned = raw.replace(",", "")
    # Fix common digit/letter confusion in numbers
    cleaned = cleaned.translate(str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1"}))
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_invoice_fields(raw_text: str) -> dict:
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    lower_text = raw_text.lower()

    # Amount - prefer the most specific keyword match, take the last/largest
    # number found near it (grand total usually appears after subtotal/GST lines)
    amount = None
    for keyword in TOTAL_KEYWORDS:
        idx = lower_text.find(keyword)
        if idx != -1:
            window = raw_text[idx: idx + 60]
            match = AMOUNT_PATTERN.search(window)
            if not match:
                # keyword present but no Rs/₹ prefix - grab first number after it
                num_match = re.search(r"[\d,]+(?:\.\d{1,2})?", window[len(keyword):])
                if num_match:
                    amount = _clean_amount(num_match.group())
            else:
                amount = _clean_amount(match.group(1))
            if amount:
                break

    if amount is None:
        # Fallback: largest Rs/₹ amount anywhere in the text
        all_amounts = [_clean_amount(m.group(1)) for m in AMOUNT_PATTERN.finditer(raw_text)]
        all_amounts = [a for a in all_amounts if a is not None]
        if all_amounts:
            amount = max(all_amounts)

    # GST amount - look for "GST" keyword specifically, but not "GSTIN"
    # (which contains "gst" as a substring and would otherwise false-match)
    gst_amount = None
    gst_match = re.search(r"\bgst\b(?!in)", lower_text)
    if gst_match:
        window = raw_text[gst_match.start(): gst_match.start() + 60]
        match = AMOUNT_PATTERN.search(window)
        if match:
            gst_amount = _clean_amount(match.group(1))

    # Date - first date-like pattern found
    invoice_date = None
    date_match = DATE_PATTERN.search(raw_text)
    if date_match:
        d, m, y = date_match.groups()
        if len(y) == 2:
            y = "20" + y
        try:
            invoice_date = f"{y}-{int(m):02d}-{int(d):02d}"
        except ValueError:
            invoice_date = None

    # Invoice number
    invoice_number = None
    inv_match = INVOICE_NO_PATTERN.search(raw_text)
    if inv_match:
        invoice_number = inv_match.group(1).strip()

    # GSTIN
    gstin = None
    for candidate in GSTIN_PATTERN.findall(raw_text):
        fixed = _fix_alphanumeric_confusion(candidate)
        if re.match(r"^\d{2}[A-Za-z]{5}\d{4}[A-Za-z]\d[A-Za-z0-9]Z[A-Za-z0-9]$", fixed):
            gstin = fixed
            break

    # Party name - look for an explicit "Party:" label first, else fall back
    # to the first non-keyword, non-numeric-heavy line as a best guess.
    party_name = None
    party_match = re.search(r"party\s*[:\-]\s*(.+)", raw_text, re.IGNORECASE)
    if party_match:
        party_name = party_match.group(1).strip()
    else:
        skip_words = ("invoice", "bill", "date", "gst", "total", "amount", "tax")
        for line in lines:
            digit_ratio = sum(c.isdigit() for c in line) / max(len(line), 1)
            if digit_ratio < 0.3 and not any(w in line.lower() for w in skip_words):
                party_name = line
                break

    # Rough confidence heuristic: how many of the key fields did we actually find
    fields_found = sum(x is not None for x in [amount, invoice_date, party_name])
    confidence = round(fields_found / 3, 2)

    return {
        "party_name": party_name,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "amount": amount,
        "gst_amount": gst_amount,
        "gstin": gstin,
        "confidence": confidence,
        "raw_text": raw_text,
    }


def extract_invoice_data(image_bytes: bytes) -> dict:
    raw_text = extract_raw_text(image_bytes)
    return parse_invoice_fields(raw_text)
