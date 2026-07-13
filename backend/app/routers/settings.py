from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas, storage, auth
from ..database import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/company", response_model=schemas.CompanySettingsOut)
def get_company_settings(request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    settings = db.query(models.CompanySettings).filter(models.CompanySettings.company_id == company_id).first()
    if not settings:
        return schemas.CompanySettingsOut()
    return settings


@router.put("/company", response_model=schemas.CompanySettingsOut)
def update_company_settings(payload: schemas.CompanySettingsUpdate, request: Request, db: Session = Depends(get_db)):
    company_id = auth.get_current_company_id(request)
    settings = db.query(models.CompanySettings).filter(models.CompanySettings.company_id == company_id).first()
    if not settings:
        settings = models.CompanySettings(company_id=company_id)
        db.add(settings)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return settings


@router.post("/company/logo", response_model=schemas.CompanySettingsOut)
async def upload_company_logo(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Empty file")

    company_id = auth.get_current_company_id(request)
    try:
        logo_url = storage.save_company_logo(contents, file.filename or "logo.png", company_id)
    except Exception as e:
        raise HTTPException(502, f"Logo storage error: {e}")

    settings = db.query(models.CompanySettings).filter(models.CompanySettings.company_id == company_id).first()
    if not settings:
        settings = models.CompanySettings(company_id=company_id)
        db.add(settings)

    settings.logo_url = logo_url
    db.commit()
    db.refresh(settings)
    return settings
