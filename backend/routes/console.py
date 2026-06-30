# WHAT DOES THIS FILE DO: admin chat console endpoints — full pipeline with trace info, bypass flags, and dry-run inspect. test traffic never logged.

# ================== IMPORTS ==================
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from config import DEFAULT_TOP_K, CORRECTION_MATCH_THRESHOLD
from core.dependencies import get_service
from utils import sanitize_input, timings_payload
from workflow_db import is_question_blocked, find_best_correction, normalize_query

from cache import find_cached_answer
# ================== IMPORTS ==================


router = APIRouter()


# =========== SCHEMA ===========
class ConsoleMessageBody(BaseModel):
    question: str
    department_slug: Optional[str] = None
    bypass_cache: bool = False
    bypass_corrections: bool = False
    top_k: int = 5
    conversation_history: List[Dict[str, Any]] = []
# =========== SCHEMA ===========


# =========== FUNCTION ===========
# ROLE: Assemble the response dict — all console_chat paths return this same shape
def _build_response(
    answer: str,
    route: str,
    response_time_ms: float,
    sources: List[Dict[str, Any]],
    pipeline_trace: Dict[str, Any],
    timings: Dict[str, Any],
) -> Dict[str, Any]:
    ''' Same shape regardless of which route produced the answer — keeps console output consistent '''

    return {
        "answer": answer,
        "route": route,
        "response_time_ms": response_time_ms,
        "pipeline_trace": pipeline_trace,
        "sources": sources,
        "timings": timings,
    }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Run full pipeline with per-step trace — no rate limit, nothing logged, bypass flags supported
@router.post("/console/chat")
async def console_chat(body: ConsoleMessageBody) -> Dict[str, Any]:
    ''' Same step order as /api/chat but returns pipeline_trace showing what each step found — test messages never touch ChatLog '''

    service = get_service()
    t_start = time.perf_counter()
    timings: Dict[str, Any] = {}
    trace: Dict[str, Any] = {}

    # FLOW-1: Sanitize input same way production does — no special treatment for console
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    question = sanitize_input(question)
    if not question:
        raise HTTPException(status_code=400, detail="invalid input after sanitization")

    # FLOW-2: Blocked check always runs — bypass flags do not skip this step
    matched_word = is_question_blocked(question)
    trace["blocked"] = {"checked": True, "matched": bool(matched_word), "word": matched_word or None}

    if matched_word:
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        trace["correction"] = {"checked": False, "matched": False}
        trace["cache"] = {"checked": False, "matched": False}
        trace["rag"] = {"executed": False}
        return _build_response("I'm not able to answer that question.", "blocked", elapsed_ms, [], trace, {})

    # FLOW-3: Corrections check — skip if admin set bypass_corrections to see what cache or RAG returns
    if not body.bypass_corrections:
        correction = find_best_correction(question, threshold=CORRECTION_MATCH_THRESHOLD)

        if correction:
            q_norm = normalize_query(question)
            corr_score = round(SequenceMatcher(None, q_norm, correction["question_norm"]).ratio(), 3)
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            trace["correction"] = {
                "checked": True, "matched": True,
                "correction_id": correction["id"],
                "fuzzy_score": corr_score,
            }
            trace["cache"] = {"checked": False, "matched": False}
            trace["rag"] = {"executed": False}
            sources = [{"title": "Verified Answer", "url": "", "category": "correction", "section_type": "exact", "snippet": ""}]
            return _build_response(correction["corrected_answer"], "correction", elapsed_ms, sources, trace, {})

        trace["correction"] = {"checked": True, "matched": False, "correction_id": None, "fuzzy_score": None}

    else:
        trace["correction"] = {"checked": False, "matched": False, "bypassed": True}

    # FLOW-4: Cache check — skip if bypass_cache so admin can force a fresh RAG answer
    if not body.bypass_cache:
        cached = find_cached_answer(question)

        if cached:
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            trace["cache"] = {
                "checked": True, "matched": True,
                "match_type": cached.get("match_type"),
                "fuzzy_score": cached.get("fuzzy_score"),
                "hit_count": cached.get("hit_count"),
            }
            trace["rag"] = {"executed": False}
            sources = [{"title": "Cached Answer", "url": "", "category": "cache", "section_type": cached.get("match_type", "exact"), "snippet": ""}]
            return _build_response(cached["answer"], "cache", elapsed_ms, sources, trace, {})

        trace["cache"] = {"checked": True, "matched": False, "match_type": None, "fuzzy_score": None}

    else:
        trace["cache"] = {"checked": False, "matched": False, "bypassed": True}

    # FLOW-5: Nothing short-circuited so run full RAG — search chunks then call LLM
    top_k = body.top_k or DEFAULT_TOP_K
    results = await run_in_threadpool(service.search, question, top_k, timings)

    context_parts = [r["text"] for r in results]
    context = "\n\n---\n\n".join(context_parts) if context_parts else ""

    sources = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "category": r.get("category", ""),
            "section_type": r.get("section_type", ""),
            "snippet": r["text"][:200],
            "score": r.get("score", 0),
        }
        for r in results
    ]

    answer = await run_in_threadpool(
        service.generate_answer, question, context, timings, body.conversation_history
    )

    total_ms = round((time.perf_counter() - t_start) * 1000, 2)
    timings["total_ms"] = total_ms

    # FLOW-6: RAG trace includes context_preview so admin can see what the LLM actually received
    trace["rag"] = {
        "executed": True,
        "chunks_found": len(results),
        "top_score": round(results[0].get("score", 0), 3) if results else 0,
        "context_preview": context[:400] if context else "",
    }

    return _build_response(answer, "rag", total_ms, sources, trace, timings_payload(timings))
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Dry-run inspect — checks all pipeline steps and returns predictions without making any LLM call
@router.get("/console/inspect")
async def console_inspect(
    question: str = Query(..., description="Question to inspect through the pipeline"),
    department_slug: Optional[str] = Query(None),
) -> Dict[str, Any]:
    ''' Check what blocked/correction/cache/rag would each return for this question — no LLM call, fast and free '''

    service = get_service()

    # FLOW-1: Sanitize input before any checks
    question = sanitize_input((question or "").strip())
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    q_norm = normalize_query(question)

    # FLOW-2: Blocked check first since thats what production does
    matched_word = is_question_blocked(question)
    blocked_info: Dict[str, Any] = {"matched": bool(matched_word), "word": matched_word or None}

    # FLOW-3: Correction check — runs even if blocked so admin sees the full picture, not just the first match
    correction = find_best_correction(question, threshold=CORRECTION_MATCH_THRESHOLD)
    if correction:
        corr_score = round(SequenceMatcher(None, q_norm, correction["question_norm"]).ratio(), 3)
        correction_info: Dict[str, Any] = {
            "matched": True,
            "id": correction["id"],
            "answer_preview": correction["corrected_answer"][:200],
            "fuzzy_score": corr_score,
        }
    else:
        correction_info = {"matched": False}

    # FLOW-4: Cache check — also runs unconditionally so admin can see if both correction and cache matched
    cached = find_cached_answer(question)
    if cached:
        cache_info: Dict[str, Any] = {
            "matched": True,
            "match_type": cached.get("match_type"),
            "fuzzy_score": cached.get("fuzzy_score"),
            "answer_preview": cached["answer"][:200],
            "hit_count": cached.get("hit_count"),
        }
    else:
        cache_info = {"matched": False}

    # FLOW-5: RAG search only — shows what chunks would be retrieved, no LLM generation
    timings: Dict[str, Any] = {}
    results = await run_in_threadpool(service.search, question, DEFAULT_TOP_K, timings)

    top_rag_results = [
        {
            "title": r.get("title", ""),
            "score": round(r.get("score", 0), 3),
            "snippet": r["text"][:200],
            "category": r.get("category", ""),
        }
        for r in results
    ]

    # FLOW-6: Compute predicted_route — same priority as production pipeline
    if matched_word:
        predicted_route = "blocked"
    elif correction:
        predicted_route = "correction"
    elif cached:
        predicted_route = "cache"
    else:
        predicted_route = "rag"

    return {
        "question_original": question,
        "question_normalized": q_norm,
        "predicted_route": predicted_route,
        "blocked": blocked_info,
        "correction": correction_info,
        "cache": cache_info,
        "top_rag_results": top_rag_results,
    }
# =========== FUNCTION ===========
