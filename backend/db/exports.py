# WHAT DOES THIS FILE DO: query functions for all 7 CSV exports — one function per export type, each returns List[Dict] ready for csv.DictWriter

# ================== IMPORTS ==================
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from .connection import session_scope
from .models import Correction, BlockedWord, FlaggedResponse, AuditLog
# ================== IMPORTS ==================


# =========== FUNCTION ===========
# ROLE: Parse an ISO date string to a timezone-aware datetime
def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    ''' Return UTC datetime from "YYYY-MM-DD" string, or None if empty '''

    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 1 — full chat log with response source label and moderation metadata
def export_chat_logs(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    department_slug: Optional[str] = None,
    limit: int = 10000,
) -> List[Dict[str, Any]]:
    ''' Return chat log rows with response_source mapped to LLM/Cache/Correction/Blocked '''

    # FLOW-1: import ChatLog at call time to avoid circular at module level
    from analytics_db import ChatLog

    _route_label = {"rag": "LLM", "cache": "Cache", "correction": "Correction", "blocked": "Blocked"}

    with session_scope() as db:
        # FLOW-2: Build query with optional filters
        q = select(ChatLog).order_by(ChatLog.created_at.desc())
        dt_from = _parse_date(date_from)
        dt_to = _parse_date(date_to)
        if dt_from:
            q = q.where(ChatLog.created_at >= dt_from)
        if dt_to:
            q = q.where(ChatLog.created_at <= dt_to)
        if department_slug:
            q = q.where(ChatLog.department_slug == department_slug)

        rows = db.execute(q.limit(limit)).scalars().all()

        return [
            {
                "timestamp": r.created_at.isoformat() if r.created_at else "",
                "session_id": r.session_id or "",
                "department": r.department_slug or "",
                "question": r.question,
                "answer": r.answer or "",
                "response_source": _route_label.get(r.route, r.route),
                "response_time_ms": r.response_time_ms if r.response_time_ms is not None else "",
                "sources_count": r.sources_count,
                "blocked_word_matched": (r.blocked_word_matched or "") if hasattr(r, "blocked_word_matched") else "",
                "correction_id": (r.correction_id or "") if hasattr(r, "correction_id") else "",
            }
            for r in rows
        ]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 2 — blocked interactions with accountability trail (who added the blocking word)
def export_blocked_interactions(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    department_slug: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ''' Return every chat interaction that was blocked, enriched with who added the blocked word '''

    from analytics_db import ChatLog

    with session_scope() as db:
        # FLOW-1: Load all blocked words once into a lookup dict
        bw_rows = db.execute(select(BlockedWord)).scalars().all()
        word_meta = {
            r.word.lower(): {"added_by": r.added_by or "", "added_at": r.created_at.isoformat() if r.created_at else "", "reason": r.reason or ""}
            for r in bw_rows
        }

        # FLOW-2: Query blocked chat logs
        q = (
            select(ChatLog)
            .where(ChatLog.route == "blocked")
            .order_by(ChatLog.created_at.desc())
        )
        dt_from = _parse_date(date_from)
        dt_to = _parse_date(date_to)
        if dt_from:
            q = q.where(ChatLog.created_at >= dt_from)
        if dt_to:
            q = q.where(ChatLog.created_at <= dt_to)
        if department_slug:
            q = q.where(ChatLog.department_slug == department_slug)

        rows = db.execute(q).scalars().all()

        # FLOW-3: Enrich each row with blocked word metadata
        result = []
        for r in rows:
            matched = (r.blocked_word_matched or "") if hasattr(r, "blocked_word_matched") else ""
            meta = word_meta.get(matched.lower(), {}) if matched else {}
            result.append({
                "timestamp": r.created_at.isoformat() if r.created_at else "",
                "session_id": r.session_id or "",
                "department": r.department_slug or "",
                "question_asked": r.question,
                "blocked_word_matched": matched,
                "blocked_word_added_by": meta.get("added_by", ""),
                "blocked_word_added_at": meta.get("added_at", ""),
                "block_reason": meta.get("reason", ""),
            })

        return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 3 — all corrections with approver identity and usage count
def export_corrections(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ''' Return correction records with who approved them and how many times they have been served '''

    from analytics_db import ChatLog

    with session_scope() as db:
        # FLOW-1: Load corrections
        q = select(Correction).order_by(Correction.created_at.desc())
        dt_from = _parse_date(date_from)
        dt_to = _parse_date(date_to)
        if dt_from:
            q = q.where(Correction.created_at >= dt_from)
        if dt_to:
            q = q.where(Correction.created_at <= dt_to)

        rows = db.execute(q).scalars().all()
        if not rows:
            return []

        # FLOW-2: Count how many times each correction was served from ChatLog
        correction_ids = [r.id for r in rows]
        count_rows = db.execute(
            select(ChatLog.correction_id, func.count(ChatLog.id).label("cnt"))
            .where(ChatLog.correction_id.in_(correction_ids))
            .group_by(ChatLog.correction_id)
        ).all()
        usage_map = {r.correction_id: r.cnt for r in count_rows}

        return [
            {
                "correction_id": r.id,
                "original_question": r.question,
                "corrected_answer": r.corrected_answer,
                "admin_note": r.admin_note or "",
                "approved_by": r.approved_by or "",
                "is_active": r.is_active,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
                "originated_from_flag": "yes" if r.source_flagged_id else "no",
                "source_flagged_id": r.source_flagged_id or "",
                "times_served": usage_map.get(r.id, 0),
            }
            for r in rows
        ]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 4 — flagged response moderation history with full resolution chain
def export_flagged_responses(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ''' Return flagged responses with who flagged, who resolved, and whether a correction was created '''

    with session_scope() as db:
        # FLOW-1: Load all flagged responses
        q = select(FlaggedResponse).order_by(FlaggedResponse.created_at.desc())
        dt_from = _parse_date(date_from)
        dt_to = _parse_date(date_to)
        if dt_from:
            q = q.where(FlaggedResponse.created_at >= dt_from)
        if dt_to:
            q = q.where(FlaggedResponse.created_at <= dt_to)

        rows = db.execute(q).scalars().all()
        if not rows:
            return []

        # FLOW-2: Find which flagged IDs have a linked correction
        flagged_ids = [r.id for r in rows]
        correction_rows = db.execute(
            select(Correction.source_flagged_id)
            .where(Correction.source_flagged_id.in_(flagged_ids))
        ).scalars().all()
        has_correction = set(correction_rows)

        return [
            {
                "flagged_at": r.created_at.isoformat() if r.created_at else "",
                "chat_id": r.chat_id or "",
                "tester_id": r.tester_id or "",
                "question": r.question,
                "original_bot_answer": r.chatbot_answer,
                "tester_verdict": r.tester_verdict,
                "tester_note": r.tester_note or "",
                "status": r.status,
                "resolved_by": r.reviewed_by or "",
                "resolved_at": r.reviewed_at.isoformat() if r.reviewed_at else "",
                "correction_created": "yes" if r.id in has_correction else "no",
            }
            for r in rows
        ]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 5 — visitor sessions with per-route message breakdown
def export_visitor_sessions(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    department_slug: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ''' Return one row per visitor session with all counters and context fields '''

    from sessions_db import VisitorSession

    with session_scope() as db:
        q = select(VisitorSession).order_by(VisitorSession.started_at.desc())
        dt_from = _parse_date(date_from)
        dt_to = _parse_date(date_to)
        if dt_from:
            q = q.where(VisitorSession.started_at >= dt_from)
        if dt_to:
            q = q.where(VisitorSession.started_at <= dt_to)
        if department_slug:
            q = q.where(VisitorSession.department_slug == department_slug)

        rows = db.execute(q).scalars().all()

        return [
            {
                "session_id": r.session_id,
                "department": r.department_slug or "",
                "started_at": r.started_at.isoformat() if r.started_at else "",
                "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else "",
                "duration_minutes": round((r.last_seen_at - r.started_at).total_seconds() / 60, 1) if r.last_seen_at and r.started_at else 0,
                "total_messages": r.total_messages,
                "llm_responses": r.rag_count,
                "cache_responses": r.cache_count if hasattr(r, "cache_count") else 0,
                "correction_responses": r.correction_count,
                "blocked_responses": r.blocked_count,
                "avg_response_ms": round(r.avg_response_ms, 1),
                "device": r.device_hint or "",
                "referrer_page": r.referrer_page or "",
                "first_question": r.first_question or "",
                "last_question": r.last_question or "",
            }
            for r in rows
        ]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 6 — full admin audit trail, every action with identity and timestamp
def export_audit_log(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ''' Return every admin action — the hardest CSV to dispute '''

    with session_scope() as db:
        q = select(AuditLog).order_by(AuditLog.created_at.desc())
        dt_from = _parse_date(date_from)
        dt_to = _parse_date(date_to)
        if dt_from:
            q = q.where(AuditLog.created_at >= dt_from)
        if dt_to:
            q = q.where(AuditLog.created_at <= dt_to)

        rows = db.execute(q).scalars().all()

        return [
            {
                "timestamp": r.created_at.isoformat() if r.created_at else "",
                "admin_email": r.admin_id,
                "admin_role": r.role or "",
                "action": r.action,
                "details": r.details,
            }
            for r in rows
        ]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 7 — blocked words list with who added each word and how many times it was triggered
def export_blocked_words() -> List[Dict[str, Any]]:
    ''' Return all blocked words with responsible admin and trigger count from chat logs '''

    from analytics_db import ChatLog

    with session_scope() as db:
        # FLOW-1: Load all blocked words (active + inactive for full accountability)
        rows = db.execute(
            select(BlockedWord).order_by(BlockedWord.created_at.desc())
        ).scalars().all()

        if not rows:
            return []

        # FLOW-2: Count trigger hits per word from ChatLog — only counts post-migration rows
        trigger_rows = db.execute(
            select(ChatLog.blocked_word_matched, func.count(ChatLog.id).label("cnt"))
            .where(
                ChatLog.route == "blocked",
                ChatLog.blocked_word_matched.isnot(None),
            )
            .group_by(ChatLog.blocked_word_matched)
        ).all()
        trigger_map = {r.blocked_word_matched: r.cnt for r in trigger_rows}

        return [
            {
                "word": r.word,
                "reason": r.reason or "",
                "added_by": r.added_by or "",
                "added_at": r.created_at.isoformat() if r.created_at else "",
                "is_active": r.is_active,
                "times_triggered": trigger_map.get(r.word, 0),
            }
            for r in rows
        ]
# =========== FUNCTION ===========
