"""
Simulation API — Comprehensive Simulation Endpoint

POST /api/simulation/comprehensive — run a comprehensive capacity simulation with multiple scenarios.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.orm.user import User
from backend.orm.simulation import ComprehensiveSimulationRequest
from backend.services.simulation_service import SimulationService
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

comprehensive_router = APIRouter()


@comprehensive_router.post("/comprehensive")
async def run_comprehensive_simulation(
    request: ComprehensiveSimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Run a comprehensive capacity simulation with multiple scenarios.

    Includes:
    - Capacity requirements analysis
    - Current capacity evaluation
    - Gap analysis
    - Staffing simulations
    - Efficiency simulations
    - Recommendations

    Args:
        request: Comprehensive simulation parameters

    Returns:
        Complete simulation results with all analyses
    """
    try:
        # Mixed-value config (numerics + optional list scenarios), so
        # annotate as Dict[str, Any] up front rather than letting mypy
        # narrow the value type to `float` from the first four fields
        # and reject the staffing/efficiency list assignments.
        config: Dict[str, Any] = {
            "target_units": request.target_units,
            "current_employees": request.current_employees,
            "shift_hours": request.shift_hours,
            "cycle_time_hours": request.cycle_time_hours,
            "efficiency": request.efficiency,
        }

        if request.staffing_scenarios:
            config["staffing_scenarios"] = request.staffing_scenarios

        if request.efficiency_scenarios:
            config["efficiency_scenarios"] = request.efficiency_scenarios

        # client_id_assigned is Optional[str] in the user model; the
        # capacity simulation entrypoint requires a str. Reject the call
        # eagerly with a 400 rather than handing None deeper.
        client_id_assigned = current_user.client_id_assigned
        if not client_id_assigned:
            raise HTTPException(status_code=400, detail="User has no client assignment")

        result = SimulationService(db).run_capacity_simulation(
            client_id=client_id_assigned, simulation_config=config
        )

        return result

    except Exception as e:
        logger.exception("Failed to run comprehensive simulation: %s", e)
        raise HTTPException(status_code=500, detail="Simulation failed")
