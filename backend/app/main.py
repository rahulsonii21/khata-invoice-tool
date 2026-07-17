from contextlib import asynccontextmanager
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import Base, engine, ensure_columns_exist, ensure_index_exists
from .routers import parties, invoices, payments, dashboard, ocr, export, backup, settings, uploads, bills, auth_router, suppliers, purchases, purchase_payments
from . import scheduler, auth

# Creates tables if they don't exist (fine for SQLite/dev;
# use Alembic migrations later once schema stabilizes in production).
Base.metadata.create_all(bind=engine)

# Additive schema fixes for tables that already existed before these columns
# were introduced (create_all() alone won't add columns to existing tables).
ensure_columns_exist("company_settings", {
    "logo_url": "VARCHAR",
    "bank_name": "VARCHAR",
    "bank_ifsc": "VARCHAR",
    "bank_account_number": "VARCHAR",
    "default_credit_days": "FLOAT",
})
ensure_columns_exist("parties", {
    "address": "TEXT",
    "city": "VARCHAR",
    "pincode": "VARCHAR",
    "email": "VARCHAR",
})
ensure_columns_exist("invoices", {
    "shipped_by": "VARCHAR",
    "vehicle_number": "VARCHAR",
    "driver_contact": "VARCHAR",
    "is_generated": "BOOLEAN DEFAULT FALSE",
    "items_json": "TEXT",
    "cgst_pct": "FLOAT",
    "sgst_pct": "FLOAT",
    "igst_pct": "FLOAT",
    "due_date": "DATE",
    "created_by": "VARCHAR",
})
ensure_columns_exist("parties", {
    "address": "TEXT",
    "city": "VARCHAR",
    "pincode": "VARCHAR",
    "email": "VARCHAR",
    "created_by": "VARCHAR",
})
ensure_columns_exist("payments", {"created_by": "VARCHAR"})
ensure_columns_exist("suppliers", {"created_by": "VARCHAR"})
ensure_columns_exist("purchases", {"created_by": "VARCHAR"})
ensure_columns_exist("purchase_payments", {"created_by": "VARCHAR"})

# Multi-tenancy: every data table gets a company_id so one business's data
# never mixes with another's. Nullable so pre-existing rows (from before
# multi-tenancy existed) don't break - those get claimed by whichever
# company bootstraps first (see auth_router.py's register() bootstrap path).
ensure_columns_exist("parties", {"company_id": "VARCHAR"})
ensure_columns_exist("invoices", {"company_id": "VARCHAR"})
ensure_columns_exist("payments", {"company_id": "VARCHAR"})
ensure_columns_exist("suppliers", {"company_id": "VARCHAR"})
ensure_columns_exist("purchases", {"company_id": "VARCHAR"})
ensure_columns_exist("purchase_payments", {"company_id": "VARCHAR"})
ensure_columns_exist("company_settings", {"company_id": "VARCHAR"})
ensure_columns_exist("app_users", {"is_platform_admin": "BOOLEAN DEFAULT FALSE"})

# Retroactively add indexes on frequently-filtered columns for databases that
# already existed before these were added to the model - index=True on a
# Column only takes effect for tables create_all() builds fresh.
ensure_index_exists("invoices", "party_id")
ensure_index_exists("invoices", "invoice_date")
ensure_index_exists("invoices", "due_date")
ensure_index_exists("payments", "invoice_id")
ensure_index_exists("purchases", "supplier_id")
ensure_index_exists("purchases", "purchase_date")
ensure_index_exists("purchases", "due_date")
ensure_index_exists("purchase_payments", "purchase_id")

# Prime the in-memory "is auth required" cache at startup, since it's derived
# from whether any user accounts exist in the database - the middleware
# checks this on every request and shouldn't have to query the DB each time.
from .database import SessionLocal
_startup_db = SessionLocal()
try:
    auth.refresh_auth_required_cache(_startup_db)

    # Safety net: ensure at least one platform admin exists. This matters
    # for accounts created before multi-tenancy existed at all (is_platform_
    # admin didn't exist as a concept yet) - when that column got added via
    # migration, an already-existing account defaulted to False rather than
    # True, even for someone who's clearly the actual founder here. Without
    # this, nobody would ever be able to invite someone to start a new,
    # separate company on this deployment. Promotes the very first account
    # ever created (by created_at) only if literally nobody currently has
    # platform-admin status - never demotes or second-guesses an existing
    # admin, and never grants this to anyone if the deployment isn't
    # actually missing one.
    from . import models
    if _startup_db.query(models.AppUser).filter(models.AppUser.is_platform_admin == True).count() == 0:  # noqa: E712
        earliest_user = _startup_db.query(models.AppUser).order_by(models.AppUser.created_at).first()
        if earliest_user:
            earliest_user.is_platform_admin = True
            _startup_db.commit()
finally:
    _startup_db.close()

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="Invoice Management Tool API", lifespan=lifespan)

# CRITICAL FIX: by default, an unhandled exception inside a route handler
# causes Starlette to generate its own bare 500 response OUTSIDE the normal
# middleware response path - which means it skips CORSMiddleware entirely,
# with NO CORS headers at all. Browsers then block that response from ever
# reaching the page's own JavaScript, since it looks like any other
# CORS-violating response - even though the browser's own Network tab
# still shows the real 500 underneath. This is exactly why the Dashboard
# specifically kept failing with an opaque "Failed to fetch": a genuine
# crash in that endpoint's code (a data record missing an expected
# relationship - see the fix in dashboard.py) surfaced as a 500 in the
# Network tab, but a network-level failure to the actual page.
#
# This handler catches any unhandled exception, logs the full traceback
# (visible in Render's logs - previously invisible anywhere), and returns
# an ordinary JSONResponse instead. Because it's an explicit response
# rather than Starlette's own internal exception path, CORSMiddleware DOES
# get to add its headers on the way out, so a genuine server bug now shows
# up to the person using the app as an actual, readable error - not a
# network failure that looks identical to a real connectivity problem.
import logging
import traceback
from fastapi.responses import JSONResponse

logger = logging.getLogger("uvicorn.error")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}:\n{traceback.format_exc()}")

    # IMPORTANT: responses from an exception handler like this one do NOT
    # pass back through CORSMiddleware, regardless of the order it was
    # added in - verified directly (a deliberately crashing test endpoint
    # came back with a real JSON body but zero CORS headers). The reliable
    # fix, rather than fighting the middleware ordering further, is to add
    # the necessary CORS headers directly on this response ourselves.
    origin = request.headers.get("origin")
    headers = {}
    if origin and origin in origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"

    return JSONResponse(
        status_code=500,
        content={"detail": f"Something went wrong on the server: {type(exc).__name__}"},
        headers=headers,
    )

# AuthMiddleware is added BEFORE CORSMiddleware so that CORS ends up as the
# outermost layer (Starlette wraps in reverse order of add_middleware calls).
# This matters: without it, a 401 response from AuthMiddleware could be sent
# without CORS headers, which browsers then report as an opaque "failed to
# fetch" rather than a readable 401 - the same class of bug seen earlier with
# the Supabase bucket error before that was fixed to fail gracefully.
app.add_middleware(auth.AuthMiddleware)

# Set ALLOWED_ORIGINS to your Vercel URL(s) in production, e.g.
# ALLOWED_ORIGINS=https://khata.vercel.app
#
# CRITICAL BUG FIXED HERE: this used to default to "*" (wildcard) when the
# env var wasn't set. That combined with allow_credentials=True below is an
# actual CORS spec violation - you cannot serve Access-Control-Allow-Origin:
# * together with Access-Control-Allow-Credentials: true. Real browsers
# correctly detect this and SILENTLY BLOCK every authenticated request
# (anything sending the Authorization header, i.e. almost everything past
# login) - but curl and other non-browser tools don't enforce CORS at all,
# so this was completely invisible to every test performed against this
# app up to this point.
#
# FOLLOW-UP FIX: the first fix only helped if ALLOWED_ORIGINS was
# completely unset. If it happens to be set on Render to something that
# doesn't exactly match the real frontend URL (a typo, a stray space, an
# old domain from before a rename, http instead of https, etc.), the env
# var still takes priority and silently reintroduces the exact same
# failure - login works, everything else fails with an opaque "Failed to
# fetch". Rather than depend on that one env var being letter-perfect,
# the known-correct production and local-dev URLs are now ALWAYS included
# no matter what ALLOWED_ORIGINS contains, in addition to whatever's
# configured there. Getting logged in but unable to load anything else
# should not be possible to trigger via a CORS environment variable typo.
KNOWN_GOOD_ORIGINS = ["http://localhost:4173", "https://vrindavan-lekha.vercel.app"]
allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
configured_origins = [o.strip() for o in allowed_origins.split(",") if o.strip()]
origins = list(dict.fromkeys(configured_origins + KNOWN_GOOD_ORIGINS))  # dedup, preserve order

if "*" in origins:
    raise RuntimeError(
        "ALLOWED_ORIGINS cannot be '*' when allow_credentials=True (CORS spec "
        "violation - browsers will silently block every authenticated request). "
        "Set ALLOWED_ORIGINS to your actual frontend URL(s), comma-separated."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Content-Disposition isn't in the browser's default CORS-safelisted
    # headers, so without this, every file download's real filename is
    # invisible to frontend JS across origins (which is the real production
    # setup: Vercel frontend, Render backend). Every export was silently
    # falling back to a generic filename because of this.
    expose_headers=["Content-Disposition"],
)

# Serves saved invoice images at /files/invoices/<name>
app.mount("/files", StaticFiles(directory=str(UPLOADS_DIR)), name="files")

app.include_router(parties.router)
app.include_router(invoices.router)
app.include_router(payments.router)
app.include_router(payments.standalone_router)
app.include_router(dashboard.router)
app.include_router(ocr.router)
app.include_router(export.router)
app.include_router(backup.router)
app.include_router(settings.router)
app.include_router(uploads.router)
app.include_router(bills.router)
app.include_router(auth_router.router)
app.include_router(suppliers.router)
app.include_router(purchases.router)
app.include_router(purchase_payments.router)
app.include_router(purchase_payments.standalone_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
