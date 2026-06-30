# WHAT DOES THIS FILE DO: Role-Based Access Control endpoint — returns user role and permissions from DB

# ================== IMPORTS ==================
from fastapi import APIRouter, Request
from sqlalchemy import select, func

from workflow_db import session_scope, AdminUser, Department, FlaggedResponse, Correction
# ================== IMPORTS ==================


router = APIRouter()


# =========== FUNCTION ===========
# ROLE: Return current user's role and permissions based on their email
@router.get("/me")
async def get_current_user_role(request: Request):
    ''' Look up user in DB by email and return their role, department, and pending counts '''

    # FLOW-1: Extract email from request header
    email = request.headers.get("X-User-Email", "").strip().lower()

    # FLOW-2: Return null role if no email provided — not logged in
    if not email:
        return {"role": None, "email": None, "department_id": None, "department_name": None, "department_slug": None, "full_name": None, "pending_counts": {}}

    # FLOW-3: Look up user in admin_users table
    with session_scope() as session:
        user = session.execute(
            select(AdminUser).where(AdminUser.email == email)
        ).scalars().first()

        # FLOW-4: Return null role if user not registered or deactivated
        if not user or not user.is_active:
            return {"role": None, "email": email, "department_id": None, "department_name": None, "department_slug": None, "full_name": None, "pending_counts": {}}

        # FLOW-5: Load department info if user is linked to one
        dept_name = None
        dept_slug = None
        if user.department_id:
            dept = session.get(Department, user.department_id)
            if dept:
                dept_name = dept.name
                dept_slug = dept.slug

        # FLOW-6: Get pending counts for the UI badge indicators
        flagged_pending = session.scalar(
            select(func.count(FlaggedResponse.id)).where(FlaggedResponse.status == "pending")
        ) or 0
        corrections_pending = session.scalar(
            select(func.count(Correction.id)).where(Correction.is_active.is_(True))
        ) or 0

        # FLOW-7: Build and return full user context
        return {
            "role": user.role,
            "email": user.email,
            "full_name": user.full_name,
            "department_id": user.department_id,
            "department_name": dept_name,
            "department_slug": dept_slug,
            "institute_name": None,
            "pending_counts": {
                "flagged_responses": flagged_pending,
                "corrections": corrections_pending,
            },
        }
# =========== FUNCTION ===========
