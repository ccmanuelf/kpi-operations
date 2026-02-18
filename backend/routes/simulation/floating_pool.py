"""
Simulation API — Floating Pool Optimization Endpoint

POST /api/simulation/floating-pool-optimization — optimize floating pool allocation across shifts.

Requires supervisor privileges.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_active_supervisor
from backend.database import get_db
from backend.schemas.user import User
from backend.schemas.simulation import (
    FloatingPoolOptimizationRequest,
    FloatingPoolOptimizationResponse,
    AllocationSuggestion,
)
from backend.calculations.simulation import optimize_floating_pool_allocation
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

floating_pool_router = APIRouter()


@floating_pool_router.post("/floating-pool-optimization", response_model=FloatingPoolOptimizationResponse)
async def optimize_floating_pool_endpoint(
    request: FloatingPoolOptimizationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> FloatingPoolOptimizationResponse:
    """
    Optimize floating pool employee allocation across shifts.

    Requires supervisor privileges.

    Args:
        request: Floating pool optimization parameters

    Returns:
        FloatingPoolOptimizationResponse with allocation recommendations
    """
    try:
        target_date_val = request.target_date or date.today()

        # Convert to dict format
        pool_employees = [
            {"employee_id": e.employee_id, "employee_code": e.employee_code, "skills": e.skills}
            for e in request.available_pool_employees
        ]

        shift_requirements = [
            {
                "shift_id": s.shift_id,
                "shift_name": s.shift_name,
                "regular_employees": s.regular_employees,
                "required": s.required,
            }
            for s in request.shift_requirements
        ]

        result = optimize_floating_pool_allocation(
            db=db,
            client_id=current_user.client_id_assigned,
            target_date=target_date_val,
            available_pool_employees=pool_employees,
            shift_requirements=shift_requirements,
            optimization_goal=request.optimization_goal,
        )

        allocation_suggestions = [
            AllocationSuggestion(
                shift_id=s["shift_id"],
                shift_name=s["shift_name"],
                employees_assigned=s["employees_assigned"],
                employee_ids=s["employee_ids"],
                gap_remaining=s["gap_remaining"],
            )
            for s in result.allocation_suggestions
        ]

        return FloatingPoolOptimizationResponse(
            total_available=result.total_available,
            total_needed=result.total_needed,
            allocation_suggestions=allocation_suggestions,
            utilization_rate=float(result.utilization_rate),
            cost_savings=float(result.cost_savings) if result.cost_savings else None,
            efficiency_gain=float(result.efficiency_gain) if result.efficiency_gain else None,
        )

    except Exception as e:
        logger.exception("Failed to optimize floating pool: %s", e)
        raise HTTPException(status_code=500, detail="Optimization failed")
