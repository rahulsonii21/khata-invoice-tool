"""
Auto-backup: bundles a full database export (via data_export.py - portable
JSON, works for both SQLite and Postgres) and all stored invoice images into
a single timestamped zip.

Uploads to TWO independent destinations when configured - Supabase Storage
and Google Drive - so a single provider's outage, billing lapse, or
misconfiguration can't take out your only copy. Falls back to local disk if
neither is configured (fine for local dev, NOT safe for production, since
Render's disk is ephemeral and vanishes on every restart/redeploy).

Triggered two ways: an in-process nightly scheduler (scheduler.py) as a
best-effort trigger, AND an external GitHub Actions cron job that calls
POST /api/backup/run on a schedule - the external trigger is the one that
actually matters for reliability, since the in-process scheduler only fires
if the app process happens to be alive at that exact moment (if Render's
free tier had put it to sleep, the in-process job would silently never run
at all - not a partial backup, no backup whatsoever that night).

Retention: keeps the most recent BACKUP_RETENTION_COUNT backups and deletes
older ones automatically on each destination independently.
"""
import os
import io
import json
import zipfile
from pathlib import Path
from datetime import datetime

from .database import SessionLocal
from . import supabase_client, data_export, google_drive

BACKEND_ROOT = Path(__file__).resolve().parent.parent
LOCAL_BACKUPS_DIR = BACKEND_ROOT / "backups"
LOCAL_UPLOADS_DIR = BACKEND_ROOT / "uploads"
BACKUP_RETENTION_COUNT = int(os.getenv("BACKUP_RETENTION_COUNT", "14"))

LOCAL_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def _build_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Full data export - works identically for SQLite and Postgres,
        # this is the actual safety net for production data now.
        db = SessionLocal()
        try:
            data = data_export.export_all_data(db)
            zf.writestr("database/data_export.json", json.dumps(data, ensure_ascii=False, indent=2))
        finally:
            db.close()

        # Local invoice images, if storage is running in local-disk mode
        # (in Supabase Storage mode, images already live in Supabase's own
        # persistent storage, not on Render's ephemeral disk, so they don't
        # need to be duplicated into this archive)
        if LOCAL_UPLOADS_DIR.exists():
            for file_path in LOCAL_UPLOADS_DIR.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, arcname=f"uploads/{file_path.relative_to(LOCAL_UPLOADS_DIR)}")

    return buf.getvalue()


def create_backup() -> dict:
    """Creates a new backup archive and uploads it to every configured
    destination independently - a failure in one (e.g. Drive being
    temporarily unreachable) never prevents the other from succeeding.
    Returns a summary of where it landed, so callers/logs can tell if a
    destination silently isn't working."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"backup_{timestamp}.zip"
    zip_bytes = _build_zip_bytes()

    destinations = {"local": False, "supabase": False, "google_drive": False}
    errors = {}

    if supabase_client.is_configured():
        try:
            existing = {o["name"] for o in supabase_client.list_objects("backups")}
            suffix = 1
            name = archive_name
            while name in existing:
                name = f"backup_{timestamp}_{suffix}.zip"
                suffix += 1
            supabase_client.upload_bytes(f"backups/{name}", zip_bytes, "application/zip")
            destinations["supabase"] = True
        except Exception as e:
            errors["supabase"] = str(e)

    if google_drive.is_configured():
        try:
            google_drive.upload_backup(archive_name, zip_bytes)
            destinations["google_drive"] = True
        except Exception as e:
            errors["google_drive"] = str(e)

    # Local disk is the safety-net fallback - used when neither destination
    # is configured (local dev), AND when destinations ARE configured but
    # every single one actually failed (e.g. bad/expired credentials, a
    # network blip) - a backup with zero surviving copies anywhere is exactly
    # the failure this whole system exists to prevent, so this must trigger
    # on real failure, not just on absence of configuration.
    any_destination_configured = supabase_client.is_configured() or google_drive.is_configured()
    any_destination_succeeded = destinations["supabase"] or destinations["google_drive"]
    if not any_destination_configured or not any_destination_succeeded:
        archive_path = LOCAL_BACKUPS_DIR / archive_name
        suffix = 1
        while archive_path.exists():
            archive_name = f"backup_{timestamp}_{suffix}.zip"
            archive_path = LOCAL_BACKUPS_DIR / archive_name
            suffix += 1
        with open(archive_path, "wb") as f:
            f.write(zip_bytes)
        destinations["local"] = True

    _enforce_retention()
    return {"filename": archive_name, "destinations": destinations, "errors": errors}


def _enforce_retention():
    if supabase_client.is_configured():
        objects = supabase_client.list_objects("backups")
        # list_objects already sorts newest-first
        for old in objects[BACKUP_RETENTION_COUNT:]:
            supabase_client.delete_object(f"backups/{old['name']}")

    if google_drive.is_configured():
        try:
            files = google_drive.list_backups()  # already newest-first
            for old in files[BACKUP_RETENTION_COUNT:]:
                google_drive.delete_backup(old["id"])
        except Exception:
            pass  # retention cleanup failing shouldn't break the backup itself

    if not supabase_client.is_configured() and not google_drive.is_configured():
        backups = sorted(LOCAL_BACKUPS_DIR.glob("backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[BACKUP_RETENTION_COUNT:]:
            old.unlink()


def list_backups() -> list[dict]:
    if supabase_client.is_configured():
        objects = supabase_client.list_objects("backups")
        return [
            {
                "filename": o["name"],
                "size_bytes": o.get("metadata", {}).get("size", 0),
                "created_at": o.get("created_at"),
                "download_url": supabase_client.public_url(f"backups/{o['name']}"),
            }
            for o in objects
        ]

    backups = sorted(LOCAL_BACKUPS_DIR.glob("backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "filename": p.name,
            "size_bytes": p.stat().st_size,
            "created_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
            "download_url": None,  # served via the local download endpoint instead
        }
        for p in backups
    ]


def get_google_drive_status() -> dict:
    """Lightweight status check for the Backups screen - shows whether Drive
    redundancy is actually configured and working, without needing to merge
    two separate file lists into one (Supabase remains the primary list used
    for download/restore; Drive is the redundant copy you'd only reach for
    if Supabase itself were unavailable)."""
    if not google_drive.is_configured():
        return {"configured": False, "count": 0}
    try:
        files = google_drive.list_backups()
        return {"configured": True, "count": len(files)}
    except Exception as e:
        return {"configured": True, "count": 0, "error": str(e)}


def get_local_backup_path(filename: str):
    """Only used in local-disk mode. Guards against path traversal."""
    path = LOCAL_BACKUPS_DIR / filename
    if path.exists() and path.parent == LOCAL_BACKUPS_DIR and filename.startswith("backup_"):
        return path
    return None


def fetch_backup_data(filename: str) -> dict:
    """Retrieves and parses the data_export.json from a given backup archive,
    regardless of whether it's stored in Supabase or on local disk."""
    if supabase_client.is_configured():
        import httpx
        url = supabase_client.public_url(f"backups/{filename}")
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            raise RuntimeError(f"Could not fetch backup {filename}: {resp.status_code}")
        zip_bytes = resp.content
    else:
        path = get_local_backup_path(filename)
        if not path:
            raise RuntimeError(f"Backup {filename} not found")
        zip_bytes = path.read_bytes()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        with zf.open("database/data_export.json") as f:
            return json.load(f)
