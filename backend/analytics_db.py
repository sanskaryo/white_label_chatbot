# WHAT DOES THIS FILE DO: ChatLog model and analytics query functions for the admin dashboard

# ================== IMPORTS ==================
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from workflow_db import Base, session_scope, UploadDocument, UploadChunk, FlaggedResponse
# ================== IMPORTS ==================


# =========== VARIABLES : logging ===========
logger = logging.getLogger("analytics_db")
# =========== VARIABLES : logging ===========


# =========== ORM MODEL ===========

class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    route: Mapped[str] = mapped_column(String(24), nullable=False, default="rag", index=True)
    sources_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    department_slug: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    # accountability columns — populated by the chat pipeline for CSV exports
    blocked_word_matched: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    correction_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

# =========== ORM MODEL ===========


# =========== FUNCTION ===========
# ROLE: Write one chat interaction to the log table
def log_chat(
    question: str,
    answer: str = "",
    route: str = "rag",
    sources_count: int = 0,
    response_time_ms: float = 0.0,
    session_id: Optional[str] = None,
    department_slug: Optional[str] = None,
    blocked_word_matched: Optional[str] = None,
    correction_id: Optional[int] = None,
) -> None:
    ''' Insert a chat log row, silently skip if anything goes wrong '''

    # FLOW-1: Wrap in try/except so a logging failure never blocks the chat response
    try:
        with session_scope() as session:
            row = ChatLog(
                question=question[:1000],
                answer=(answer or "")[:2000],
                route=route,
                sources_count=sources_count,
                response_time_ms=response_time_ms,
                session_id=session_id,
                department_slug=department_slug,
                blocked_word_matched=blocked_word_matched,
                correction_id=correction_id,
            )
            session.add(row)

    except Exception as exc:
        logger.warning(f"chat log write failed: {exc}")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Pull high-level KPI counts for the main dashboard cards
def get_dashboard_metrics() -> Dict[str, Any]:
    ''' Return total chats, today chats, avg latency, blocked rate, doc counts '''

    # FLOW-1: Set time boundaries for today and this week
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)

    # FLOW-2: Query chat log aggregates in a single session
    with session_scope() as session:
        total_chats = session.scalar(select(func.count(ChatLog.id))) or 0
        chats_today = session.scalar(
            select(func.count(ChatLog.id)).where(ChatLog.created_at >= today_start)
        ) or 0
        chats_this_week = session.scalar(
            select(func.count(ChatLog.id)).where(ChatLog.created_at >= week_start)
        ) or 0
        avg_response_ms = session.scalar(select(func.avg(ChatLog.response_time_ms))) or 0.0
        blocked_count = session.scalar(
            select(func.count(ChatLog.id)).where(ChatLog.route == "blocked")
        ) or 0
        correction_count = session.scalar(
            select(func.count(ChatLog.id)).where(ChatLog.route == "correction")
        ) or 0

        # FLOW-3: Pull document and chunk counts from workflow tables
        docs_count = session.scalar(
            select(func.count(UploadDocument.id)).where(UploadDocument.is_active.is_(True))
        ) or 0
        chunks_count = session.scalar(
            select(func.count(UploadChunk.id)).where(UploadChunk.is_active.is_(True))
        ) or 0

    # FLOW-4: Compute rates safely so no division by zero
    blocked_rate = round(blocked_count / total_chats * 100, 1) if total_chats > 0 else 0.0
    correction_rate = round(correction_count / total_chats * 100, 1) if total_chats > 0 else 0.0

    return {
        "total_chats": total_chats,
        "chats_today": chats_today,
        "chats_this_week": chats_this_week,
        "avg_response_ms": round(avg_response_ms, 1),
        "blocked_count": blocked_count,
        "blocked_rate": blocked_rate,
        "correction_count": correction_count,
        "correction_rate": correction_rate,
        "documents_count": docs_count,
        "chunks_count": chunks_count,
    }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return daily chat counts for the last N days for a line chart
def get_chat_volume_by_day(days: int = 30) -> List[Dict[str, Any]]:
    ''' Return list of {date, count} for each day in range, zeroing out empty days '''

    # FLOW-1: Calculate the start of the date range
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # FLOW-2: Query daily counts grouped by truncated date — PostgreSQL specific
    with session_scope() as session:
        rows = session.execute(
            select(
                func.date_trunc("day", ChatLog.created_at).label("day"),
                func.count(ChatLog.id).label("count"),
            )
            .where(ChatLog.created_at >= start_date)
            .group_by(func.date_trunc("day", ChatLog.created_at))
            .order_by(func.date_trunc("day", ChatLog.created_at))
        ).all()

    # FLOW-3: Build lookup dict so we can fill in missing days with zero
    counts_by_day = {row.day.date().isoformat(): row.count for row in rows}

    # FLOW-4: Generate full date range and merge with actual counts
    result = []
    for i in range(days):
        day = (start_date + timedelta(days=i)).date().isoformat()
        result.append({"date": day, "count": counts_by_day.get(day, 0)})

    return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return the most frequently asked questions
def get_top_questions(limit: int = 10) -> List[Dict[str, Any]]:
    ''' Return top N questions by frequency, skipping blocked ones '''

    # FLOW-1: Group by question text, exclude blocked route, sort by count
    with session_scope() as session:
        rows = session.execute(
            select(ChatLog.question, func.count(ChatLog.id).label("count"))
            .where(ChatLog.route != "blocked")
            .group_by(ChatLog.question)
            .order_by(func.count(ChatLog.id).desc())
            .limit(limit)
        ).all()

    # FLOW-2: Return as simple list of dicts
    return [{"question": row.question, "count": row.count} for row in rows]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return response quality and moderation metrics
def get_quality_metrics() -> Dict[str, Any]:
    ''' Return flagged counts and route breakdown for the review panel '''

    # FLOW-1: Query flagged response table counts
    with session_scope() as session:
        flagged_total = session.scalar(select(func.count(FlaggedResponse.id))) or 0
        flagged_pending = session.scalar(
            select(func.count(FlaggedResponse.id)).where(FlaggedResponse.status == "pending")
        ) or 0

        # FLOW-2: Break down chat log routes to see how traffic is being handled
        rag_count = session.scalar(select(func.count(ChatLog.id)).where(ChatLog.route == "rag")) or 0
        correction_count = session.scalar(select(func.count(ChatLog.id)).where(ChatLog.route == "correction")) or 0
        blocked_count = session.scalar(select(func.count(ChatLog.id)).where(ChatLog.route == "blocked")) or 0

    return {
        "flagged_total": flagged_total,
        "flagged_pending": flagged_pending,
        "route_breakdown": {
            "rag": rag_count,
            "correction": correction_count,
            "blocked": blocked_count,
        },
    }
# =========== FUNCTION ===========
