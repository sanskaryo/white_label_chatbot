# WHAT DOES THIS FILE DO: CRUD for WidgetConfig — per-department chatbot widget appearance and behavior settings

# ================== IMPORTS ==================
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from .connection import session_scope
from .models import WidgetConfig
# ================== IMPORTS ==================


# =========== DEFAULTS ===========
# Returned when no DB config exists at all — keeps the public endpoint from ever 404-ing
_DEFAULT_CONFIG: Dict[str, Any] = {
    "department_slug": None,
    "bot_name": "AskGLA",
    "welcome_message": "Hi! I'm AskGLA. How can I help you today?",
    "starter_questions": [
        "What courses does GLA offer?",
        "How do I apply for admission?",
        "Tell me about scholarships",
        "What are the placement stats?",
    ],
    "theme_color": "#1a3a2a",
    "accent_color": "#c9a227",
    "position": "bottom-right",
    "is_active": True,
}
# =========== DEFAULTS ===========


# =========== FUNCTION ===========
# ROLE: Resolve the config for a department — dept-specific → global → hardcoded default
def get_widget_config(department_slug: Optional[str] = None) -> Dict[str, Any]:
    ''' Public resolver — never returns None: falls back to global config, then to built-in defaults '''

    with session_scope() as session:
        # FLOW-1: Try the department-specific config first
        if department_slug:
            row = session.execute(
                select(WidgetConfig).where(
                    WidgetConfig.department_slug == department_slug,
                    WidgetConfig.is_active == True,
                )
            ).scalars().first()
            if row:
                return _row_to_dict(row)

        # FLOW-2: Fall back to the global config (department_slug IS NULL)
        global_row = session.execute(
            select(WidgetConfig).where(
                WidgetConfig.department_slug.is_(None),
                WidgetConfig.is_active == True,
            )
        ).scalars().first()
        if global_row:
            return _row_to_dict(global_row)

    # FLOW-3: Nothing saved yet — return built-in defaults
    return dict(_DEFAULT_CONFIG)
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: List every saved widget config for the admin panel
def list_widget_configs() -> List[Dict[str, Any]]:
    ''' Return all configs, global first then departments alphabetically '''

    with session_scope() as session:
        rows = session.execute(
            select(WidgetConfig).order_by(
                WidgetConfig.department_slug.is_(None).desc(),
                WidgetConfig.department_slug,
            )
        ).scalars().all()
        return [_row_to_dict(r) for r in rows]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Create or update a config by department_slug (upsert)
def upsert_widget_config(
    department_slug: Optional[str] = None,
    bot_name: Optional[str] = None,
    welcome_message: Optional[str] = None,
    starter_questions: Optional[List[str]] = None,
    theme_color: Optional[str] = None,
    accent_color: Optional[str] = None,
    position: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Dict[str, Any]:
    ''' Insert a new config or patch the existing one for this department_slug — only provided fields change '''

    slug = (department_slug or "").strip() or None

    with session_scope() as session:
        # FLOW-1: Find existing config for this slug (global slug is None)
        if slug is None:
            existing = session.execute(
                select(WidgetConfig).where(WidgetConfig.department_slug.is_(None))
            ).scalars().first()
        else:
            existing = session.execute(
                select(WidgetConfig).where(WidgetConfig.department_slug == slug)
            ).scalars().first()

        # FLOW-2: Update existing row — only overwrite fields that were supplied
        if existing:
            if bot_name is not None:
                existing.bot_name = bot_name
            if welcome_message is not None:
                existing.welcome_message = welcome_message
            if starter_questions is not None:
                existing.starter_questions = starter_questions[:4]
            if theme_color is not None:
                existing.theme_color = theme_color
            if accent_color is not None:
                existing.accent_color = accent_color
            if position is not None:
                existing.position = position
            if is_active is not None:
                existing.is_active = is_active
            session.flush()
            return _row_to_dict(existing)

        # FLOW-3: Create a fresh row, filling unset fields from defaults
        row = WidgetConfig(
            department_slug=slug,
            bot_name=bot_name if bot_name is not None else _DEFAULT_CONFIG["bot_name"],
            welcome_message=welcome_message if welcome_message is not None else _DEFAULT_CONFIG["welcome_message"],
            starter_questions=(starter_questions[:4] if starter_questions is not None else list(_DEFAULT_CONFIG["starter_questions"])),
            theme_color=theme_color if theme_color is not None else _DEFAULT_CONFIG["theme_color"],
            accent_color=accent_color if accent_color is not None else _DEFAULT_CONFIG["accent_color"],
            position=position if position is not None else _DEFAULT_CONFIG["position"],
            is_active=is_active if is_active is not None else True,
        )
        session.add(row)
        session.flush()
        return _row_to_dict(row)
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Delete a department config so it reverts to the global default
def delete_widget_config(department_slug: str) -> bool:
    ''' Hard-delete the config for a department, returns False if none found '''

    slug = (department_slug or "").strip()
    if not slug:
        return False

    with session_scope() as session:
        row = session.execute(
            select(WidgetConfig).where(WidgetConfig.department_slug == slug)
        ).scalars().first()
        if not row:
            return False
        session.delete(row)
        return True
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Serialize ORM row to plain dict
def _row_to_dict(row: WidgetConfig) -> Dict[str, Any]:
    return {
        "id": row.id,
        "department_slug": row.department_slug,
        "bot_name": row.bot_name,
        "welcome_message": row.welcome_message,
        "starter_questions": row.starter_questions or [],
        "theme_color": row.theme_color,
        "accent_color": row.accent_color,
        "position": row.position,
        "is_active": row.is_active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
# =========== FUNCTION ===========
