"""
Simulation API — Comprehensive Simulation Endpoint

POST /api/simulation/comprehensive — run a comprehensive capacity simulation with multiple scenarios.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.schemas.user import User
from backend.schemas.simulation import ComprehensiveSimulationRequest
from backend.calculations.simulation import run_capacity_simulation
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
        config = {
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

        result = run_capacity_simulation(db=db, client_id=current_user.client_id_assigned, simulation_config=config)

        return result

    except Exception as e:
        logger.exception("Failed to run comprehensive simulation: %s", e)
        raise HTTPException(status_code=500, detail="Simulation failed")
