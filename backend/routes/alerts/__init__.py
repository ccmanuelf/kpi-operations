"""
Alerts API Routes Package

Split from the monolithic alerts.py (752 lines) into focused sub-modules:
- crud.py           — CRUD operations (list, get, create, acknowledge, resolve, dismiss)
                      and dashboard/summary read endpoints
- generate.py       — Alert generation endpoints (check-all, otd-risk, quality, capacity)
                      and private _check_* helper functions
- config_history.py — Alert configuration management and prediction accuracy history

All endpoints enforce multi-tenant isolation via client_id.
"""

from fastapi import APIRouter

from .crud import crud_router
from .generate import generate_router
from .config_history import config_history_router

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

router.include_router(crud_router)
router.include_router(generate_router)
router.include_router(config_history_router)
