# WHAT DOES THIS FILE DO: moderation panel queries — summary dashboard, blocked interactions log

# ================== IMPORTS ==================
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from .connection import session_scope
from .models import FlaggedResponse, BlockedWord, Correction
# ================== IMPORTS ==================


# =========== FUNCTION ===========
# ROLE: Return everything the moderation panel header needs in one DB round-trip
def get_moderation_summary() -> Dict[str, Any]:
    ''' Counts + 5-item previews for pending flagged and recent blocked interactions '''

    # local import — avoids circular: db/ -> analytics_db -> workflow_db -> db/
    from analytics_db import ChatLog

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=6)

    with session_scope() as session:

        # FLOW-1: Aggregate counts
        pending_flagged = session.scalar(
            select(func.count(FlaggedResponse.id)).where(FlaggedResponse.status == "pending")
        ) or 0

        blocked_today = session.scalar(
            select(func.count(ChatLog.id))
            .where(ChatLog.route == "blocked")
            .where(ChatLog.created_at >= today_start)
        ) or 0

        blocked_this_week = session.scalar(
            select(func.count(ChatLog.id))
            .where(ChatLog.route == "blocked")
            .where(ChatLog.created_at >= week_start)
        ) or 0

        active_blocked_words = session.scalar(
            select(func.count(BlockedWord.id)).where(BlockedWord.is_active.is_(True))
        ) or 0

        total_corrections = session.scalar(
            select(func.count(Correction.id)).where(Correction.is_active.is_(True))
        ) or 0

        # FLOW-2: Recent pending flagged items for quick preview
        pending_rows = session.execute(
            select(FlaggedResponse)
            .where(FlaggedResponse.status == "pending")
            .order_by(FlaggedResponse.created_at.desc())
            .limit(5)
        ).scalars().all()

        recent_pending = [
            {
                "id": r.id,
                "question": r.question[:120],
                "tester_verdict": r.tester_verdict,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in pending_rows
        ]

        # FLOW-3: Recent blocked interactions for moderation awareness
        blocked_rows = session.execute(
            select(ChatLog)
            .where(ChatLog.route == "blocked")
            .order_by(ChatLog.created_at.desc())
            .limit(5)
        ).scalars().all()

        recent_blocked_interactions = [
            {
                "question": r.question[:120],
                "blocked_word_matched": r.blocked_word_matched,
                "department_slug": r.department_slug,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in blocked_rows
        ]

    return {
        "pending_flagged": pending_flagged,
        "blocked_today": blocked_today,
        "blocked_this_week": blocked_this_week,
        "active_blocked_words": active_blocked_words,
        "total_corrections": total_corrections,
        "recent_pending": recent_pending,
        "recent_blocked_interactions": recent_blocked_interactions,
    }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Paginated log of blocked chat interactions with optional filters
def get_blocked_interactions(
    limit: int = 50,
    offset: int = 0,
    word: Optional[str] = None,
    department_slug: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    ''' Return {total, items} for blocked chat logs — filter by word, dept, or date range '''

    from analytics_db import ChatLog

    with session_scope() as session:

        # FLOW-1: Build base filter
        base = select(ChatLog).where(ChatLog.route == "blocked")

        if word:
            base = base.where(ChatLog.blocked_word_matched == word.strip().lower())
        if department_slug:
            base = base.where(ChatLog.department_slug == department_slug)
        if date_from:
            base = base.where(ChatLog.created_at >= _parse_date(date_from))
        if date_to:
            base = base.where(ChatLog.created_at <= _parse_date(date_to))

        # FLOW-2: Count total matching rows before applying pagination
        count_stmt = select(func.count(ChatLog.id)).where(ChatLog.route == "blocked")
        if word:
            count_stmt = count_stmt.where(ChatLog.blocked_word_matched == word.strip().lower())
        if department_slug:
            count_stmt = count_stmt.where(ChatLog.department_slug == department_slug)
        if date_from:
            count_stmt = count_stmt.where(ChatLog.created_at >= _parse_date(date_from))
        if date_to:
            count_stmt = count_stmt.where(ChatLog.created_at <= _parse_date(date_to))

        total = session.scalar(count_stmt) or 0

        # FLOW-3: Fetch paginated rows
        rows = session.execute(
            base.order_by(ChatLog.created_at.desc()).offset(offset).limit(limit)
        ).scalars().all()

        items = [
            {
                "id": r.id,
                "question": r.question,
                "blocked_word_matched": r.blocked_word_matched,
                "session_id": r.session_id,
                "department_slug": r.department_slug,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    return {"total": total, "items": items}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Parse ISO date string to UTC datetime for query filters
def _parse_date(date_str: str) -> datetime:
    ''' Convert YYYY-MM-DD or ISO datetime string to UTC datetime '''

    try:
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.now(timezone.utc)
# =========== FUNCTION ===========
