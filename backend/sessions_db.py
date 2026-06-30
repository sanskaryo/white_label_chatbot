# WHAT DOES THIS FILE DO: VisitorSession ORM model and all session-level analytics — one persistent row per unique visitor, updated on every chat message

# ================== IMPORTS ==================
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column

from workflow_db import Base, session_scope
from analytics_db import ChatLog
# ================== IMPORTS ==================


# =========== VARIABLES ===========
logger = logging.getLogger("sessions_db")

_ACTIVE_CUTOFF_MINUTES = 10
_IDLE_CUTOFF_MINUTES = 30
# =========== VARIABLES ===========


# =========== ORM MODEL ===========

class VisitorSession(Base):
    __tablename__ = "visitor_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    department_slug: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)

    # FLOW fields: lifecycle timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # FLOW fields: running message counters — updated in O(1) on each upsert
    total_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rag_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # FLOW fields: running weighted average latency
    avg_response_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # FLOW fields: message content snapshots
    first_question: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_question: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # FLOW fields: optional client hints from widget headers
    device_hint: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    referrer_page: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

# =========== ORM MODEL ===========


# =========== COMPOSITE INDEXES ===========
Index("ix_vs_dept_started", VisitorSession.department_slug, VisitorSession.started_at)
Index("ix_vs_last_seen_dept", VisitorSession.last_seen_at, VisitorSession.department_slug)
# =========== COMPOSITE INDEXES ===========


# =========== FUNCTION ===========
# ROLE: Compute status label from last_seen_at — not stored, always derived
def _compute_status(last_seen_at: datetime) -> str:
    ''' Return active / idle / ended based on how long ago the visitor was last seen '''

    # FLOW-1: Compute minutes since last activity
    delta_minutes = (datetime.now(timezone.utc) - last_seen_at).total_seconds() / 60

    # FLOW-2: Map to status label
    if delta_minutes < _ACTIVE_CUTOFF_MINUTES:
        return "active"
    if delta_minutes < _IDLE_CUTOFF_MINUTES:
        return "idle"
    return "ended"
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Serialize a VisitorSession ORM row to a dict for API responses
def _row_to_dict(row: VisitorSession) -> Dict[str, Any]:
    ''' Convert ORM row to dict with computed status and duration_minutes '''

    # FLOW-1: Compute duration as float minutes between first and last seen
    duration_seconds = (row.last_seen_at - row.started_at).total_seconds()
    duration_minutes = round(duration_seconds / 60, 1)

    # FLOW-2: Build dict with all fields
    return {
        "session_id": row.session_id,
        "department_slug": row.department_slug,
        "status": _compute_status(row.last_seen_at),
        "started_at": row.started_at.isoformat(),
        "last_seen_at": row.last_seen_at.isoformat(),
        "duration_minutes": duration_minutes,
        "total_messages": row.total_messages,
        "blocked_count": row.blocked_count,
        "correction_count": row.correction_count,
        "rag_count": row.rag_count,
        "cache_count": row.cache_count,
        "avg_response_ms": round(row.avg_response_ms, 1),
        "first_question": row.first_question,
        "last_question": row.last_question,
        "device_hint": row.device_hint,
        "referrer_page": row.referrer_page,
    }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Create or update the session record whenever a new chat message comes in
def upsert_visitor_session(
    session_id: Optional[str],
    question: str,
    route: str = "rag",
    response_time_ms: float = 0.0,
    department_slug: Optional[str] = None,
    device_hint: Optional[str] = None,
    referrer_page: Optional[str] = None,
) -> None:
    ''' Upsert visitor session stats — silently skip if session_id is missing or on any error '''

    # FLOW-1: Skip anonymous messages with no session ID
    if not session_id:
        return

    # FLOW-2: Wrap in try/except so a session write failure never blocks chat
    try:
        with session_scope() as db:
            now = datetime.now(timezone.utc)
            existing = db.execute(
                select(VisitorSession).where(VisitorSession.session_id == session_id)
            ).scalars().first()

            if existing:
                # FLOW-3: Update existing session — running counters and weighted avg
                n = existing.total_messages + 1
                existing.total_messages = n
                existing.last_seen_at = now
                existing.last_question = question[:500]

                # FLOW-4: O(1) running weighted average for latency
                if response_time_ms and response_time_ms > 0:
                    existing.avg_response_ms = (existing.avg_response_ms * (n - 1) + response_time_ms) / n

                # FLOW-5: Increment the correct route counter
                if route == "blocked":
                    existing.blocked_count += 1
                elif route == "correction":
                    existing.correction_count += 1
                elif route == "cache":
                    existing.cache_count += 1
                else:
                    existing.rag_count += 1

            else:
                # FLOW-6: First message from this session — create the row
                row = VisitorSession(
                    session_id=session_id,
                    department_slug=department_slug,
                    started_at=now,
                    last_seen_at=now,
                    total_messages=1,
                    blocked_count=1 if route == "blocked" else 0,
                    correction_count=1 if route == "correction" else 0,
                    rag_count=1 if route == "rag" else 0,
                    cache_count=1 if route == "cache" else 0,
                    avg_response_ms=response_time_ms if response_time_ms else 0.0,
                    first_question=question[:500],
                    last_question=question[:500],
                    device_hint=(device_hint or "")[:20] or None,
                    referrer_page=(referrer_page or "")[:500] or None,
                )
                db.add(row)

    except Exception as exc:
        logger.warning(f"visitor session upsert failed: {exc}")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return a paginated, filtered list of visitor sessions for the admin panel
def list_sessions(
    page: int = 1,
    page_size: int = 25,
    department_slug: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_messages: Optional[int] = None,
    has_blocked: Optional[bool] = None,
) -> Dict[str, Any]:
    ''' Return paginated session list with optional filters applied '''

    # FLOW-1: Build base query ordered by last_seen_at descending
    with session_scope() as db:
        q = select(VisitorSession).order_by(VisitorSession.last_seen_at.desc())

        # FLOW-2: Apply each filter if provided
        if department_slug:
            q = q.where(VisitorSession.department_slug == department_slug)
        if date_from:
            q = q.where(VisitorSession.started_at >= datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc))
        if date_to:
            q = q.where(VisitorSession.started_at <= datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc))
        if min_messages is not None:
            q = q.where(VisitorSession.total_messages >= min_messages)
        if has_blocked is True:
            q = q.where(VisitorSession.blocked_count > 0)
        elif has_blocked is False:
            q = q.where(VisitorSession.blocked_count == 0)

        # FLOW-3: Count total matching rows before applying pagination
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0

        # FLOW-4: Apply offset pagination
        offset = (page - 1) * page_size
        rows = db.execute(q.offset(offset).limit(page_size)).scalars().all()

        # FLOW-5: Serialize rows and return with pagination metadata
        sessions = [_row_to_dict(r) for r in rows]

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return {
        "sessions": sessions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return the full detail record for a single session by session_id
def get_session_detail(session_id: str) -> Optional[Dict[str, Any]]:
    ''' Return full session dict or None if session_id not found '''

    # FLOW-1: Load by unique session_id
    with session_scope() as db:
        row = db.execute(
            select(VisitorSession).where(VisitorSession.session_id == session_id)
        ).scalars().first()

        if not row:
            return None

        return _row_to_dict(row)
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return the ordered message history for a session from ChatLog
def get_session_timeline(session_id: str, limit: int = 100) -> Dict[str, Any]:
    ''' Return ordered chat messages for a session — sourced from ChatLog '''

    # FLOW-1: Query ChatLog rows for this session ordered chronologically
    with session_scope() as db:
        rows = db.execute(
            select(ChatLog)
            .where(ChatLog.session_id == session_id)
            .order_by(ChatLog.created_at.asc())
            .limit(limit)
        ).scalars().all()

        # FLOW-2: Serialize each message
        messages = [
            {
                "id": r.id,
                "question": r.question,
                "answer": r.answer,
                "route": r.route,
                "sources_count": r.sources_count,
                "response_time_ms": r.response_time_ms,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    return {"session_id": session_id, "messages": messages}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return funnel and aggregate stats across all sessions for the given date range
def get_session_funnel_stats(days: int = 30) -> Dict[str, Any]:
    ''' Return totals, funnel breakdown, device split, top referrers, and department breakdown '''

    # FLOW-1: Compute date boundary
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    with session_scope() as db:
        base_q = select(VisitorSession).where(VisitorSession.started_at >= cutoff)

        # FLOW-2: Pull aggregate scalars
        total_sessions = db.scalar(select(func.count()).select_from(base_q.subquery())) or 0
        total_messages = db.scalar(
            select(func.sum(VisitorSession.total_messages)).where(VisitorSession.started_at >= cutoff)
        ) or 0
        avg_messages = round(total_messages / total_sessions, 1) if total_sessions > 0 else 0.0
        avg_response_ms = db.scalar(
            select(func.avg(VisitorSession.avg_response_ms)).where(VisitorSession.started_at >= cutoff)
        ) or 0.0

        # FLOW-3: Compute average session duration in minutes using SQL
        duration_avg = db.scalar(
            select(
                func.avg(
                    func.extract("epoch", VisitorSession.last_seen_at - VisitorSession.started_at) / 60
                )
            ).where(VisitorSession.started_at >= cutoff)
        ) or 0.0

        # FLOW-4: Funnel — sessions by outcome category
        fully_blocked = db.scalar(
            select(func.count(VisitorSession.id)).where(
                VisitorSession.started_at >= cutoff,
                VisitorSession.rag_count == 0,
                VisitorSession.correction_count == 0,
                VisitorSession.blocked_count > 0,
            )
        ) or 0

        had_any_block = db.scalar(
            select(func.count(VisitorSession.id)).where(
                VisitorSession.started_at >= cutoff,
                VisitorSession.blocked_count > 0,
            )
        ) or 0

        used_correction = db.scalar(
            select(func.count(VisitorSession.id)).where(
                VisitorSession.started_at >= cutoff,
                VisitorSession.correction_count > 0,
            )
        ) or 0

        fully_answered = total_sessions - had_any_block

        # FLOW-5: Return visitors — sessions where last_seen date is later than started date
        return_visitors = db.scalar(
            select(func.count(VisitorSession.id)).where(
                VisitorSession.started_at >= cutoff,
                func.date_trunc("day", VisitorSession.last_seen_at) > func.date_trunc("day", VisitorSession.started_at),
            )
        ) or 0

        # FLOW-6: Breakdown by department
        dept_rows = db.execute(
            select(
                VisitorSession.department_slug,
                func.count(VisitorSession.id).label("sessions"),
                func.avg(VisitorSession.total_messages).label("avg_msgs"),
            )
            .where(VisitorSession.started_at >= cutoff)
            .group_by(VisitorSession.department_slug)
            .order_by(func.count(VisitorSession.id).desc())
        ).all()

        by_department = [
            {"department_slug": r.department_slug, "sessions": r.sessions, "avg_messages": round(r.avg_msgs or 0, 1)}
            for r in dept_rows
        ]

        # FLOW-7: Breakdown by device hint
        device_rows = db.execute(
            select(
                VisitorSession.device_hint,
                func.count(VisitorSession.id).label("sessions"),
            )
            .where(VisitorSession.started_at >= cutoff, VisitorSession.device_hint.isnot(None))
            .group_by(VisitorSession.device_hint)
            .order_by(func.count(VisitorSession.id).desc())
        ).all()

        by_device = [{"device": r.device_hint, "sessions": r.sessions} for r in device_rows]

        # FLOW-8: Top referrer pages by session count
        referrer_rows = db.execute(
            select(
                VisitorSession.referrer_page,
                func.count(VisitorSession.id).label("sessions"),
            )
            .where(VisitorSession.started_at >= cutoff, VisitorSession.referrer_page.isnot(None))
            .group_by(VisitorSession.referrer_page)
            .order_by(func.count(VisitorSession.id).desc())
            .limit(10)
        ).all()

        top_referrer_pages = [{"page": r.referrer_page, "sessions": r.sessions} for r in referrer_rows]

    return {
        "period_days": days,
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "avg_messages_per_session": avg_messages,
        "avg_session_duration_minutes": round(duration_avg, 1),
        "avg_response_ms": round(avg_response_ms, 1),
        "funnel": {
            "fully_answered": fully_answered,
            "had_at_least_one_block": had_any_block,
            "fully_blocked": fully_blocked,
            "used_correction": used_correction,
        },
        "return_visitors": return_visitors,
        "by_department": by_department,
        "by_device": by_device,
        "top_referrer_pages": top_referrer_pages,
    }
# =========== FUNCTION ===========
