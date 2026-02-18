"""
Simulation API — Overview Endpoint

GET /api/simulation/ — returns simulation capabilities summary.
"""

from fastapi import APIRouter, Depends

from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.schemas.simulation import SimulationSummary
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

overview_router = APIRouter()


@overview_router.get("/", response_model=SimulationSummary)
async def get_simulation_overview(current_user: User = Depends(get_current_user)) -> SimulationSummary:
    """
    Get simulation capabilities overview.

    **DEPRECATED**: This endpoint is deprecated. Please use /api/v2/simulation/info
    for the enhanced simulation API with multi-product support and SimPy-based
    discrete-event simulation.

    Returns available simulation types and use cases.
    """
    return SimulationSummary(
        available_simulation_types=[
            "capacity_requirements",
            "production_capacity",
            "staffing_simulation",
            "efficiency_simulation",
            "shift_coverage",
            "multi_shift_coverage",
            "floating_pool_optimization",
            "comprehensive_simulation",
        ],
        description=(
            "[DEPRECATED] Simulation and capacity planning module for production forecasting "
            "and what-if analysis. Please migrate to /api/v2/simulation for enhanced "
            "multi-product SimPy-based simulation with 8 output blocks."
        ),
        example_use_cases=[
            "Calculate staffing requirements for production targets",
            "Simulate production capacity with different staffing levels",
            "Analyze shift coverage gaps and floating pool allocation",
            "Run what-if scenarios for efficiency improvements",
            "Optimize floating pool employee distribution",
            "[RECOMMENDED] Use /api/v2/simulation/run for enhanced discrete-event simulation",
        ],
    )
