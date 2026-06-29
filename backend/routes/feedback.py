# WHAT DOES THIS FILE DO: User feedback submission endpoints

# ================== IMPORTS ==================
from fastapi import APIRouter, HTTPException, Request
from workflow_db import create_flagged_response
# ================== IMPORTS ==================

router = APIRouter()


# ROLE: Submit corrected answer feedback
@router.post("/feedback")
async def submit_feedback(request: Request):
    ''' Create flagged response from user feedback for admin review '''

    # FLOW-1: Parse and validate request
    data = await request.json()
    question = data.get("question", "").strip()
    chatbot_answer = data.get("chatbot_answer", "").strip()
    correct_answer = data.get("correct_answer", "").strip()

    # FLOW-2: Validate required fields
    if not question or not chatbot_answer:
        raise HTTPException(status_code=400, detail="question and chatbot_answer are required")

    # FLOW-3: Create flagged response for admin review
    result = create_flagged_response(
        question=question,
        chatbot_answer=chatbot_answer,
        tester_answer_raw=correct_answer,
        tester_note=data.get("note", ""),
        tester_id=data.get("tester_id", ""),
    )

    return result
