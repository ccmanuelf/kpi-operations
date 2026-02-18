"""
Simulation API — Staffing Simulation Endpoint

POST /api/simulation/staffing — simulate production outcomes with different staffing levels.
"""

from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.schemas.simulation import (
    StaffingSimulationRequest,
    SimulationResultResponse,
)
from backend.calculations.simulation import run_staffing_simulation
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

staffing_router = APIRouter()


@staffing_router.post("/staffing", response_model=List[SimulationResultResponse])
async def run_staffing_simulation_endpoint(
    request: StaffingSimulationRequest, current_user: User = Depends(get_current_user)
) -> List[SimulationResultResponse]:
    """
    Simulate production outcomes with different staffing levels.

    Args:
        request: Staffing simulation parameters

    Returns:
        List of simulation results for each scenario
    """
    try:
        # Filter out invalid scenarios
        valid_scenarios = [s for s in request.scenarios if s > 0]
        if not valid_scenarios:
            raise ValueError("At least one valid scenario (> 0 employees) required")

        results = run_staffing_simulation(
            base_employees=request.base_employees,
            scenarios=valid_scenarios,
            shift_hours=Decimal(str(request.shift_hours)),
            cycle_time_hours=Decimal(str(request.cycle_time_hours)),
            base_efficiency=Decimal(str(request.base_efficiency)),
            efficiency_scaling=request.efficiency_scaling,
        )

        return [
            SimulationResultResponse(
                scenario_name=r.scenario_name,
                scenario_type=r.scenario_type,
                input_parameters=r.input_parameters,
                projected_output=r.projected_output,
                kpi_impact={k: float(v) for k, v in r.kpi_impact.items()},
                recommendations=r.recommendations,
                confidence_score=float(r.confidence_score),
                comparison_to_baseline=(
                    {k: float(v) for k, v in r.comparison_to_baseline.items()} if r.comparison_to_baseline else None
                ),
            )
            for r in results
        ]

    except ValueError as e:
        logger.exception("Invalid input for staffing simulation: %s", e)
        raise HTTPException(status_code=400, detail="Invalid input: validation failed")
    except Exception as e:
        logger.exception("Failed to run staffing simulation: %s", e)
        raise HTTPException(status_code=500, detail="Simulation failed")
