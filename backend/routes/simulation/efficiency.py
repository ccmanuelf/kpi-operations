"""
Simulation API — Efficiency Simulation Endpoint

POST /api/simulation/efficiency — simulate production outcomes with different efficiency levels.
"""

from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.schemas.simulation import (
    EfficiencySimulationRequest,
    SimulationResultResponse,
)
from backend.calculations.simulation import run_efficiency_simulation
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

efficiency_router = APIRouter()


@efficiency_router.post("/efficiency", response_model=List[SimulationResultResponse])
async def run_efficiency_simulation_endpoint(
    request: EfficiencySimulationRequest, current_user: User = Depends(get_current_user)
) -> List[SimulationResultResponse]:
    """
    Simulate production outcomes with different efficiency levels.

    Args:
        request: Efficiency simulation parameters

    Returns:
        List of simulation results for each scenario
    """
    try:
        # Convert efficiency values to Decimal
        efficiency_scenarios = [Decimal(str(e)) for e in request.efficiency_scenarios]

        results = run_efficiency_simulation(
            employees=request.employees,
            efficiency_scenarios=efficiency_scenarios,
            shift_hours=Decimal(str(request.shift_hours)),
            cycle_time_hours=Decimal(str(request.cycle_time_hours)),
            base_efficiency=Decimal(str(request.base_efficiency)),
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
        logger.exception("Invalid input for efficiency simulation: %s", e)
        raise HTTPException(status_code=400, detail="Invalid input: validation failed")
    except Exception as e:
        logger.exception("Failed to run efficiency simulation: %s", e)
        raise HTTPException(status_code=500, detail="Simulation failed")
