# WHAT DOES THIS FILE DO: Admin user management endpoints for inviting and managing users

# ================== IMPORTS ==================
from fastapi import APIRouter, HTTPException, Request

from workflow_db import list_users, create_user, update_user, deactivate_user, get_user_by_email
# ================== IMPORTS ==================


router = APIRouter()


# =========== FUNCTION ===========
# ROLE: List all users in the system
@router.get("/users")
def list_users_endpoint(limit: int = 100):
    ''' Return all admin users with their department info '''
    return {"items": list_users(limit=limit)}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Create or invite a new admin user
@router.post("/users")
async def create_user_endpoint(request: Request):
    ''' Invite a new user by email with role and optional department '''

    # FLOW-1: Parse request body
    data = await request.json()
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    # FLOW-2: Get optional fields with defaults
    role = (data.get("role") or "dept_admin").strip()
    full_name = (data.get("full_name") or "").strip()
    department_id = data.get("department_id")
    created_by = request.headers.get("X-User-Email", "admin")

    # FLOW-3: Validate role value
    allowed_roles = {"super_admin", "dept_admin"}
    if role not in allowed_roles:
        raise HTTPException(status_code=400, detail=f"role must be one of: {', '.join(allowed_roles)}")

    # FLOW-4: Create user and check for errors
    result = create_user(
        email=email, role=role, full_name=full_name,
        department_id=department_id, created_by=created_by
    )
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])

    return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Get a single user by their database ID
@router.get("/users/{user_id}")
def get_user_endpoint(user_id: int):
    ''' Return user record for given ID '''

    # FLOW-1: Import and query by ID via session
    from workflow_db import session_scope, AdminUser, Department
    from sqlalchemy import select

    with session_scope() as session:
        row = session.get(AdminUser, user_id)
        if not row or not row.is_active:
            raise HTTPException(status_code=404, detail="User not found")

        # FLOW-2: Load department name if linked
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
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Update a user's role, name, or department assignment
@router.put("/users/{user_id}")
async def update_user_endpoint(user_id: int, request: Request):
    ''' Update user record and return updated fields '''

    # FLOW-1: Parse request body
    data = await request.json()
    role = (data.get("role") or "").strip()
    full_name = data.get("full_name", "")
    department_id = data.get("department_id")
    updated_by = request.headers.get("X-User-Email", "admin")

    # FLOW-2: Validate role if provided
    if role:
        allowed_roles = {"super_admin", "dept_admin"}
        if role not in allowed_roles:
            raise HTTPException(status_code=400, detail=f"role must be one of: {', '.join(allowed_roles)}")

    # FLOW-3: Run update and check if found
    result = update_user(
        user_id=user_id, role=role, full_name=full_name,
        department_id=department_id, updated_by=updated_by
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Deactivate a user account so they can no longer access admin
@router.delete("/users/{user_id}")
def deactivate_user_endpoint(user_id: int, request: Request):
    ''' Soft-delete user and return confirmation '''

    # FLOW-1: Get who is doing the deactivation
    deactivated_by = request.headers.get("X-User-Email", "admin")

    # FLOW-2: Run deactivation and check if found
    success = deactivate_user(user_id=user_id, deactivated_by=deactivated_by)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return {"deactivated": True, "id": user_id}
# =========== FUNCTION ===========
