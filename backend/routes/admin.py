# WHAT DOES THIS FILE DO: Admin configuration endpoints (system prompt, temperature)

# ================== IMPORTS ==================
import time
from fastapi import APIRouter, HTTPException, Request

from core import (
    get_cached_system_prompt, invalidate_system_prompt_cache,
    get_cached_llm_temperature, DEFAULT_SYSTEM_PROMPT
)
from core.middleware import _llm_temperature_cache, _llm_temperature_last_fetch, _llm_temperature_lock
from workflow_db import get_system_setting, set_system_setting, get_predefined_questions
# ================== IMPORTS ==================

router = APIRouter()


# ROLE: Get bot configuration and LLM settings
@router.get("/config")
def get_config():
    ''' Return bot identity, system prompt, and temperature setting '''
    return {
        "bot_name": get_system_setting("bot_name", "Bot"),
        "bot_description": get_system_setting("bot_description", ""),
        "system_prompt": get_cached_system_prompt(),
        "llm_temperature": get_cached_llm_temperature(),
    }


# ROLE: Get current system prompt
@router.get("/system-prompt")
def get_system_prompt_endpoint():
    ''' Return current and default system prompts '''
    return {"system_prompt": get_cached_system_prompt(), "default": DEFAULT_SYSTEM_PROMPT}


# ROLE: Update system prompt
@router.post("/system-prompt")
async def update_system_prompt_endpoint(request: Request):
    ''' Update system prompt, invalidate cache, and return confirmation '''

    # FLOW-1: Parse request and validate input
    data = await request.json()
    new_prompt = data.get("system_prompt", "").strip()
    if not new_prompt:
        raise HTTPException(status_code=400, detail="system_prompt is required")

    # FLOW-2: Save to database and clear cache
    set_system_setting("system_prompt", new_prompt)
    invalidate_system_prompt_cache()

    return {"status": "updated", "length": len(new_prompt)}


# ROLE: Get LLM temperature setting
@router.get("/temperature")
def get_temperature_endpoint():
    ''' Return current LLM temperature '''
    return {"temperature": get_cached_llm_temperature()}


# ROLE: Update LLM temperature
@router.post("/temperature")
async def update_temperature_endpoint(request: Request):
    ''' Update temperature, clamp to 0.0-1.0 range, and update cache '''

    # FLOW-1: Parse and validate temperature value
    data = await request.json()
    temp = data.get("temperature", 0.2)
    temp = max(0.0, min(1.0, float(temp)))  # USE: Clamp to valid range

    # FLOW-2: Save to database
    set_system_setting("llm_temperature", str(temp))

    # FLOW-3: Update in-memory cache with timestamp
    global _llm_temperature_cache, _llm_temperature_last_fetch
    with _llm_temperature_lock:
        _llm_temperature_cache = temp
        _llm_temperature_last_fetch = time.time()

    return {"status": "updated", "temperature": temp}


# ROLE: List predefined questions
@router.get("/predefined-questions")
def predefined_questions_endpoint():
    ''' Return list of pre-configured questions for the UI '''
    return {"items": get_predefined_questions()}
