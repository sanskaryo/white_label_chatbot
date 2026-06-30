# WHAT DOES THIS FILE DO: admin endpoints for viewing, managing, and clearing the question response cache (backed by Upstash Redis)

# ================== IMPORTS ==================
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from cache import (
    list_cache_entries,
    add_cache_entry_manual,
    invalidate_cache_entry,
    clear_all_cache,
    get_cache_stats,
)
# ================== IMPORTS ==================


router = APIRouter()


# =========== SCHEMA ===========
class ManualCacheEntryBody(BaseModel):
    question: str
    answer: str
    route_origin: str = "rag"
# =========== SCHEMA ===========


# =========== FUNCTION ===========
# ROLE: Return all active cache entries ordered by hit count
@router.get("/cache")
def cache_list(include_inactive: bool = False) -> Dict[str, Any]:
    ''' List cache entries from Redis, most-hit first '''

    # FLOW-1: Reads index set then HGETALL each entry
    entries = list_cache_entries(include_inactive=include_inactive)
    return {"entries": entries, "count": len(entries)}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return aggregate cache performance stats
@router.get("/cache/stats")
def cache_stats() -> Dict[str, Any]:
    ''' Return hit counts, active entry count, and API calls saved '''

    # FLOW-1: Reads from Redis — always current, no in-memory lag
    return get_cache_stats()
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Manually add a Q&A pair to cache — admin shortcut that skips the frequency threshold
@router.post("/cache")
def cache_add(body: ManualCacheEntryBody) -> Dict[str, Any]:
    ''' Pin a known-good answer to Redis immediately without waiting for CACHE_MIN_HITS '''

    # FLOW-1: Validate inputs
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    if not body.answer.strip():
        raise HTTPException(status_code=400, detail="answer is required")

    # FLOW-2: Promote — upserts if normalized form already exists
    try:
        return add_cache_entry_manual(body.question.strip(), body.answer.strip(), body.route_origin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Delete a single cache entry from Redis by its question norm
@router.put("/cache/{entry_id:path}/deactivate")
def cache_deactivate(entry_id: str) -> Dict[str, Any]:
    ''' entry_id is the question_norm (URL-decoded by FastAPI) — deletes from Redis and index set '''

    # FLOW-1: Delete key and remove from index — returns 404 if key did not exist
    found = invalidate_cache_entry(entry_id)
    if not found:
        raise HTTPException(status_code=404, detail="cache entry not found")
    return {"status": "deactivated", "id": entry_id}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Wipe the entire cache — useful after updating the knowledge base
@router.post("/cache/clear")
def cache_clear() -> Dict[str, Any]:
    ''' Delete all entries from Redis — use after uploading new documents to avoid stale answers '''

    # FLOW-1: clear_all_cache returns count of deleted entries
    count = clear_all_cache()
    return {"status": "cleared", "entries_removed": count}
# =========== FUNCTION ===========
