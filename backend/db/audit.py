# WHAT DOES THIS FILE DO: audit log writing and workflow summary queries

# ================== IMPORTS ==================
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .connection import session_scope
from .models import AuditLog, FlaggedResponse, Correction, UploadDocument
# ================== IMPORTS ==================


# =========== FUNCTION ===========
# ROLE: Write an admin action into the audit trail
def log_audit_action(
    session: Session,
    action: str,
    details: str,
    admin_id: Optional[str] = None,
    role: Optional[str] = None,
) -> None:
    ''' Build and add an AuditLog row to the session — caller handles commit '''

    # FLOW-1: Build the log entry with normalized fields
    log = AuditLog(
        admin_id=(admin_id or "admin").strip(),
        role=(role or "").strip() or None,
        action=action.strip(),
        details=details.strip(),
    )

    # FLOW-2: Add to session, will commit when caller's session_scope exits
    session.add(log)
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Retrieve recent audit log entries for the admin log viewer
def list_audit_logs(limit: int = 100) -> List[Dict[str, Any]]:
    ''' Return audit log records ordered newest first '''

    # FLOW-1: Query logs newest first
    with session_scope() as session:
        rows = session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        ).scalars().all()

        # FLOW-2: Transform to dict with ISO timestamp
        return [
            {"id": r.id, "admin_id": r.admin_id, "action": r.action, "details": r.details,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Pull a quick summary of pending work across the whole system
def get_workflow_summary() -> Dict[str, Any]:
    ''' Return pending flagged count, total flagged, active corrections, and total uploads '''

    # FLOW-1: Query all three counts in a single session
    with session_scope() as session:
        flagged_pending = session.scalar(select(func.count(FlaggedResponse.id)).where(FlaggedResponse.status == "pending")) or 0
        flagged_total = session.scalar(select(func.count(FlaggedResponse.id))) or 0
        corrections_count = session.scalar(select(func.count(Correction.id)).where(Correction.is_active.is_(True))) or 0
        uploads_count = session.scalar(select(func.count(UploadDocument.id)).where(UploadDocument.is_active.is_(True))) or 0

    # FLOW-2: Return as nested structure that matches what chat.py status endpoint expects
    return {
        "flagged": {"pending": flagged_pending, "total": flagged_total},
        "corrections": {"active": corrections_count},
        "uploads": {"total": uploads_count},
    }
# =========== FUNCTION ===========
