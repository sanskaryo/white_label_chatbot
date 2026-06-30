# WHAT DOES THIS FILE DO: 7 CSV export endpoints for admin accountability — each streams a downloadable CSV file

# ================== IMPORTS ==================
import csv
import io
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response

from db.exports import (
    export_chat_logs,
    export_blocked_interactions,
    export_corrections,
    export_flagged_responses,
    export_visitor_sessions,
    export_audit_log,
    export_blocked_words,
)
# ================== IMPORTS ==================


router = APIRouter()


# =========== FUNCTION ===========
# ROLE: Build a CSV Response from a list of dicts — shared by all 7 endpoints
def _csv_response(rows: List[Dict[str, Any]], filename: str) -> Response:
    ''' Write rows to a StringIO buffer and return as downloadable CSV '''

    output = io.StringIO()

    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    else:
        output.write("no_data\n")

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 1 — full chat history with response source (LLM/Cache/Correction/Blocked)
@router.get("/export/chat-logs")
def export_chat_logs_csv(
    date_from: Optional[str] = Query(None, description="ISO date e.g. 2026-06-01"),
    date_to: Optional[str] = Query(None, description="ISO date e.g. 2026-06-30"),
    department_slug: Optional[str] = Query(None),
    limit: int = Query(10000, ge=1, le=50000),
) -> Response:
    ''' Download chat logs as CSV — use date filters to keep file size manageable '''

    rows = export_chat_logs(date_from=date_from, date_to=date_to, department_slug=department_slug, limit=limit)
    return _csv_response(rows, "chat_logs.csv")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 2 — every blocked interaction with who is responsible for the block
@router.get("/export/blocked-interactions")
def export_blocked_interactions_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    department_slug: Optional[str] = Query(None),
) -> Response:
    ''' Download blocked questions with the admin who added each blocking word '''

    rows = export_blocked_interactions(date_from=date_from, date_to=date_to, department_slug=department_slug)
    return _csv_response(rows, "blocked_interactions.csv")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 3 — all corrections with approver identity and usage stats
@router.get("/export/corrections")
def export_corrections_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> Response:
    ''' Download corrections with who approved each one and how many times it has been served '''

    rows = export_corrections(date_from=date_from, date_to=date_to)
    return _csv_response(rows, "corrections.csv")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 4 — flagged response moderation history with resolution trail
@router.get("/export/flagged-responses")
def export_flagged_responses_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> Response:
    ''' Download flagged responses with tester identity, resolution outcome, and correction link '''

    rows = export_flagged_responses(date_from=date_from, date_to=date_to)
    return _csv_response(rows, "flagged_responses.csv")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 5 — one row per visitor session with full message breakdown
@router.get("/export/visitor-sessions")
def export_visitor_sessions_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    department_slug: Optional[str] = Query(None),
) -> Response:
    ''' Download visitor sessions with LLM/Cache/Correction/Blocked message counts per session '''

    rows = export_visitor_sessions(date_from=date_from, date_to=date_to, department_slug=department_slug)
    return _csv_response(rows, "visitor_sessions.csv")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 6 — complete admin audit trail ordered newest first
@router.get("/export/audit-log")
def export_audit_log_csv(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
) -> Response:
    ''' Download every admin action with identity, role, and timestamp '''

    rows = export_audit_log(date_from=date_from, date_to=date_to)
    return _csv_response(rows, "audit_log.csv")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Export 7 — blocked words list with responsible admin and trigger count
@router.get("/export/blocked-words")
def export_blocked_words_csv() -> Response:
    ''' Download the full blocked words list including deactivated ones — no date filter needed '''

    rows = export_blocked_words()
    return _csv_response(rows, "blocked_words.csv")
# =========== FUNCTION ===========
