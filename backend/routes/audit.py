# WHAT DOES THIS FILE DO: Audit log viewing endpoints

# ================== IMPORTS ==================
from fastapi import APIRouter
from workflow_db import list_audit_logs
# ================== IMPORTS ==================

router = APIRouter()


# ROLE: List audit log entries
@router.get("/audit-logs")
def list_audit_logs_endpoint(limit: int = 100):
    ''' Return audit log entries tracking admin actions '''
    return {"items": list_audit_logs(limit=limit)}
