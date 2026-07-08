from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/company", response_model=schemas.CompanySettingsOut)
def get_company_settings(db: Session = Depends(get_db)):
    settings = db.query(models.CompanySettings).filter(models.CompanySettings.id == "default").first()
    if not settings:
        return schemas.CompanySettingsOut()
    return settings


@router.put("/company", response_model=schemas.CompanySettingsOut)
def update_company_settings(payload: schemas.CompanySettingsUpdate, db: Session = Depends(get_db)):
    settings = db.query(models.CompanySettings).filter(models.CompanySettings.id == "default").first()
    if not settings:
        settings = models.CompanySettings(id="default")
        db.add(settings)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)
    return settings
