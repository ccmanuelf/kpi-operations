"""
Capacity Planning API Routes Package

Split from the monolithic capacity.py (2194 lines) into focused sub-modules:
- calendar.py    — Master Calendar (working days, shifts, holidays)
- lines.py       — Production Lines (capacity specifications)
- orders.py      — Orders (planning orders)
- standards.py   — Production Standards (SAM data)
- bom_stock.py   — BOM (Bill of Materials) and Stock Snapshots
- analysis.py    — Component Check, Capacity Analysis, and Schedules
- scenarios.py   — Scenario (what-if analysis)
- kpi_workbook.py — KPI Integration and Workbook (multi-sheet operations)
- _models.py     — Shared Pydantic request/response models

All endpoints enforce multi-tenant isolation via client_id.
"""

from fastapi import APIRouter

from .calendar import calendar_router
from .lines import lines_router
from .orders import orders_router
from .standards import standards_router
from .bom_stock import bom_stock_router
from .analysis import analysis_router
from .scenarios import scenarios_router
from .kpi_workbook import kpi_workbook_router

router = APIRouter(
    prefix="/api/capacity",
    tags=["Capacity Planning"],
    responses={404: {"description": "Not found"}},
)

router.include_router(calendar_router)
router.include_router(lines_router)
router.include_router(orders_router)
router.include_router(standards_router)
router.include_router(bom_stock_router)
router.include_router(analysis_router)
router.include_router(scenarios_router)
router.include_router(kpi_workbook_router)
