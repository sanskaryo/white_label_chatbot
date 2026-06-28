# WHAT DOES THIS FILE DO: SQLAlchemy ORM layer for the white-label chatbot — defines tables, seeds initial data, and provides DB helper functions

# ================== IMPORTS ==================
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text,
    create_engine, func, inspect, select, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
# ================== IMPORTS ==================


class Base(DeclarativeBase):
    pass


from dotenv import load_dotenv
load_dotenv(override=True)


# =========== VARIABLES : database config ===========
_db_default = "workflow.db"
_cache_dir_env = os.getenv("CACHE_DIR")
if _cache_dir_env:
    from pathlib import Path
    _db_default = str((Path(_cache_dir_env) / "workflow.db").resolve())

WORKFLOW_DATABASE_URL = os.getenv(
    "WORKFLOW_DATABASE_URL", f"sqlite:///{_db_default}")

_connect_args = {"check_same_thread": False} if WORKFLOW_DATABASE_URL.startswith(
    "sqlite") else {}
engine = create_engine(
    WORKFLOW_DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
# =========== VARIABLES : database config ===========


# =========== VARIABLES : in-memory caches ===========
_blocked_words_cache: Optional[List[str]] = None
_blocked_words_lock = threading.Lock()

_corrections_cache: Optional[List[Tuple[str, Dict[str, Any]]]] = None
_corrections_cache_lock = threading.Lock()
# =========== VARIABLES : in-memory caches ===========


# =========== ORM MODELS ===========

class PredefinedQuestion(Base):
    __tablename__ = "predefined_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class FlaggedResponse(Base):
    __tablename__ = "flagged_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_norm: Mapped[str] = mapped_column(String(768), nullable=False, index=True)
    chatbot_answer: Mapped[str] = mapped_column(Text, nullable=False)
    tester_verdict: Mapped[str] = mapped_column(String(24), nullable=False, default="wrong")
    tester_answer_raw: Mapped[str] = mapped_column(Text, nullable=False)
    tester_answer_improved: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tester_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tester_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    chat_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class Correction(Base):
    __tablename__ = "corrections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_norm: Mapped[str] = mapped_column(String(768), nullable=False, index=True)
    corrected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    source_flagged_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("flagged_responses.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), index=True)
    source_flagged: Mapped[Optional[FlaggedResponse]] = relationship("FlaggedResponse")


class BlockedWord(Base):
    __tablename__ = "blocked_words"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(300), nullable=False, unique=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    added_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[str] = mapped_column(String(120), nullable=False, default="admin")
    role: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)


class UploadDocument(Base):
    __tablename__ = "upload_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(260), nullable=False)
    display_title: Mapped[Optional[str]] = mapped_column(String(260), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="file")
    uploader_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="processing", index=True)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pgvector_document_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    chunks: Mapped[List["UploadChunk"]] = relationship("UploadChunk", back_populates="upload", cascade="all, delete-orphan")


class UploadChunk(Base):
    __tablename__ = "upload_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("upload_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(260), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(600), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="uploaded")
    section_type: Mapped[str] = mapped_column(String(64), nullable=False, default="uploaded_chunk")
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    embedding_json: Mapped[List[float]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    upload: Mapped[UploadDocument] = relationship("UploadDocument", back_populates="chunks")


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    role: Mapped[str] = mapped_column(String(24), nullable=False, default="admin", index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)


# =========== COMPOSITE INDEXES ===========
Index("ix_flagged_status_created", FlaggedResponse.status, FlaggedResponse.created_at)
Index("ix_corrections_active_updated", Correction.is_active, Correction.updated_at)
Index("ix_upload_chunks_active_upload", UploadChunk.is_active, UploadChunk.upload_id)


# =========== HELPER FUNCTIONS ===========

def normalize_query(text: str) -> str:
    if not text:
        return ""
    lowered = " ".join(text.lower().strip().split())
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)
    return " ".join(cleaned.split())[:760]


@contextmanager
def session_scope() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def log_audit_action(
    session: Session,
    action: str,
    details: str,
    admin_id: Optional[str] = None,
    role: Optional[str] = None,
):
    log = AuditLog(
        admin_id=(admin_id or "admin").strip(),
        role=(role or "").strip() or None,
        action=action.strip(),
        details=details.strip()
    )
    session.add(log)


def init_workflow_db() -> None:
    """Create all tables and seed initial data. Safe to call multiple times."""
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()

    Base.metadata.create_all(bind=engine)

    with session_scope() as session:
        # Seed a default admin if ADMIN_EMAIL is set
        admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
        if admin_email:
            existing = session.execute(
                select(AdminUser).where(AdminUser.email == admin_email)
            ).scalars().first()
            if not existing:
                session.add(AdminUser(
                    email=admin_email,
                    role="admin",
                    full_name="Admin",
                    is_active=True,
                ))


# =========== BLOCKED WORDS FUNCTIONS ===========

def _invalidate_blocked_words_cache() -> None:
    global _blocked_words_cache
    with _blocked_words_lock:
        _blocked_words_cache = None


def get_blocked_words_list() -> List[str]:
    global _blocked_words_cache
    with _blocked_words_lock:
        if _blocked_words_cache is not None:
            return _blocked_words_cache
        with session_scope() as session:
            rows = session.execute(
                select(BlockedWord.word).where(BlockedWord.is_active.is_(True))
            ).scalars().all()
        _blocked_words_cache = [w.lower() for w in rows]
        return _blocked_words_cache


def is_question_blocked(question: str) -> Optional[str]:
    q_lower = question.lower()
    for word in get_blocked_words_list():
        if word in q_lower:
            return word
    return None


def list_blocked_words() -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(
            select(BlockedWord).where(BlockedWord.is_active.is_(True)).order_by(BlockedWord.created_at.desc())
        ).scalars().all()
        return [{"id": r.id, "word": r.word, "reason": r.reason, "added_by": r.added_by} for r in rows]


def add_blocked_word(word: str, reason: str = "", added_by: str = "admin") -> Dict[str, Any]:
    with session_scope() as session:
        existing = session.execute(
            select(BlockedWord).where(BlockedWord.word == word.strip().lower())
        ).scalars().first()
        if existing:
            existing.is_active = True
            existing.reason = reason
            row = existing
        else:
            row = BlockedWord(word=word.strip().lower(), reason=reason, added_by=added_by, is_active=True)
            session.add(row)
        session.flush()
        result = {"id": row.id, "word": row.word, "reason": row.reason}
    _invalidate_blocked_words_cache()
    return result


def delete_blocked_word(word_id: int) -> bool:
    with session_scope() as session:
        row = session.get(BlockedWord, word_id)
        if row:
            row.is_active = False
            _invalidate_blocked_words_cache()
            return True
    return False


# =========== CORRECTIONS FUNCTIONS ===========

def _invalidate_corrections_cache() -> None:
    global _corrections_cache
    with _corrections_cache_lock:
        _corrections_cache = None


def _load_corrections_cache() -> List[Tuple[str, Dict[str, Any]]]:
    global _corrections_cache
    with _corrections_cache_lock:
        if _corrections_cache is not None:
            return _corrections_cache
        with session_scope() as session:
            rows = session.execute(
                select(Correction).where(Correction.is_active.is_(True)).order_by(Correction.updated_at.desc())
            ).scalars().all()
        _corrections_cache = [
            (row.question_norm, {"id": row.id, "question": row.question, "question_norm": row.question_norm, "corrected_answer": row.corrected_answer})
            for row in rows
        ]
        return _corrections_cache


def find_best_correction(question: str, threshold: float = 0.90) -> Optional[Dict[str, Any]]:
    q_norm = normalize_query(question)
    if not q_norm:
        return None
    cache = _load_corrections_cache()
    best_match = None
    best_ratio = 0.0
    for stored_norm, row_dict in cache:
        ratio = SequenceMatcher(None, q_norm, stored_norm).ratio()
        if ratio >= threshold and ratio > best_ratio:
            best_ratio = ratio
            best_match = row_dict
    return best_match


def list_corrections(limit: int = 100) -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(
            select(Correction).where(Correction.is_active.is_(True)).order_by(Correction.updated_at.desc()).limit(limit)
        ).scalars().all()
        return [{"id": r.id, "question": r.question, "corrected_answer": r.corrected_answer, "admin_note": r.admin_note, "approved_by": r.approved_by} for r in rows]


def create_direct_correction(question: str, corrected_answer: str, admin_note: str = "", approved_by: str = "admin") -> Dict[str, Any]:
    q_norm = normalize_query(question)
    with session_scope() as session:
        row = Correction(
            question=question, question_norm=q_norm,
            corrected_answer=corrected_answer, admin_note=admin_note,
            approved_by=approved_by, is_active=True,
        )
        session.add(row)
        log_audit_action(session, "correction_created", f"Q: {question[:100]}", admin_id=approved_by)
        session.flush()
        result = {"id": row.id, "question": row.question, "corrected_answer": row.corrected_answer}
    _invalidate_corrections_cache()
    return result


# =========== FLAGGED RESPONSES FUNCTIONS ===========

def create_flagged_response(question: str, chatbot_answer: str, tester_answer_raw: str, tester_verdict: str = "wrong", tester_note: str = "", tester_id: str = "", chat_id: str = "") -> Dict[str, Any]:
    q_norm = normalize_query(question)
    with session_scope() as session:
        row = FlaggedResponse(
            question=question, question_norm=q_norm,
            chatbot_answer=chatbot_answer, tester_verdict=tester_verdict,
            tester_answer_raw=tester_answer_raw, tester_note=tester_note,
            tester_id=tester_id, chat_id=chat_id, status="pending",
        )
        session.add(row)
        session.flush()
        return {"id": row.id, "status": "pending"}


def list_flagged_responses(status: str = "pending", limit: int = 50) -> List[Dict[str, Any]]:
    with session_scope() as session:
        query = select(FlaggedResponse).order_by(FlaggedResponse.created_at.desc())
        if status:
            query = query.where(FlaggedResponse.status == status)
        rows = session.execute(query.limit(limit)).scalars().all()
        return [
            {"id": r.id, "question": r.question, "chatbot_answer": r.chatbot_answer,
             "tester_answer_raw": r.tester_answer_raw, "tester_note": r.tester_note,
             "tester_id": r.tester_id, "status": r.status}
            for r in rows
        ]


def approve_flagged_response(flagged_id: int, reviewed_by: str = "admin", improved_answer: str = "") -> Dict[str, Any]:
    with session_scope() as session:
        row = session.get(FlaggedResponse, flagged_id)
        if not row:
            return {"error": "Not found"}
        row.status = "approved"
        row.reviewed_by = reviewed_by
        row.reviewed_at = datetime.now(timezone.utc)
        if improved_answer:
            row.tester_answer_improved = improved_answer
        final_answer = improved_answer or row.tester_answer_raw
        correction = Correction(
            question=row.question, question_norm=row.question_norm,
            corrected_answer=final_answer, approved_by=reviewed_by,
            source_flagged_id=flagged_id, is_active=True,
        )
        session.add(correction)
        log_audit_action(session, "flagged_approved", f"Flagged #{flagged_id}: {row.question[:80]}", admin_id=reviewed_by)
        session.flush()
        result = {"id": row.id, "status": "approved", "correction_id": correction.id}
    _invalidate_corrections_cache()
    return result


def reject_flagged_response(flagged_id: int, reviewed_by: str = "admin") -> Dict[str, Any]:
    with session_scope() as session:
        row = session.get(FlaggedResponse, flagged_id)
        if not row:
            return {"error": "Not found"}
        row.status = "rejected"
        row.reviewed_by = reviewed_by
        row.reviewed_at = datetime.now(timezone.utc)
        log_audit_action(session, "flagged_rejected", f"Flagged #{flagged_id}: {row.question[:80]}", admin_id=reviewed_by)
        return {"id": row.id, "status": "rejected"}


# =========== UPLOAD FUNCTIONS ===========

def create_upload_document(filename: str, content_type: str = "", file_size_bytes: int = 0, uploader_id: str = "admin") -> Dict[str, Any]:
    with session_scope() as session:
        row = UploadDocument(
            filename=filename, content_type=content_type,
            file_size_bytes=file_size_bytes, uploader_id=uploader_id,
            status="processing", is_active=True,
        )
        session.add(row)
        session.flush()
        return {"id": row.id, "filename": row.filename, "status": row.status}


def save_upload_chunks(upload_id: int, chunks: List[Dict[str, Any]]) -> int:
    with session_scope() as session:
        doc = session.get(UploadDocument, upload_id)
        if not doc:
            return 0
        count = 0
        for idx, chunk in enumerate(chunks):
            row = UploadChunk(
                upload_id=upload_id, chunk_index=idx,
                title=chunk.get("title", ""), text=chunk["text"],
                source_url=chunk.get("url", ""), category=chunk.get("category", "uploaded"),
                section_type=chunk.get("section_type", "uploaded_chunk"),
                embedding_json=chunk.get("embedding", []),
                is_active=True,
            )
            session.add(row)
            count += 1
        doc.total_chunks = count
        doc.status = "processed"
        doc.processed_at = datetime.now(timezone.utc)
        return count


def mark_upload_failed(upload_id: int, error_message: str) -> None:
    with session_scope() as session:
        doc = session.get(UploadDocument, upload_id)
        if doc:
            doc.status = "failed"
            doc.error_message = error_message


def list_upload_documents(limit: int = 100) -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(
            select(UploadDocument).where(UploadDocument.is_active.is_(True)).order_by(UploadDocument.created_at.desc()).limit(limit)
        ).scalars().all()
        return [
            {"id": r.id, "filename": r.filename, "display_title": r.display_title,
             "status": r.status, "total_chunks": r.total_chunks,
             "file_size_bytes": r.file_size_bytes, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]


def delete_upload_document(upload_id: int) -> bool:
    with session_scope() as session:
        doc = session.get(UploadDocument, upload_id)
        if doc:
            doc.is_active = False
            return True
    return False


def get_upload_document(upload_id: int) -> Optional[Dict[str, Any]]:
    with session_scope() as session:
        doc = session.get(UploadDocument, upload_id)
        if not doc:
            return None
        return {"id": doc.id, "filename": doc.filename, "status": doc.status, "total_chunks": doc.total_chunks, "pgvector_document_id": doc.pgvector_document_id}


def get_active_upload_chunks(limit: int = 50000) -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(
            select(UploadChunk).where(UploadChunk.is_active.is_(True)).limit(limit)
        ).scalars().all()
        return [
            {"text": r.text, "url": r.source_url, "title": r.title, "category": r.category,
             "section_type": r.section_type, "embedding": r.embedding_json}
            for r in rows
        ]


# =========== SYSTEM SETTINGS FUNCTIONS ===========

def get_system_setting(key: str, default: str = "") -> str:
    with session_scope() as session:
        row = session.get(SystemSetting, key)
        return row.value if row else default


def set_system_setting(key: str, value: str) -> None:
    with session_scope() as session:
        row = session.get(SystemSetting, key)
        if row:
            row.value = value
        else:
            session.add(SystemSetting(key=key, value=value))


# =========== PREDEFINED QUESTIONS ===========

def get_predefined_questions(limit: int = 100) -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(
            select(PredefinedQuestion).where(PredefinedQuestion.is_active.is_(True)).order_by(PredefinedQuestion.id).limit(limit)
        ).scalars().all()
        return [{"id": r.id, "question": r.question, "category": r.category} for r in rows]


# =========== AUDIT LOGS ===========

def list_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        ).scalars().all()
        return [{"id": r.id, "admin_id": r.admin_id, "action": r.action, "details": r.details, "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]


# =========== WORKFLOW SUMMARY ===========

def get_workflow_summary() -> Dict[str, Any]:
    with session_scope() as session:
        flagged_pending = session.scalar(select(func.count(FlaggedResponse.id)).where(FlaggedResponse.status == "pending")) or 0
        flagged_total = session.scalar(select(func.count(FlaggedResponse.id))) or 0
        corrections_count = session.scalar(select(func.count(Correction.id)).where(Correction.is_active.is_(True))) or 0
        uploads_count = session.scalar(select(func.count(UploadDocument.id)).where(UploadDocument.is_active.is_(True))) or 0
        return {
            "flagged": {"pending": flagged_pending, "total": flagged_total},
            "corrections": {"active": corrections_count},
            "uploads": {"total": uploads_count},
        }
