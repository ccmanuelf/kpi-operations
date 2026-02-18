"""
Reports API Routes Package

Split from the monolithic reports.py (796 lines) into focused sub-modules:
- production_reports.py    — Production PDF and Excel report endpoints + parse_date helper
- kpi_reports.py           — Quality and attendance PDF/Excel report endpoints
- comprehensive_reports.py — Comprehensive all-KPI reports and /available catalog endpoint
- email_config.py          — Email report configuration CRUD, test email, and manual sending
- _models.py               — Shared Pydantic request/response models

All endpoints enforce multi-tenant client access via verify_client_access.
"""

from fastapi import APIRouter

from .production_reports import production_reports_router
from .kpi_reports import kpi_reports_router
from .comprehensive_reports import comprehensive_reports_router
from .email_config import email_config_router

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    responses={404: {"description": "Not found"}},
)

router.include_router(production_reports_router)
router.include_router(kpi_reports_router)
router.include_router(comprehensive_reports_router)
router.include_router(email_config_router)
