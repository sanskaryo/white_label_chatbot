# WHAT DOES THIS FILE DO: Middleware, rate limiting, and caching for FastAPI

# ================== IMPORTS ==================
import logging
import threading
import time
from contextlib import contextmanager
from typing import Optional

from fastapi import HTTPException, Request
from config import DISABLE_RATE_LIMIT, RATE_LIMIT_CALLS, RATE_LIMIT_SECONDS
from core.constants import DEFAULT_SYSTEM_PROMPT
from workflow_db import get_system_setting, set_system_setting
# ================== IMPORTS ==================


# =========== VARIABLES : logging ===========
logger = logging.getLogger("white_label")
# =========== VARIABLES : logging ===========


# =========== RATE LIMITER ===========

class RateLimiter:
    ''' Track requests per IP and enforce rate limits using sliding window '''

    def __init__(self, max_requests: int = RATE_LIMIT_CALLS, window_seconds: int = RATE_LIMIT_SECONDS):
        ''' Initialize rate limiter with request limit and time window '''
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}
        self.lock = threading.Lock()

    def __call__(self, request: Request) -> None:
        ''' Check if request exceeds rate limit; raise HTTPException if limit hit '''

        # FLOW-1: Skip rate limiting if disabled via DISABLE_RATE_LIMIT env var
        if DISABLE_RATE_LIMIT:
            return

        # FLOW-2: Get client IP and current timestamp
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # FLOW-3: Remove old requests outside the sliding window
        with self.lock:
            if client_ip in self.requests:
                self.requests[client_ip] = [ts for ts in self.requests[client_ip] if now - ts < self.window_seconds]

            # FLOW-4: Check if request count for this IP exceeds limit
            if client_ip in self.requests and len(self.requests[client_ip]) >= self.max_requests:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            # FLOW-5: Record this request timestamp for future checks
            if client_ip not in self.requests:
                self.requests[client_ip] = []
            self.requests[client_ip].append(now)

# =========== RATE LIMITER ===========


# =========== SYSTEM PROMPT CACHE ===========

# ROLE: Global variables for caching system prompt and LLM temperature settings
_system_prompt_cache = None
_system_prompt_lock = threading.Lock()
_llm_temperature_cache = 0.2
_llm_temperature_lock = threading.Lock()
_llm_temperature_last_fetch = 0.0
_LLM_TEMP_CACHE_TTL = 60.0


# ROLE: Get system prompt from cache or database
def get_cached_system_prompt() -> str:
    ''' Return cached system prompt or fetch from database if not cached '''

    global _system_prompt_cache

    # FLOW-1: Acquire lock to prevent race conditions
    with _system_prompt_lock:
        # FLOW-2: Return cached value if already loaded
        if _system_prompt_cache is not None:
            return _system_prompt_cache

        # FLOW-3: Load from database and cache the result
        val = get_system_setting("system_prompt", DEFAULT_SYSTEM_PROMPT)
        _system_prompt_cache = val

        return val


# ROLE: Clear system prompt cache to force reload on next access
def invalidate_system_prompt_cache() -> None:
    ''' Clear cached system prompt so it reloads from database '''

    global _system_prompt_cache

    with _system_prompt_lock:
        _system_prompt_cache = None


# ROLE: Get LLM temperature with TTL-based caching
def get_cached_llm_temperature() -> float:
    ''' Return cached temperature or fetch from database with TTL '''

    global _llm_temperature_cache, _llm_temperature_last_fetch

    # FLOW-1: Check if cache is valid (within TTL)
    with _llm_temperature_lock:
        now = time.time()
        if _llm_temperature_last_fetch > 0 and (now - _llm_temperature_last_fetch) < _LLM_TEMP_CACHE_TTL:
            return _llm_temperature_cache

        # FLOW-2: Fetch from database if cache expired
        try:
            val = float(get_system_setting("llm_temperature", "0.2"))
        except (ValueError, TypeError):
            val = 0.2

        # FLOW-3: Clamp temperature to valid range 0.0-1.0
        val = max(0.0, min(1.0, val))  # USE: Clamp to valid LLM temperature range

        # FLOW-4: Update cache and timestamp
        _llm_temperature_cache = val
        _llm_temperature_last_fetch = now

        return val

# =========== SYSTEM PROMPT CACHE ===========
