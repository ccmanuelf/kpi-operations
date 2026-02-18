"""
KPI API Routes Package

Split from the monolithic kpi.py (1361 lines) into focused sub-modules:
- calculations.py  — Core KPI calculation (/calculate/{entry_id}) and basic dashboard
- efficiency.py    — Efficiency by shift, by product, and trend data
- otd.py           — On-Time Delivery KPI, late orders, OTD by client, late deliveries
- trends.py        — Performance, quality, availability, OEE, OTD, and absenteeism trends
- dashboard.py     — Aggregated dashboard (single call combining all metrics)
- thresholds.py    — KPI threshold CRUD (separate /api/kpi-thresholds prefix)

Each sub-module router carries its own full prefix ("/api/kpi" or
"/api/kpi-thresholds"), so this __init__.py wraps them in a bare
router (no prefix) and re-exports under the names that
routes/__init__.py and main.py expect.

All endpoints enforce multi-tenant isolation via client_id.
"""

from fastapi import APIRouter

from .calculations import calculations_router
from .efficiency import efficiency_router
from .otd import otd_router
from .trends import trends_router
from .dashboard import dashboard_router
from .thresholds import thresholds_router

# Bare router (no prefix) — each sub-router already carries the full /api/kpi prefix.
# This avoids double-prefixing while keeping the expected 'router' export name.
router = APIRouter()
router.include_router(calculations_router)
router.include_router(efficiency_router)
router.include_router(otd_router)
router.include_router(trends_router)
router.include_router(dashboard_router)

# thresholds_router is exported separately — it uses /api/kpi-thresholds prefix
# and is registered independently in backend/routes/__init__.py
__all__ = ["router", "thresholds_router"]
