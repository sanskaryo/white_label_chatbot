# WHAT DOES THIS FILE DO: admin user CRUD — list, lookup, create, update, and deactivate users

# ================== IMPORTS ==================
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from .connection import session_scope
from .models import AdminUser, Department
from .audit import log_audit_action
# ================== IMPORTS ==================


# =========== FUNCTION ===========
# ROLE: Return all users with their department names
def list_users(limit: int = 100) -> List[Dict[str, Any]]:
    ''' Return user records ordered newest first, including department name if linked '''

    # FLOW-1: Query all users
    with session_scope() as session:
        rows = session.execute(
            select(AdminUser).order_by(AdminUser.created_at.desc()).limit(limit)
        ).scalars().all()

        # FLOW-2: Load department name per user
        result = []
        for r in rows:
            dept_name = None
            if r.department_id:
                dept = session.get(Department, r.department_id)
                dept_name = dept.name if dept else None

            result.append({
                "id": r.id, "email": r.email, "role": r.role,
                "full_name": r.full_name, "is_active": r.is_active,
                "department_id": r.department_id, "department_name": dept_name,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Fetch a single user by their email address
def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    ''' Return user dict for given email, or None if not found '''

    # FLOW-1: Normalize email and query
    email = email.strip().lower()
    with session_scope() as session:
        row = session.execute(
            select(AdminUser).where(AdminUser.email == email)
        ).scalars().first()

        if not row:
            return None

        # FLOW-2: Load department name and slug if user is linked to one
        dept_name = None
        dept_slug = None
        if row.department_id:
            dept = session.get(Department, row.department_id)
            if dept:
                dept_name = dept.name
                dept_slug = dept.slug

        return {
            "id": row.id, "email": row.email, "role": row.role,
            "full_name": row.full_name, "is_active": row.is_active,
            "department_id": row.department_id, "department_name": dept_name,
            "department_slug": dept_slug,
        }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Create a new admin user record (invite a user by email)
def create_user(email: str, role: str = "dept_admin", full_name: str = "", department_id: Optional[int] = None, created_by: str = "admin") -> Dict[str, Any]:
    ''' Insert user record and return it, or return error dict if email already exists '''

    # FLOW-1: Normalize email
    email = email.strip().lower()

    # FLOW-2: Check for duplicate email
    with session_scope() as session:
        existing = session.execute(
            select(AdminUser).where(AdminUser.email == email)
        ).scalars().first()

        if existing:
            return {"error": "User with this email already exists"}

        # FLOW-3: Insert new user and log
        row = AdminUser(
            email=email, role=role,
            full_name=full_name.strip() or None,
            department_id=department_id,
            created_by=created_by, is_active=True,
        )
        session.add(row)
        log_audit_action(session, "user_created", f"email={email} role={role}", admin_id=created_by)

        # FLOW-4: Flush and return result
        session.flush()
        return {"id": row.id, "email": row.email, "role": row.role, "full_name": row.full_name}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Update a user's role, full name, or department assignment
def update_user(user_id: int, role: str = "", full_name: str = "", department_id: Optional[int] = None, updated_by: str = "admin") -> Dict[str, Any]:
    ''' Apply provided field updates and return the updated user record '''

    # FLOW-1: Load user by ID
    with session_scope() as session:
        row = session.get(AdminUser, user_id)
        if not row:
            return {"error": "Not found"}

        # FLOW-2: Only update fields that were actually provided
        if role:
            row.role = role
        if full_name is not None:
            row.full_name = full_name.strip() or None
        if department_id is not None:
            row.department_id = department_id

        # FLOW-3: Log and flush
        log_audit_action(session, "user_updated", f"user_id={user_id}", admin_id=updated_by)
        session.flush()

        return {"id": row.id, "email": row.email, "role": row.role, "full_name": row.full_name, "department_id": row.department_id}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Deactivate an admin user so they can no longer access the dashboard
def deactivate_user(user_id: int, deactivated_by: str = "admin") -> bool:
    ''' Mark user inactive and log action; return True if found '''

    # FLOW-1: Load user by ID
    with session_scope() as session:
        row = session.get(AdminUser, user_id)
        if not row:
            return False

        # FLOW-2: Mark inactive and log
        row.is_active = False
        log_audit_action(session, "user_deactivated", f"user_id={user_id} email={row.email}", admin_id=deactivated_by)

        return True
# =========== FUNCTION ===========
