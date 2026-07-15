"""
AMASCI GraphRAG Memory / Cache
================================
TTL-based caching for graph context, subgraphs, and query results.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300  # 5 minutes
MAX_CACHE_SIZE = 1000


@dataclass
class CacheEntry:
    """Single cache entry with TTL."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = DEFAULT_TTL_SECONDS
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class GraphRAGCache:
    """
    TTL-based in-memory cache for GraphRAG operations.

    Supports:
    - Graph context cache
    - Subgraph cache
    - Query result cache
    - Embedding cache
    - Automatic eviction on TTL expiry
    - LRU eviction when max size reached
    """

    def __init__(self, default_ttl: float = DEFAULT_TTL_SECONDS, max_size: int = MAX_CACHE_SIZE):
        self._store: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Retrieve a cached value. Returns None if expired or missing."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired:
            del self._store[key]
            self._misses += 1
            return None
        entry.hit_count += 1
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store a value with optional custom TTL."""
        if len(self._store) >= self._max_size:
            self._evict_expired()
            if len(self._store) >= self._max_size:
                self._evict_lru()

        self._store[key] = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl if ttl is not None else self._default_ttl,
        )

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all keys matching a prefix."""
        keys_to_remove = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._store[k]
        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear entire cache."""
        self._store.clear()
        self._hits = 0
        self._misses = 0

    def get_statistics(self) -> dict[str, Any]:
        """Return cache performance statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
        active_entries = sum(1 for e in self._store.values() if not e.is_expired)
        return {
            "total_entries": len(self._store),
            "active_entries": active_entries,
            "expired_entries": len(self._store) - active_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "max_size": self._max_size,
            "default_ttl_seconds": self._default_ttl,
        }

    def _evict_expired(self) -> None:
        """Remove all expired entries."""
        expired_keys = [k for k, v in self._store.items() if v.is_expired]
        for k in expired_keys:
            del self._store[k]
        if expired_keys:
            logger.debug(f"[Cache] Evicted {len(expired_keys)} expired entries")

    def _evict_lru(self) -> None:
        """Evict least recently used (lowest hit count, oldest) entries."""
        if not self._store:
            return
        sorted_entries = sorted(
            self._store.items(),
            key=lambda x: (x[1].hit_count, -x[1].age_seconds),
        )
        evict_count = max(1, len(self._store) // 10)
        for key, _ in sorted_entries[:evict_count]:
            del self._store[key]
        logger.debug(f"[Cache] LRU evicted {evict_count} entries")


# Module-level cache instances
_context_cache: GraphRAGCache | None = None
_query_cache: GraphRAGCache | None = None
_embedding_cache: GraphRAGCache | None = None


def get_context_cache() -> GraphRAGCache:
    """Get or create the context cache singleton."""
    global _context_cache
    if _context_cache is None:
        _context_cache = GraphRAGCache(default_ttl=300, max_size=500)
    return _context_cache


def get_query_cache() -> GraphRAGCache:
    """Get or create the query cache singleton."""
    global _query_cache
    if _query_cache is None:
        _query_cache = GraphRAGCache(default_ttl=120, max_size=200)
    return _query_cache


def get_embedding_cache() -> GraphRAGCache:
    """Get or create the embedding cache singleton."""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = GraphRAGCache(default_ttl=600, max_size=1000)
    return _embedding_cache
