# WHAT DOES THIS FILE DO: corrections management endpoints — list, create, update, deactivate

# ================== IMPORTS ==================
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from workflow_db import list_corrections, create_direct_correction, update_correction, deactivate_correction
# ================== IMPORTS ==================


router = APIRouter()


# =========== SCHEMA ===========
class CreateCorrectionBody(BaseModel):
    question: str
    corrected_answer: str
    admin_note: str = ""
    approved_by: str = "admin"


class UpdateCorrectionBody(BaseModel):
    corrected_answer: Optional[str] = None
    admin_note: Optional[str] = None
    updated_by: str = "admin"
# =========== SCHEMA ===========


# =========== FUNCTION ===========
# ROLE: List all active corrections
@router.get("/corrections")
def list_corrections_endpoint(limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    ''' Return active corrections with full fields ordered by last updated '''

    return {"items": list_corrections(limit=limit)}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Create a correction manually from the admin panel
@router.post("/corrections")
def create_correction_endpoint(body: CreateCorrectionBody) -> Dict[str, Any]:
    ''' Create a new question-answer correction directly without a flagged response source '''

    question = body.question.strip()
    answer = body.corrected_answer.strip()

    if not question or not answer:
        raise HTTPException(status_code=400, detail="question and corrected_answer are required")

    return create_direct_correction(
        question, answer,
        admin_note=body.admin_note,
        approved_by=body.approved_by,
    )
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Edit the answer or note on an existing correction
@router.put("/corrections/{correction_id}")
def update_correction_endpoint(correction_id: int, body: UpdateCorrectionBody) -> Dict[str, Any]:
    ''' Update corrected_answer or admin_note — at least one field must be provided '''

    if body.corrected_answer is None and body.admin_note is None:
        raise HTTPException(status_code=400, detail="provide corrected_answer or admin_note to update")

    result = update_correction(
        correction_id,
        corrected_answer=body.corrected_answer,
        admin_note=body.admin_note,
        updated_by=body.updated_by,
    )

    if "error" in result:
        status_code = 404 if result["error"] == "not found" else 409
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Soft-delete a correction so it stops matching questions
@router.delete("/corrections/{correction_id}")
def deactivate_correction_endpoint(
    correction_id: int,
    deactivated_by: str = Query("admin"),
) -> Dict[str, Any]:
    ''' Set is_active=False and invalidate cache — correction will no longer match any question '''

    result = deactivate_correction(correction_id, deactivated_by=deactivated_by)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
# =========== FUNCTION ===========
