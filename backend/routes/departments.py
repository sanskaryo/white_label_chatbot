# WHAT DOES THIS FILE DO: Department management endpoints for creating and organizing departments

# ================== IMPORTS ==================
from fastapi import APIRouter, HTTPException, Request

from workflow_db import list_departments, create_department, update_department, delete_department
# ================== IMPORTS ==================


router = APIRouter()


# =========== FUNCTION ===========
# ROLE: List all active departments
@router.get("/departments")
def list_departments_endpoint():
    ''' Return list of all active departments '''
    return {"items": list_departments()}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Create a new department
@router.post("/departments")
async def create_department_endpoint(request: Request):
    ''' Create department from request body and return created record '''

    # FLOW-1: Parse request body
    data = await request.json()
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    # FLOW-2: Get optional fields
    description = (data.get("description") or "").strip()
    created_by = request.headers.get("X-User-Email", "admin")

    # FLOW-3: Try creating department, catch duplicate name
    try:
        result = create_department(name=name, description=description, created_by=created_by)
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Department with this name already exists")
        raise HTTPException(status_code=500, detail="Failed to create department")

    return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Update department name or description
@router.put("/departments/{dept_id}")
async def update_department_endpoint(dept_id: int, request: Request):
    ''' Update department fields and return updated record '''

    # FLOW-1: Parse request body
    data = await request.json()
    name = (data.get("name") or "").strip()
    description = data.get("description", "")
    updated_by = request.headers.get("X-User-Email", "admin")

    # FLOW-2: Run update and check if found
    result = update_department(dept_id=dept_id, name=name, description=description, updated_by=updated_by)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Delete a department by ID
@router.delete("/departments/{dept_id}")
def delete_department_endpoint(dept_id: int, request: Request):
    ''' Soft-delete department and return confirmation '''

    # FLOW-1: Get who is deleting
    deleted_by = request.headers.get("X-User-Email", "admin")

    # FLOW-2: Run delete and check if found
    success = delete_department(dept_id=dept_id, deleted_by=deleted_by)
    if not success:
        raise HTTPException(status_code=404, detail="Department not found")

    return {"deleted": True, "id": dept_id}
# =========== FUNCTION ===========
