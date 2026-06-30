# WHAT DOES THIS FILE DO: moderation panel endpoints — summary dashboard, blocked interaction log, bulk flagged actions

# ================== IMPORTS ==================
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from workflow_db import get_moderation_summary, get_blocked_interactions, approve_flagged_response, reject_flagged_response
# ================== IMPORTS ==================


router = APIRouter()

_BULK_ACTION_LIMIT = 50


# =========== SCHEMA ===========
class BulkActionBody(BaseModel):
    action: str                     # "approve" or "reject"
    flagged_ids: List[int]
    reviewed_by: str = "admin"
    admin_note: str = ""
# =========== SCHEMA ===========


# =========== FUNCTION ===========
# ROLE: Single call for moderation panel header — counts and previews
@router.get("/moderation/summary")
def moderation_summary_endpoint() -> Dict[str, Any]:
    ''' Return pending flagged count, blocked interaction counts, recent items — one call for the whole panel header '''

    return get_moderation_summary()
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Paginated log of blocked chat queries with filters
@router.get("/moderation/blocked-interactions")
def blocked_interactions_endpoint(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    word: Optional[str] = Query(None, description="Filter by the specific blocked word that was matched"),
    department_slug: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
) -> Dict[str, Any]:
    ''' Return paginated blocked chat interactions so moderators can see what students are asking that triggers the blocklist '''

    return get_blocked_interactions(
        limit=limit,
        offset=offset,
        word=word,
        department_slug=department_slug,
        date_from=date_from,
        date_to=date_to,
    )
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Bulk approve or reject multiple flagged responses in one request
@router.post("/moderation/flagged/bulk-action")
def bulk_flagged_action(body: BulkActionBody) -> Dict[str, Any]:
    ''' Approve or reject up to 50 flagged items at once — returns per-item result including errors '''

    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    if not body.flagged_ids:
        raise HTTPException(status_code=400, detail="flagged_ids must not be empty")

    if len(body.flagged_ids) > _BULK_ACTION_LIMIT:
        raise HTTPException(status_code=400, detail=f"max {_BULK_ACTION_LIMIT} items per bulk action")

    results = []

    for fid in body.flagged_ids:
        if body.action == "approve":
            res = approve_flagged_response(fid, reviewed_by=body.reviewed_by, admin_note=body.admin_note)
        else:
            res = reject_flagged_response(fid, reviewed_by=body.reviewed_by, admin_note=body.admin_note)

        if "error" in res:
            results.append({"id": fid, "result": "error", "reason": res["error"]})
        else:
            entry: Dict[str, Any] = {"id": fid, "result": res.get("status", body.action + "d")}
            if "correction_id" in res:
                entry["correction_id"] = res["correction_id"]
            results.append(entry)

    succeeded = sum(1 for r in results if r["result"] != "error")
    failed = len(results) - succeeded

    return {
        "processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
# =========== FUNCTION ===========
