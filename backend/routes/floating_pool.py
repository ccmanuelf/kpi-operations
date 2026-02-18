"""
Floating Pool Management API Routes
All floating pool CRUD and assignment endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date

from backend.database import get_db
from backend.calculations.simulation import (
    optimize_floating_pool_allocation,
    simulate_shift_coverage,
    run_staffing_simulation,
)
from backend.models.floating_pool import (
    FloatingPoolCreate,
    FloatingPoolUpdate,
    FloatingPoolResponse,
    FloatingPoolAssignmentRequest,
    FloatingPoolUnassignmentRequest,
    FloatingPoolAvailability,
    FloatingPoolSummary,
)
from backend.crud.floating_pool import (
    create_floating_pool_entry,
    get_floating_pool_entry,
    get_floating_pool_entries,
    update_floating_pool_entry,
    delete_floating_pool_entry,
    assign_floating_pool_to_client,
    unassign_floating_pool_from_client,
    get_available_floating_pool_employees,
    get_floating_pool_assignments_by_client,
    is_employee_available_for_assignment,
    get_floating_pool_summary,
)
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/floating-pool", tags=["Floating Pool"])


@router.post("", response_model=FloatingPoolResponse, status_code=status.HTTP_201_CREATED)
def create_floating_pool_entry_endpoint(
    pool_entry: FloatingPoolCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Create new floating pool entry
    SECURITY: Supervisor/admin only
    """
    pool_data = pool_entry.model_dump()
    return create_floating_pool_entry(db, pool_data, current_user)


@router.get("", response_model=List[FloatingPoolResponse])
def list_floating_pool_entries(
    skip: int = 0,
    limit: int = 100,
    employee_id: Optional[int] = None,
    available_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List floating pool entries with filters
    """
    return get_floating_pool_entries(db, current_user, skip, limit, employee_id, available_only)


@router.get("/available/list")
def get_available_floating_pool_list(
    as_of_date: Optional[datetime] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get all currently available floating pool employees
    """
    return get_available_floating_pool_employees(db, current_user, as_of_date)


@router.get("/check-availability/{employee_id}")
def check_employee_availability(
    employee_id: int,
    proposed_start: Optional[datetime] = None,
    proposed_end: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check if an employee is available for a new assignment.
    Returns availability status with conflict details if any.

    Use this before attempting to assign an employee to prevent double-assignment errors.

    Returns:
        {
            "is_available": bool,
            "current_assignment": str or None,
            "conflict_dates": dict or None,
            "message": str
        }
    """
    return is_employee_available_for_assignment(db, employee_id, proposed_start, proposed_end)


@router.get("/summary")
def get_floating_pool_summary_endpoint(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get summary statistics for floating pool.
    Useful for dashboard widgets.

    Returns:
        {
            "total_floating_pool_employees": int,
            "currently_available": int,
            "currently_assigned": int,
            "available_employees": list
        }
    """
    return get_floating_pool_summary(db, current_user)


@router.get("/{pool_id}", response_model=FloatingPoolResponse)
def get_floating_pool_entry_endpoint(
    pool_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get floating pool entry by ID
    """
    pool_entry = get_floating_pool_entry(db, pool_id, current_user)
    if not pool_entry:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")
    return pool_entry


@router.put("/{pool_id}", response_model=FloatingPoolResponse)
def update_floating_pool_entry_endpoint(
    pool_id: int,
    pool_update: FloatingPoolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update floating pool entry
    SECURITY: Supervisor/admin only
    """
    pool_data = pool_update.model_dump(exclude_unset=True)
    updated = update_floating_pool_entry(db, pool_id, pool_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")
    return updated


@router.delete("/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_floating_pool_entry_endpoint(
    pool_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Delete floating pool entry
    SECURITY: Supervisor/admin only
    """
    success = delete_floating_pool_entry(db, pool_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")


@router.post("/assign", response_model=FloatingPoolResponse)
def assign_floating_pool_employee_to_client(
    assignment: FloatingPoolAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Assign floating pool employee to a client
    SECURITY: Supervisor/admin only, verifies client access
    """
    return assign_floating_pool_to_client(
        db,
        assignment.employee_id,
        assignment.client_id,
        assignment.available_from,
        assignment.available_to,
        current_user,
        assignment.notes,
    )


@router.post("/unassign", response_model=FloatingPoolResponse)
def unassign_floating_pool_employee_from_client(
    unassignment: FloatingPoolUnassignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unassign floating pool employee from client
    SECURITY: Supervisor/admin only
    """
    return unassign_floating_pool_from_client(db, unassignment.pool_id, current_user)


# Client floating pool endpoint (separate prefix for /api/clients namespace)
client_floating_pool_router = APIRouter(prefix="/api/clients", tags=["Floating Pool"])


@client_floating_pool_router.get("/{client_id}/floating-pool", response_model=List[FloatingPoolResponse])
def get_client_floating_pool_assignments(
    client_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all floating pool assignments for a specific client
    SECURITY: Verifies user has access to client
    """
    return get_floating_pool_assignments_by_client(db, client_id, current_user, skip, limit)


# ============================================================================
# Simulation-Based Floating Pool Optimization Endpoints
# ============================================================================


@router.get("/simulation/insights")
def get_floating_pool_simulation_insights(
    target_date: Optional[date] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get simulation-based insights for floating pool optimization.
    Analyzes current staffing levels and provides recommendations.

    Returns:
        - current_status: Summary of current floating pool state
        - staffing_scenarios: Simulated outcomes for different pool sizes
        - recommendations: AI-generated recommendations for optimization
        - optimal_allocation: Suggested optimal allocation across shifts/clients
    """
    # Get current floating pool summary
    summary = get_floating_pool_summary(db, current_user)
    total_pool = summary.get("total_floating_pool_employees", 0)
    available = summary.get("currently_available", 0)
    assigned = summary.get("currently_assigned", 0)

    # Run staffing simulation scenarios
    scenarios = [
        {"name": "Current", "employees_change": 0},
        {"name": "-2 employees", "employees_change": -2},
        {"name": "+2 employees", "employees_change": 2},
        {"name": "+5 employees", "employees_change": 5},
    ]

    # Base simulation parameters (would normally come from client config)
    base_employees = assigned if assigned > 0 else 10
    shift_hours = 8.0
    cycle_time_hours = 0.5
    base_efficiency = 85.0

    # Run staffing simulations
    simulation_results = []
    try:
        result = run_staffing_simulation(
            base_employees=base_employees,
            scenarios=scenarios,
            shift_hours=shift_hours,
            cycle_time_hours=cycle_time_hours,
            base_efficiency=base_efficiency,
        )
        simulation_results = result.get("scenario_results", [])
    except Exception:
        logger.warning("run_staffing_simulation failed, using fallback", exc_info=True)
        simulation_results = [
            {
                "scenario": "Current",
                "employees": base_employees,
                "units_per_shift": base_employees * shift_hours / cycle_time_hours * (base_efficiency / 100),
                "efficiency": base_efficiency,
            }
        ]

    # Generate recommendations based on utilization
    recommendations = []
    utilization = (assigned / total_pool * 100) if total_pool > 0 else 0

    if utilization > 90:
        recommendations.append(
            {
                "priority": "high",
                "type": "capacity",
                "message": "Floating pool utilization is very high (>90%). Consider expanding pool size to maintain flexibility.",
                "action": "Consider hiring 2-3 additional floating pool employees",
            }
        )
    elif utilization > 75:
        recommendations.append(
            {
                "priority": "medium",
                "type": "capacity",
                "message": "Floating pool utilization is high (>75%). Monitor closely for potential shortfalls.",
                "action": "Review upcoming production schedules for coverage needs",
            }
        )
    elif utilization < 25 and total_pool > 5:
        recommendations.append(
            {
                "priority": "low",
                "type": "efficiency",
                "message": "Floating pool utilization is low (<25%). Pool may be oversized.",
                "action": "Consider cross-training for additional skills or reassigning permanently",
            }
        )

    if available > 5:
        recommendations.append(
            {
                "priority": "info",
                "type": "optimization",
                "message": f"{available} employees currently unassigned. Review shift coverage needs.",
                "action": "Check production line bottlenecks that could benefit from additional staffing",
            }
        )

    return {
        "current_status": {
            "total_pool_size": total_pool,
            "currently_available": available,
            "currently_assigned": assigned,
            "utilization_percent": round(utilization, 1),
            "target_date": target_date or date.today(),
        },
        "staffing_scenarios": simulation_results,
        "recommendations": recommendations,
        "simulation_parameters": {
            "base_employees": base_employees,
            "shift_hours": shift_hours,
            "cycle_time_hours": cycle_time_hours,
            "base_efficiency": base_efficiency,
        },
    }


@router.post("/simulation/optimize-allocation")
def optimize_floating_pool_allocation_endpoint(
    shift_requirements: List[dict],
    optimization_goal: str = "maximize_coverage",
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Optimize floating pool allocation across shifts/lines.

    Args:
        shift_requirements: List of shift requirements
            [{"shift_id": "S1", "shift_name": "Morning", "required": 10, "current": 8}, ...]
        optimization_goal: "maximize_coverage" | "minimize_overtime" | "balance_workload"
        target_date: Date for the allocation (defaults to today)

    Returns:
        Optimized allocation recommendations for each shift/line
    """
    # Get available floating pool employees
    summary = get_floating_pool_summary(db, current_user)
    available_pool = summary.get("currently_available", 0)

    # Use simulation engine for optimization
    try:
        result = optimize_floating_pool_allocation(
            available_pool_employees=available_pool,
            shift_requirements=shift_requirements,
            optimization_goal=optimization_goal,
            target_date=target_date or date.today(),
        )
        return result
    except Exception:
        logger.warning("optimize_floating_pool_allocation failed, using fallback", exc_info=True)
        # Fallback simple allocation
        total_shortage = sum(max(0, sr.get("required", 0) - sr.get("current", 0)) for sr in shift_requirements)
        allocations = []
        remaining_pool = available_pool

        for sr in shift_requirements:
            shortage = max(0, sr.get("required", 0) - sr.get("current", 0))
            if shortage > 0 and remaining_pool > 0:
                alloc = min(shortage, remaining_pool)
                remaining_pool -= alloc
                allocations.append(
                    {
                        "shift_id": sr.get("shift_id"),
                        "shift_name": sr.get("shift_name"),
                        "required": sr.get("required"),
                        "current": sr.get("current"),
                        "shortage": shortage,
                        "allocated_from_pool": alloc,
                        "final_coverage": sr.get("current", 0) + alloc,
                        "coverage_percent": round(((sr.get("current", 0) + alloc) / sr.get("required", 1)) * 100, 1),
                    }
                )
            else:
                allocations.append(
                    {
                        "shift_id": sr.get("shift_id"),
                        "shift_name": sr.get("shift_name"),
                        "required": sr.get("required"),
                        "current": sr.get("current"),
                        "shortage": shortage,
                        "allocated_from_pool": 0,
                        "final_coverage": sr.get("current", 0),
                        "coverage_percent": (
                            round((sr.get("current", 0) / sr.get("required", 1)) * 100, 1)
                            if sr.get("required", 0) > 0
                            else 100
                        ),
                    }
                )

        return {
            "optimization_goal": optimization_goal,
            "target_date": str(target_date or date.today()),
            "available_pool_employees": available_pool,
            "total_shortage": total_shortage,
            "allocated": available_pool - remaining_pool,
            "remaining_unallocated": remaining_pool,
            "allocations": allocations,
            "coverage_achieved": total_shortage <= available_pool,
        }


@router.post("/simulation/shift-coverage")
def simulate_shift_coverage_endpoint(
    shift_id: str,
    shift_name: str,
    regular_employees: int,
    floating_pool_available: int,
    required_employees: int,
    target_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Simulate coverage for a specific shift with floating pool.

    Returns detailed analysis of coverage gaps and recommendations.
    """
    try:
        result = simulate_shift_coverage(
            shift_id=shift_id,
            shift_name=shift_name,
            regular_employees=regular_employees,
            floating_pool_available=floating_pool_available,
            required_employees=required_employees,
            target_date=target_date or date.today(),
        )
        return result
    except Exception:
        logger.warning("simulate_shift_coverage failed, using fallback", exc_info=True)
        # Fallback calculation
        shortage = max(0, required_employees - regular_employees)
        pool_needed = min(shortage, floating_pool_available)
        final_coverage = regular_employees + pool_needed

        return {
            "shift_id": shift_id,
            "shift_name": shift_name,
            "target_date": str(target_date or date.today()),
            "regular_employees": regular_employees,
            "floating_pool_available": floating_pool_available,
            "required_employees": required_employees,
            "shortage": shortage,
            "floating_pool_allocated": pool_needed,
            "final_coverage": final_coverage,
            "coverage_percent": (
                round((final_coverage / required_employees) * 100, 1) if required_employees > 0 else 100
            ),
            "is_fully_covered": final_coverage >= required_employees,
            "remaining_shortage": max(0, required_employees - final_coverage),
        }
