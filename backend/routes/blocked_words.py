# WHAT DOES THIS FILE DO: Blocked words management endpoints

# ================== IMPORTS ==================
from fastapi import APIRouter, HTTPException, Request
from workflow_db import list_blocked_words, add_blocked_word, delete_blocked_word
# ================== IMPORTS ==================

router = APIRouter()


# ROLE: List all blocked words
@router.get("/blocked-words")
def list_blocked_words_endpoint():
    ''' Return list of blocked words/phrases '''
    return {"items": list_blocked_words()}


# ROLE: Add new blocked word
@router.post("/blocked-words")
async def add_blocked_word_endpoint(request: Request):
    ''' Add word or phrase to blocklist '''

    # FLOW-1: Parse and validate request
    data = await request.json()
    word = data.get("word", "").strip()

    # FLOW-2: Validate word required
    if not word:
        raise HTTPException(status_code=400, detail="word is required")

    # FLOW-3: Add to blocklist with metadata
    result = add_blocked_word(word, reason=data.get("reason", ""), added_by=data.get("added_by", "admin"))

    return result


# ROLE: Delete blocked word
@router.delete("/blocked-words/{word_id}")
def delete_blocked_word_endpoint(word_id: int):
    ''' Remove word from blocklist '''
    ok = delete_blocked_word(word_id)
    return {"deleted": ok}
