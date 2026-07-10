"""
Auto-backup: bundles a full database export (via data_export.py - portable
JSON, works for both SQLite and Postgres) and all stored invoice images into
a single timestamped zip. Runs nightly via the scheduler in scheduler.py,
and can also be triggered manually from the /api/backup/run endpoint.

IMPORTANT CORRECTION: an earlier version of this file skipped the database
entirely when running on Postgres, with a comment claiming "Supabase keeps
its own automatic backups separately." That claim was wrong - Supabase's
free tier (which this app runs on) has ZERO automatic backups; daily
backups and point-in-time recovery are Pro-plan-only features. This means
production had no real database backup at all until this was fixed to
always include a full data export, regardless of database type.

Uses Supabase Storage when configured (needed in production - Render's disk
is ephemeral, so a backup only living on local disk would vanish on the next
restart/redeploy, defeating the point). Falls back to local disk otherwise.

Retention: keeps the most recent BACKUP_RETENTION_COUNT backups and deletes
older ones automatically, so storage usage doesn't grow unbounded.
"""
import os
import io
import json
import zipfile
from pathlib import Path
from datetime import datetime

from .database import SessionLocal
from . import supabase_client, data_export

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


def create_backup() -> str:
    """Creates a new backup archive and returns its filename.
    Uploads to Supabase Storage when configured; otherwise saves locally.
    Enforces retention either way."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"backup_{timestamp}.zip"
    zip_bytes = _build_zip_bytes()

    if supabase_client.is_configured():
        # Avoid same-second collisions the same way the local path does
        existing = {o["name"] for o in supabase_client.list_objects("backups")}
        suffix = 1
        while archive_name in existing:
            archive_name = f"backup_{timestamp}_{suffix}.zip"
            suffix += 1
        supabase_client.upload_bytes(f"backups/{archive_name}", zip_bytes, "application/zip")
    else:
        archive_path = LOCAL_BACKUPS_DIR / archive_name
        suffix = 1
        while archive_path.exists():
            archive_name = f"backup_{timestamp}_{suffix}.zip"
            archive_path = LOCAL_BACKUPS_DIR / archive_name
            suffix += 1
        with open(archive_path, "wb") as f:
            f.write(zip_bytes)

    _enforce_retention()
    return archive_name


def _enforce_retention():
    if supabase_client.is_configured():
        objects = supabase_client.list_objects("backups")
        # list_objects already sorts newest-first
        for old in objects[BACKUP_RETENTION_COUNT:]:
            supabase_client.delete_object(f"backups/{old['name']}")
    else:
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
