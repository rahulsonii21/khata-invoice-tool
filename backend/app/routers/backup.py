from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from .. import backup
from .. import supabase_client
from .. import data_export
from ..database import SessionLocal

router = APIRouter(prefix="/api/backup", tags=["backup"])


class RestoreRequest(BaseModel):
    confirm: str  # must be exactly "RESTORE" - a deliberate speed bump against misclicks


@router.get("")
def list_backups():
    return backup.list_backups()


@router.post("/run")
def run_backup_now():
    filename = backup.create_backup()
    return {"filename": filename, "message": "Backup created"}


@router.get("/{filename}/download")
def download_backup(filename: str):
    if supabase_client.is_configured():
        # Bucket is public, so we can just redirect straight to it
        return RedirectResponse(supabase_client.public_url(f"backups/{filename}"))

    path = backup.get_local_backup_path(filename)
    if not path:
        raise HTTPException(404, "Backup not found")
    return FileResponse(path, media_type="application/zip", filename=filename)


@router.post("/{filename}/restore")
def restore_backup(filename: str, payload: RestoreRequest):
    """Replaces ALL current data with what's in the given backup. Destructive
    and irreversible (short of restoring yet another backup afterward) -
    requires the caller to send back the literal string "RESTORE" as a
    deliberate speed bump against accidental clicks on something this serious."""
    if payload.confirm != "RESTORE":
        raise HTTPException(400, 'Confirmation required: send {"confirm": "RESTORE"}')

    try:
        data = backup.fetch_backup_data(filename)
    except Exception as e:
        raise HTTPException(404, f"Could not read backup: {e}")

    db = SessionLocal()
    try:
        summary = data_export.restore_all_data(db, data)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Restore failed, no changes were made: {e}")
    finally:
        db.close()

    return {"message": "Restore complete", "restored": summary}
