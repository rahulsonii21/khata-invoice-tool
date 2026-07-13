"""
Multi-tenant authentication: real per-person accounts, each belonging to one
or more Companies (fully separate businesses sharing this one deployment).
Signup is invite-only - see routers/auth_router.py for how invites work.

Design principle: fails SAFE, same as always in this app. If there are zero
user accounts anywhere, authentication is completely bypassed - a fresh
install or an accidentally-empty database never locks anyone out. It only
activates once at least one account exists ANYWHERE (across all companies).
"""
import os
import secrets
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "khata-default-secret-change-me")
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days

_serializer = URLSafeTimedSerializer(APP_SECRET_KEY)

# Cached in memory rather than querying the DB on every single request (the
# middleware runs on every API call). Refreshed at startup and whenever a
# user is created/deactivated via refresh_auth_required_cache().
_auth_required_cache = None


def refresh_auth_required_cache(db) -> bool:
    from . import models
    global _auth_required_cache
    count = db.query(models.AppUser).filter(models.AppUser.is_active == True).count()  # noqa: E712
    _auth_required_cache = count > 0
    return _auth_required_cache


def is_auth_required() -> bool:
    if _auth_required_cache is None:
        return False  # fail safe rather than crash if this was ever missed at startup
    return _auth_required_cache


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_invite_token() -> str:
    return secrets.token_urlsafe(24)


def authenticate(db, username: str, password: str):
    """Returns the AppUser if credentials are correct and active, else None."""
    from . import models
    user = (
        db.query(models.AppUser)
        .filter(models.AppUser.username == username.strip().lower(), models.AppUser.is_active == True)  # noqa: E712
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def get_active_company_id(db, user) -> str:
    """Which company is 'active' for this user's session. Someone can
    belong to more than one company in the data model, but for now we just
    pick their first membership - a company switcher UI can come later if
    it's ever actually needed; most people belong to exactly one."""
    from . import models
    membership = (
        db.query(models.CompanyMembership)
        .filter(models.CompanyMembership.user_id == user.id)
        .order_by(models.CompanyMembership.created_at)
        .first()
    )
    return membership.company_id if membership else None


def create_token(user, company_id: str) -> str:
    return _serializer.dumps({
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "company_id": company_id,
        "is_platform_admin": user.is_platform_admin,
    })


def decode_token(token: str):
    """Returns the decoded payload dict if the token is valid, else None."""
    try:
        return _serializer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


# Paths that never require auth, even when accounts exist.
EXEMPT_PATHS = {"/api/auth/login", "/api/auth/status", "/api/health", "/api/auth/register"}


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
        if not header.startswith("Bearer "):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        payload = decode_token(header[7:])
        if payload is None:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        # Stashed here so route handlers can know who's making the request
        # AND which company's data they should see - every query in every
        # router needs to filter by this, or one business could see
        # another's financial data.
        request.state.current_user = payload

        return await call_next(request)


def get_current_username(request) -> str:
    """Best-effort: returns the logged-in person's display name if auth is
    active and a valid token was presented, else None."""
    user = getattr(request.state, "current_user", None)
    return user["display_name"] if user else None


def get_current_company_id(request) -> str:
    """The active company for this request. Returns None when auth isn't
    required at all (single-tenant/fresh-install mode) - callers should
    treat None as 'no company filtering' in that case, not as an error."""
    user = getattr(request.state, "current_user", None)
    return user["company_id"] if user else None


def get_current_user_id(request) -> str:
    user = getattr(request.state, "current_user", None)
    return user["user_id"] if user else None


def is_current_user_platform_admin(request) -> bool:
    user = getattr(request.state, "current_user", None)
    return bool(user and user.get("is_platform_admin"))
