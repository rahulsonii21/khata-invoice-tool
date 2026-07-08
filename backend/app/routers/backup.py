from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from .. import backup
from .. import supabase_client

router = APIRouter(prefix="/api/backup", tags=["backup"])


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
