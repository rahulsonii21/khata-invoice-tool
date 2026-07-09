"""
Generates an outgoing bill as a JPG image - the reverse direction from OCR
(instead of reading a photographed bill, this creates one from typed data),
styled after the user's own letterhead: company name/logo at top, GSTIN and
phone numbers, a party/date row, an item table with Hindi column headers
(विवरण/नग/भाव/कीमत), a GST breakdown footer, and bank details.

This is a clean, professionally laid-out digital version of that structure -
not a pixel-identical reproduction of a specific pre-printed paper ledger
book (matching hand-drawn ruling, a particular calligraphic font, etc. would
be a design-fidelity exercise disproportionate to the practical value here).
"""
import io
from pathlib import Path
from datetime import date as date_type

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
DEVANAGARI_FONT_PATH = FONT_DIR / "NotoSansDevanagari.ttf"

INK = (31, 58, 52)       # matches the app's --ink color
RUST = (161, 61, 43)
LINE = (180, 180, 180)
WIDTH, HEIGHT = 1000, 1400
MARGIN = 50


def _font(size, bold=False):
    # The variable font file covers both weights; PIL uses its default
    # instance regardless of the "bold" flag, but callers still pass it for
    # readability / to make intent obvious at call sites.
    return ImageFont.truetype(str(DEVANAGARI_FONT_PATH), size)


def _fmt_amount(n):
    if n is None:
        return ""
    return f"{n:,.2f}" if n != int(n) else f"{int(n):,}"


def generate_bill_image(
    company: dict,
    party_name: str,
    bill_number: str,
    bill_date: str,
    items: list,
    cgst_pct: float = 0,
    sgst_pct: float = 0,
    igst_pct: float = 0,
    party_gstin: str = None,
    party_address: str = None,
    party_city: str = None,
    party_pincode: str = None,
    party_phone: str = None,
    shipped_by: str = None,
    vehicle_number: str = None,
    driver_contact: str = None,
) -> bytes:
    """
    company: {"company_name", "gstin", "address", "phone", "logo_bytes" (optional),
              "bank_name", "bank_ifsc", "bank_account_number"}
    items: [{"description": str, "qty_label": str, "rate": float, "amount": float}]
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), color="white")
    draw = ImageDraw.Draw(img)

    f_company = _font(42, bold=True)
    f_header_small = _font(16)
    f_label = _font(16)
    f_value = _font(18)
    f_table_header = _font(17, bold=True)
    f_table_cell = _font(17)
    f_footer_label = _font(16, bold=True)
    f_footer_value = _font(17)
    f_small = _font(14)

    y = MARGIN

    # --- Top row: GSTIN left, phone right ---
    if company.get("gstin"):
        draw.text((MARGIN, y), f"GSTIN - {company['gstin']}", font=f_header_small, fill=INK)
    if company.get("phone"):
        phone_text = f"Mob.: {company['phone']}"
        w = draw.textlength(phone_text, font=f_header_small)
        draw.text((WIDTH - MARGIN - w, y), phone_text, font=f_header_small, fill=INK)
    y += 40

    # --- Logo + company name, centered ---
    logo_bytes = company.get("logo_bytes")
    if logo_bytes:
        try:
            logo_img = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            logo_h = 90
            logo_w = int(logo_img.width * (logo_h / logo_img.height))
            logo_img = logo_img.resize((logo_w, logo_h))
            img.paste(logo_img, (WIDTH // 2 - logo_w // 2, y), logo_img)
            y += logo_h + 10
        except Exception:
            pass  # bad/corrupt logo file shouldn't break bill generation

    company_name = company.get("company_name") or ""
    w = draw.textlength(company_name, font=f_company)
    draw.text((WIDTH // 2 - w / 2, y), company_name, font=f_company, fill=(20, 90, 60))
    y += 60

    if company.get("address"):
        w = draw.textlength(company["address"], font=f_small)
        draw.text((WIDTH // 2 - w / 2, y), company["address"], font=f_small, fill=INK)
        y += 30

    y += 15
    draw.line([(MARGIN, y), (WIDTH - MARGIN, y)], fill=LINE, width=2)
    y += 25

    # --- Bill number + date ---
    draw.text((MARGIN, y), f"क्र. {bill_number or ''}", font=f_value, fill=INK)
    date_text = f"दिनांक {bill_date or ''}"
    w = draw.textlength(date_text, font=f_value)
    draw.text((WIDTH - MARGIN - w, y), date_text, font=f_value, fill=INK)
    y += 40

    # --- Party name ---
    draw.text((MARGIN, y), f"श्रीमान् {party_name or ''}", font=f_value, fill=INK)
    y += 35

    if party_gstin:
        draw.text((MARGIN, y), f"GSTIN {party_gstin}", font=f_label, fill=INK)
        y += 30

    # Full postal address line: address, city, pincode combined
    address_parts = [p for p in [party_address, party_city, party_pincode] if p]
    if address_parts:
        draw.text((MARGIN, y), f"पता {', '.join(address_parts)}", font=f_label, fill=INK)
        y += 30

    if party_phone:
        draw.text((MARGIN, y), f"Contact: {party_phone}", font=f_label, fill=INK)
        y += 30

    # --- Shipping / vehicle details, if provided ---
    shipping_parts = []
    if shipped_by:
        shipping_parts.append(f"Shipped By: {shipped_by}")
    if vehicle_number:
        shipping_parts.append(f"Vehicle No.: {vehicle_number}")
    if driver_contact:
        shipping_parts.append(f"Driver Contact: {driver_contact}")
    if shipping_parts:
        draw.text((MARGIN, y), "   ".join(shipping_parts), font=f_label, fill=INK)
        y += 30

    y += 10

    # --- Item table ---
    table_top = y
    col_x = [MARGIN, MARGIN + 480, MARGIN + 620, MARGIN + 760, WIDTH - MARGIN]
    headers = ["विवरण", "नग", "भाव", "कीमत"]

    row_h = 45
    header_h = 40
    draw.rectangle([col_x[0], table_top, col_x[-1], table_top + header_h], outline=INK, width=2)
    for i, h in enumerate(headers):
        hw = draw.textlength(h, font=f_table_header)
        cx = (col_x[i] + col_x[i + 1]) / 2
        draw.text((cx - hw / 2, table_top + 8), h, font=f_table_header, fill=INK)
    for x in col_x[1:-1]:
        draw.line([(x, table_top), (x, table_top + header_h)], fill=INK, width=1)

    y = table_top + header_h
    min_rows = 6  # keeps the table a reasonable size even with just 1-2 items
    display_rows = max(len(items), min_rows)

    for i in range(display_rows):
        row_bottom = y + row_h
        draw.rectangle([col_x[0], y, col_x[-1], row_bottom], outline=LINE, width=1)
        for x in col_x[1:-1]:
            draw.line([(x, y), (x, row_bottom)], fill=LINE, width=1)

        if i < len(items):
            item = items[i]
            desc_text = str(item.get("description", ""))
            if item.get("hsn_code"):
                desc_text += f"  (HSN: {item['hsn_code']})"
            draw.text((col_x[0] + 10, y + 10), desc_text, font=f_table_cell, fill=INK)
            draw.text((col_x[1] + 10, y + 10), str(item.get("qty_label", "")), font=f_table_cell, fill=INK)
            rate_text = _fmt_amount(item.get("rate"))
            draw.text((col_x[2] + 10, y + 10), rate_text, font=f_table_cell, fill=INK)
            amount_text = _fmt_amount(item.get("amount"))
            draw.text((col_x[3] + 10, y + 10), amount_text, font=f_table_cell, fill=INK)

        y = row_bottom

    # --- GST / total footer, inside the same table's right-most columns ---
    total_amount = sum(item.get("amount") or 0 for item in items)
    cgst_amt = total_amount * (cgst_pct or 0) / 100
    sgst_amt = total_amount * (sgst_pct or 0) / 100
    igst_amt = total_amount * (igst_pct or 0) / 100
    grand_total = total_amount + cgst_amt + sgst_amt + igst_amt

    footer_rows = [
        ("Total", "", _fmt_amount(total_amount)),
        ("CGST", f"{cgst_pct or 0}%", _fmt_amount(cgst_amt) if cgst_pct else "-"),
        ("SGST", f"{sgst_pct or 0}%", _fmt_amount(sgst_amt) if sgst_pct else "-"),
        ("IGST", f"{igst_pct or 0}%", _fmt_amount(igst_amt) if igst_pct else "-"),
        ("G. Total", "", _fmt_amount(grand_total)),
    ]
    for label, pct, val in footer_rows:
        row_bottom = y + row_h
        draw.rectangle([col_x[0], y, col_x[-1], row_bottom], outline=LINE, width=1)
        draw.line([(col_x[2], y), (col_x[2], row_bottom)], fill=LINE, width=1)
        draw.line([(col_x[3], y), (col_x[3], row_bottom)], fill=LINE, width=1)
        label_font = f_footer_label if label in ("Total", "G. Total") else f_footer_value
        label_text = f"{label} {pct}".strip()
        draw.text((col_x[2] + 10, y + 10), label_text, font=label_font, fill=INK)
        val_color = RUST if label == "G. Total" else INK
        draw.text((col_x[3] + 10, y + 10), val, font=label_font, fill=val_color)
        y = row_bottom

    y += 30

    # --- Bank details (left) + signature line (right) ---
    bank_lines = []
    if company.get("bank_name"):
        bank_lines.append(company["bank_name"])
    if company.get("bank_ifsc"):
        bank_lines.append(f"IFSC - {company['bank_ifsc']}")
    if company.get("bank_account_number"):
        bank_lines.append(f"A/c No.: {company['bank_account_number']}")

    for line in bank_lines:
        draw.text((MARGIN, y), line, font=f_small, fill=INK)
        y += 24

    signature_text = f"वास्ते : {company_name}"
    w = draw.textlength(signature_text, font=f_label)
    draw.text((WIDTH - MARGIN - w, y - 24 * len(bank_lines) if bank_lines else y),
               signature_text, font=f_label, fill=INK)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()
