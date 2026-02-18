"""
Advanced Analytics API Routes Package

Split from the monolithic analytics.py (683 lines) into focused sub-modules:
- trends.py      — KPI trend analysis endpoint (moving averages, anomaly detection)
- predictions.py — KPI predictive forecasting endpoint (exponential smoothing, extrapolation)
- comparisons.py — Client benchmarking, performance heatmap, and Pareto analysis endpoints
- _helpers.py    — Shared utility functions (parse_time_range, performance rating, color codes)

All endpoints enforce client access control and multi-tenant isolation.
"""

from fastapi import APIRouter

from .trends import trends_router
from .predictions import predictions_router
from .comparisons import comparisons_router

# Re-export shared helper functions so tests and other modules can import
# them directly from backend.routes.analytics (preserving the original interface)
from ._helpers import parse_time_range, get_performance_rating, get_heatmap_color_code  # noqa: F401

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

router.include_router(trends_router)
router.include_router(predictions_router)
router.include_router(comparisons_router)
