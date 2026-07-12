"""
Per-person account authentication, replacing the old single-shared-PIN
system. Everyone has equal permissions - the point isn't access control,
it's accountability: every invoice/payment/party change gets tagged with
the real person who made it, instead of a generic "user" string.

Design principle: fails SAFE, same as before. If there are zero user
accounts in the database, authentication is completely bypassed - this
means a fresh install or someone who never sets up accounts never gets
locked out. It only activates once at least one account actually exists.
"""
import os
import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "khata-default-secret-change-me")
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days

_serializer = URLSafeTimedSerializer(APP_SECRET_KEY)

# Cached in memory rather than querying the DB on every single request (the
# middleware runs on every API call). Refreshed at startup and whenever a
# user is created/deleted via refresh_auth_required_cache().
_auth_required_cache = None


def refresh_auth_required_cache(db) -> bool:
    from . import models
    global _auth_required_cache
    count = db.query(models.AppUser).filter(models.AppUser.is_active == True).count()  # noqa: E712
    _auth_required_cache = count > 0
    return _auth_required_cache


def is_auth_required() -> bool:
    if _auth_required_cache is None:
        # Shouldn't normally happen (main.py primes this at startup), but
        # fail safe rather than crash if it's ever missed: treat as "not
        # required" so a bug here can't lock everyone out.
        return False
    return _auth_required_cache


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def authenticate(db, username: str, password: str):
    """Returns the AppUser if credentials are correct and the account is
    active, else None. Doesn't distinguish 'wrong username' from 'wrong
    password' in its return value - that distinction shouldn't be visible
    to a caller trying to guess valid usernames."""
    from . import models
    user = (
        db.query(models.AppUser)
        .filter(models.AppUser.username == username.strip().lower(), models.AppUser.is_active == True)  # noqa: E712
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def create_token(user) -> str:
    return _serializer.dumps({
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
    })


def decode_token(token: str):
    """Returns the decoded payload dict if the token is valid, else None."""
    try:
        return _serializer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


# Paths that never require auth, even when accounts exist.
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
        if not header.startswith("Bearer "):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        payload = decode_token(header[7:])
        if payload is None:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        # Stashed here so route handlers can know who's making the request
        # (used to stamp changed_by on audit-logged edits with the real
        # logged-in person, instead of trusting whatever the client sends).
        request.state.current_user = payload

        return await call_next(request)


def get_current_username(request) -> str:
    """Best-effort: returns the logged-in person's display name if auth is
    active and a valid token was presented, else None. Safe to call even
    when auth is disabled entirely (just returns None)."""
    user = getattr(request.state, "current_user", None)
    return user["display_name"] if user else None
