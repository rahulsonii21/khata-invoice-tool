import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from .. import schemas
from .. import ocr
from .. import tesseract_ocr
from .. import storage

router = APIRouter(prefix="/api/ocr", tags=["ocr"])

# "tesseract" (free, local, no API key) or "gemini" (needs GEMINI_API_KEY with
# working quota). Defaults to tesseract since it has no external dependency.
OCR_ENGINE = os.getenv("OCR_ENGINE", "tesseract")


@router.post("/extract", response_model=schemas.OCRExtractResult)
async def extract_from_upload(file: UploadFile = File(...)):
    """Accepts a multipart file upload (used by the bulk-upload screen).
    Saves the original image to storage so it's retained for reference/backup,
    and returns its URL alongside the extracted fields."""
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty file")

    if OCR_ENGINE == "gemini":
        b64 = ocr.image_file_to_base64(contents)
        mime_type = file.content_type or "image/jpeg"
        try:
            result = ocr.extract_invoice_data(b64, mime_type)
        except RuntimeError as e:
            raise HTTPException(502, str(e))
    else:
        try:
            result = tesseract_ocr.extract_invoice_data(contents)
        except Exception as e:
            raise HTTPException(502, f"Tesseract OCR error: {e}")

    try:
        image_url = storage.save_invoice_image(contents, file.filename or "invoice.jpg")
    except Exception as e:
        raise HTTPException(502, f"Image storage error: {e}")
    result["image_url"] = image_url

    return schemas.OCRExtractResult(**result)
