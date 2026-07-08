"""
Auto-backup: bundles the database and all stored invoice images into a single
timestamped zip. Runs nightly via the scheduler in scheduler.py, and can also
be triggered manually from the /api/backup/run endpoint.

Uses Supabase Storage when configured (needed in production - Render's disk
is ephemeral, so a backup only living on local disk would vanish on the next
restart/redeploy, defeating the point). Falls back to local disk otherwise.

Retention: keeps the most recent BACKUP_RETENTION_COUNT backups and deletes
older ones automatically, so storage usage doesn't grow unbounded.
"""
import os
import io
import zipfile
from pathlib import Path
from datetime import datetime

from .database import DATABASE_URL
from . import supabase_client

BACKEND_ROOT = Path(__file__).resolve().parent.parent
LOCAL_BACKUPS_DIR = BACKEND_ROOT / "backups"
LOCAL_UPLOADS_DIR = BACKEND_ROOT / "uploads"
BACKUP_RETENTION_COUNT = int(os.getenv("BACKUP_RETENTION_COUNT", "14"))

LOCAL_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def _sqlite_path_from_url(url: str):
    if not url.startswith("sqlite:///"):
        return None
    return BACKEND_ROOT / url.replace("sqlite:///", "").replace("./", "")


def _build_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        sqlite_path = _sqlite_path_from_url(DATABASE_URL)
        if sqlite_path and sqlite_path.exists():
            zf.write(sqlite_path, arcname=f"database/{sqlite_path.name}")
        else:
            zf.writestr(
                "database/NOTE.txt",
                "DATABASE_URL is Postgres (Supabase) - this zip does not include a DB dump, "
                "since Supabase keeps its own automatic backups of the Postgres database "
                "separately. This archive covers the invoice images only."
            )

        # Local invoice images, if storage is running in local-disk mode
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
