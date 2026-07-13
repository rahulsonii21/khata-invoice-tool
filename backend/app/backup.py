"""
Auto-backup: bundles one company's full data export (via data_export.py -
portable JSON, works for both SQLite and Postgres) and all stored invoice
images into a single timestamped zip.

Uploads to TWO independent destinations when configured - Supabase Storage
and Google Drive - so a single provider's outage, billing lapse, or
misconfiguration can't take out your only copy. Falls back to local disk if
neither is configured (fine for local dev, NOT safe for production, since
Render's disk is ephemeral and vanishes on every restart/redeploy).

Triggered two ways:
- An in-process nightly scheduler (scheduler.py) that loops over every
  company and backs each one up separately - best-effort, since it only
  runs if the app process happens to be alive at that exact moment.
- An external GitHub Actions cron job that calls POST /api/backup/run on a
  schedule, authenticated as one specific person - this backs up just
  THAT person's company, and is the more reliable trigger of the two since
  it doesn't depend on the app happening to be awake at 2am. If you add
  more companies to this deployment, each would need its own scheduled
  trigger (or ask for a platform-admin "back up every company" endpoint).

IMPORTANT (multi-tenant): every backup belongs to exactly one company -
filenames/storage paths always include the company_id specifically so two
companies' backups can never collide, get mixed up in a shared listing, or
have one company accidentally restore another's data.

Retention: keeps the most recent BACKUP_RETENTION_COUNT backups per company
and deletes older ones automatically on each destination independently.
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


def _build_zip_bytes(company_id: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        db = SessionLocal()
        try:
            data = data_export.export_all_data(db, company_id)
            zf.writestr("database/data_export.json", json.dumps(data, ensure_ascii=False, indent=2))
        finally:
            db.close()

        # Local invoice images, if storage is running in local-disk mode.
        # NOTE: local-disk mode doesn't currently separate images by company
        # (an existing limitation, not introduced by multi-tenancy) - this
        # only matters for single-company local/dev use, since production
        # uses Supabase Storage where images already live independently of
        # this backup archive entirely.
        if LOCAL_UPLOADS_DIR.exists():
            for file_path in LOCAL_UPLOADS_DIR.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, arcname=f"uploads/{file_path.relative_to(LOCAL_UPLOADS_DIR)}")

    return buf.getvalue()


def create_backup(company_id: str) -> dict:
    """Creates a new backup archive for ONE company and uploads it to every
    configured destination independently - a failure in one (e.g. Drive
    being temporarily unreachable) never prevents the other from
    succeeding. Returns a summary of where it landed."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"backup_{company_id}_{timestamp}.zip"
    zip_bytes = _build_zip_bytes(company_id)

    destinations = {"local": False, "supabase": False, "google_drive": False}
    errors = {}

    if supabase_client.is_configured():
        try:
            existing = {o["name"] for o in supabase_client.list_objects("backups")}
            suffix = 1
            name = archive_name
            while name in existing:
                name = f"backup_{company_id}_{timestamp}_{suffix}.zip"
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

    any_destination_configured = supabase_client.is_configured() or google_drive.is_configured()
    any_destination_succeeded = destinations["supabase"] or destinations["google_drive"]
    if not any_destination_configured or not any_destination_succeeded:
        archive_path = LOCAL_BACKUPS_DIR / archive_name
        suffix = 1
        while archive_path.exists():
            archive_name = f"backup_{company_id}_{timestamp}_{suffix}.zip"
            archive_path = LOCAL_BACKUPS_DIR / archive_name
            suffix += 1
        with open(archive_path, "wb") as f:
            f.write(zip_bytes)
        destinations["local"] = True

    _enforce_retention(company_id)
    return {"filename": archive_name, "destinations": destinations, "errors": errors}


def create_backups_for_all_companies() -> dict:
    """Used by the in-process nightly scheduler, which has direct DB access
    and no single 'current user' - loops over every company and backs each
    one up separately, so adding a new company never requires separately
    wiring up its own nightly job."""
    from . import models
    db = SessionLocal()
    try:
        companies = db.query(models.Company).all()
    finally:
        db.close()

    results = {}
    for company in companies:
        try:
            results[company.name] = create_backup(company.id)
        except Exception as e:
            results[company.name] = {"error": str(e)}
    return results


def _enforce_retention(company_id: str):
    prefix = f"backup_{company_id}_"

    if supabase_client.is_configured():
        objects = [o for o in supabase_client.list_objects("backups") if o["name"].startswith(prefix)]
        for old in objects[BACKUP_RETENTION_COUNT:]:
            supabase_client.delete_object(f"backups/{old['name']}")

    if google_drive.is_configured():
        try:
            files = [f for f in google_drive.list_backups() if f["name"].startswith(prefix)]
            for old in files[BACKUP_RETENTION_COUNT:]:
                google_drive.delete_backup(old["id"])
        except Exception:
            pass  # retention cleanup failing shouldn't break the backup itself

    if not supabase_client.is_configured() and not google_drive.is_configured():
        backups = sorted(
            LOCAL_BACKUPS_DIR.glob(f"{prefix}*.zip"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        for old in backups[BACKUP_RETENTION_COUNT:]:
            old.unlink()


def list_backups(company_id: str) -> list[dict]:
    prefix = f"backup_{company_id}_"

    if supabase_client.is_configured():
        objects = [o for o in supabase_client.list_objects("backups") if o["name"].startswith(prefix)]
        return [
            {
                "filename": o["name"],
                "size_bytes": o.get("metadata", {}).get("size", 0),
                "created_at": o.get("created_at"),
                "download_url": supabase_client.public_url(f"backups/{o['name']}"),
            }
            for o in objects
        ]

    backups = sorted(
        LOCAL_BACKUPS_DIR.glob(f"{prefix}*.zip"), key=lambda p: p.stat().st_mtime, reverse=True
    )
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
    redundancy is actually configured and working."""
    if not google_drive.is_configured():
        return {"configured": False, "count": 0}
    try:
        files = google_drive.list_backups()
        return {"configured": True, "count": len(files)}
    except Exception as e:
        return {"configured": True, "count": 0, "error": str(e)}


def get_local_backup_path(filename: str, company_id: str):
    """Only used in local-disk mode. Guards against path traversal AND
    against fetching a filename that doesn't actually belong to the
    requesting company - the filename must start with this exact
    company's prefix, not just any 'backup_' prefix."""
    path = LOCAL_BACKUPS_DIR / filename
    expected_prefix = f"backup_{company_id}_"
    if path.exists() and path.parent == LOCAL_BACKUPS_DIR and filename.startswith(expected_prefix):
        return path
    return None


def fetch_backup_data(filename: str, company_id: str) -> dict:
    """Retrieves and parses the data_export.json from a given backup
    archive. Requires the filename to actually belong to the given
    company (see get_local_backup_path / the prefix check below) - without
    this, someone could potentially restore a DIFFERENT company's backup
    file if they guessed or otherwise obtained its filename."""
    expected_prefix = f"backup_{company_id}_"
    if not filename.startswith(expected_prefix):
        raise RuntimeError("That backup doesn't belong to your company")

    if supabase_client.is_configured():
        import httpx
        url = supabase_client.public_url(f"backups/{filename}")
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            raise RuntimeError(f"Could not fetch backup {filename}: {resp.status_code}")
        zip_bytes = resp.content
    else:
        path = get_local_backup_path(filename, company_id)
        if not path:
            raise RuntimeError(f"Backup {filename} not found")
        zip_bytes = path.read_bytes()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        with zf.open("database/data_export.json") as f:
            return json.load(f)
