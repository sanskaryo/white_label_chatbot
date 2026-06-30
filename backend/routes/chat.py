# WHAT DOES THIS FILE DO: Chat, status, and health endpoints

# ================== IMPORTS ==================
import time
from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.concurrency import run_in_threadpool
from pathlib import Path

from config import (
    BOT_NAME, DEFAULT_TOP_K, CORRECTION_MATCH_THRESHOLD, FOUNDRY_DEPLOYMENT,
    PGVECTOR_ENABLED, INCLUDE_TIMINGS,
)
from core import ChatRequest, get_cached_system_prompt, get_cached_llm_temperature
from core.dependencies import get_service, get_rate_limiter
from utils import sanitize_input, timings_payload
from workflow_db import get_workflow_summary, is_question_blocked, find_best_correction, normalize_query
from analytics_db import log_chat
from activity import touch_session
from sessions_db import upsert_visitor_session
from cache import find_cached_answer, record_cache_hit, maybe_promote_to_cache
from observability import create_chat_trace, finalize_trace, flush_safe

try:
    from pgvector_store import pgvector_store
except Exception:
    pgvector_store = None
# ================== IMPORTS ==================


router = APIRouter()


# =========== FUNCTION ===========
# ROLE: Serve frontend index or fallback message
@router.get("/")
def read_index():
    ''' Serve frontend index.html if it exists, otherwise return API status '''

    FRONTEND_DIST = Path("frontend/dist")
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")

    return JSONResponse({"message": f"{BOT_NAME} API is running. Deploy a frontend to serve the UI."})
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return service status with document counts and workflow summary
@router.get("/api/status")
def status():
    ''' Return service readiness, document count, and workflow state '''

    service = get_service()
    workflow = {}
    try:
        workflow = get_workflow_summary()
    except Exception:
        workflow = {}

    return {
        "status": "ready",
        "bot_name": BOT_NAME,
        "documents": len(service.documents),
        "embedded": len(service.embeddings) if hasattr(service.embeddings, '__len__') else 0,
        "reranker_enabled": service.reranker is not None,
        "model": FOUNDRY_DEPLOYMENT,
        "pgvector_enabled": PGVECTOR_ENABLED,
        "workflow": workflow,
    }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Check if service and dependencies are healthy
@router.get("/health")
async def health():
    ''' Return health status of API and pgvector '''

    service = get_service()
    health_result = {"status": "ok", "fastapi": "ok"}

    try:
        if pgvector_store:
            pgv_ok = await run_in_threadpool(pgvector_store.health_check)
            health_result["pgvector"] = "ok" if pgv_ok else "degraded"
    except Exception:
        health_result["pgvector"] = "error"

    health_result["documents_indexed"] = len(service.documents)

    return health_result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Main chat endpoint — runs RAG pipeline and returns answer
@router.post("/api/chat")
async def chat_endpoint(body: ChatRequest, request: Request, background_tasks: BackgroundTasks, _rl=Depends(get_rate_limiter)):
    ''' Process question through RAG pipeline and return answer with sources '''

    service = get_service()
    t_start = time.perf_counter()
    timings = {}

    # FLOW-1: Read session, department, and widget context headers
    session_id = request.headers.get("X-Session-ID") or None
    dept_slug = request.headers.get("X-Department-Slug") or None
    device_hint = request.headers.get("X-Device-Type") or None
    referrer_page = request.headers.get("X-Referrer-Page") or None

    # FLOW-2: Validate and sanitize input
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    # FLOW-2b: Open Langfuse trace for this request — no-op if Langfuse is disabled
    lf_trace = create_chat_trace(question, session_id=session_id, department_slug=dept_slug)

    question = sanitize_input(question)
    if not question:
        raise HTTPException(status_code=400, detail="Invalid input detected")

    # FLOW-3: Check if question is blocked — log matched word for accountability and return early
    matched_word = is_question_blocked(question)
    if matched_word:
        background_tasks.add_task(touch_session, session_id, dept_slug)
        background_tasks.add_task(log_chat, question=question, route="blocked", session_id=session_id, department_slug=dept_slug, blocked_word_matched=matched_word)
        background_tasks.add_task(upsert_visitor_session, session_id, question, "blocked", 0.0, dept_slug, device_hint, referrer_page)
        background_tasks.add_task(finalize_trace, lf_trace, "blocked", 0.0)
        background_tasks.add_task(flush_safe)
        return {"answer": "I'm not able to answer that question.", "sources": [], "blocked": True}

    # FLOW-4: Check if a human correction exists — log correction_id for accountability
    correction = find_best_correction(question, threshold=CORRECTION_MATCH_THRESHOLD)
    if correction:
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        background_tasks.add_task(touch_session, session_id, dept_slug)
        background_tasks.add_task(log_chat, question=question, answer=correction["corrected_answer"], route="correction", response_time_ms=elapsed_ms, session_id=session_id, department_slug=dept_slug, correction_id=correction.get("id"))
        background_tasks.add_task(upsert_visitor_session, session_id, question, "correction", elapsed_ms, dept_slug, device_hint, referrer_page)
        background_tasks.add_task(finalize_trace, lf_trace, "correction", elapsed_ms, correction["corrected_answer"])
        background_tasks.add_task(flush_safe)
        return {
            "answer": correction["corrected_answer"],
            "sources": [{"title": "Verified Answer", "url": "", "category": "correction", "section_type": "exact", "snippet": ""}],
            "route": "correction",
        }

    # FLOW-5: Check question cache — return immediately if hit, no LLM call needed
    cached = find_cached_answer(question)
    if cached:
        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        background_tasks.add_task(touch_session, session_id, dept_slug)
        background_tasks.add_task(log_chat, question=question, answer=cached["answer"], route="cache", response_time_ms=elapsed_ms, session_id=session_id, department_slug=dept_slug)
        background_tasks.add_task(upsert_visitor_session, session_id, question, "cache", elapsed_ms, dept_slug, device_hint, referrer_page)
        background_tasks.add_task(record_cache_hit, cached["matched_norm"])
        background_tasks.add_task(finalize_trace, lf_trace, "cache", elapsed_ms, cached["answer"])
        background_tasks.add_task(flush_safe)
        return {
            "answer": cached["answer"],
            "sources": [{"title": "Cached Answer", "url": "", "category": "cache", "section_type": cached.get("match_type", "exact"), "snippet": ""}],
            "route": "cache",
        }

    # FLOW-6: Run RAG search to find relevant context chunks
    top_k = body.top_k or DEFAULT_TOP_K
    results = await run_in_threadpool(service.search, question, top_k, timings, lf_trace)

    context_parts = [r["text"] for r in results]
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
    context = "\n\n---\n\n".join(context_parts) if context_parts else ""

    # FLOW-7: Generate answer from LLM using retrieved context
    answer = await run_in_threadpool(service.generate_answer, question, context, timings, body.conversation_history, lf_trace)

    total_ms = round((time.perf_counter() - t_start) * 1000, 2)
    timings["total_ms"] = total_ms

    # FLOW-8: Log and check promotion — background tasks so response is not delayed
    question_norm = normalize_query(question)
    background_tasks.add_task(touch_session, session_id, dept_slug)
    background_tasks.add_task(log_chat, question=question, answer=answer, route="rag", sources_count=len(results), response_time_ms=total_ms, session_id=session_id, department_slug=dept_slug)
    background_tasks.add_task(upsert_visitor_session, session_id, question, "rag", total_ms, dept_slug, device_hint, referrer_page)
    background_tasks.add_task(maybe_promote_to_cache, question_norm, question, answer, "rag")
    background_tasks.add_task(finalize_trace, lf_trace, "rag", total_ms, answer)
    background_tasks.add_task(flush_safe)

    # FLOW-9: Build and return response
    response = {"answer": answer, "sources": sources, "route": "rag"}
    if INCLUDE_TIMINGS:
        response["timings"] = timings_payload(timings)

    return response
# =========== FUNCTION ===========
