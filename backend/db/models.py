# WHAT DOES THIS FILE DO: all SQLAlchemy ORM models for the chatbot — one place for all table definitions

# ================== IMPORTS ==================
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .connection import Base

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
# ================== IMPORTS ==================


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
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    source_flagged_id: Mapped[Optional[int]] = mapped_column(ForeignKey("flagged_responses.id", ondelete="SET NULL"), nullable=True)
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
    s3_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
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


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    users: Mapped[List["AdminUser"]] = relationship("AdminUser", back_populates="department")


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    role: Mapped[str] = mapped_column(String(24), nullable=False, default="dept_admin", index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(180), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="users")


class TestCase(Base):
    __tablename__ = "test_cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    department_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    expected_route: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    expected_answer_contains: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class WidgetConfig(Base):
    __tablename__ = "widget_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    department_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)  # NULL = global default
    bot_name: Mapped[str] = mapped_column(String(120), nullable=False, default="AskGLA")
    welcome_message: Mapped[str] = mapped_column(Text, nullable=False, default="Hi! I'm AskGLA. How can I help you today?")
    starter_questions: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # list[str], up to 4 shown
    theme_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#1a3a2a")
    accent_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#c9a227")
    position: Mapped[str] = mapped_column(String(20), nullable=False, default="bottom-right")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# =========== ORM MODELS ===========


# =========== COMPOSITE INDEXES ===========
Index("ix_flagged_status_created", FlaggedResponse.status, FlaggedResponse.created_at)
Index("ix_corrections_active_updated", Correction.is_active, Correction.updated_at)
Index("ix_upload_chunks_active_upload", UploadChunk.is_active, UploadChunk.upload_id)
# =========== COMPOSITE INDEXES ===========
