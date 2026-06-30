# WHAT DOES THIS FILE DO: in-memory live session tracker — records who is active right now and provides a snapshot for the admin dashboard

# ================== IMPORTS ==================
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
# ================== IMPORTS ==================


# =========== VARIABLES : config ===========
_TTL_MINUTES = int(os.getenv("ACTIVITY_TTL_MINUTES", "10"))
# =========== VARIABLES : config ===========


# =========== CLASS ===========
# ROLE: Thread-safe in-memory store for active visitor sessions
class ActivityTracker:
    ''' Keeps a dict of session_id → session state, auto-expires stale entries every 60 seconds '''

    def __init__(self, ttl_minutes: int = _TTL_MINUTES) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        # FLOW-1: Start background cleanup thread as daemon so it dies with the process
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True, name="activity-cleanup")
        self._cleanup_thread.start()


    def touch(self, session_id: str, department_slug: Optional[str] = None) -> None:
        ''' Update last_seen for a session, create it if new '''

        # FLOW-1: Acquire lock and update or create session entry
        now = datetime.now(timezone.utc)
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["last_seen"] = now
                self._sessions[session_id]["question_count"] += 1
            else:
                self._sessions[session_id] = {
                    "session_id": session_id,
                    "department_slug": department_slug,
                    "started_at": now,
                    "last_seen": now,
                    "question_count": 1,
                }


    def get_live(self) -> List[Dict[str, Any]]:
        ''' Return all sessions active within the TTL window, newest last_seen first '''

        # FLOW-1: Compute cutoff and collect sessions that are still within TTL
        cutoff = datetime.now(timezone.utc) - self._ttl
        with self._lock:
            active = [
                {**s, "started_at": s["started_at"].isoformat(), "last_seen": s["last_seen"].isoformat()}
                for s in self._sessions.values()
                if s["last_seen"] >= cutoff
            ]

        # FLOW-2: Sort by last_seen descending so most-recent session is first
        active.sort(key=lambda x: x["last_seen"], reverse=True)
        return active


    def count_active(self) -> int:
        ''' Return number of sessions currently within TTL '''

        cutoff = datetime.now(timezone.utc) - self._ttl
        with self._lock:
            return sum(1 for s in self._sessions.values() if s["last_seen"] >= cutoff)


    def _cleanup_loop(self) -> None:
        ''' Remove expired sessions every 60 seconds to keep the dict from growing forever '''

        import time
        while True:
            time.sleep(60)
            cutoff = datetime.now(timezone.utc) - self._ttl
            with self._lock:
                expired = [sid for sid, s in self._sessions.items() if s["last_seen"] < cutoff]
                for sid in expired:
                    del self._sessions[sid]

# =========== CLASS ===========


# =========== VARIABLES : singleton ===========
_tracker = ActivityTracker()
# =========== VARIABLES : singleton ===========


# =========== FUNCTION ===========
# ROLE: Record a session heartbeat — called as background task from chat endpoint
def touch_session(session_id: Optional[str], department_slug: Optional[str] = None) -> None:
    ''' Update tracker for session_id; silently skip if session_id is missing '''

    # FLOW-1: Skip anonymous requests that sent no session ID
    if not session_id:
        return

    # FLOW-2: Update in-memory tracker
    _tracker.touch(session_id.strip(), department_slug)
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return snapshot of currently active sessions for the admin live-feed endpoint
def get_live_sessions() -> Dict[str, Any]:
    ''' Return active session list and metadata for GET /activity/live '''

    # FLOW-1: Pull current snapshot from tracker
    sessions = _tracker.get_live()
    return {
        "active_sessions": sessions,
        "count": len(sessions),
        "ttl_minutes": _TTL_MINUTES,
    }
# =========== FUNCTION ===========
