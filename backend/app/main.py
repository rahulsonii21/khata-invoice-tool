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

# AuthMiddleware is added BEFORE CORSMiddleware so that CORS ends up as the
# outermost layer (Starlette wraps in reverse order of add_middleware calls).
# This matters: without it, a 401 response from AuthMiddleware could be sent
# without CORS headers, which browsers then report as an opaque "failed to
# fetch" rather than a readable 401 - the same class of bug seen earlier with
# the Supabase bucket error before that was fixed to fail gracefully.
app.add_middleware(auth.AuthMiddleware)

# Set ALLOWED_ORIGINS to your Vercel URL(s) in production, e.g.
# ALLOWED_ORIGINS=https://khata.vercel.app
# Defaults to "*" so local development keeps working without any setup.
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
origins = [o.strip() for o in allowed_origins.split(",")] if allowed_origins != "*" else ["*"]

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
