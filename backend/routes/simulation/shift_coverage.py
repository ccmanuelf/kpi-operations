"""
Simulation API — Shift Coverage Simulation Endpoints

POST /api/simulation/shift-coverage       — single shift coverage simulation
POST /api/simulation/multi-shift-coverage — multi-shift coverage with floating pool allocation
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.schemas.simulation import (
    ShiftCoverageSimulationRequest,
    ShiftCoverageSimulationResponse,
    MultiShiftCoverageRequest,
    MultiShiftCoverageResponse,
    MultiShiftCoverageSummary,
)
from backend.calculations.simulation import (
    simulate_shift_coverage,
    simulate_multi_shift_coverage,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

shift_coverage_router = APIRouter()


@shift_coverage_router.post("/shift-coverage", response_model=ShiftCoverageSimulationResponse)
async def simulate_shift_coverage_endpoint(
    request: ShiftCoverageSimulationRequest, current_user: User = Depends(get_current_user)
) -> ShiftCoverageSimulationResponse:
    """
    Simulate shift coverage with regular and floating pool employees.

    Args:
        request: Shift coverage simulation parameters

    Returns:
        ShiftCoverageSimulationResponse with coverage analysis
    """
    try:
        target_date_val = request.target_date or date.today()

        result = simulate_shift_coverage(
            regular_employees=request.regular_employees,
            floating_pool_available=request.floating_pool_available,
            required_employees=request.required_employees,
            shift_name=request.shift_name,
            shift_id=request.shift_id,
            target_date=target_date_val,
        )

        return ShiftCoverageSimulationResponse(
            shift_id=result.shift_id,
            shift_name=result.shift_name,
            date=result.date,
            required_employees=result.required_employees,
            available_regular=result.available_regular,
            available_floating_pool=result.available_floating_pool,
            coverage_gap=result.coverage_gap,
            coverage_percent=float(result.coverage_percent),
            recommendations=result.recommendations,
        )

    except Exception as e:
        logger.exception("Failed to simulate shift coverage: %s", e)
        raise HTTPException(status_code=500, detail="Simulation failed")


@shift_coverage_router.post("/multi-shift-coverage", response_model=MultiShiftCoverageResponse)
async def simulate_multi_shift_coverage_endpoint(
    request: MultiShiftCoverageRequest, current_user: User = Depends(get_current_user)
) -> MultiShiftCoverageResponse:
    """
    Simulate coverage across multiple shifts with floating pool allocation.

    Args:
        request: Multi-shift coverage parameters

    Returns:
        MultiShiftCoverageResponse with shift simulations and allocation summary
    """
    try:
        # Convert to dict format for calculation function
        shifts = [
            {
                "shift_id": s.shift_id,
                "shift_name": s.shift_name,
                "regular_employees": s.regular_employees,
                "required": s.required,
                "target_date": s.target_date or date.today(),
            }
            for s in request.shifts
        ]

        shift_results, summary = simulate_multi_shift_coverage(
            shifts=shifts, floating_pool_total=request.floating_pool_total
        )

        shift_responses = [
            ShiftCoverageSimulationResponse(
                shift_id=r.shift_id,
                shift_name=r.shift_name,
                date=r.date,
                required_employees=r.required_employees,
                available_regular=r.available_regular,
                available_floating_pool=r.available_floating_pool,
                coverage_gap=r.coverage_gap,
                coverage_percent=float(r.coverage_percent),
                recommendations=r.recommendations,
            )
            for r in shift_results
        ]

        summary_response = MultiShiftCoverageSummary(
            total_shifts=summary["total_shifts"],
            total_required=summary["total_required"],
            total_covered=summary["total_covered"],
            total_gap=summary["total_gap"],
            overall_coverage_percent=float(summary["overall_coverage_percent"]),
            floating_pool_total=summary["floating_pool_total"],
            floating_pool_allocated=summary["floating_pool_allocated"],
            floating_pool_remaining=summary["floating_pool_remaining"],
            allocations=summary["allocations"],
        )

        return MultiShiftCoverageResponse(shift_simulations=shift_responses, summary=summary_response)

    except Exception as e:
        logger.exception("Failed to simulate multi-shift coverage: %s", e)
        raise HTTPException(status_code=500, detail="Simulation failed")
