# WHAT DOES THIS FILE DO: CRUD for TestCase — save, list, and deactivate QA test cases

# ================== IMPORTS ==================
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from .connection import session_scope
from .models import TestCase
# ================== IMPORTS ==================


# =========== FUNCTION ===========
# ROLE: Return all test cases with optional filters
def list_test_cases(
    department_slug: Optional[str] = None,
    expected_route: Optional[str] = None,
    active_only: bool = True,
) -> List[Dict[str, Any]]:
    ''' Fetch test cases ordered newest first, filtered by dept/route/active state '''

    with session_scope() as session:
        stmt = select(TestCase)

        if active_only:
            stmt = stmt.where(TestCase.is_active == True)
        if department_slug:
            stmt = stmt.where(TestCase.department_slug == department_slug)
        if expected_route:
            stmt = stmt.where(TestCase.expected_route == expected_route)

        stmt = stmt.order_by(TestCase.created_at.desc())
        rows = session.execute(stmt).scalars().all()
        return [_row_to_dict(r) for r in rows]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Insert a new test case and return it
def create_test_case(
    question: str,
    label: Optional[str] = None,
    department_slug: Optional[str] = None,
    expected_route: Optional[str] = None,
    expected_answer_contains: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    ''' Create and persist a test case, return the saved row as a dict '''

    with session_scope() as session:
        row = TestCase(
            question=question,
            label=label,
            department_slug=department_slug,
            expected_route=expected_route,
            expected_answer_contains=expected_answer_contains,
            created_by=created_by,
        )
        session.add(row)
        session.flush()
        return _row_to_dict(row)
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Soft-delete a test case by id
def deactivate_test_case(case_id: int) -> bool:
    ''' Set is_active=False — row stays in DB for audit trail, returns False if not found '''

    with session_scope() as session:
        row = session.get(TestCase, case_id)
        if not row:
            return False
        row.is_active = False
        return True
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Serialize ORM row to plain dict
def _row_to_dict(row: TestCase) -> Dict[str, Any]:
    return {
        "id": row.id,
        "label": row.label,
        "question": row.question,
        "department_slug": row.department_slug,
        "expected_route": row.expected_route,
        "expected_answer_contains": row.expected_answer_contains,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "is_active": row.is_active,
    }
# =========== FUNCTION ===========
