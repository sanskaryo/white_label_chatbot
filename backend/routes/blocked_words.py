# WHAT DOES THIS FILE DO: blocked words management endpoints — list, add, delete

# ================== IMPORTS ==================
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from workflow_db import list_blocked_words, add_blocked_word, delete_blocked_word
# ================== IMPORTS ==================


router = APIRouter()


# =========== SCHEMA ===========
class AddBlockedWordBody(BaseModel):
    word: str
    reason: Optional[str] = ""
    added_by: Optional[str] = "admin"
# =========== SCHEMA ===========


# =========== FUNCTION ===========
# ROLE: List all active blocked words with trigger counts
@router.get("/blocked-words")
def list_blocked_words_endpoint() -> Dict[str, Any]:
    ''' Return blocked words with created_at and how many times each was triggered in chat logs '''

    return {"items": list_blocked_words()}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Add a new blocked word or reactivate an existing one
@router.post("/blocked-words")
def add_blocked_word_endpoint(body: AddBlockedWordBody) -> Dict[str, Any]:
    ''' Add word or phrase to blocklist — reactivates if it was previously deleted '''

    word = (body.word or "").strip()
    if not word:
        raise HTTPException(status_code=400, detail="word is required")

    return add_blocked_word(word, reason=body.reason or "", added_by=body.added_by or "admin")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Remove a blocked word by id
@router.delete("/blocked-words/{word_id}")
def delete_blocked_word_endpoint(word_id: int, deleted_by: str = Query("admin")) -> Dict[str, Any]:
    ''' Soft-delete word from blocklist — it stops matching immediately via cache invalidation '''

    ok = delete_blocked_word(word_id)
    if not ok:
        raise HTTPException(status_code=404, detail="blocked word not found")

    return {"deleted": True, "word_id": word_id}
# =========== FUNCTION ===========
