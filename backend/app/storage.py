"""
Stores original invoice images so they're retained alongside the extracted
data (and so auto-backup has something meaningful to back up).

Uses Supabase Storage when SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are set
(needed for production - Render's filesystem is ephemeral and wipes local
files on every restart/redeploy). Falls back to local disk otherwise, so
local development without a Supabase project still works.
"""
import uuid
from pathlib import Path

from . import supabase_client

LOCAL_UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads" / "invoices"
LOCAL_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def save_invoice_image(file_bytes: bytes, original_filename: str) -> str:
    ext = Path(original_filename).suffix or ".jpg"
    name = f"{uuid.uuid4()}{ext}"

    if supabase_client.is_configured():
        content_type = _guess_content_type(ext)
        return supabase_client.upload_bytes(name, file_bytes, content_type)

    # Local dev fallback
    path = LOCAL_UPLOADS_DIR / name
    with open(path, "wb") as f:
        f.write(file_bytes)
    return f"/files/invoices/{name}"


def _guess_content_type(ext: str) -> str:
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(ext.lower(), "application/octet-stream")
