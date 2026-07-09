from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    pin: str


@router.get("/status")
def auth_status():
    """Unauthenticated - lets the frontend know whether to show a PIN screen at all."""
    return {"required": auth.is_auth_required()}


@router.post("/login")
def login(payload: LoginRequest):
    if not auth.is_auth_required():
        return {"token": None, "required": False}

    if not auth.check_pin(payload.pin):
        raise HTTPException(401, "Incorrect PIN")

    return {"token": auth.create_token(), "required": True}
