# WHAT DOES THIS FILE DO: Analytics endpoints that power the admin dashboard charts and KPI cards

# ================== IMPORTS ==================
from fastapi import APIRouter, Query

from analytics_db import get_dashboard_metrics, get_chat_volume_by_day, get_top_questions, get_quality_metrics
# ================== IMPORTS ==================


router = APIRouter()


# =========== FUNCTION ===========
# ROLE: Return high-level KPI metrics for the main dashboard header cards
@router.get("/analytics/metrics")
def dashboard_metrics():
    ''' Return total chats, today chats, avg response time, doc counts, and rates '''
    return get_dashboard_metrics()
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return daily chat volume data for a line chart
@router.get("/analytics/chat-volume")
def chat_volume(days: int = Query(default=30, ge=1, le=90)):
    ''' Return list of {date, count} for each day in last N days '''
    return {"items": get_chat_volume_by_day(days=days)}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return the most frequently asked questions
@router.get("/analytics/top-questions")
def top_questions(limit: int = Query(default=10, ge=1, le=50)):
    ''' Return top N questions by frequency '''
    return {"items": get_top_questions(limit=limit)}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return quality and moderation metrics for the review panel
@router.get("/analytics/quality")
def quality_metrics():
    ''' Return flagged counts, pending reviews, and route breakdown '''
    return get_quality_metrics()
# =========== FUNCTION ===========
