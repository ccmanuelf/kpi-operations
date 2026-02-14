"""
Cache Management API Routes

Phase A.1: Provides endpoints for cache monitoring and management.
Supports the Capacity Planning Module caching infrastructure.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from datetime import datetime

from backend.auth.jwt import get_current_user, get_current_admin
from backend.schemas.user import User
from backend.cache import get_cache


router = APIRouter(
    prefix="/api/cache",
    tags=["cache"],
    responses={404: {"description": "Not found"}},
)


@router.get("/stats", response_model=Dict[str, Any])
async def get_cache_stats(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns cache metrics including:
    - entries: Number of cached items
    - hits: Number of cache hits
    - misses: Number of cache misses
    - hit_rate: Cache hit percentage
    - sets: Number of cache writes
    - evictions: Number of expired/evicted entries

    Requires authentication.
    """
    cache = get_cache()
    stats = cache.get_stats()

    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "statistics": stats}


@router.post("/clear", response_model=Dict[str, Any])
async def clear_cache(current_user: User = Depends(get_current_admin)) -> Dict[str, Any]:
    """
    Clear all cache entries.

    This is an administrative operation that requires admin privileges.
    Use with caution as it will cause temporary performance degradation
    while the cache is repopulated.

    Returns:
        Dictionary with number of entries cleared
    """
    cache = get_cache()
    cleared_count = cache.clear()

    return {
        "status": "success",
        "message": f"Cache cleared successfully",
        "entries_cleared": cleared_count,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.delete("/invalidate/{pattern}", response_model=Dict[str, Any])
async def invalidate_cache_pattern(pattern: str, current_user: User = Depends(get_current_admin)) -> Dict[str, Any]:
    """
    Invalidate cache entries matching a pattern prefix.

    Useful for selectively clearing cached data:
    - "client_config:" - Clear all client config cache
    - "product:" - Clear all product cache
    - "shift:" - Clear all shift cache
    - "daily_summary:" - Clear all daily summary cache
    - "daily_summary:CLIENT_A:" - Clear summaries for specific client

    Requires admin privileges.

    Args:
        pattern: Cache key prefix to match

    Returns:
        Dictionary with number of entries invalidated
    """
    cache = get_cache()
    invalidated_count = cache.invalidate_pattern(pattern)

    return {
        "status": "success",
        "pattern": pattern,
        "entries_invalidated": invalidated_count,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health", response_model=Dict[str, Any])
async def cache_health() -> Dict[str, Any]:
    """
    Check cache health status.

    This endpoint does not require authentication and can be used
    for infrastructure health checks.

    Returns:
        Dictionary with cache health status
    """
    try:
        cache = get_cache()
        stats = cache.get_stats()

        # Determine health status based on hit rate
        hit_rate = stats.get("hit_rate", 0)
        if hit_rate >= 50:
            status = "healthy"
        elif hit_rate >= 20:
            status = "degraded"
        elif stats.get("hits", 0) + stats.get("misses", 0) < 10:
            # Not enough data to determine health
            status = "warming_up"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "entries": stats.get("entries", 0),
            "hit_rate": hit_rate,
        }
    except Exception as e:
        return {"status": "error", "timestamp": datetime.utcnow().isoformat(), "error": str(e)}
