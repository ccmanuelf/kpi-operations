"""
KPI Cache Implementation
In-memory caching with TTL for expensive KPI aggregations.

Phase 1.4: Add Caching Layer
Simple dict-based cache with TTL (no Redis for now).
Used for caching dashboard summaries, trend calculations, and client config lookups.
"""
from typing import Optional, Any, Dict, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import threading
import hashlib
import json


@dataclass
class CacheEntry:
    """A single cache entry with value and expiry time."""
    value: Any
    expiry: datetime
    created_at: datetime


class KPICache:
    """
    Thread-safe in-memory cache with TTL support.

    Features:
    - TTL-based expiration
    - Thread-safe operations
    - Automatic cleanup on access
    - Cache statistics

    Usage:
        cache = KPICache(ttl_seconds=300)
        cache.set("dashboard:client123", dashboard_data)
        data = cache.get("dashboard:client123")
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 1000):
        """
        Initialize the cache.

        Args:
            ttl_seconds: Default time-to-live in seconds (default: 5 minutes)
            max_entries: Maximum number of entries before cleanup (default: 1000)
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_entries = max_entries
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0
        }

    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if datetime.now() < entry.expiry:
                    self._stats["hits"] += 1
                    return entry.value
                else:
                    # Expired - remove it
                    del self._cache[key]
                    self._stats["evictions"] += 1

            self._stats["misses"] += 1
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional custom TTL (uses default if not specified)
        """
        with self._lock:
            # Cleanup if we're at capacity
            if len(self._cache) >= self._max_entries:
                self._cleanup_expired()

            ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else self._ttl
            now = datetime.now()

            self._cache[key] = CacheEntry(
                value=value,
                expiry=now + ttl,
                created_at=now
            )
            self._stats["sets"] += 1

    def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False if not found
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern prefix.

        Args:
            pattern: Key prefix to match (e.g., "dashboard:" invalidates all dashboard keys)

        Returns:
            Number of keys invalidated
        """
        with self._lock:
            keys_to_delete = [
                key for key in self._cache.keys()
                if key.startswith(pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
                self._stats["evictions"] += 1
            return len(keys_to_delete)

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl_seconds: Optional[int] = None
    ) -> Any:
        """
        Get a value from cache, or compute and cache it if not found.

        This is the preferred method for caching expensive operations.

        Args:
            key: Cache key
            factory: Function to call if value not in cache
            ttl_seconds: Optional custom TTL

        Returns:
            Cached or newly computed value

        Usage:
            def compute_expensive_summary():
                # expensive database queries here
                return summary_data

            result = cache.get_or_set(
                "dashboard:client123:2024-01-15",
                compute_expensive_summary,
                ttl_seconds=300
            )
        """
        value = self.get(key)
        if value is not None:
            return value

        # Compute the value
        value = factory()
        self.set(key, value, ttl_seconds)
        return value

    def clear(self) -> int:
        """
        Clear all entries from the cache.

        Returns:
            Number of entries cleared
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with hit rate, entry count, etc.
        """
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0

            return {
                "entries": len(self._cache),
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": round(hit_rate, 2),
                "sets": self._stats["sets"],
                "evictions": self._stats["evictions"]
            }

    def _cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now >= entry.expiry
        ]

        for key in expired_keys:
            del self._cache[key]
            self._stats["evictions"] += 1

        return len(expired_keys)


# =============================================================================
# Cache Key Builders
# =============================================================================

def build_cache_key(*parts: Any) -> str:
    """
    Build a consistent cache key from parts.

    Args:
        parts: Key components (will be joined with ":")

    Returns:
        Cache key string

    Examples:
        >>> build_cache_key("dashboard", "client123", "2024-01-15")
        "dashboard:client123:2024-01-15"
    """
    return ":".join(str(part) for part in parts)


def build_hash_key(prefix: str, **kwargs) -> str:
    """
    Build a cache key with a hash of the parameters.

    Useful for complex queries with many parameters.

    Args:
        prefix: Key prefix
        kwargs: Parameters to hash

    Returns:
        Cache key with hashed parameters

    Examples:
        >>> build_hash_key("ppm", start_date="2024-01-01", end_date="2024-01-31", client_id="X")
        "ppm:abc123def456"
    """
    # Sort kwargs for consistent ordering
    param_str = json.dumps(kwargs, sort_keys=True, default=str)
    hash_value = hashlib.md5(param_str.encode()).hexdigest()[:12]
    return f"{prefix}:{hash_value}"


# =============================================================================
# Global Cache Instance
# =============================================================================

# Global cache instance (singleton pattern)
_global_cache: Optional[KPICache] = None
_cache_lock = threading.Lock()


def get_cache(ttl_seconds: int = 300) -> KPICache:
    """
    Get the global cache instance (creates if needed).

    This is the recommended way to access the cache.

    Args:
        ttl_seconds: TTL for new cache (only used on first call)

    Returns:
        Global KPICache instance

    Usage:
        from backend.cache import get_cache

        cache = get_cache()
        cache.set("my_key", my_value)
    """
    global _global_cache

    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = KPICache(ttl_seconds=ttl_seconds)

    return _global_cache


def reset_cache() -> None:
    """
    Reset the global cache instance.

    Useful for testing or complete cache invalidation.
    """
    global _global_cache

    with _cache_lock:
        if _global_cache is not None:
            _global_cache.clear()
            _global_cache = None


# =============================================================================
# Cache Decorators
# =============================================================================

def cached(
    key_prefix: str,
    ttl_seconds: int = 300,
    key_builder: Optional[Callable[..., str]] = None
):
    """
    Decorator to cache function results.

    Args:
        key_prefix: Prefix for cache keys
        ttl_seconds: TTL in seconds
        key_builder: Optional function to build cache key from args

    Usage:
        @cached("dashboard_summary", ttl_seconds=300)
        def get_dashboard_summary(client_id: str, date: str):
            # expensive computation
            return summary

        # Cache key will be: "dashboard_summary:client123:2024-01-15"
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default: use all args in key
                key_parts = [key_prefix] + list(str(a) for a in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

            # Try to get from cache
            return cache.get_or_set(cache_key, lambda: func(*args, **kwargs), ttl_seconds)

        return wrapper
    return decorator
