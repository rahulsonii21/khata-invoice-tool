from contextlib import asynccontextmanager
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import parties, invoices, payments, dashboard, ocr, export, backup, settings
from . import scheduler

# Creates tables if they don't exist (fine for SQLite/dev;
# use Alembic migrations later once schema stabilizes in production).
Base.metadata.create_all(bind=engine)

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start_scheduler()
    yield
    scheduler.stop_scheduler()


app = FastAPI(title="Invoice Management Tool API", lifespan=lifespan)

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


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
