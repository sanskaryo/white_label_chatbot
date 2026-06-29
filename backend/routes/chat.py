# WHAT DOES THIS FILE DO: Chat, status, and health endpoints

# ================== IMPORTS ==================
import time
from fastapi import APIRouter, HTTPException, Request, Depends
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
from workflow_db import (
    get_workflow_summary, is_question_blocked, find_best_correction
)

try:
    from pgvector_store import pgvector_store
except Exception:
    pgvector_store = None
# ================== IMPORTS ==================

router = APIRouter()


@router.get("/")
def read_index():
    FRONTEND_DIST = Path("frontend/dist")
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    return JSONResponse({"message": f"{BOT_NAME} API is running. Deploy a frontend to serve the UI."})


@router.get("/api/status")
def status():
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


@router.get("/health")
async def health():
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


@router.post("/api/chat")
async def chat_endpoint(body: ChatRequest, request: Request, _rl=Depends(get_rate_limiter)):
    service = get_service()
    t_start = time.perf_counter()
    timings = {}

    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    question = sanitize_input(question)
    if not question:
        raise HTTPException(status_code=400, detail="Invalid input detected")

    if is_question_blocked(question):
        return {"answer": "I'm not able to answer that question.", "sources": [], "blocked": True}

    correction = find_best_correction(question, threshold=CORRECTION_MATCH_THRESHOLD)
    if correction:
        return {
            "answer": correction["corrected_answer"],
            "sources": [{"title": "Verified Answer", "url": "", "category": "correction", "section_type": "exact", "snippet": ""}],
            "route": "correction",
        }

    top_k = body.top_k or DEFAULT_TOP_K
    results = await run_in_threadpool(service.search, question, top_k, timings)

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

    answer = await run_in_threadpool(service.generate_answer, question, context, timings, body.conversation_history)

    total_ms = round((time.perf_counter() - t_start) * 1000, 2)
    timings["total_ms"] = total_ms

    response = {
        "answer": answer,
        "sources": sources,
        "route": "rag",
    }

    if INCLUDE_TIMINGS:
        response["timings"] = timings_payload(timings)

    return response
