# WHAT DOES THIS FILE DO: re-exports all public symbols from cache_store so callers can do `from cache import X`

from .cache_store import (
    init_cache,
    find_cached_answer,
    record_cache_hit,
    maybe_promote_to_cache,
    invalidate_cache_entry,
    clear_all_cache,
    list_cache_entries,
    add_cache_entry_manual,
    get_cache_stats,
)

__all__ = [
    "init_cache",
    "find_cached_answer",
    "record_cache_hit",
    "maybe_promote_to_cache",
    "invalidate_cache_entry",
    "clear_all_cache",
    "list_cache_entries",
    "add_cache_entry_manual",
    "get_cache_stats",
]
