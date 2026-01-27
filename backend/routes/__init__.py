"""
API Routes Package
Modular route organization for the KPI Operations API

Phase 5 Update: Added predictions router for comprehensive KPI forecasting
Phase 6 Update: Added QR code router for work order/product/job/employee scanning
Phase 7 Update: Added preferences router for dashboard customization
Phase 8 Update: Added filters router for saved filter configurations
Phase 9 Update: Extracted all inline routes from main.py into modular route files
"""
# Existing routers
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

# Newly extracted routers (Phase 9)
from .auth import router as auth_router
from .users import router as users_router
from .production import router as production_router
from .production import import_logs_router
from .kpi import router as kpi_router
from .kpi import thresholds_router as kpi_thresholds_router
from .downtime import router as downtime_router
from .downtime import availability_router
from .holds import router as holds_router
from .holds import wip_aging_router
from .jobs import router as jobs_router
from .jobs import work_order_jobs_router
from .work_orders import router as work_orders_router
from .work_orders import client_work_orders_router
from .clients import router as clients_router
from .client_config import router as client_config_router
from .employees import router as employees_router
from .employees import client_employees_router
from .floating_pool import router as floating_pool_router
from .floating_pool import client_floating_pool_router
from .part_opportunities import router as part_opportunities_router
from .reference import router as reference_router
from .data_completeness import router as data_completeness_router
from .my_shift import router as my_shift_router
from .alerts import router as alerts_router

__all__ = [
    # Existing routers
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
    "filters_router",
    # Newly extracted routers
    "auth_router",
    "users_router",
    "production_router",
    "import_logs_router",
    "kpi_router",
    "kpi_thresholds_router",
    "downtime_router",
    "availability_router",
    "holds_router",
    "wip_aging_router",
    "jobs_router",
    "work_order_jobs_router",
    "work_orders_router",
    "client_work_orders_router",
    "clients_router",
    "client_config_router",
    "employees_router",
    "client_employees_router",
    "floating_pool_router",
    "client_floating_pool_router",
    "part_opportunities_router",
    "reference_router",
    "data_completeness_router",
    "my_shift_router",
    "alerts_router"
]
