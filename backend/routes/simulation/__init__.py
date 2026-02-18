"""
Simulation API Routes Package (V1 — Deprecated)

**DEPRECATION NOTICE**: This API (v1) is deprecated in favor of /api/v2/simulation
which provides enhanced SimPy-based discrete-event simulation with:
- Multi-product support (up to 5 products)
- Configurable variability (triangular/deterministic)
- 8 output blocks with comprehensive analytics
- Rebalancing suggestions and bottleneck detection

Split from the monolithic simulation.py (1064 lines) into focused sub-modules:
- overview.py        — Simulation capabilities overview
- capacity.py        — Capacity requirements and production capacity endpoints
- staffing.py        — Staffing simulation endpoints
- efficiency.py      — Efficiency simulation endpoints
- shift_coverage.py  — Shift and multi-shift coverage simulation endpoints
- floating_pool.py   — Floating pool optimization endpoints
- comprehensive.py   — Comprehensive capacity simulation endpoint
- production_line.py — SimPy-based production line simulation endpoints

All endpoints enforce multi-tenant isolation via client_id.
"""

from fastapi import APIRouter

from .overview import overview_router
from .capacity import capacity_router
from .staffing import staffing_router
from .efficiency import efficiency_router
from .shift_coverage import shift_coverage_router
from .floating_pool import floating_pool_router
from .comprehensive import comprehensive_router
from .production_line import production_line_router

router = APIRouter(
    prefix="/api/simulation",
    tags=["simulation"],
    deprecated=True,  # Marks all endpoints as deprecated in OpenAPI docs
)

router.include_router(overview_router)
router.include_router(capacity_router)
router.include_router(staffing_router)
router.include_router(efficiency_router)
router.include_router(shift_coverage_router)
router.include_router(floating_pool_router)
router.include_router(comprehensive_router)
router.include_router(production_line_router)
