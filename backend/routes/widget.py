# WHAT DOES THIS FILE DO: widget config endpoints — one public resolver the embedded widget calls on load, plus admin CRUD

# ================== IMPORTS ==================
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from workflow_db import (
    get_widget_config, list_widget_configs, upsert_widget_config, delete_widget_config,
)
# ================== IMPORTS ==================


# Public router: no /api/admin prefix — the embedded widget hits this without auth
public_router = APIRouter()

# Admin router: mounted under /api/admin alongside the other admin routers
admin_router = APIRouter()

_VALID_POSITIONS = {"bottom-right", "bottom-left"}


# =========== SCHEMA ===========
class WidgetConfigBody(BaseModel):
    department_slug: Optional[str] = None        # None = global default config
    bot_name: Optional[str] = None
    welcome_message: Optional[str] = None
    starter_questions: Optional[List[str]] = None
    theme_color: Optional[str] = None
    accent_color: Optional[str] = None
    position: Optional[str] = None
    is_active: Optional[bool] = None
# =========== SCHEMA ===========


# =========== FUNCTION ===========
# ROLE: Public config the widget fetches on page load — never 404s, always returns a usable config
@public_router.get("/api/widget-config")
def widget_config_public(department_slug: Optional[str] = Query(None)) -> Dict[str, Any]:
    ''' Resolve config for a department: dept-specific → global → built-in defaults. Always returns 200 '''

    return get_widget_config(department_slug=department_slug)
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: List every saved widget config for the admin panel
@admin_router.get("/widget-configs")
def widget_configs_list() -> Dict[str, Any]:
    ''' Return all saved configs, global first then departments '''

    return {"items": list_widget_configs()}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Create or update a config (upsert by department_slug)
@admin_router.post("/widget-configs")
def widget_config_upsert(body: WidgetConfigBody) -> Dict[str, Any]:
    ''' Create a new config or patch the existing one for this department_slug '''

    if body.position is not None and body.position not in _VALID_POSITIONS:
        raise HTTPException(status_code=400, detail=f"position must be one of: {', '.join(sorted(_VALID_POSITIONS))}")

    return upsert_widget_config(
        department_slug=body.department_slug,
        bot_name=body.bot_name,
        welcome_message=body.welcome_message,
        starter_questions=body.starter_questions,
        theme_color=body.theme_color,
        accent_color=body.accent_color,
        position=body.position,
        is_active=body.is_active,
    )
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Get the saved config for a single department
@admin_router.get("/widget-configs/{department_slug}")
def widget_config_get(department_slug: str) -> Dict[str, Any]:
    ''' Return the resolved config for a department (falls back to global/defaults) '''

    return get_widget_config(department_slug=department_slug)
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Delete a department config so it reverts to the global default
@admin_router.delete("/widget-configs/{department_slug}")
def widget_config_delete(department_slug: str) -> Dict[str, Any]:
    ''' Hard-delete a department config — that department reverts to the global config '''

    ok = delete_widget_config(department_slug)
    if not ok:
        raise HTTPException(status_code=404, detail="widget config not found for that department")

    return {"ok": True, "department_slug": department_slug}
# =========== FUNCTION ===========
