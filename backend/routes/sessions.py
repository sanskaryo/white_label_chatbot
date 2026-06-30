# WHAT DOES THIS FILE DO: visitor session tracking endpoints — list, detail, timeline, and funnel stats

# ================== IMPORTS ==================
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from sessions_db import (
    list_sessions,
    get_session_detail,
    get_session_timeline,
    get_session_funnel_stats,
)
# ================== IMPORTS ==================


router = APIRouter()


# =========== FUNCTION ===========
# ROLE: Return paginated, filtered list of all visitor sessions
@router.get("/sessions")
def sessions_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    department_slug: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO date string e.g. 2026-06-01"),
    date_to: Optional[str] = Query(None, description="ISO date string e.g. 2026-06-30"),
    min_messages: Optional[int] = Query(None, ge=1),
    has_blocked: Optional[bool] = Query(None),
) -> Dict[str, Any]:
    ''' List sessions newest-first with optional filters for department, date range, depth, and frustration flag '''

    # FLOW-1: Delegate entirely to sessions_db with all filter params
    return list_sessions(
        page=page,
        page_size=page_size,
        department_slug=department_slug,
        date_from=date_from,
        date_to=date_to,
        min_messages=min_messages,
        has_blocked=has_blocked,
    )
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return aggregate funnel stats and breakdowns for the sessions dashboard widget
@router.get("/sessions/stats")
def sessions_stats(
    days: int = Query(30, ge=1, le=365),
) -> Dict[str, Any]:
    ''' Return funnel breakdown, device split, top referrers, and department breakdown for given period '''

    # FLOW-1: Query is purely aggregative — no 404 case
    return get_session_funnel_stats(days=days)
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return the full detail record for one specific visitor session
@router.get("/sessions/{session_id}")
def session_detail(session_id: str) -> Dict[str, Any]:
    ''' Return all persisted fields for a session plus computed status and duration '''

    # FLOW-1: Load session or 404
    result = get_session_detail(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return the ordered message timeline for a session from ChatLog
@router.get("/sessions/{session_id}/timeline")
def session_timeline(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
) -> Dict[str, Any]:
    ''' Return chronological list of all messages sent in this session '''

    # FLOW-1: Load detail first to confirm session exists
    if not get_session_detail(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    # FLOW-2: Return timeline from ChatLog
    return get_session_timeline(session_id=session_id, limit=limit)
# =========== FUNCTION ===========
