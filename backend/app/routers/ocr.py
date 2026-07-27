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


@router.post("/extract-order", response_model=schemas.OrderExtractResult)
async def extract_order_from_upload(file: UploadFile = File(...)):
    """
    For Generate Bill's 'fill from photo' option - reads a screenshot or
    photo of a casual order/message and returns a party name plus line
    items to pre-fill the bill form with. Requires Gemini specifically
    (not Tesseract): this needs actual reasoning about which numbers are
    quantities vs amounts and where one item ends and the next begins,
    not just character recognition. The source image is used only for
    this one-time read and is not saved anywhere afterward.
    """
    if OCR_ENGINE != "gemini":
        raise HTTPException(
            502,
            "Reading orders from a photo needs the Gemini OCR engine specifically - "
            "set OCR_ENGINE=gemini and a working GEMINI_API_KEY to use this.",
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty file")

    b64 = ocr.image_file_to_base64(contents)
    mime_type = file.content_type or "image/jpeg"
    try:
        result = ocr.extract_order_data(b64, mime_type)
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    return schemas.OrderExtractResult(**result)
