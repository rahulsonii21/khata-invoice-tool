"""
Thin wrapper around Supabase Storage's REST API. Used instead of the full
supabase-py SDK to keep dependencies light - this only needs upload + list.

Requires these env vars to be set (falls back to local disk elsewhere in the
app if they're absent, so local dev without Supabase still works):
  SUPABASE_URL              e.g. https://wqwyzgcwqemrtkrcibba.supabase.co
  SUPABASE_SERVICE_ROLE_KEY the service_role key (NOT the anon key)
  SUPABASE_BUCKET           defaults to "invoices"
"""
import os
import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "invoice")


def is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _headers():
    # Supabase's newer sb_secret_... keys are NOT JWTs and must go on the
    # apikey header only - sending them as "Authorization: Bearer ..." is
    # rejected. This also still works fine with legacy service_role JWT keys.
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
    }


def upload_bytes(path: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Uploads to {bucket}/{path}, overwriting if it already exists.
    Returns the public URL (bucket must be set to public in Supabase)."""
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{path}"
    headers = {**_headers(), "Content-Type": content_type, "x-upsert": "true"}

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, content=data)

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Supabase upload failed ({resp.status_code}): {resp.text[:300]}")

    return public_url(path)


def public_url(path: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{path}"


def list_objects(prefix: str = "") -> list[dict]:
    """Lists objects under a prefix (folder) in the bucket."""
    url = f"{SUPABASE_URL}/storage/v1/object/list/{SUPABASE_BUCKET}"
    payload = {"prefix": prefix, "limit": 1000, "sortBy": {"column": "created_at", "order": "desc"}}

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers={**_headers(), "Content-Type": "application/json"}, json=payload)

    if resp.status_code != 200:
        raise RuntimeError(f"Supabase list failed ({resp.status_code}): {resp.text[:300]}")

    return resp.json()


def delete_object(path: str):
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}"
    with httpx.Client(timeout=30.0) as client:
        client.request("DELETE", url, headers={**_headers(), "Content-Type": "application/json"},
                        json={"prefixes": [path]})
