# WHAT DOES THIS FILE DO: department CRUD — slugify, list, create, update, and soft-delete

# ================== IMPORTS ==================
import re
from typing import Any, Dict, List

from sqlalchemy import select

from .connection import session_scope
from .models import Department
from .audit import log_audit_action
# ================== IMPORTS ==================


# =========== FUNCTION ===========
# ROLE: Convert a department name to a URL-friendly slug
def _slugify(name: str) -> str:
    ''' Return lowercase hyphenated slug from name — e.g. "Computer Science" -> "computer-science" '''

    # FLOW-1: Lowercase and strip whitespace
    cleaned = name.strip().lower()

    # FLOW-2: Replace anything that isnt alphanumeric with a hyphen
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)

    # FLOW-3: Strip leading and trailing hyphens
    return cleaned.strip("-")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return all active departments ordered alphabetically
def list_departments() -> List[Dict[str, Any]]:
    ''' Return active department records with ISO timestamps '''

    # FLOW-1: Query active departments by name
    with session_scope() as session:
        rows = session.execute(
            select(Department).where(Department.is_active.is_(True)).order_by(Department.name)
        ).scalars().all()

        # FLOW-2: Return as list of dicts
        return [
            {"id": r.id, "name": r.name, "slug": r.slug, "description": r.description,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Create a new department record
def create_department(name: str, description: str = "", created_by: str = "admin") -> Dict[str, Any]:
    ''' Insert department, log the action, return created record '''

    # FLOW-1: Generate slug from the department name
    slug = _slugify(name)

    # FLOW-2: Insert and log
    with session_scope() as session:
        row = Department(name=name.strip(), slug=slug, description=description.strip() or None, created_by=created_by, is_active=True)
        session.add(row)
        log_audit_action(session, "department_created", f"dept: {name}", admin_id=created_by)

        # FLOW-3: Flush to get the assigned ID
        session.flush()
        return {"id": row.id, "name": row.name, "slug": row.slug, "description": row.description}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Update a department's name or description
def update_department(dept_id: int, name: str = "", description: str = "", updated_by: str = "admin") -> Dict[str, Any]:
    ''' Apply name/description updates if provided, log action, return updated record '''

    # FLOW-1: Load department by ID
    with session_scope() as session:
        row = session.get(Department, dept_id)
        if not row:
            return {"error": "Not found"}

        # FLOW-2: Apply only fields that were provided
        if name:
            row.name = name.strip()
            row.slug = _slugify(name)
        if description is not None:
            row.description = description.strip() or None

        # FLOW-3: Log and flush
        log_audit_action(session, "department_updated", f"dept_id={dept_id}", admin_id=updated_by)
        session.flush()

        return {"id": row.id, "name": row.name, "slug": row.slug, "description": row.description}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Soft-delete a department
def delete_department(dept_id: int, deleted_by: str = "admin") -> bool:
    ''' Mark department inactive and log action; return True if found '''

    # FLOW-1: Load department by ID
    with session_scope() as session:
        row = session.get(Department, dept_id)
        if not row:
            return False

        # FLOW-2: Mark inactive and log
        row.is_active = False
        log_audit_action(session, "department_deleted", f"dept_id={dept_id}", admin_id=deleted_by)

        return True
# =========== FUNCTION ===========
