# WHAT DOES THIS FILE DO: Langfuse LLM observability — trace every RAG pipeline call with token counts, latency, and prompt logging

# ================== IMPORTS ==================
import logging
from typing import Any, Dict, List, Optional

from config import (
    LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST,
    LANGFUSE_ENABLED, LANGFUSE_LOG_PROMPTS, FOUNDRY_DEPLOYMENT, MAX_COMPLETION_TOKENS,
)
# ================== IMPORTS ==================


# =========== VARIABLES ===========
logger = logging.getLogger("observability")

try:
    from langfuse import Langfuse
    _HAS_LANGFUSE = True
except ImportError:
    _HAS_LANGFUSE = False
    logger.warning("langfuse package not installed — observability disabled")

_client: Optional[Any] = None
# =========== VARIABLES ===========


# =========== FUNCTION ===========
# ROLE: Initialize Langfuse client on startup — called once from main.py
def init_langfuse() -> None:
    ''' Create and verify the Langfuse client — sets _client to None if credentials missing or auth fails '''

    global _client

    if not LANGFUSE_ENABLED:
        logger.info("Langfuse disabled — set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable")
        return

    if not _HAS_LANGFUSE:
        logger.warning("Langfuse not available — install langfuse>=2.0.0")
        return

    try:
        _client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )

        # FLOW-1: Verify credentials so we fail loud at startup, not silently mid-request
        _client.auth_check()
        logger.info(f"Langfuse connected — host: {LANGFUSE_HOST}")

    except Exception as exc:
        logger.warning(f"Langfuse init failed — observability disabled: {exc}")
        _client = None
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Open a new trace for one chat request — returns trace object or None if disabled
def create_chat_trace(
    question: str,
    session_id: Optional[str] = None,
    department_slug: Optional[str] = None,
) -> Optional[Any]:
    ''' Start a Langfuse trace for a single /api/chat request — returns None when Langfuse is off '''

    if not _client:
        return None

    try:
        return _client.trace(
            name="rag-chat",
            session_id=session_id or "anonymous",
            input={"question": question},
            metadata={"department": department_slug},
            tags=["production"],
        )
    except Exception as exc:
        logger.debug(f"create_chat_trace failed: {exc}")
        return None
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Log a RAG search step as a span on the trace
def log_search_span(
    trace: Optional[Any],
    query: str,
    results: List[Dict[str, Any]],
    top_k: int,
    timings: Dict[str, Any],
) -> None:
    ''' Attach a search span to the trace showing chunks found, top score, and per-step timings '''

    if not trace:
        return

    try:
        span = trace.span(
            name="rag-search",
            input={"query": query, "top_k": top_k},
        )
        span.end(
            output={
                "chunks_found": len(results),
                "top_score": round(results[0].get("score", 0), 3) if results else 0,
            },
            metadata={k: v for k, v in timings.items() if k != "total_ms"},
        )
    except Exception as exc:
        logger.debug(f"log_search_span failed: {exc}")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Log the LLM completion call as a Langfuse generation with token counts
def log_llm_generation(
    trace: Optional[Any],
    messages: List[Dict[str, Any]],
    answer: str,
    temperature: float,
    usage: Optional[Any],
) -> None:
    ''' Attach an LLM generation to the trace — includes prompt, answer, model, and token usage '''

    if not trace:
        return

    try:
        # FLOW-1: Respect privacy flag — skip full prompt if LANGFUSE_LOG_PROMPTS is off
        prompt_input = messages if LANGFUSE_LOG_PROMPTS else [{"role": "user", "content": messages[-1].get("content", "")[:200]}]

        trace.generation(
            name="llm-completion",
            model=FOUNDRY_DEPLOYMENT,
            model_parameters={
                "temperature": temperature,
                "max_tokens": MAX_COMPLETION_TOKENS,
            },
            input=prompt_input,
            output=answer,
            usage={
                "input": getattr(usage, "prompt_tokens", 0) if usage else 0,
                "output": getattr(usage, "completion_tokens", 0) if usage else 0,
                "total": getattr(usage, "total_tokens", 0) if usage else 0,
                "unit": "TOKENS",
            },
        )
    except Exception as exc:
        logger.debug(f"log_llm_generation failed: {exc}")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Close the trace with final route and timing info after the response is sent
def finalize_trace(
    trace: Optional[Any],
    route: str,
    response_time_ms: float,
    answer: str = "",
) -> None:
    ''' Update trace with route, total latency, and answer preview — called as a background task '''

    if not trace:
        return

    try:
        trace.update(
            output={"answer": answer[:400]} if answer else {},
            metadata={"route": route, "response_time_ms": response_time_ms},
        )
    except Exception as exc:
        logger.debug(f"finalize_trace failed: {exc}")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Flush buffered Langfuse events — called as a background task after response is sent
def flush_safe() -> None:
    ''' Send any buffered traces to Langfuse — never blocks the caller, silently skips if disabled '''

    if not _client:
        return

    try:
        _client.flush()
    except Exception as exc:
        logger.debug(f"langfuse flush failed: {exc}")
# =========== FUNCTION ===========
