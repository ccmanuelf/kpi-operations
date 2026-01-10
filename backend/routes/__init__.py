"""
API Routes Package
Modular route organization for the KPI Operations API

Phase 5 Update: Added predictions router for comprehensive KPI forecasting
"""
from .attendance import router as attendance_router
from .coverage import router as coverage_router
from .quality import router as quality_router
from .defect import router as defect_router
from .reports import router as reports_router
from .health import router as health_router
from .analytics import router as analytics_router
from .predictions import router as predictions_router

__all__ = [
    "attendance_router",
    "coverage_router",
    "quality_router",
    "defect_router",
    "reports_router",
    "health_router",
    "analytics_router",
    "predictions_router"
]
