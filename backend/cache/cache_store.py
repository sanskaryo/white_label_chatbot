# WHAT DOES THIS FILE DO: question response cache backed by Upstash Redis — fuzzy match lookup, frequency-based auto-promotion, admin controls

# ================== IMPORTS ==================
import logging
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from upstash_redis import Redis

from config import (
    UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN,
    CACHE_MIN_HITS, CACHE_FUZZY_THRESHOLD, REDIS_RESPONSE_CACHE_TTL,
)
from workflow_db import normalize_query
# ================== IMPORTS ==================


# =========== VARIABLES ===========
logger = logging.getLogger("cache_store")

_redis_client: Optional[Redis] = None

_INDEX_KEY = "qcache_index"       # Redis Set storing all active question norms
_FREQ_TTL_SECONDS = 7 * 24 * 3600  # freq counters auto-expire after 7 days if never promoted
# =========== VARIABLES ===========


# =========== FUNCTION ===========
# ROLE: Return a shared Redis client instance — lazy init so import does not fail if env vars are missing
def _r() -> Redis:
    ''' Return singleton Redis client, creating it on first call '''

    global _redis_client
    if _redis_client is None:
        _redis_client = Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN)
    return _redis_client
# =========== FUNCTION ===========


def _cache_key(norm: str) -> str:
    return f"qcache:{norm}"


def _freq_key(norm: str) -> str:
    return f"qcache_freq:{norm}"


# =========== FUNCTION ===========
# ROLE: Verify Redis connection on startup — called once from main.py after init_workflow_db
def init_cache() -> None:
    ''' Ping Upstash Redis to confirm credentials and connectivity '''

    try:
        _r().ping()
        logger.info("Upstash Redis cache connected")
    except Exception as exc:
        logger.warning(f"Redis cache connection failed on startup: {exc}")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Look up a question in Redis — exact match first, fuzzy fallback at CACHE_FUZZY_THRESHOLD
def find_cached_answer(question: str) -> Optional[Dict[str, Any]]:
    ''' Return cached entry dict or None — never raises, Redis miss returns None cleanly '''

    # FLOW-1: Normalize for consistent key lookup
    norm = normalize_query(question)
    if not norm:
        return None

    try:
        r = _r()

        # FLOW-2: Exact key match — single HGETALL call
        data = r.hgetall(_cache_key(norm))
        if data:
            return {
                "answer": data["answer"],
                "route_origin": data.get("route_origin", "rag"),
                "hit_count": int(data.get("hit_count", 0)),
                "question_original": data.get("question_original", ""),
                "matched_norm": norm,
                "match_type": "exact",
            }

        # FLOW-3: Fuzzy scan — get all norms from index set and run SequenceMatcher
        all_norms = r.smembers(_INDEX_KEY) or set()
        if not all_norms or len(all_norms) > 5000:
            return None

        best_score = 0.0
        best_norm = None
        for key_norm in all_norms:
            score = SequenceMatcher(None, norm, key_norm).ratio()
            if score > best_score:
                best_score = score
                best_norm = key_norm

        if best_norm and best_score >= CACHE_FUZZY_THRESHOLD:
            data = r.hgetall(_cache_key(best_norm))
            if data:
                return {
                    "answer": data["answer"],
                    "route_origin": data.get("route_origin", "rag"),
                    "hit_count": int(data.get("hit_count", 0)),
                    "question_original": data.get("question_original", ""),
                    "matched_norm": best_norm,
                    "match_type": "fuzzy",
                    "fuzzy_score": round(best_score, 3),
                }

    except Exception as exc:
        logger.warning(f"find_cached_answer failed: {exc}")

    return None
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Bump hit_count and last_used_at in Redis after a cache hit — background task
def record_cache_hit(matched_norm: str) -> None:
    ''' Two Redis calls: HINCRBY hit_count and HSET last_used_at — silently skip on error '''

    try:
        r = _r()
        key = _cache_key(matched_norm)
        r.hincrby(key, "hit_count", 1)
        r.hset(key, "last_used_at", datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        logger.warning(f"record_cache_hit failed: {exc}")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Increment Redis frequency counter per question; promote to cache when count >= CACHE_MIN_HITS
def maybe_promote_to_cache(question_norm: str, question_original: str, answer: str, route_origin: str = "rag") -> None:
    ''' Redis INCR-based counter shared across all workers — promotes on threshold, background task '''

    try:
        r = _r()
        freq_key = _freq_key(question_norm)

        # FLOW-1: Increment counter — shared across all Uvicorn workers via Redis
        count = r.incr(freq_key)

        # FLOW-2: Set TTL on first write so abandoned counters clean themselves up
        if count == 1:
            r.expire(freq_key, _FREQ_TTL_SECONDS)

        # FLOW-3: Not yet at threshold — nothing to do
        if count < CACHE_MIN_HITS:
            return

        # FLOW-4: Already cached — counter is stale, clean it up
        cache_key = _cache_key(question_norm)
        if r.exists(cache_key):
            r.delete(freq_key)
            return

        # FLOW-5: Threshold hit — write cache entry and remove freq counter
        r.delete(freq_key)
        now = datetime.now(timezone.utc)

        r.hset(cache_key, mapping={
            "question_original": question_original[:1000],
            "answer": answer,
            "route_origin": route_origin,
            "hit_count": "0",
            "created_at": now.isoformat(),
            "last_used_at": now.isoformat(),
        })

        # FLOW-6: Set TTL so Redis handles expiry automatically — no cleanup thread needed
        if REDIS_RESPONSE_CACHE_TTL > 0:
            r.expire(cache_key, REDIS_RESPONSE_CACHE_TTL)

        # FLOW-7: Register norm in index set so list and stats can find it
        r.sadd(_INDEX_KEY, question_norm)

        logger.info(f"promoted to cache after {CACHE_MIN_HITS} hits: '{question_original[:60]}'")

    except Exception as exc:
        logger.warning(f"maybe_promote_to_cache failed: {exc}")
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Remove a single cache entry from Redis and from the index set
def invalidate_cache_entry(question_norm: str) -> bool:
    ''' Delete cache key and remove from index — returns False if key did not exist '''

    try:
        r = _r()
        deleted = r.delete(_cache_key(question_norm))
        r.srem(_INDEX_KEY, question_norm)
        return bool(deleted)
    except Exception as exc:
        logger.warning(f"invalidate_cache_entry failed: {exc}")
        return False
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Wipe all cache entries from Redis — admin nuclear option
def clear_all_cache() -> int:
    ''' Delete all qcache keys and the index set — returns count of entries removed '''

    try:
        r = _r()
        norms = r.smembers(_INDEX_KEY) or set()
        count = 0
        for norm in norms:
            r.delete(_cache_key(norm))
            r.delete(_freq_key(norm))
            count += 1
        r.delete(_INDEX_KEY)
        logger.info(f"cache cleared — {count} entries removed from Redis")
        return count
    except Exception as exc:
        logger.warning(f"clear_all_cache failed: {exc}")
        return 0
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return all active cache entries for the admin list endpoint
def list_cache_entries(include_inactive: bool = False) -> List[Dict[str, Any]]:
    ''' Read index set then HGETALL each entry — stale index entries cleaned up inline '''

    try:
        r = _r()
        norms = r.smembers(_INDEX_KEY) or set()
        entries = []
        stale = []

        for norm in norms:
            data = r.hgetall(_cache_key(norm))
            if not data:
                # Key expired in Redis but index wasn't updated — prune it
                stale.append(norm)
                continue
            ttl = r.ttl(_cache_key(norm))
            entries.append({
                "id": norm,
                "question_original": data.get("question_original", ""),
                "answer_preview": (data.get("answer") or "")[:200],
                "route_origin": data.get("route_origin", "rag"),
                "hit_count": int(data.get("hit_count", 0)),
                "is_active": True,
                "created_at": data.get("created_at"),
                "last_used_at": data.get("last_used_at"),
                "ttl_seconds": ttl if ttl >= 0 else None,
            })

        # FLOW: Prune stale norms from index in one pass
        if stale:
            for norm in stale:
                r.srem(_INDEX_KEY, norm)

        entries.sort(key=lambda e: e["hit_count"], reverse=True)
        return entries

    except Exception as exc:
        logger.warning(f"list_cache_entries failed: {exc}")
        return []
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Manually promote a Q&A pair to cache — admin-triggered, skips frequency threshold
def add_cache_entry_manual(question_original: str, answer: str, route_origin: str = "rag") -> Dict[str, Any]:
    ''' Pin a known-good answer immediately without waiting for CACHE_MIN_HITS — upserts if norm exists '''

    # FLOW-1: Normalize question for key
    norm = normalize_query(question_original)
    if not norm:
        raise ValueError("question cannot be empty after normalization")

    now = datetime.now(timezone.utc)
    r = _r()
    cache_key = _cache_key(norm)

    # FLOW-2: Write hash — HSET overwrites existing fields so this is safe as an upsert
    r.hset(cache_key, mapping={
        "question_original": question_original[:1000],
        "answer": answer,
        "route_origin": route_origin,
        "hit_count": "0",
        "created_at": now.isoformat(),
        "last_used_at": now.isoformat(),
    })

    # FLOW-3: Reset TTL on every manual add
    if REDIS_RESPONSE_CACHE_TTL > 0:
        r.expire(cache_key, REDIS_RESPONSE_CACHE_TTL)

    # FLOW-4: Register in index so list endpoints can find it
    r.sadd(_INDEX_KEY, norm)

    return {"id": norm, "status": "promoted"}
# =========== FUNCTION ===========


# =========== FUNCTION ===========
# ROLE: Return aggregate cache performance stats for the admin dashboard
def get_cache_stats() -> Dict[str, Any]:
    ''' Read index set, count active entries and total hits from Redis hashes '''

    try:
        r = _r()
        norms = r.smembers(_INDEX_KEY) or set()
        active_count = 0
        total_hits = 0

        for norm in norms:
            data = r.hgetall(_cache_key(norm))
            if data:
                active_count += 1
                total_hits += int(data.get("hit_count", 0))

        return {
            "active_entries": active_count,
            "total_cache_hits": total_hits,
            "api_calls_saved": total_hits,
            "promotion_threshold": CACHE_MIN_HITS,
            "ttl_seconds": REDIS_RESPONSE_CACHE_TTL,
        }

    except Exception as exc:
        logger.warning(f"get_cache_stats failed: {exc}")
        return {
            "active_entries": 0,
            "total_cache_hits": 0,
            "api_calls_saved": 0,
            "promotion_threshold": CACHE_MIN_HITS,
            "ttl_seconds": REDIS_RESPONSE_CACHE_TTL,
            "error": str(exc),
        }
# =========== FUNCTION ===========
