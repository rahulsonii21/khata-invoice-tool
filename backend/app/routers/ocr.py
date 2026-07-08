from fastapi import APIRouter, UploadFile, File, HTTPException
from .. import schemas
from .. import ocr
from .. import storage

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.post("/extract", response_model=schemas.OCRExtractResult)
async def extract_from_upload(file: UploadFile = File(...)):
    """Accepts a multipart file upload (used by the bulk-upload screen).
    Saves the original image to storage so it's retained for reference/backup,
    and returns its URL alongside the extracted fields."""
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty file")

    b64 = ocr.image_file_to_base64(contents)
    mime_type = file.content_type or "image/jpeg"

    try:
        result = ocr.extract_invoice_data(b64, mime_type)
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    image_url = storage.save_invoice_image(contents, file.filename or "invoice.jpg")
    result["image_url"] = image_url

    return schemas.OCRExtractResult(**result)


@router.post("/extract-base64", response_model=schemas.OCRExtractResult)
def extract_from_base64(payload: schemas.OCRExtractRequest):
    """Accepts base64 JSON (used when the frontend already has the image in memory,
    e.g. from a mobile camera capture)."""
    try:
        result = ocr.extract_invoice_data(payload.image_base64, payload.mime_type)
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    import base64
    ext = ".png" if "png" in payload.mime_type else ".jpg"
    image_bytes = base64.b64decode(payload.image_base64)
    image_url = storage.save_invoice_image(image_bytes, f"invoice{ext}")
    result["image_url"] = image_url

    return schemas.OCRExtractResult(**result)
