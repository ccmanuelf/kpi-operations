"""
KPI Operations Cache Package
In-memory caching with TTL for expensive KPI aggregations.

Phase A.1: Added build_cache_key export for consistent key generation.
"""

from backend.cache.kpi_cache import KPICache, get_cache, build_cache_key

__all__ = [
    "KPICache",
    "get_cache",
    "build_cache_key",
]
