# WHAT DOES THIS FILE DO: tester page endpoints — run questions with pass/fail assertions, save test cases, run regression suites. no rate limit, nothing logged.

# ================== IMPORTS ==================
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from config import DEFAULT_TOP_K, CORRECTION_MATCH_THRESHOLD
from core.dependencies import get_service
from utils import sanitize_input
from workflow_db import is_question_blocked, find_best_correction, normalize_query
from cache import find_cached_answer
from db import list_test_cases, create_test_case, deactivate_test_case
# ================== IMPORTS ==================


router = APIRouter()

_VALID_ROUTES = {"rag", "correction", "cache", "blocked"}
_SUITE_CASE_LIMIT = 100


# =========== SCHEMA ===========
class TestRunBody(BaseModel):
    question: str
    department_slug: Optional[str] = None
    expected_route: Optional[str] = None
    expected_answer_contains: Optional[str] = None


class TestCaseBody(BaseModel):
    question: str
    label: Optional[str] = None
    department_slug: Optional[str] = None
    expected_route: Optional[str] = None
    expected_answer_contains: Optional[str] = None
    created_by: Optional[str] = None


class SuiteRunBody(BaseModel):
    department_slug: Optional[str] = None
# =========== SCHEMA ===========


# =========== FUNCTION ===========
# ROLE: Compute pass/fail/info given actual results and the test case expectations
def _assess(
    actual_route: str,
    answer: str,
    expected_route: Optional[str],
    expected_answer_contains: Optional[str],
) -> Dict[str, Any]:
    ''' "info" when no assertions given, "pass" when all pass, "fail" when any fail '''

    if not expected_route and not expected_answer_contains:
        return {"result": "info", "route_match": None, "contains_match": None}

    route_ok = (actual_route == expected_route) if expected_route else None
    contains_ok = (expected_answer_contains.lower() in answer.lower()) if expected_answer_contains else None

    both_ok = all(v for v in [route_ok, contains_ok] if v is not None)
    return {
        "result": "pass" if both_ok else "fail",
        "route_match": route_ok,
        "contains_match": contains_ok,
    }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Run full pipeline for one question — shared by /run and /run-suite, no logging
async def _run_pipeline(question: str, service) -> Dict[str, Any]:
    ''' blocked → correction → cache → RAG, returns answer + actual_route + route_summary '''

    timings: Dict[str, Any] = {}

    # STEP-1: Blocked check always runs first
    matched_word = is_question_blocked(question)
    if matched_word:
        return {
            "answer": "I'm not able to answer that question.",
            "actual_route": "blocked",
            "route_summary": {"word": matched_word},
        }

    # STEP-2: Correction check
    correction = find_best_correction(question, threshold=CORRECTION_MATCH_THRESHOLD)
    if correction:
        q_norm = normalize_query(question)
        score = round(SequenceMatcher(None, q_norm, correction["question_norm"]).ratio(), 3)
        return {
            "answer": correction["corrected_answer"],
            "actual_route": "correction",
            "route_summary": {"correction_id": correction["id"], "match_score": score},
        }

    # STEP-3: Cache check
    cached = find_cached_answer(question)
    if cached:
        return {
            "answer": cached["answer"],
            "actual_route": "cache",
            "route_summary": {
                "match_type": cached.get("match_type"),
                "fuzzy_score": cached.get("fuzzy_score"),
                "hit_count": cached.get("hit_count"),
            },
        }

    # STEP-4: RAG — search then generate
    results = await run_in_threadpool(service.search, question, DEFAULT_TOP_K, timings)
    context = "\n\n---\n\n".join(r["text"] for r in results) if results else ""
    answer = await run_in_threadpool(service.generate_answer, question, context, timings, [])

    return {
        "answer": answer,
        "actual_route": "rag",
        "route_summary": {
            "chunks_found": len(results),
            "top_score": round(results[0].get("score", 0), 3) if results else 0,
        },
    }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Run a single question through the pipeline with optional pass/fail assertion
@router.post("/tester/run")
async def tester_run(body: TestRunBody) -> Dict[str, Any]:
    ''' Run one question live and return answer, route, route_summary, and assertion if expectations given '''

    service = get_service()
    t_start = time.perf_counter()

    question = sanitize_input((body.question or "").strip())
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    if body.expected_route and body.expected_route not in _VALID_ROUTES:
        raise HTTPException(status_code=400, detail=f"expected_route must be one of: {', '.join(sorted(_VALID_ROUTES))}")

    result = await _run_pipeline(question, service)
    elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

    return {
        "question": question,
        "answer": result["answer"],
        "actual_route": result["actual_route"],
        "route_summary": result["route_summary"],
        "response_time_ms": elapsed_ms,
        "assertion": _assess(result["actual_route"], result["answer"], body.expected_route, body.expected_answer_contains),
    }
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: List saved test cases
@router.get("/tester/cases")
def tester_list_cases(
    department_slug: Optional[str] = Query(None),
    expected_route: Optional[str] = Query(None),
    active_only: bool = Query(True),
) -> List[Dict[str, Any]]:
    ''' Return saved test cases, newest first, with optional filters '''

    return list_test_cases(
        department_slug=department_slug,
        expected_route=expected_route,
        active_only=active_only,
    )
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Save a new test case
@router.post("/tester/cases")
def tester_create_case(body: TestCaseBody) -> Dict[str, Any]:
    ''' Persist a test case with optional route and answer assertions '''

    question = sanitize_input((body.question or "").strip())
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    if body.expected_route and body.expected_route not in _VALID_ROUTES:
        raise HTTPException(status_code=400, detail=f"expected_route must be one of: {', '.join(sorted(_VALID_ROUTES))}")

    return create_test_case(
        question=question,
        label=body.label,
        department_slug=body.department_slug,
        expected_route=body.expected_route,
        expected_answer_contains=body.expected_answer_contains,
        created_by=body.created_by,
    )
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Soft-delete a test case
@router.delete("/tester/cases/{case_id}")
def tester_delete_case(case_id: int) -> Dict[str, Any]:
    ''' Deactivate test case — row stays in DB, only is_active flipped '''

    ok = deactivate_test_case(case_id)
    if not ok:
        raise HTTPException(status_code=404, detail="test case not found")

    return {"ok": True, "case_id": case_id}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Run all active test cases and return a pass/fail report
@router.post("/tester/cases/run-suite")
async def tester_run_suite(body: SuiteRunBody) -> Dict[str, Any]:
    ''' Run every active test case through the live pipeline — capped at 100 per run to prevent timeout '''

    service = get_service()
    cases = list_test_cases(department_slug=body.department_slug, active_only=True)

    if not cases:
        return {
            "summary": {"total": 0, "passed": 0, "failed": 0, "info": 0, "suite_time_ms": 0},
            "results": [],
        }

    if len(cases) > _SUITE_CASE_LIMIT:
        cases = cases[:_SUITE_CASE_LIMIT]

    results = []
    t_suite_start = time.perf_counter()

    for case in cases:
        question = sanitize_input((case["question"] or "").strip())
        if not question:
            results.append({
                "case_id": case["id"],
                "label": case["label"],
                "question": case["question"],
                "actual_route": None,
                "expected_route": case.get("expected_route"),
                "answer_preview": None,
                "route_summary": None,
                "assertion": {"result": "error", "route_match": None, "contains_match": None},
                "error": "question could not be sanitized",
                "response_time_ms": 0,
            })
            continue

        t_case = time.perf_counter()
        pipeline_result = await _run_pipeline(question, service)
        case_ms = round((time.perf_counter() - t_case) * 1000, 2)

        results.append({
            "case_id": case["id"],
            "label": case["label"],
            "question": question,
            "actual_route": pipeline_result["actual_route"],
            "expected_route": case.get("expected_route"),
            "answer_preview": pipeline_result["answer"][:200],
            "route_summary": pipeline_result["route_summary"],
            "assertion": _assess(
                pipeline_result["actual_route"],
                pipeline_result["answer"],
                case.get("expected_route"),
                case.get("expected_answer_contains"),
            ),
            "response_time_ms": case_ms,
        })

    suite_ms = round((time.perf_counter() - t_suite_start) * 1000, 2)

    passed = sum(1 for r in results if r["assertion"]["result"] == "pass")
    failed = sum(1 for r in results if r["assertion"]["result"] == "fail")
    info = sum(1 for r in results if r["assertion"]["result"] == "info")

    return {
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "info": info,
            "suite_time_ms": suite_ms,
        },
        "results": results,
    }
# =========== FUNCTION ===========
