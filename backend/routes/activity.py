# WHAT DOES THIS FILE DO: live activity monitoring endpoints — active sessions snapshot and today's summary

# ================== IMPORTS ==================
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from fastapi import APIRouter
from sqlalchemy import func, select

from activity import get_live_sessions, _tracker
from analytics_db import ChatLog
from workflow_db import session_scope
# ================== IMPORTS ==================


router = APIRouter()


# =========== FUNCTION ===========
# ROLE: Return all sessions that had activity within the TTL window
@router.get("/activity/live")
def live_sessions() -> Dict[str, Any]:
    ''' Poll this every 10-30s from the admin dashboard to see who is active right now '''

    # FLOW-1: Delegate entirely to the in-memory tracker
    return get_live_sessions()
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return today's session and message counts plus the busiest hour
@router.get("/activity/summary")
def activity_summary() -> Dict[str, Any]:
    ''' Combine live tracker count with ChatLog aggregates for the activity widget '''

    # FLOW-1: Set today's time boundary
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # FLOW-2: Query today's session and message counts from ChatLog
    with session_scope() as session:
        messages_today = session.scalar(
            select(func.count(ChatLog.id)).where(ChatLog.created_at >= today_start)
        ) or 0

        # FLOW-3: Count distinct sessions today
        sessions_today = session.scalar(
            select(func.count(func.distinct(ChatLog.session_id))).where(
                ChatLog.created_at >= today_start,
                ChatLog.session_id.isnot(None),
            )
        ) or 0

        # FLOW-4: Find the busiest hour today by grouping message counts per hour
        hourly_rows = session.execute(
            select(
                func.date_trunc("hour", ChatLog.created_at).label("hour"),
                func.count(ChatLog.id).label("count"),
            )
            .where(ChatLog.created_at >= today_start)
            .group_by(func.date_trunc("hour", ChatLog.created_at))
            .order_by(func.count(ChatLog.id).desc())
            .limit(1)
        ).first()

    # FLOW-5: Extract peak hour info, default to None if no data yet today
    peak_hour = None
    peak_count = 0
    if hourly_rows:
        peak_hour = hourly_rows.hour.strftime("%H:00") if hourly_rows.hour else None
        peak_count = hourly_rows.count

    # FLOW-6: Combine with live count from in-memory tracker
    return {
        "active_now": _tracker.count_active(),
        "sessions_today": sessions_today,
        "messages_today": messages_today,
        "peak_hour_today": peak_hour,
        "peak_messages_that_hour": peak_count,
    }
# =========== FUNCTION ===========
