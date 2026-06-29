# WHAT DOES THIS FILE DO: Flagged responses management endpoints

# ================== IMPORTS ==================
from fastapi import APIRouter, Request
from workflow_db import list_flagged_responses, approve_flagged_response, reject_flagged_response
# ================== IMPORTS ==================

router = APIRouter()


# ROLE: List flagged responses
@router.get("/flagged-responses")
def list_flagged_endpoint(status: str = "pending", limit: int = 50):
    ''' Return flagged responses filtered by status '''
    return {"items": list_flagged_responses(status=status, limit=limit)}


# ROLE: Approve flagged response and create correction
@router.post("/flagged-responses/{flagged_id}/approve")
async def approve_flagged_endpoint(flagged_id: int, request: Request):
    ''' Mark flagged response as approved and create a correction '''

    # FLOW-1: Parse request body if JSON
    data = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}

    # FLOW-2: Extract improved answer and reviewer info
    improved = data.get("improved_answer", "")
    reviewed_by = data.get("reviewed_by", "admin")

    # FLOW-3: Call workflow function to approve and create correction
    result = approve_flagged_response(flagged_id, reviewed_by=reviewed_by, improved_answer=improved)

    return result


# ROLE: Reject flagged response
@router.post("/flagged-responses/{flagged_id}/reject")
async def reject_flagged_endpoint(flagged_id: int, request: Request):
    ''' Mark flagged response as rejected '''

    # FLOW-1: Parse request body if JSON
    data = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}

    # FLOW-2: Extract reviewer info
    reviewed_by = data.get("reviewed_by", "admin")

    # FLOW-3: Call workflow function to reject
    result = reject_flagged_response(flagged_id, reviewed_by=reviewed_by)

    return result
