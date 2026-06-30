# WHAT DOES THIS FILE DO: database engine, session, and core DB utilities used by every other db module

# ================== IMPORTS ==================
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from dotenv import load_dotenv
# ================== IMPORTS ==================


load_dotenv(override=True)


# =========== VARIABLES : database engine setup ===========
_db_default = "workflow.db"
_cache_dir_env = os.getenv("CACHE_DIR")
if _cache_dir_env:
    from pathlib import Path
    _db_default = str((Path(_cache_dir_env) / "workflow.db").resolve())

WORKFLOW_DATABASE_URL = os.getenv("WORKFLOW_DATABASE_URL", f"sqlite:///{_db_default}")

_connect_args = {"check_same_thread": False} if WORKFLOW_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(WORKFLOW_DATABASE_URL, future=True, pool_pre_ping=True, connect_args=_connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
# =========== VARIABLES : database engine setup ===========


# =========== CLASS ===========
class Base(DeclarativeBase):
    pass
# =========== CLASS ===========


# =========== FUNCTION ===========
# ROLE: Normalize query text for comparison and fuzzy matching
def normalize_query(text_input: str) -> str:
    ''' Lowercase, strip special chars, collapse spaces, and truncate to 760 chars '''

    # FLOW-1: Return empty string if input is missing
    if not text_input:
        return ""

    # FLOW-2: Lowercase and normalize whitespace
    lowered = " ".join(text_input.lower().strip().split())

    # FLOW-3: Keep only alphanumeric and spaces
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)

    # FLOW-4: Collapse repeated spaces and cap at 760 chars
    return " ".join(cleaned.split())[:760]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Context manager that wraps DB operations in a safe transaction
@contextmanager
def session_scope() -> Session:
    ''' Provide transactional scope with auto-commit on success, rollback on error '''

    # FLOW-1: Open a new session
    session = SessionLocal()

    # FLOW-2: Yield session, commit on clean exit or rollback on exception
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Add missing columns to tables that were created before Phase 1
def _run_migrations() -> None:
    ''' Try each ALTER TABLE statement, silently skip if column already exists '''

    # FLOW-1: List of SQL migration statements to attempt
    migrations = [
        "ALTER TABLE upload_documents ADD COLUMN s3_key VARCHAR(500)",
        "ALTER TABLE admin_users ADD COLUMN department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL",
        "ALTER TABLE visitor_sessions ADD COLUMN cache_count INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE chat_logs ADD COLUMN blocked_word_matched VARCHAR(100)",
        "ALTER TABLE chat_logs ADD COLUMN correction_id INTEGER",
        "ALTER TABLE flagged_responses ADD COLUMN admin_note TEXT",
    ]

    # FLOW-2: Run each one and ignore errors (column probably already exists)
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Create all tables, run migrations, and seed the super admin user
def init_workflow_db() -> None:
    ''' Set up the database schema on first run — safe to call on every startup '''

    # FLOW-1: Enable pgvector extension if database is PostgreSQL
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()

    # FLOW-2: Create all registered ORM tables
    Base.metadata.create_all(bind=engine)

    # FLOW-3: Run column-level migrations for existing tables
    _run_migrations()

    # FLOW-4: Seed super_admin from ADMIN_EMAIL env variable
    from .models import AdminUser  # local import to avoid circular at module level
    with session_scope() as session:
        admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
        if not admin_email:
            return

        existing = session.execute(
            select(AdminUser).where(AdminUser.email == admin_email)
        ).scalars().first()

        # FLOW-5: Create super_admin if not present, or upgrade old role
        if not existing:
            session.add(AdminUser(email=admin_email, role="super_admin", full_name="Admin", is_active=True))
        elif existing.role == "admin":
            existing.role = "super_admin"
# =========== FUNCTION ===========
