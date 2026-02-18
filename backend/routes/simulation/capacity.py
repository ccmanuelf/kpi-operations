"""
Simulation API — Capacity Endpoints

POST /api/simulation/capacity-requirements  — staffing requirements to meet targets
POST /api/simulation/production-capacity    — production capacity given staffing levels
GET  /api/simulation/quick/capacity         — quick capacity gap calculation
GET  /api/simulation/quick/staffing         — quick staffing requirement calculation
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.schemas.user import User
from backend.schemas.simulation import (
    CapacityRequirementRequest,
    CapacityRequirementResponse,
    ProductionCapacityRequest,
    ProductionCapacityResponse,
)
from backend.calculations.simulation import (
    calculate_capacity_requirements,
    calculate_production_capacity,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

capacity_router = APIRouter()


@capacity_router.post("/capacity-requirements", response_model=CapacityRequirementResponse)
async def calculate_capacity_requirements_endpoint(
    request: CapacityRequirementRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> CapacityRequirementResponse:
    """
    Calculate staffing requirements to meet production targets.

    Formula: employees = (target_units × cycle_time) / (shift_hours × (efficiency/100))

    Args:
        request: Capacity requirement parameters

    Returns:
        CapacityRequirementResponse with staffing recommendations
    """
    try:
        target_date_val = request.target_date or date.today()
        cycle_time = Decimal(str(request.cycle_time_hours)) if request.cycle_time_hours else None

        result = calculate_capacity_requirements(
            db=db,
            client_id=current_user.client_id_assigned,
            target_units=request.target_units,
            target_date=target_date_val,
            cycle_time_hours=cycle_time,
            shift_hours=Decimal(str(request.shift_hours)),
            target_efficiency=Decimal(str(request.target_efficiency)),
            absenteeism_rate=Decimal(str(request.absenteeism_rate)),
            include_buffer=request.include_buffer,
        )

        return CapacityRequirementResponse(
            target_units=result.target_units,
            required_employees=result.required_employees,
            required_hours=float(result.required_hours),
            required_shifts=result.required_shifts,
            estimated_efficiency=float(result.estimated_efficiency),
            buffer_employees=result.buffer_employees,
            total_recommended=result.total_recommended,
            cost_estimate=float(result.cost_estimate) if result.cost_estimate else None,
            confidence_score=float(result.confidence_score),
            notes=result.notes,
        )

    except ValueError as e:
        logger.exception("Invalid input for capacity requirements: %s", e)
        raise HTTPException(status_code=400, detail="Invalid input: validation failed")
    except Exception as e:
        logger.exception("Failed to calculate capacity requirements: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@capacity_router.post("/production-capacity", response_model=ProductionCapacityResponse)
async def calculate_production_capacity_endpoint(
    request: ProductionCapacityRequest, current_user: User = Depends(get_current_user)
) -> ProductionCapacityResponse:
    """
    Calculate production capacity given staffing levels.

    Formula: capacity = (employees × shift_hours × (efficiency/100)) / cycle_time

    Args:
        request: Production capacity parameters

    Returns:
        ProductionCapacityResponse with capacity metrics
    """
    try:
        result = calculate_production_capacity(
            employees=request.employees,
            shift_hours=Decimal(str(request.shift_hours)),
            cycle_time_hours=Decimal(str(request.cycle_time_hours)),
            efficiency_percent=Decimal(str(request.efficiency_percent)),
        )

        return ProductionCapacityResponse(
            employees=result["employees"],
            shift_hours=float(result["shift_hours"]),
            cycle_time_hours=float(result["cycle_time_hours"]),
            efficiency_percent=float(result["efficiency_percent"]),
            units_capacity=result["units_capacity"],
            hourly_rate=float(result["hourly_rate"]),
            effective_production_hours=float(result["effective_production_hours"]),
        )

    except ValueError as e:
        logger.exception("Invalid input for production capacity: %s", e)
        raise HTTPException(status_code=400, detail="Invalid input: validation failed")
    except Exception as e:
        logger.exception("Failed to calculate production capacity: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@capacity_router.get("/quick/capacity")
async def quick_capacity_calculation(
    employees: int = Query(..., ge=1, description="Number of employees"),
    target_units: int = Query(..., gt=0, description="Target production units"),
    shift_hours: float = Query(default=8.0, gt=0, le=24),
    cycle_time_hours: float = Query(default=0.25, gt=0),
    efficiency: float = Query(default=85.0, ge=0, le=100),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Quick capacity gap calculation via query parameters.

    Args:
        employees: Number of available employees
        target_units: Target production units
        shift_hours: Hours per shift
        cycle_time_hours: Hours per unit
        efficiency: Expected efficiency percentage

    Returns:
        Quick capacity analysis
    """
    capacity = calculate_production_capacity(
        employees=employees,
        shift_hours=Decimal(str(shift_hours)),
        cycle_time_hours=Decimal(str(cycle_time_hours)),
        efficiency_percent=Decimal(str(efficiency)),
    )

    gap = target_units - capacity["units_capacity"]
    meets_target = gap <= 0

    return {
        "employees": employees,
        "target_units": target_units,
        "current_capacity": capacity["units_capacity"],
        "gap": gap,
        "meets_target": meets_target,
        "hourly_rate": float(capacity["hourly_rate"]),
        "utilization_needed": (
            min(100, (target_units / max(1, capacity["units_capacity"])) * 100) if capacity["units_capacity"] > 0 else 0
        ),
    }


@capacity_router.get("/quick/staffing")
async def quick_staffing_calculation(
    target_units: int = Query(..., gt=0, description="Target production units"),
    shift_hours: float = Query(default=8.0, gt=0, le=24),
    cycle_time_hours: float = Query(default=0.25, gt=0),
    efficiency: float = Query(default=85.0, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Quick staffing requirement calculation via query parameters.

    Args:
        target_units: Target production units
        shift_hours: Hours per shift
        cycle_time_hours: Hours per unit
        efficiency: Expected efficiency percentage

    Returns:
        Quick staffing requirements
    """
    result = calculate_capacity_requirements(
        db=db,
        client_id=current_user.client_id_assigned,
        target_units=target_units,
        target_date=date.today(),
        cycle_time_hours=Decimal(str(cycle_time_hours)),
        shift_hours=Decimal(str(shift_hours)),
        target_efficiency=Decimal(str(efficiency)),
    )

    return {
        "target_units": target_units,
        "required_employees": result.required_employees,
        "buffer_employees": result.buffer_employees,
        "total_recommended": result.total_recommended,
        "required_hours": float(result.required_hours),
        "estimated_efficiency": float(result.estimated_efficiency),
    }
