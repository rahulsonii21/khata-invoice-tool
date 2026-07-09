"""
Simple shared-PIN authentication for this small, family-use app - not a full
user account system, just a lock on the front door.

Design principle: fails SAFE. If APP_PIN isn't set as an environment variable,
authentication is completely bypassed - this means forgetting to configure it
never locks anyone out or breaks an existing deployment. It only activates
once you deliberately set APP_PIN.
"""
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

APP_PIN = os.getenv("APP_PIN", "")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "khata-default-secret-change-me")
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days

_serializer = URLSafeTimedSerializer(APP_SECRET_KEY)


def is_auth_required() -> bool:
    return bool(APP_PIN)


def check_pin(pin: str) -> bool:
    return is_auth_required() and pin == APP_PIN


def create_token() -> str:
    return _serializer.dumps({"authenticated": True})


def verify_token(token: str) -> bool:
    try:
        _serializer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
        return True
    except (BadSignature, SignatureExpired):
        return False


# Paths that never require auth, even when APP_PIN is configured.
EXEMPT_PATHS = {"/api/auth/login", "/api/auth/status", "/api/health"}


from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not is_auth_required():
            return await call_next(request)

        path = request.url.path
        if path in EXEMPT_PATHS or not path.startswith("/api/"):
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer ") or not verify_token(header[7:]):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        return await call_next(request)
