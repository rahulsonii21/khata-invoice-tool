from fastapi import APIRouter, UploadFile, File, HTTPException

from .. import storage

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    """Stores an image (e.g. a bill photo attached during manual entry) without
    running it through OCR. Returns the URL to save on the invoice record."""
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty file")

    image_url = storage.save_invoice_image(contents, file.filename or "invoice.jpg")
    return {"image_url": image_url}
