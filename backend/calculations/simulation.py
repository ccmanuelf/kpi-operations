"""
Simulation & Capacity Planning Engine
Phase 11: Core calculation module for capacity planning, what-if scenarios, and production simulation

Provides:
- Capacity requirement calculations based on production targets
- What-if simulation for staffing scenarios
- Production forecasting with different configurations
- Floating pool optimization recommendations
- Shift coverage simulation
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple, Any
from datetime import date, datetime, timedelta, timezone
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from backend.crud.client_config import get_client_config_or_defaults
from backend.schemas.simulation import SimulationScenarioType, OptimizationGoal  # canonical definitions

# ---------------------------------------------------------------------------
# Named constants — avoid magic numbers in calculation logic
# ---------------------------------------------------------------------------

# Staffing ratio thresholds used in run_staffing_simulation
STAFFING_UNDERSTAFFED_RATIO = Decimal("0.7")   # below this → understaffed
STAFFING_OVERSTAFFED_RATIO = Decimal("1.5")    # above this → overstaffed
STAFFING_UNDERSTAFFED_EFFICIENCY_PENALTY = Decimal("0.95")  # efficiency multiplier when understaffed
STAFFING_OVERSTAFFED_EFFICIENCY_BONUS = Decimal("0.98")    # efficiency multiplier when overstaffed


@dataclass
class CapacityRequirement:
    """Container for capacity requirement calculation results"""

    target_units: int
    required_employees: int
    required_hours: Decimal
    required_shifts: int
    estimated_efficiency: Decimal
    buffer_employees: int  # Additional employees for absenteeism/breaks
    total_recommended: int
    cost_estimate: Optional[Decimal] = None
    confidence_score: Decimal = Decimal("85.0")
    notes: List[str] = field(default_factory=list)


@dataclass
class SimulationResult:
    """Container for simulation results"""

    scenario_name: str
    scenario_type: SimulationScenarioType
    input_parameters: Dict[str, Any]
    projected_output: Dict[str, Any]
    kpi_impact: Dict[str, Decimal]
    recommendations: List[str]
    confidence_score: Decimal
    comparison_to_baseline: Optional[Dict[str, Decimal]] = None


@dataclass
class ShiftCoverageSimulation:
    """Container for shift coverage simulation"""

    shift_id: int
    shift_name: str
    date: date
    required_employees: int
    available_regular: int
    available_floating_pool: int
    coverage_gap: int
    coverage_percent: Decimal
    recommendations: List[str]


@dataclass
class FloatingPoolOptimization:
    """Container for floating pool optimization results"""

    total_available: int
    total_needed: int
    allocation_suggestions: List[Dict[str, Any]]
    utilization_rate: Decimal
    cost_savings: Optional[Decimal] = None
    efficiency_gain: Optional[Decimal] = None


# =============================================================================
# Capacity Requirement Calculations
# =============================================================================


def calculate_capacity_requirements(
    db: Session,
    client_id: str,
    target_units: int,
    target_date: date,
    cycle_time_hours: Optional[Decimal] = None,
    shift_hours: Decimal = Decimal("8.0"),
    target_efficiency: Decimal = Decimal("85.0"),
    absenteeism_rate: Decimal = Decimal("5.0"),
    include_buffer: bool = True,
) -> CapacityRequirement:
    """
    Calculate staffing requirements to meet production targets.

    Formula: employees = (target_units × cycle_time) / (shift_hours × (efficiency/100))

    Args:
        db: Database session
        client_id: Client ID for configuration lookup
        target_units: Target production units
        target_date: Target date for production
        cycle_time_hours: Hours per unit (uses client config if None)
        shift_hours: Hours per shift (default 8)
        target_efficiency: Target efficiency percentage (default 85%)
        absenteeism_rate: Expected absenteeism percentage (default 5%)
        include_buffer: Include buffer for absenteeism

    Returns:
        CapacityRequirement with staffing recommendations
    """
    # Get client configuration
    config = get_client_config_or_defaults(db, client_id)

    if cycle_time_hours is None:
        cycle_time_hours = Decimal(str(config.get("default_cycle_time_hours", "0.25")))

    # Convert to Decimal for precision
    target_units_dec = Decimal(str(target_units))
    efficiency_factor = target_efficiency / Decimal("100")

    # Calculate raw hours needed
    total_hours_needed = target_units_dec * cycle_time_hours

    # Calculate employees needed (accounting for efficiency)
    effective_hours_per_employee = shift_hours * efficiency_factor

    if effective_hours_per_employee == 0:
        raise ValueError("Invalid efficiency or shift hours")

    raw_employees = (total_hours_needed / effective_hours_per_employee).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    required_employees = int(raw_employees.to_integral_value(rounding=ROUND_HALF_UP))

    # Calculate buffer for absenteeism
    buffer_employees = 0
    if include_buffer:
        buffer_rate = absenteeism_rate / Decimal("100")
        buffer_employees = int((Decimal(required_employees) * buffer_rate).to_integral_value(rounding=ROUND_HALF_UP))
        # Minimum 1 buffer if any employees needed
        if required_employees > 0 and buffer_employees == 0:
            buffer_employees = 1

    total_recommended = required_employees + buffer_employees

    # Calculate shifts needed
    required_shifts = 1
    if total_recommended > 0:
        # Assume max 20 employees per shift as reasonable
        max_per_shift = 20
        required_shifts = max(1, (total_recommended + max_per_shift - 1) // max_per_shift)

    notes = []
    if required_employees == 0 and target_units > 0:
        notes.append("Target can be met with fractional employee allocation")
        required_employees = 1
        total_recommended = 1 + buffer_employees

    if buffer_employees > 0:
        notes.append(f"Buffer includes {absenteeism_rate}% absenteeism allowance")

    return CapacityRequirement(
        target_units=target_units,
        required_employees=required_employees,
        required_hours=total_hours_needed,
        required_shifts=required_shifts,
        estimated_efficiency=target_efficiency,
        buffer_employees=buffer_employees,
        total_recommended=total_recommended,
        confidence_score=Decimal("85.0"),
        notes=notes,
    )


def calculate_production_capacity(
    employees: int,
    shift_hours: Decimal = Decimal("8.0"),
    cycle_time_hours: Decimal = Decimal("0.25"),
    efficiency_percent: Decimal = Decimal("85.0"),
) -> Dict[str, Any]:
    """
    Calculate production capacity given staffing levels.

    Formula: capacity = (employees × shift_hours × (efficiency/100)) / cycle_time

    Args:
        employees: Number of available employees
        shift_hours: Hours per shift
        cycle_time_hours: Hours per unit
        efficiency_percent: Expected efficiency percentage

    Returns:
        Dictionary with capacity metrics
    """
    if cycle_time_hours == 0:
        raise ValueError("Cycle time cannot be zero")

    efficiency_factor = efficiency_percent / Decimal("100")

    # Calculate effective production hours
    effective_hours = Decimal(employees) * shift_hours * efficiency_factor

    # Calculate units capacity
    units_capacity = (effective_hours / cycle_time_hours).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Calculate hourly rate
    hourly_rate = (
        (units_capacity / shift_hours).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if shift_hours > 0
        else Decimal("0")
    )

    return {
        "employees": employees,
        "shift_hours": shift_hours,
        "cycle_time_hours": cycle_time_hours,
        "efficiency_percent": efficiency_percent,
        "units_capacity": int(units_capacity),
        "hourly_rate": hourly_rate,
        "effective_production_hours": effective_hours,
    }


# =============================================================================
# What-If Simulation Engine
# =============================================================================


def run_staffing_simulation(
    base_employees: int,
    scenarios: List[int],
    shift_hours: Decimal = Decimal("8.0"),
    cycle_time_hours: Decimal = Decimal("0.25"),
    base_efficiency: Decimal = Decimal("85.0"),
    efficiency_scaling: bool = True,
) -> List[SimulationResult]:
    """
    Simulate production outcomes with different staffing levels.

    Args:
        base_employees: Current/baseline employee count
        scenarios: List of employee counts to simulate
        shift_hours: Hours per shift
        cycle_time_hours: Hours per unit
        base_efficiency: Baseline efficiency percentage
        efficiency_scaling: Apply efficiency scaling for team size

    Returns:
        List of SimulationResult for each scenario
    """
    results = []

    # Calculate baseline for comparison
    baseline = calculate_production_capacity(
        employees=base_employees,
        shift_hours=shift_hours,
        cycle_time_hours=cycle_time_hours,
        efficiency_percent=base_efficiency,
    )

    for employee_count in scenarios:
        # Apply efficiency scaling if enabled
        # Efficiency tends to decrease slightly with very large or very small teams
        adjusted_efficiency = base_efficiency
        if efficiency_scaling:
            ratio = Decimal(employee_count) / Decimal(max(1, base_employees))
            if ratio < STAFFING_UNDERSTAFFED_RATIO:
                # Understaffed - efficiency drops
                adjusted_efficiency = base_efficiency * STAFFING_UNDERSTAFFED_EFFICIENCY_PENALTY
            elif ratio > STAFFING_OVERSTAFFED_RATIO:
                # Overstaffed - marginal efficiency decrease
                adjusted_efficiency = base_efficiency * STAFFING_OVERSTAFFED_EFFICIENCY_BONUS

        # Calculate capacity for this scenario
        capacity = calculate_production_capacity(
            employees=employee_count,
            shift_hours=shift_hours,
            cycle_time_hours=cycle_time_hours,
            efficiency_percent=adjusted_efficiency,
        )

        # Calculate comparison to baseline
        production_change = Decimal("0")
        if baseline["units_capacity"] > 0:
            production_change = (
                (Decimal(capacity["units_capacity"]) - Decimal(baseline["units_capacity"]))
                / Decimal(baseline["units_capacity"])
                * Decimal("100")
            ).quantize(Decimal("0.01"))

        employee_change = employee_count - base_employees
        employee_change_pct = Decimal("0")
        if base_employees > 0:
            employee_change_pct = (Decimal(employee_change) / Decimal(base_employees) * Decimal("100")).quantize(
                Decimal("0.01")
            )

        # Generate recommendations
        recommendations = []
        if employee_count > base_employees:
            recommendations.append(
                f"Adding {employee_count - base_employees} employees increases capacity by {production_change}%"
            )
        elif employee_count < base_employees:
            recommendations.append(
                f"Reducing {base_employees - employee_count} employees decreases capacity by {abs(production_change)}%"
            )

        if adjusted_efficiency < base_efficiency:
            recommendations.append("Note: Efficiency adjustment applied due to team size change")

        result = SimulationResult(
            scenario_name=f"{employee_count}_employees",
            scenario_type=SimulationScenarioType.STAFFING,
            input_parameters={
                "employees": employee_count,
                "shift_hours": str(shift_hours),
                "cycle_time_hours": str(cycle_time_hours),
                "efficiency_percent": str(adjusted_efficiency),
            },
            projected_output={
                "units_capacity": capacity["units_capacity"],
                "hourly_rate": str(capacity["hourly_rate"]),
                "effective_hours": str(capacity["effective_production_hours"]),
            },
            kpi_impact={
                "production_change_percent": production_change,
                "efficiency": adjusted_efficiency,
                "employee_change": Decimal(employee_change),
                "employee_change_percent": employee_change_pct,
            },
            recommendations=recommendations,
            confidence_score=Decimal("90.0"),
            comparison_to_baseline={
                "baseline_units": Decimal(baseline["units_capacity"]),
                "scenario_units": Decimal(capacity["units_capacity"]),
                "difference": Decimal(capacity["units_capacity"]) - Decimal(baseline["units_capacity"]),
            },
        )
        results.append(result)

    return results


def run_efficiency_simulation(
    employees: int,
    efficiency_scenarios: List[Decimal],
    shift_hours: Decimal = Decimal("8.0"),
    cycle_time_hours: Decimal = Decimal("0.25"),
    base_efficiency: Decimal = Decimal("85.0"),
) -> List[SimulationResult]:
    """
    Simulate production outcomes with different efficiency levels.

    Args:
        employees: Number of employees
        efficiency_scenarios: List of efficiency percentages to simulate
        shift_hours: Hours per shift
        cycle_time_hours: Hours per unit
        base_efficiency: Baseline efficiency for comparison

    Returns:
        List of SimulationResult for each scenario
    """
    results = []

    # Calculate baseline
    baseline = calculate_production_capacity(
        employees=employees,
        shift_hours=shift_hours,
        cycle_time_hours=cycle_time_hours,
        efficiency_percent=base_efficiency,
    )

    for efficiency in efficiency_scenarios:
        capacity = calculate_production_capacity(
            employees=employees,
            shift_hours=shift_hours,
            cycle_time_hours=cycle_time_hours,
            efficiency_percent=efficiency,
        )

        production_change = Decimal("0")
        if baseline["units_capacity"] > 0:
            production_change = (
                (Decimal(capacity["units_capacity"]) - Decimal(baseline["units_capacity"]))
                / Decimal(baseline["units_capacity"])
                * Decimal("100")
            ).quantize(Decimal("0.01"))

        efficiency_change = efficiency - base_efficiency

        recommendations = []
        if efficiency > base_efficiency:
            recommendations.append(
                f"Improving efficiency by {efficiency_change}% increases output by {production_change}%"
            )
            recommendations.append("Consider: training, process optimization, better tooling")
        elif efficiency < base_efficiency:
            recommendations.append(
                f"Efficiency drop of {abs(efficiency_change)}% reduces output by {abs(production_change)}%"
            )
            recommendations.append("Investigate: equipment issues, training gaps, process bottlenecks")

        result = SimulationResult(
            scenario_name=f"{efficiency}_percent_efficiency",
            scenario_type=SimulationScenarioType.EFFICIENCY,
            input_parameters={"employees": employees, "efficiency_percent": str(efficiency)},
            projected_output={
                "units_capacity": capacity["units_capacity"],
                "hourly_rate": str(capacity["hourly_rate"]),
            },
            kpi_impact={"production_change_percent": production_change, "efficiency_change": efficiency_change},
            recommendations=recommendations,
            confidence_score=Decimal("88.0"),
            comparison_to_baseline={
                "baseline_units": Decimal(baseline["units_capacity"]),
                "scenario_units": Decimal(capacity["units_capacity"]),
                "difference": Decimal(capacity["units_capacity"]) - Decimal(baseline["units_capacity"]),
            },
        )
        results.append(result)

    return results


# =============================================================================
# Shift Coverage Simulation
# =============================================================================


def simulate_shift_coverage(
    regular_employees: int,
    floating_pool_available: int,
    required_employees: int,
    shift_name: str = "Default Shift",
    shift_id: int = 0,
    target_date: Optional[date] = None,
) -> ShiftCoverageSimulation:
    """
    Simulate shift coverage with regular and floating pool employees.

    Args:
        regular_employees: Number of regular shift employees
        floating_pool_available: Available floating pool employees
        required_employees: Required employees for the shift
        shift_name: Name of the shift
        shift_id: Shift ID
        target_date: Target date for simulation

    Returns:
        ShiftCoverageSimulation with coverage analysis
    """
    if target_date is None:
        target_date = date.today()

    total_available = regular_employees + floating_pool_available
    coverage_gap = max(0, required_employees - total_available)

    coverage_percent = Decimal("100.0")
    if required_employees > 0:
        coverage_percent = (
            Decimal(min(total_available, required_employees)) / Decimal(required_employees) * Decimal("100")
        ).quantize(Decimal("0.01"))

    recommendations = []

    if coverage_gap > 0:
        recommendations.append(f"Coverage gap: {coverage_gap} employees needed")
        recommendations.append("Consider: overtime, temporary staff, cross-training")
    elif floating_pool_available > 0 and regular_employees < required_employees:
        needed_from_pool = required_employees - regular_employees
        recommendations.append(f"Assign {needed_from_pool} floating pool employees to cover gap")
    elif total_available > required_employees:
        excess = total_available - required_employees
        recommendations.append(f"Overstaffed by {excess} employees")
        recommendations.append("Consider: reassignment to other shifts, training activities")

    if coverage_percent < Decimal("90"):
        recommendations.append("WARNING: Coverage below 90% - production targets at risk")

    return ShiftCoverageSimulation(
        shift_id=shift_id,
        shift_name=shift_name,
        date=target_date,
        required_employees=required_employees,
        available_regular=regular_employees,
        available_floating_pool=floating_pool_available,
        coverage_gap=coverage_gap,
        coverage_percent=coverage_percent,
        recommendations=recommendations,
    )


def simulate_multi_shift_coverage(
    shifts: List[Dict[str, Any]], floating_pool_total: int
) -> Tuple[List[ShiftCoverageSimulation], Dict[str, Any]]:
    """
    Simulate coverage across multiple shifts with floating pool allocation.

    Args:
        shifts: List of shift configurations with regular_employees and required
        floating_pool_total: Total floating pool employees available

    Returns:
        Tuple of (list of shift simulations, allocation summary)
    """
    results = []
    remaining_pool = floating_pool_total
    total_gap = 0
    total_required = 0
    total_covered = 0
    allocations = []

    # Sort shifts by coverage gap (prioritize most understaffed)
    sorted_shifts = sorted(shifts, key=lambda s: s.get("required", 0) - s.get("regular_employees", 0), reverse=True)

    for shift in sorted_shifts:
        shift_id = shift.get("shift_id", 0)
        shift_name = shift.get("shift_name", f"Shift {shift_id}")
        regular = shift.get("regular_employees", 0)
        required = shift.get("required", 0)
        target_date = shift.get("target_date", date.today())

        # Calculate gap and allocate from pool
        gap = max(0, required - regular)
        pool_allocation = min(gap, remaining_pool)
        remaining_pool -= pool_allocation

        if pool_allocation > 0:
            allocations.append(
                {"shift_id": shift_id, "shift_name": shift_name, "pool_employees_assigned": pool_allocation}
            )

        simulation = simulate_shift_coverage(
            regular_employees=regular,
            floating_pool_available=pool_allocation,
            required_employees=required,
            shift_name=shift_name,
            shift_id=shift_id,
            target_date=target_date,
        )
        results.append(simulation)

        total_gap += simulation.coverage_gap
        total_required += required
        total_covered += min(regular + pool_allocation, required)

    overall_coverage = Decimal("100.0")
    if total_required > 0:
        overall_coverage = (Decimal(total_covered) / Decimal(total_required) * Decimal("100")).quantize(Decimal("0.01"))

    summary = {
        "total_shifts": len(shifts),
        "total_required": total_required,
        "total_covered": total_covered,
        "total_gap": total_gap,
        "overall_coverage_percent": overall_coverage,
        "floating_pool_total": floating_pool_total,
        "floating_pool_allocated": floating_pool_total - remaining_pool,
        "floating_pool_remaining": remaining_pool,
        "allocations": allocations,
    }

    return results, summary


# =============================================================================
# Floating Pool Optimization
# =============================================================================


def optimize_floating_pool_allocation(
    db: Session,
    client_id: str,
    target_date: date,
    available_pool_employees: List[Dict[str, Any]],
    shift_requirements: List[Dict[str, Any]],
    optimization_goal: OptimizationGoal = OptimizationGoal.BALANCE_WORKLOAD,
) -> FloatingPoolOptimization:
    """
    Optimize floating pool employee allocation across shifts.

    Args:
        db: Database session
        client_id: Client ID
        target_date: Target date for allocation
        available_pool_employees: List of available floating pool employees
        shift_requirements: List of shift requirements with gaps
        optimization_goal: Optimization objective

    Returns:
        FloatingPoolOptimization with allocation recommendations
    """
    total_available = len(available_pool_employees)

    # Calculate total need across all shifts
    total_needed = sum(max(0, req.get("required", 0) - req.get("regular_employees", 0)) for req in shift_requirements)

    allocation_suggestions = []
    assigned_count = 0

    if optimization_goal == OptimizationGoal.BALANCE_WORKLOAD:
        # Distribute evenly across shifts with gaps
        shifts_with_gaps = [
            req for req in shift_requirements if req.get("required", 0) > req.get("regular_employees", 0)
        ]

        if shifts_with_gaps and total_available > 0:
            employees_per_shift = total_available // len(shifts_with_gaps)
            remainder = total_available % len(shifts_with_gaps)

            pool_index = 0
            for i, shift in enumerate(shifts_with_gaps):
                allocation_count = employees_per_shift + (1 if i < remainder else 0)
                gap = shift.get("required", 0) - shift.get("regular_employees", 0)
                actual_allocation = min(allocation_count, gap, total_available - assigned_count)

                if actual_allocation > 0:
                    employees_for_shift = available_pool_employees[pool_index : pool_index + actual_allocation]
                    allocation_suggestions.append(
                        {
                            "shift_id": shift.get("shift_id"),
                            "shift_name": shift.get("shift_name", ""),
                            "employees_assigned": actual_allocation,
                            "employee_ids": [e.get("employee_id") for e in employees_for_shift],
                            "gap_remaining": max(0, gap - actual_allocation),
                        }
                    )
                    pool_index += actual_allocation
                    assigned_count += actual_allocation

    elif optimization_goal == OptimizationGoal.MEET_TARGET:
        # Fill gaps in priority order until pool exhausted
        sorted_by_gap = sorted(
            shift_requirements, key=lambda x: x.get("required", 0) - x.get("regular_employees", 0), reverse=True
        )

        pool_index = 0
        for shift in sorted_by_gap:
            gap = max(0, shift.get("required", 0) - shift.get("regular_employees", 0))
            if gap > 0 and pool_index < total_available:
                allocation_count = min(gap, total_available - pool_index)
                employees_for_shift = available_pool_employees[pool_index : pool_index + allocation_count]

                allocation_suggestions.append(
                    {
                        "shift_id": shift.get("shift_id"),
                        "shift_name": shift.get("shift_name", ""),
                        "employees_assigned": allocation_count,
                        "employee_ids": [e.get("employee_id") for e in employees_for_shift],
                        "gap_remaining": max(0, gap - allocation_count),
                    }
                )
                pool_index += allocation_count
                assigned_count += allocation_count

    utilization_rate = Decimal("0")
    if total_available > 0:
        utilization_rate = (Decimal(assigned_count) / Decimal(total_available) * Decimal("100")).quantize(
            Decimal("0.01")
        )

    return FloatingPoolOptimization(
        total_available=total_available,
        total_needed=total_needed,
        allocation_suggestions=allocation_suggestions,
        utilization_rate=utilization_rate,
    )


# =============================================================================
# Combined Simulation Runner
# =============================================================================


def run_capacity_simulation(db: Session, client_id: str, simulation_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a comprehensive capacity simulation with multiple scenarios.

    Args:
        db: Database session
        client_id: Client ID
        simulation_config: Configuration with:
            - target_units: Production target
            - current_employees: Current staffing
            - shift_hours: Hours per shift
            - cycle_time_hours: Time per unit
            - efficiency: Current efficiency
            - staffing_scenarios: List of employee counts to simulate
            - efficiency_scenarios: List of efficiency levels to simulate

    Returns:
        Comprehensive simulation results
    """
    target_units = simulation_config.get("target_units", 100)
    current_employees = simulation_config.get("current_employees", 10)
    shift_hours = Decimal(str(simulation_config.get("shift_hours", "8.0")))
    cycle_time = Decimal(str(simulation_config.get("cycle_time_hours", "0.25")))
    efficiency = Decimal(str(simulation_config.get("efficiency", "85.0")))

    # Calculate capacity requirements
    requirements = calculate_capacity_requirements(
        db=db,
        client_id=client_id,
        target_units=target_units,
        target_date=date.today(),
        cycle_time_hours=cycle_time,
        shift_hours=shift_hours,
        target_efficiency=efficiency,
    )

    # Calculate current capacity
    current_capacity = calculate_production_capacity(
        employees=current_employees, shift_hours=shift_hours, cycle_time_hours=cycle_time, efficiency_percent=efficiency
    )

    # Run staffing simulations
    staffing_scenarios = simulation_config.get(
        "staffing_scenarios",
        [current_employees - 2, current_employees - 1, current_employees, current_employees + 1, current_employees + 2],
    )
    staffing_results = run_staffing_simulation(
        base_employees=current_employees,
        scenarios=[s for s in staffing_scenarios if s > 0],
        shift_hours=shift_hours,
        cycle_time_hours=cycle_time,
        base_efficiency=efficiency,
    )

    # Run efficiency simulations
    efficiency_scenarios = simulation_config.get(
        "efficiency_scenarios", [Decimal("75.0"), Decimal("80.0"), Decimal("85.0"), Decimal("90.0"), Decimal("95.0")]
    )
    efficiency_results = run_efficiency_simulation(
        employees=current_employees,
        efficiency_scenarios=[Decimal(str(e)) for e in efficiency_scenarios],
        shift_hours=shift_hours,
        cycle_time_hours=cycle_time,
        base_efficiency=efficiency,
    )

    # Calculate gap analysis
    capacity_gap = target_units - current_capacity["units_capacity"]
    gap_percent = Decimal("0")
    if target_units > 0:
        gap_percent = (Decimal(capacity_gap) / Decimal(target_units) * Decimal("100")).quantize(Decimal("0.01"))

    recommendations = []
    if capacity_gap > 0:
        recommendations.append(f"Current capacity short by {capacity_gap} units ({gap_percent}%)")
        recommendations.append(f"Recommended staffing: {requirements.total_recommended} employees")
        if requirements.total_recommended > current_employees:
            recommendations.append(f"Need {requirements.total_recommended - current_employees} additional employees")
    elif capacity_gap < 0:
        recommendations.append(f"Current capacity exceeds target by {abs(capacity_gap)} units")
        recommendations.append("Consider: reduced hours, cross-training, or reassignment")
    else:
        recommendations.append("Current capacity meets target")

    return {
        "simulation_date": datetime.now(tz=timezone.utc).isoformat(),
        "client_id": client_id,
        "configuration": {
            "target_units": target_units,
            "current_employees": current_employees,
            "shift_hours": str(shift_hours),
            "cycle_time_hours": str(cycle_time),
            "efficiency_percent": str(efficiency),
        },
        "capacity_requirements": {
            "target_units": requirements.target_units,
            "required_employees": requirements.required_employees,
            "buffer_employees": requirements.buffer_employees,
            "total_recommended": requirements.total_recommended,
            "required_hours": str(requirements.required_hours),
            "required_shifts": requirements.required_shifts,
            "notes": requirements.notes,
        },
        "current_capacity": current_capacity,
        "gap_analysis": {
            "capacity_gap_units": capacity_gap,
            "gap_percent": str(gap_percent),
            "meets_target": capacity_gap <= 0,
        },
        "staffing_simulations": [
            {
                "scenario": r.scenario_name,
                "input": r.input_parameters,
                "output": r.projected_output,
                "impact": {k: str(v) for k, v in r.kpi_impact.items()},
                "recommendations": r.recommendations,
            }
            for r in staffing_results
        ],
        "efficiency_simulations": [
            {
                "scenario": r.scenario_name,
                "input": r.input_parameters,
                "output": r.projected_output,
                "impact": {k: str(v) for k, v in r.kpi_impact.items()},
                "recommendations": r.recommendations,
            }
            for r in efficiency_results
        ],
        "recommendations": recommendations,
    }
