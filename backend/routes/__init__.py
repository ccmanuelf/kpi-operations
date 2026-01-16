"""
API Routes Package
Modular route organization for the KPI Operations API

Phase 5 Update: Added predictions router for comprehensive KPI forecasting
Phase 6 Update: Added QR code router for work order/product/job/employee scanning
Phase 7 Update: Added preferences router for dashboard customization
Phase 8 Update: Added filters router for saved filter configurations
"""
from .attendance import router as attendance_router
from .coverage import router as coverage_router
from .quality import router as quality_router
from .defect import router as defect_router
from .reports import router as reports_router
from .health import router as health_router
from .analytics import router as analytics_router
from .predictions import router as predictions_router
from .qr import router as qr_router
from .preferences import router as preferences_router
from .filters import router as filters_router

__all__ = [
    "attendance_router",
    "coverage_router",
    "quality_router",
    "defect_router",
    "reports_router",
    "health_router",
    "analytics_router",
    "predictions_router",
    "qr_router",
    "preferences_router",
    "filters_router"
]
