# WHAT DOES THIS FILE DO: flagged response review endpoints — list, detail, stats, approve, reject

# ================== IMPORTS ==================
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from workflow_db import (
    list_flagged_responses, get_flagged_response, get_flagged_stats,
    approve_flagged_response, reject_flagged_response,
)
# ================== IMPORTS ==================


router = APIRouter()


# =========== SCHEMA ===========
class ApproveBody(BaseModel):
    reviewed_by: str = "admin"
    improved_answer: str = ""
    admin_note: str = ""


class RejectBody(BaseModel):
    reviewed_by: str = "admin"
    admin_note: str = ""
# =========== SCHEMA ===========


# =========== FUNCTION ===========
# ROLE: Return pending count and totals for dashboard badge
@router.get("/flagged-responses/stats")
def flagged_stats_endpoint() -> Dict[str, int]:
    ''' Return {pending, approved, rejected, total} counts '''

    return get_flagged_stats()
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: List flagged responses filtered by status with pagination
@router.get("/flagged-responses")
def list_flagged_endpoint(
    status: str = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Filter by question text (case-insensitive substring)"),
) -> Dict[str, Any]:
    ''' Return flagged responses with full fields — status filter accepts: pending, approved, rejected, or empty string for all '''

    return {"items": list_flagged_responses(status=status, limit=limit, offset=offset, search=search)}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return full detail of one flagged response
@router.get("/flagged-responses/{flagged_id}")
def get_flagged_endpoint(flagged_id: int) -> Dict[str, Any]:
    ''' Fetch a single flagged response with all fields for the review UI '''

    item = get_flagged_response(flagged_id)
    if not item:
        raise HTTPException(status_code=404, detail="flagged response not found")

    return item
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Approve a flagged response and auto-create a correction
@router.post("/flagged-responses/{flagged_id}/approve")
def approve_flagged_endpoint(flagged_id: int, body: ApproveBody) -> Dict[str, Any]:
    ''' Mark approved and create linked correction — 409 if already reviewed '''

    result = approve_flagged_response(
        flagged_id,
        reviewed_by=body.reviewed_by,
        improved_answer=body.improved_answer,
        admin_note=body.admin_note,
    )

    if "error" in result:
        status_code = 409 if result["error"] == "already reviewed" else 404
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Reject a flagged response without creating a correction
@router.post("/flagged-responses/{flagged_id}/reject")
def reject_flagged_endpoint(flagged_id: int, body: RejectBody) -> Dict[str, Any]:
    ''' Mark rejected with optional note — 409 if already reviewed '''

    result = reject_flagged_response(
        flagged_id,
        reviewed_by=body.reviewed_by,
        admin_note=body.admin_note,
    )

    if "error" in result:
        status_code = 409 if result["error"] == "already reviewed" else 404
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result
# =========== FUNCTION ===========
