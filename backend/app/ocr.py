"""
OCR extraction using Gemini's vision API.

Sends the invoice image directly to Gemini along with a structured prompt.
Gemini handles both text recognition AND field extraction in one call -
this works noticeably better than traditional OCR for Hindi/English/Hinglish
mixed-script invoices, since it reasons about content rather than just
recognizing characters.

Requires GEMINI_API_KEY env var (free tier available at aistudio.google.com).
"""
import os
import json
import base64
import re
import httpx

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")  # gemini-2.0-flash was deprecated to 0 free-tier quota
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

EXTRACTION_PROMPT = """You are reading a business invoice or bill. The text may be in Hindi (Devanagari script), English, or Hinglish (Hindi written in Latin letters, or mixed Hindi/English). Numbers may use Indian formatting (e.g. 1,00,000 for one lakh) or symbols like Rs, ₹, /-.

Extract the following fields and return ONLY a JSON object, no markdown fences, no explanation:

{
  "party_name": string or null,       // the customer/vendor name on the invoice
  "invoice_number": string or null,
  "invoice_date": string or null,     // convert to YYYY-MM-DD if possible
  "amount": number or null,           // total invoice amount, as a plain number (no commas, no currency symbol)
  "gst_amount": number or null,       // GST/tax amount if shown separately, as a plain number
  "confidence": number,               // your confidence in this extraction, 0.0 to 1.0
  "raw_text": string                  // all text you could read from the image, verbatim, for manual review
}

If a field is unclear or not present, use null. Do not guess wildly - if the amount is ambiguous, set confidence lower rather than inventing a number."""


def extract_invoice_data(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Get a free key at https://aistudio.google.com/apikey "
            "and set it as an environment variable."
        )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": EXTRACTION_PROMPT},
                    {"inline_data": {"mime_type": mime_type, "data": image_base64}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,  # low temperature - we want consistent extraction, not creativity
            "responseMimeType": "application/json",
        },
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
        )

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Gemini response shape: {data}") from e

    # Defensive cleanup in case the model wraps output in markdown fences anyway
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Could not parse Gemini output as JSON: {cleaned[:500]}") from e

    return result


def image_file_to_base64(file_bytes: bytes) -> str:
    return base64.b64encode(file_bytes).decode("utf-8")


ORDER_EXTRACTION_PROMPT = """You are reading a casual order or message - this could be a screenshot of a WhatsApp/SMS text message, or a photo of a handwritten note, listing a party name and one or more items being ordered or billed. The text may be in Hindi (Devanagari script), English, or Hinglish. Numbers may use Indian formatting (e.g. 1,00,000) or symbols like Rs, ₹, /-.

A line like "बैग मिक्स 5" followed by "₹ 1330" means: item description "बैग मिक्स" (Bag Mix), quantity "5", amount 1330 for that line. There may be one item or several listed together - extract every one you can find, each as its own entry.

Extract and return ONLY a JSON object, no markdown fences, no explanation:

{
  "party_name": string or null,        // the customer/village/business name this order is for
  "items": [
    {
      "description": string,          // what the item is, in its original language/script
      "qty_label": string or null,    // quantity as written (e.g. "5", "2 bags") - null if not present
      "amount": number or null         // the rupee amount for this specific line, as a plain number
    }
  ],
  "confidence": number,                // your confidence in this extraction overall, 0.0 to 1.0
  "raw_text": string                   // all text you could read from the image, verbatim, for manual review
}

If you can't confidently identify separate items, return the whole thing as one item with your best guess at a description. Do not invent amounts that aren't actually shown - use null rather than guessing."""


def extract_order_data(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    """
    Reads a screenshot or photo of a casual order/message (not a formal
    invoice) and pulls out a party name plus one or more line items - built
    for Generate Bill's 'fill from photo' option, which needs actual line
    items to work with, not a single total the way invoice OCR does.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Get a free key at https://aistudio.google.com/apikey "
            "and set it as an environment variable."
        )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": ORDER_EXTRACTION_PROMPT},
                    {"inline_data": {"mime_type": mime_type, "data": image_base64}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(GEMINI_URL, params={"key": GEMINI_API_KEY}, json=payload)

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Gemini response shape: {data}") from e

    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Could not parse Gemini output as JSON: {cleaned[:500]}") from e

    return result
