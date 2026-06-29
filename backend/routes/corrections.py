# WHAT DOES THIS FILE DO: Corrections management endpoints

# ================== IMPORTS ==================
from fastapi import APIRouter, HTTPException, Request
from workflow_db import list_corrections, create_direct_correction
# ================== IMPORTS ==================

router = APIRouter()


# ROLE: List all active corrections
@router.get("/corrections")
def list_corrections_endpoint(limit: int = 100):
    ''' Return list of active corrections '''
    return {"items": list_corrections(limit=limit)}


# ROLE: Create new correction
@router.post("/corrections")
async def create_correction_endpoint(request: Request):
    ''' Create new question-answer correction '''

    # FLOW-1: Parse and validate request
    data = await request.json()
    question = data.get("question", "").strip()
    answer = data.get("corrected_answer", "").strip()

    # FLOW-2: Validate both fields required
    if not question or not answer:
        raise HTTPException(status_code=400, detail="question and corrected_answer are required")

    # FLOW-3: Create correction with metadata
    result = create_direct_correction(
        question, answer,
        admin_note=data.get("admin_note", ""),
        approved_by=data.get("approved_by", "admin")
    )

    return result
