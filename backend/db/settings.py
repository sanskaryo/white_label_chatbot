# WHAT DOES THIS FILE DO: system settings key-value store and predefined questions lookup

# ================== IMPORTS ==================
from typing import Any, Dict, List

from sqlalchemy import select

from .connection import session_scope
from .models import SystemSetting, PredefinedQuestion
# ================== IMPORTS ==================


# =========== FUNCTION ===========
# ROLE: Get a system setting value by key
def get_system_setting(key: str, default: str = "") -> str:
    ''' Return the stored value for key, or default if key not found '''

    # FLOW-1: Load setting by primary key
    with session_scope() as session:
        row = session.get(SystemSetting, key)

        # FLOW-2: Return value or fall back to default
        return row.value if row else default
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Create or update a system setting value
def set_system_setting(key: str, value: str) -> None:
    ''' Upsert the value for key — creates if missing, updates if exists '''

    # FLOW-1: Load existing setting by key
    with session_scope() as session:
        row = session.get(SystemSetting, key)

        # FLOW-2: Update if exists, otherwise insert new row
        if row:
            row.value = value
        else:
            session.add(SystemSetting(key=key, value=value))
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return all active predefined questions for the chat UI
def get_predefined_questions(limit: int = 100) -> List[Dict[str, Any]]:
    ''' Return active predefined question records ordered by ID '''

    # FLOW-1: Query active questions
    with session_scope() as session:
        rows = session.execute(
            select(PredefinedQuestion).where(PredefinedQuestion.is_active.is_(True)).order_by(PredefinedQuestion.id).limit(limit)
        ).scalars().all()

        # FLOW-2: Return as simple dicts
        return [{"id": r.id, "question": r.question, "category": r.category} for r in rows]
# =========== FUNCTION ===========
