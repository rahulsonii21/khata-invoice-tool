"""
Uploads backup archives to a Google Drive folder, as a genuinely independent
second storage location alongside Supabase Storage - if one provider has an
outage, a billing issue, or gets accidentally misconfigured, the other still
has a copy. This is real redundancy, not just belt-and-suspenders on the same
provider.

Uses a Google service account (not the user's personal OAuth login) because
this only ever needs to do one thing - write backup files into one specific
shared folder - and a service account avoids needing a browser-based consent
flow or refresh-token handling for an unattended, scheduled task.

Setup (see DEPLOYMENT.md for full step-by-step):
1. Create a Google Cloud project, enable the Drive API
2. Create a service account, download its JSON key
3. Share a Drive folder with the service account's email (as Editor)
4. Set GOOGLE_SERVICE_ACCOUNT_JSON (the full JSON key content) and
   GOOGLE_DRIVE_FOLDER_ID (from the folder's URL) as environment variables

If these aren't set, Drive upload is silently skipped - Supabase Storage
alone still works exactly as before. This is purely additive.
"""
import os
import io
import json

_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")


def is_configured() -> bool:
    return bool(_FOLDER_ID and _SERVICE_ACCOUNT_JSON)


def _get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(_SERVICE_ACCOUNT_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def upload_backup(filename: str, content_bytes: bytes) -> str | None:
    """Uploads a backup archive to the configured Drive folder. Returns the
    file's Drive ID on success, or None if Drive isn't configured. Raises on
    genuine upload failure (caller decides how to handle - a Drive outage
    shouldn't block the Supabase copy from still succeeding)."""
    if not is_configured():
        return None

    from googleapiclient.http import MediaIoBaseUpload

    service = _get_drive_service()
    media = MediaIoBaseUpload(io.BytesIO(content_bytes), mimetype="application/zip", resumable=False)
    file_metadata = {"name": filename, "parents": [_FOLDER_ID]}

    result = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return result.get("id")


def delete_backup(drive_file_id: str) -> None:
    """Used for retention cleanup - mirrors the Supabase side's behavior of
    deleting old backups beyond the retention count."""
    if not is_configured():
        return
    service = _get_drive_service()
    service.files().delete(fileId=drive_file_id).execute()


def list_backups() -> list[dict]:
    """Lists backup files in the configured Drive folder, newest first."""
    if not is_configured():
        return []
    service = _get_drive_service()
    results = (
        service.files()
        .list(
            q=f"'{_FOLDER_ID}' in parents and trashed = false",
            fields="files(id, name, createdTime, size)",
            orderBy="createdTime desc",
        )
        .execute()
    )
    return results.get("files", [])
