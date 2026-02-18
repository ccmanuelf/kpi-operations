"""
Quality Inspection API Routes Package

Split from the monolithic quality.py (794 lines) into focused sub-modules:
- entries.py   — Quality inspection CRUD (create, list, get, update, delete, statistics, by-work-order)
- ppm_dpmo.py  — PPM and DPMO KPI calculation endpoints with client filtering
- fpy_rty.py   — FPY/RTY calculation, breakdown with repair/rework, and quality score
- pareto.py    — Pareto/defect analysis (top-defects, defects-by-type, by-product)

All endpoints enforce multi-tenant isolation via client_id.
"""

from fastapi import APIRouter

from .entries import entries_router
from .ppm_dpmo import ppm_dpmo_router
from .fpy_rty import fpy_rty_router
from .pareto import pareto_router

router = APIRouter(
    prefix="/api/quality",
    tags=["Quality Inspection"],
    responses={404: {"description": "Not found"}},
)

router.include_router(entries_router)
router.include_router(ppm_dpmo_router)
router.include_router(fpy_rty_router)
router.include_router(pareto_router)
