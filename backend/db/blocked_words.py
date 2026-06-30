# WHAT DOES THIS FILE DO: blocked words management — cache, lookup, and CRUD functions

# ================== IMPORTS ==================
import threading
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from .connection import session_scope
from .models import BlockedWord
# ================== IMPORTS ==================


# =========== VARIABLES : in-memory cache for blocked words ===========
_blocked_words_cache: Optional[List[str]] = None
_blocked_words_lock = threading.Lock()
# =========== VARIABLES : in-memory cache for blocked words ===========


# =========== FUNCTION ===========
# ROLE: Clear the cached blocked words list so next call reloads from DB
def _invalidate_blocked_words_cache() -> None:
    ''' Set cache to None — next call to get_blocked_words_list will hit DB '''

    # FLOW-1: Acquire lock and clear the reference
    global _blocked_words_cache
    with _blocked_words_lock:
        _blocked_words_cache = None
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return list of active blocked words, loading from DB on cache miss
def get_blocked_words_list() -> List[str]:
    ''' Return cached list of blocked words, reload from DB if cache is empty '''

    # FLOW-1: Acquire lock and check cache first
    global _blocked_words_cache
    with _blocked_words_lock:
        if _blocked_words_cache is not None:
            return _blocked_words_cache

        # FLOW-2: Cache miss — load active words from DB
        with session_scope() as session:
            rows = session.execute(
                select(BlockedWord.word).where(BlockedWord.is_active.is_(True))
            ).scalars().all()

        # FLOW-3: Lowercase and store in cache before returning
        _blocked_words_cache = [w.lower() for w in rows]
        return _blocked_words_cache
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Check if a question contains any blocked word
def is_question_blocked(question: str) -> Optional[str]:
    ''' Return the matching blocked word if found in question, else None '''

    # FLOW-1: Lowercase question for case-insensitive check
    q_lower = question.lower()

    # FLOW-2: Scan through blocked words and return on first match
    for word in get_blocked_words_list():
        if word in q_lower:
            return word

    return None
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return all active blocked word records with usage counts for the admin panel
def list_blocked_words() -> List[Dict[str, Any]]:
    ''' Return active blocked words with trigger_count and created_at, newest first '''

    # local import — avoids circular: db/ -> analytics_db -> workflow_db -> db/
    from analytics_db import ChatLog

    with session_scope() as session:

        # FLOW-1: Fetch active blocked word rows
        rows = session.execute(
            select(BlockedWord).where(BlockedWord.is_active.is_(True)).order_by(BlockedWord.created_at.desc())
        ).scalars().all()

        # FLOW-2: Fetch trigger counts grouped by matched word in one query
        count_rows = session.execute(
            select(ChatLog.blocked_word_matched, func.count(ChatLog.id).label("cnt"))
            .where(ChatLog.blocked_word_matched.isnot(None))
            .group_by(ChatLog.blocked_word_matched)
        ).all()

    # FLOW-3: Merge counts into word list in Python — avoids complex JOIN
    trigger_counts = {r.blocked_word_matched: r.cnt for r in count_rows}

    return [
        {
            "id": r.id,
            "word": r.word,
            "reason": r.reason,
            "added_by": r.added_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "trigger_count": trigger_counts.get(r.word.lower(), 0),
        }
        for r in rows
    ]
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Add a new blocked word or reactivate an existing one
def add_blocked_word(word: str, reason: str = "", added_by: str = "admin") -> Dict[str, Any]:
    ''' Insert or reactivate blocked word, invalidate cache, return record '''

    # FLOW-1: Check if word already exists
    with session_scope() as session:
        existing = session.execute(
            select(BlockedWord).where(BlockedWord.word == word.strip().lower())
        ).scalars().first()

        # FLOW-2: Reactivate if it exists, otherwise create new record
        if existing:
            existing.is_active = True
            existing.reason = reason
            row = existing
        else:
            row = BlockedWord(word=word.strip().lower(), reason=reason, added_by=added_by, is_active=True)
            session.add(row)

        # FLOW-3: Flush to get ID before session commits
        session.flush()
        result = {"id": row.id, "word": row.word, "reason": row.reason}

    # FLOW-4: Invalidate cache so new word is picked up immediately
    _invalidate_blocked_words_cache()
    return result
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Soft-delete a blocked word by its ID
def delete_blocked_word(word_id: int) -> bool:
    ''' Mark word inactive and invalidate cache; return True if found '''

    # FLOW-1: Load word and mark it inactive
    with session_scope() as session:
        row = session.get(BlockedWord, word_id)
        if row:
            row.is_active = False
            _invalidate_blocked_words_cache()
            return True

    return False
# =========== FUNCTION ===========
