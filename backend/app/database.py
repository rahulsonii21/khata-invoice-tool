import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# For local dev, defaults to SQLite. In production (Supabase/Postgres),
# set DATABASE_URL env var, e.g.:
# postgresql://user:password@host:5432/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./invoice_tool.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns_exist(table: str, column_defs: dict):
    """Lightweight migration helper: adds columns to an existing table if they're
    missing. create_all() only creates whole tables, not new columns on tables
    that already exist - this covers that gap for simple additive schema changes
    without needing a full migration framework (Alembic) for a project this size.

    column_defs: {"column_name": "SQL_TYPE", ...}
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return  # table doesn't exist yet - create_all() will handle it fresh

    existing = {col["name"] for col in inspector.get_columns(table)}
    with engine.connect() as conn:
        for col_name, col_type in column_defs.items():
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                conn.commit()
