# WHAT DOES THIS FILE DO: flagged response lifecycle — create, list, get, approve, and reject

# ================== IMPORTS ==================
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from .connection import session_scope, normalize_query
from .models import FlaggedResponse, Correction
from .audit import log_audit_action
from .corrections import _invalidate_corrections_cache
# ================== IMPORTS ==================


# =========== FUNCTION ===========
# ROLE: Save a new flagged response from user/tester feedback
def create_flagged_response(
    question: str,
    chatbot_answer: str,
    tester_answer_raw: str,
    tester_verdict: str = "wrong",
    tester_note: str = "",
    tester_id: str = "",
    chat_id: str = "",
) -> Dict[str, Any]:
    ''' Insert flagged response in pending state and return its id '''

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
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return all fields for a single flagged response
def get_flagged_response(flagged_id: int) -> Optional[Dict[str, Any]]:
    ''' Fetch one flagged response by id — returns None if not found '''

    with session_scope() as session:
        row = session.get(FlaggedResponse, flagged_id)
        if not row:
            return None
        return _row_to_dict(row)
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return flagged responses list with all fields, filtered by status
def list_flagged_responses(
    status: str = "pending",
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ''' Return full flagged response records ordered newest first — search does ilike on question text '''

    with session_scope() as session:
        stmt = select(FlaggedResponse).order_by(FlaggedResponse.created_at.desc())

        if status:
            stmt = stmt.where(FlaggedResponse.status == status)
        if search:
            stmt = stmt.where(FlaggedResponse.question.ilike(f"%{search}%"))

        rows = session.execute(stmt.offset(offset).limit(limit)).scalars().all()
        return [_row_to_dict(r) for r in rows]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return counts by status for dashboard badge
def get_flagged_stats() -> Dict[str, int]:
    ''' Return {pending, approved, rejected, total} counts '''

    with session_scope() as session:
        rows = session.execute(
            select(FlaggedResponse.status, func.count(FlaggedResponse.id))
            .group_by(FlaggedResponse.status)
        ).all()

    counts = {"pending": 0, "approved": 0, "rejected": 0}
    for status_val, count in rows:
        if status_val in counts:
            counts[status_val] = count

    counts["total"] = sum(counts.values())
    return counts
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Approve a flagged response and create a linked correction
def approve_flagged_response(
    flagged_id: int,
    reviewed_by: str = "admin",
    improved_answer: str = "",
    admin_note: str = "",
) -> Dict[str, Any]:
    ''' Mark as approved, create correction, log action — returns 409-style error dict if already reviewed '''

    with session_scope() as session:
        row = session.get(FlaggedResponse, flagged_id)
        if not row:
            return {"error": "not found"}

        # guard: re-approval would create a duplicate correction
        if row.status != "pending":
            return {"error": "already reviewed", "status": row.status}

        row.status = "approved"
        row.reviewed_by = reviewed_by
        row.reviewed_at = datetime.now(timezone.utc)
        if admin_note:
            row.admin_note = admin_note
        if improved_answer:
            row.tester_answer_improved = improved_answer

        final_answer = improved_answer or row.tester_answer_raw

        correction = Correction(
            question=row.question, question_norm=row.question_norm,
            corrected_answer=final_answer, admin_note=admin_note or None,
            approved_by=reviewed_by, source_flagged_id=flagged_id, is_active=True,
        )
        session.add(correction)
        log_audit_action(
            session, "flagged_approved",
            f"Flagged #{flagged_id}: {row.question[:80]}",
            admin_id=reviewed_by,
        )

        session.flush()
        result = {"id": row.id, "status": "approved", "correction_id": correction.id}

    _invalidate_corrections_cache()
    return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Reject a flagged response without creating a correction
def reject_flagged_response(
    flagged_id: int,
    reviewed_by: str = "admin",
    admin_note: str = "",
) -> Dict[str, Any]:
    ''' Mark as rejected and store admin note — returns error dict if already reviewed '''

    with session_scope() as session:
        row = session.get(FlaggedResponse, flagged_id)
        if not row:
            return {"error": "not found"}

        if row.status != "pending":
            return {"error": "already reviewed", "status": row.status}

        row.status = "rejected"
        row.reviewed_by = reviewed_by
        row.reviewed_at = datetime.now(timezone.utc)
        if admin_note:
            row.admin_note = admin_note

        log_audit_action(
            session, "flagged_rejected",
            f"Flagged #{flagged_id}: {row.question[:80]}",
            admin_id=reviewed_by,
        )

        return {"id": row.id, "status": "rejected"}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Serialize ORM row to full dict
def _row_to_dict(row: FlaggedResponse) -> Dict[str, Any]:
    return {
        "id": row.id,
        "question": row.question,
        "chatbot_answer": row.chatbot_answer,
        "tester_verdict": row.tester_verdict,
        "tester_answer_raw": row.tester_answer_raw,
        "tester_answer_improved": row.tester_answer_improved,
        "tester_note": row.tester_note,
        "tester_id": row.tester_id,
        "chat_id": row.chat_id,
        "status": row.status,
        "admin_note": row.admin_note,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
# =========== FUNCTION ===========
