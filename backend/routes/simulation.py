"""
Simulation & Capacity Planning API Routes
Phase 11: REST endpoints for simulation and capacity planning

Provides endpoints for:
- Capacity requirement calculations
- Production capacity analysis
- What-if staffing simulations
- Efficiency simulations
- Shift coverage analysis
- Floating pool optimization
- Comprehensive capacity simulation
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from decimal import Decimal

from backend.database import get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User

from backend.calculations.simulation import (
    calculate_capacity_requirements,
    calculate_production_capacity,
    run_staffing_simulation,
    run_efficiency_simulation,
    simulate_shift_coverage,
    simulate_multi_shift_coverage,
    optimize_floating_pool_allocation,
    run_capacity_simulation,
    OptimizationGoal as CalcOptimizationGoal
)

from backend.schemas.simulation import (
    CapacityRequirementRequest,
    CapacityRequirementResponse,
    ProductionCapacityRequest,
    ProductionCapacityResponse,
    StaffingSimulationRequest,
    EfficiencySimulationRequest,
    ShiftCoverageSimulationRequest,
    ShiftCoverageSimulationResponse,
    MultiShiftCoverageRequest,
    MultiShiftCoverageResponse,
    MultiShiftCoverageSummary,
    FloatingPoolOptimizationRequest,
    FloatingPoolOptimizationResponse,
    AllocationSuggestion,
    ComprehensiveSimulationRequest,
    ComprehensiveSimulationResponse,
    GapAnalysis,
    SimulationResultResponse,
    SimulationSummary,
    OptimizationGoal
)

router = APIRouter(prefix="/simulation", tags=["simulation"])


# =============================================================================
# Simulation Overview
# =============================================================================

@router.get("/", response_model=SimulationSummary)
async def get_simulation_overview(
    current_user: User = Depends(get_current_user)
) -> SimulationSummary:
    """
    Get simulation capabilities overview.

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
            "comprehensive_simulation"
        ],
        description="Simulation and capacity planning module for production forecasting and what-if analysis",
        example_use_cases=[
            "Calculate staffing requirements for production targets",
            "Simulate production capacity with different staffing levels",
            "Analyze shift coverage gaps and floating pool allocation",
            "Run what-if scenarios for efficiency improvements",
            "Optimize floating pool employee distribution"
        ]
    )


# =============================================================================
# Capacity Requirements
# =============================================================================

@router.post("/capacity-requirements", response_model=CapacityRequirementResponse)
async def calculate_capacity_requirements_endpoint(
    request: CapacityRequirementRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
            client_id=current_user.client_id,
            target_units=request.target_units,
            target_date=target_date_val,
            cycle_time_hours=cycle_time,
            shift_hours=Decimal(str(request.shift_hours)),
            target_efficiency=Decimal(str(request.target_efficiency)),
            absenteeism_rate=Decimal(str(request.absenteeism_rate)),
            include_buffer=request.include_buffer
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
            notes=result.notes
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating capacity requirements: {str(e)}")


# =============================================================================
# Production Capacity
# =============================================================================

@router.post("/production-capacity", response_model=ProductionCapacityResponse)
async def calculate_production_capacity_endpoint(
    request: ProductionCapacityRequest,
    current_user: User = Depends(get_current_user)
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
            efficiency_percent=Decimal(str(request.efficiency_percent))
        )

        return ProductionCapacityResponse(
            employees=result["employees"],
            shift_hours=float(result["shift_hours"]),
            cycle_time_hours=float(result["cycle_time_hours"]),
            efficiency_percent=float(result["efficiency_percent"]),
            units_capacity=result["units_capacity"],
            hourly_rate=float(result["hourly_rate"]),
            effective_production_hours=float(result["effective_production_hours"])
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating production capacity: {str(e)}")


# =============================================================================
# Staffing Simulation
# =============================================================================

@router.post("/staffing", response_model=List[SimulationResultResponse])
async def run_staffing_simulation_endpoint(
    request: StaffingSimulationRequest,
    current_user: User = Depends(get_current_user)
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
            efficiency_scaling=request.efficiency_scaling
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
                comparison_to_baseline={k: float(v) for k, v in r.comparison_to_baseline.items()}
                if r.comparison_to_baseline else None
            )
            for r in results
        ]

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running staffing simulation: {str(e)}")


# =============================================================================
# Efficiency Simulation
# =============================================================================

@router.post("/efficiency", response_model=List[SimulationResultResponse])
async def run_efficiency_simulation_endpoint(
    request: EfficiencySimulationRequest,
    current_user: User = Depends(get_current_user)
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
            base_efficiency=Decimal(str(request.base_efficiency))
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
                comparison_to_baseline={k: float(v) for k, v in r.comparison_to_baseline.items()}
                if r.comparison_to_baseline else None
            )
            for r in results
        ]

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running efficiency simulation: {str(e)}")


# =============================================================================
# Shift Coverage Simulation
# =============================================================================

@router.post("/shift-coverage", response_model=ShiftCoverageSimulationResponse)
async def simulate_shift_coverage_endpoint(
    request: ShiftCoverageSimulationRequest,
    current_user: User = Depends(get_current_user)
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
            target_date=target_date_val
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
            recommendations=result.recommendations
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error simulating shift coverage: {str(e)}")


@router.post("/multi-shift-coverage", response_model=MultiShiftCoverageResponse)
async def simulate_multi_shift_coverage_endpoint(
    request: MultiShiftCoverageRequest,
    current_user: User = Depends(get_current_user)
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
                "target_date": s.target_date or date.today()
            }
            for s in request.shifts
        ]

        shift_results, summary = simulate_multi_shift_coverage(
            shifts=shifts,
            floating_pool_total=request.floating_pool_total
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
                recommendations=r.recommendations
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
            allocations=summary["allocations"]
        )

        return MultiShiftCoverageResponse(
            shift_simulations=shift_responses,
            summary=summary_response
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error simulating multi-shift coverage: {str(e)}")


# =============================================================================
# Floating Pool Optimization
# =============================================================================

@router.post("/floating-pool-optimization", response_model=FloatingPoolOptimizationResponse)
async def optimize_floating_pool_endpoint(
    request: FloatingPoolOptimizationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
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
                "required": s.required
            }
            for s in request.shift_requirements
        ]

        # Map optimization goal
        calc_goal = CalcOptimizationGoal(request.optimization_goal.value)

        result = optimize_floating_pool_allocation(
            db=db,
            client_id=current_user.client_id,
            target_date=target_date_val,
            available_pool_employees=pool_employees,
            shift_requirements=shift_requirements,
            optimization_goal=calc_goal
        )

        allocation_suggestions = [
            AllocationSuggestion(
                shift_id=s["shift_id"],
                shift_name=s["shift_name"],
                employees_assigned=s["employees_assigned"],
                employee_ids=s["employee_ids"],
                gap_remaining=s["gap_remaining"]
            )
            for s in result.allocation_suggestions
        ]

        return FloatingPoolOptimizationResponse(
            total_available=result.total_available,
            total_needed=result.total_needed,
            allocation_suggestions=allocation_suggestions,
            utilization_rate=float(result.utilization_rate),
            cost_savings=float(result.cost_savings) if result.cost_savings else None,
            efficiency_gain=float(result.efficiency_gain) if result.efficiency_gain else None
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error optimizing floating pool: {str(e)}")


# =============================================================================
# Comprehensive Simulation
# =============================================================================

@router.post("/comprehensive")
async def run_comprehensive_simulation(
    request: ComprehensiveSimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
            "efficiency": request.efficiency
        }

        if request.staffing_scenarios:
            config["staffing_scenarios"] = request.staffing_scenarios

        if request.efficiency_scenarios:
            config["efficiency_scenarios"] = request.efficiency_scenarios

        result = run_capacity_simulation(
            db=db,
            client_id=current_user.client_id,
            simulation_config=config
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running comprehensive simulation: {str(e)}")


# =============================================================================
# Quick Calculations
# =============================================================================

@router.get("/quick/capacity")
async def quick_capacity_calculation(
    employees: int = Query(..., ge=1, description="Number of employees"),
    target_units: int = Query(..., gt=0, description="Target production units"),
    shift_hours: float = Query(default=8.0, gt=0, le=24),
    cycle_time_hours: float = Query(default=0.25, gt=0),
    efficiency: float = Query(default=85.0, ge=0, le=100),
    current_user: User = Depends(get_current_user)
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
        efficiency_percent=Decimal(str(efficiency))
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
        "utilization_needed": min(100, (target_units / max(1, capacity["units_capacity"])) * 100)
        if capacity["units_capacity"] > 0 else 0
    }


@router.get("/quick/staffing")
async def quick_staffing_calculation(
    target_units: int = Query(..., gt=0, description="Target production units"),
    shift_hours: float = Query(default=8.0, gt=0, le=24),
    cycle_time_hours: float = Query(default=0.25, gt=0),
    efficiency: float = Query(default=85.0, ge=0, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
        client_id=current_user.client_id,
        target_units=target_units,
        target_date=date.today(),
        cycle_time_hours=Decimal(str(cycle_time_hours)),
        shift_hours=Decimal(str(shift_hours)),
        target_efficiency=Decimal(str(efficiency))
    )

    return {
        "target_units": target_units,
        "required_employees": result.required_employees,
        "buffer_employees": result.buffer_employees,
        "total_recommended": result.total_recommended,
        "required_hours": float(result.required_hours),
        "estimated_efficiency": float(result.estimated_efficiency)
    }


# =============================================================================
# SimPy Production Line Simulation
# =============================================================================

from backend.calculations.production_line_simulation import (
    ProductionLineConfig,
    WorkStation,
    WorkStationType,
    run_production_simulation,
    compare_scenarios,
    analyze_bottlenecks,
    simulate_floating_pool_impact,
    create_default_production_line
)


@router.get("/production-line/guide")
async def get_production_line_simulation_guide(
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Get a guide for using the production line simulation.

    Returns configuration options, example scenarios, and best practices.
    """
    return {
        "title": "Production Line Simulation Guide",
        "description": "SimPy-based discrete-event simulation for manufacturing process modeling",
        "quick_start": [
            "1. Use /production-line/default to generate a default production line config",
            "2. Customize the configuration for your specific use case",
            "3. Run simulation with /production-line/run endpoint",
            "4. Analyze bottlenecks with /production-line/bottlenecks",
            "5. Compare scenarios with /production-line/compare"
        ],
        "configuration_options": {
            "line_config": {
                "line_id": "Unique identifier for the production line",
                "name": "Human-readable name",
                "shift_duration_hours": "Length of a shift (default: 8)",
                "break_duration_minutes": "Duration of breaks (default: 30)",
                "breaks_per_shift": "Number of breaks per shift (default: 2)",
                "workers_per_station": "Default workers per station",
                "floating_pool_size": "Number of floating pool workers"
            },
            "station_config": {
                "station_id": "Unique station identifier",
                "name": "Station name",
                "station_type": ["receiving", "inspection", "assembly", "testing", "packaging", "shipping"],
                "cycle_time_minutes": "Average processing time per unit",
                "cycle_time_variability": "Variability coefficient (0.1 = 10% variation)",
                "num_workers": "Workers assigned to this station",
                "quality_rate": "Pass rate (0.98 = 98% pass)",
                "downtime_probability": "Hourly downtime probability (0.02 = 2%)",
                "downtime_duration_minutes": "Average downtime duration"
            }
        },
        "example_scenarios": [
            {
                "name": "Add Workers to Bottleneck",
                "description": "Increase workers at the slowest station",
                "config_change": {"workers_per_station": 3}
            },
            {
                "name": "Reduce Cycle Time",
                "description": "Improve process to reduce cycle time by 20%",
                "station_modifications": {"Assembly 2": {"cycle_time_minutes": 12}}
            },
            {
                "name": "Add Floating Pool",
                "description": "Add flexible workers to cover gaps",
                "config_change": {"floating_pool_size": 2}
            }
        ],
        "best_practices": [
            "Start with the default configuration and adjust based on your actual data",
            "Run simulations for at least 8 hours (one shift) for meaningful results",
            "Use random_seed for reproducible results when comparing scenarios",
            "Focus on bottleneck stations first - they limit overall throughput",
            "Consider quality rates and downtime, not just cycle times"
        ],
        "metrics_explained": {
            "throughput_per_hour": "Units completed per hour",
            "efficiency": "Actual vs theoretical output percentage",
            "utilization": "Time station is busy vs available",
            "bottleneck": "Station with highest utilization limiting throughput",
            "quality_yield": "Percentage of units passing all quality checks"
        }
    }


@router.get("/production-line/default")
async def get_default_production_line_config(
    num_stations: int = Query(default=4, ge=2, le=10, description="Number of work stations"),
    workers_per_station: int = Query(default=2, ge=1, le=10, description="Workers per station"),
    floating_pool_size: int = Query(default=0, ge=0, le=10, description="Floating pool size"),
    base_cycle_time: float = Query(default=15.0, gt=0, le=120, description="Base cycle time in minutes"),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Generate a default production line configuration.

    Use this as a starting point and customize for your specific needs.
    """
    config = create_default_production_line(
        line_id=f"LINE-{current_user.client_id or 'DEFAULT'}",
        num_stations=num_stations,
        workers_per_station=workers_per_station,
        floating_pool_size=floating_pool_size,
        base_cycle_time=base_cycle_time
    )

    return {
        "line_id": config.line_id,
        "name": config.name,
        "shift_duration_hours": config.shift_duration_hours,
        "break_duration_minutes": config.break_duration_minutes,
        "breaks_per_shift": config.breaks_per_shift,
        "workers_per_station": config.workers_per_station,
        "floating_pool_size": config.floating_pool_size,
        "stations": [
            {
                "station_id": s.station_id,
                "name": s.name,
                "station_type": s.station_type.value,
                "cycle_time_minutes": s.cycle_time_minutes,
                "cycle_time_variability": s.cycle_time_variability,
                "num_workers": s.num_workers,
                "quality_rate": s.quality_rate,
                "downtime_probability": s.downtime_probability,
                "downtime_duration_minutes": s.downtime_duration_minutes
            }
            for s in config.stations
        ]
    }


@router.post("/production-line/run")
async def run_production_line_simulation(
    config: dict,
    duration_hours: float = Query(default=8.0, gt=0, le=24, description="Simulation duration in hours"),
    arrival_rate_per_hour: Optional[float] = Query(default=None, gt=0, description="Unit arrival rate (auto-calculated if not specified)"),
    max_units: Optional[int] = Query(default=None, gt=0, description="Maximum units to simulate"),
    random_seed: int = Query(default=42, description="Random seed for reproducibility"),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Run a production line simulation with custom configuration.

    Args:
        config: Production line configuration (use /production-line/default as template)
        duration_hours: How long to simulate (default: 8 hours = one shift)
        arrival_rate_per_hour: How many units arrive per hour (auto-calculated if not set)
        max_units: Stop after this many units (optional)
        random_seed: For reproducible results

    Returns:
        Complete simulation results with metrics and recommendations
    """
    try:
        # Parse configuration
        stations = [
            WorkStation(
                station_id=s["station_id"],
                name=s["name"],
                station_type=WorkStationType(s["station_type"]),
                cycle_time_minutes=s["cycle_time_minutes"],
                cycle_time_variability=s.get("cycle_time_variability", 0.1),
                num_workers=s.get("num_workers", 1),
                quality_rate=s.get("quality_rate", 0.98),
                downtime_probability=s.get("downtime_probability", 0.02),
                downtime_duration_minutes=s.get("downtime_duration_minutes", 30)
            )
            for s in config["stations"]
        ]

        line_config = ProductionLineConfig(
            line_id=config.get("line_id", "LINE-001"),
            name=config.get("name", "Production Line"),
            stations=stations,
            shift_duration_hours=config.get("shift_duration_hours", 8.0),
            break_duration_minutes=config.get("break_duration_minutes", 30),
            breaks_per_shift=config.get("breaks_per_shift", 2),
            workers_per_station=config.get("workers_per_station", 1),
            floating_pool_size=config.get("floating_pool_size", 0)
        )

        result = run_production_simulation(
            config=line_config,
            duration_hours=duration_hours,
            arrival_rate_per_hour=arrival_rate_per_hour,
            max_units=max_units,
            random_seed=random_seed
        )

        return {
            "line_id": result.line_id,
            "simulation_duration_hours": result.simulation_duration_hours,
            "summary": {
                "units_started": result.units_started,
                "units_completed": result.units_completed,
                "units_rejected": result.units_rejected,
                "throughput_per_hour": round(result.throughput_per_hour, 2),
                "efficiency": round(result.efficiency, 2),
                "quality_yield": round(result.quality_yield, 2),
                "total_downtime_minutes": round(result.total_downtime_minutes, 2)
            },
            "bottleneck_analysis": {
                "bottleneck_station": result.bottleneck_station,
                "avg_cycle_time_minutes": round(result.avg_cycle_time_minutes, 2)
            },
            "station_utilization": {
                k: round(v, 2) for k, v in result.utilization_by_station.items()
            },
            "recommendations": result.recommendations,
            "events_sample": result.events_log[:20] if result.events_log else []
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error running simulation: {str(e)}")


@router.post("/production-line/compare")
async def compare_production_scenarios(
    base_config: dict,
    scenarios: List[dict],
    duration_hours: float = Query(default=8.0, gt=0, le=24),
    random_seed: int = Query(default=42),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Compare multiple production scenarios against a baseline.

    Args:
        base_config: Base production line configuration
        scenarios: List of scenario modifications to compare
        duration_hours: Simulation duration
        random_seed: For reproducible comparisons

    Returns:
        Comparison results showing impact of each scenario
    """
    try:
        # Parse base configuration
        base_stations = [
            WorkStation(
                station_id=s["station_id"],
                name=s["name"],
                station_type=WorkStationType(s["station_type"]),
                cycle_time_minutes=s["cycle_time_minutes"],
                cycle_time_variability=s.get("cycle_time_variability", 0.1),
                num_workers=s.get("num_workers", 1),
                quality_rate=s.get("quality_rate", 0.98),
                downtime_probability=s.get("downtime_probability", 0.02),
                downtime_duration_minutes=s.get("downtime_duration_minutes", 30)
            )
            for s in base_config["stations"]
        ]

        line_config = ProductionLineConfig(
            line_id=base_config.get("line_id", "LINE-001"),
            name=base_config.get("name", "Production Line"),
            stations=base_stations,
            shift_duration_hours=base_config.get("shift_duration_hours", 8.0),
            break_duration_minutes=base_config.get("break_duration_minutes", 30),
            breaks_per_shift=base_config.get("breaks_per_shift", 2),
            workers_per_station=base_config.get("workers_per_station", 1),
            floating_pool_size=base_config.get("floating_pool_size", 0)
        )

        results = compare_scenarios(
            base_config=line_config,
            scenarios=scenarios,
            duration_hours=duration_hours,
            random_seed=random_seed
        )

        return {
            "comparison_date": datetime.utcnow().isoformat(),
            "duration_hours": duration_hours,
            "baseline": results[0] if results else None,
            "scenarios": results[1:] if len(results) > 1 else [],
            "summary": {
                "best_throughput": max(r["throughput_per_hour"] for r in results) if results else 0,
                "best_scenario": max(results, key=lambda r: r["throughput_per_hour"])["scenario"] if results else None,
                "highest_efficiency": max(r["efficiency"] for r in results) if results else 0
            }
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error comparing scenarios: {str(e)}")


@router.post("/production-line/bottlenecks")
async def analyze_production_bottlenecks(
    config: dict,
    duration_hours: float = Query(default=8.0, gt=0, le=24),
    random_seed: int = Query(default=42),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Analyze bottlenecks in the production line.

    Returns detailed analysis of where constraints are limiting throughput.
    """
    try:
        stations = [
            WorkStation(
                station_id=s["station_id"],
                name=s["name"],
                station_type=WorkStationType(s["station_type"]),
                cycle_time_minutes=s["cycle_time_minutes"],
                cycle_time_variability=s.get("cycle_time_variability", 0.1),
                num_workers=s.get("num_workers", 1),
                quality_rate=s.get("quality_rate", 0.98),
                downtime_probability=s.get("downtime_probability", 0.02),
                downtime_duration_minutes=s.get("downtime_duration_minutes", 30)
            )
            for s in config["stations"]
        ]

        line_config = ProductionLineConfig(
            line_id=config.get("line_id", "LINE-001"),
            name=config.get("name", "Production Line"),
            stations=stations,
            shift_duration_hours=config.get("shift_duration_hours", 8.0),
            break_duration_minutes=config.get("break_duration_minutes", 30),
            breaks_per_shift=config.get("breaks_per_shift", 2),
            workers_per_station=config.get("workers_per_station", 1),
            floating_pool_size=config.get("floating_pool_size", 0)
        )

        analysis = analyze_bottlenecks(
            config=line_config,
            duration_hours=duration_hours,
            random_seed=random_seed
        )

        return {
            "primary_bottleneck": analysis.primary_bottleneck,
            "bottleneck_utilization": round(analysis.bottleneck_utilization, 2),
            "queue_times": {k: round(v, 2) for k, v in analysis.queue_times.items()},
            "station_wait_times": {k: round(v, 2) for k, v in analysis.station_wait_times.items()},
            "suggestions": analysis.suggestions
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error analyzing bottlenecks: {str(e)}")


@router.post("/production-line/floating-pool-impact")
async def analyze_floating_pool_impact(
    config: dict,
    pool_sizes: List[int] = Query(default=[0, 1, 2, 3, 5], description="Pool sizes to simulate"),
    duration_hours: float = Query(default=8.0, gt=0, le=24),
    random_seed: int = Query(default=42),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Analyze the impact of different floating pool sizes on production.

    Compares throughput, efficiency, and quality across different pool sizes.
    """
    try:
        stations = [
            WorkStation(
                station_id=s["station_id"],
                name=s["name"],
                station_type=WorkStationType(s["station_type"]),
                cycle_time_minutes=s["cycle_time_minutes"],
                cycle_time_variability=s.get("cycle_time_variability", 0.1),
                num_workers=s.get("num_workers", 1),
                quality_rate=s.get("quality_rate", 0.98),
                downtime_probability=s.get("downtime_probability", 0.02),
                downtime_duration_minutes=s.get("downtime_duration_minutes", 30)
            )
            for s in config["stations"]
        ]

        line_config = ProductionLineConfig(
            line_id=config.get("line_id", "LINE-001"),
            name=config.get("name", "Production Line"),
            stations=stations,
            shift_duration_hours=config.get("shift_duration_hours", 8.0),
            break_duration_minutes=config.get("break_duration_minutes", 30),
            breaks_per_shift=config.get("breaks_per_shift", 2),
            workers_per_station=config.get("workers_per_station", 1),
            floating_pool_size=0  # Will be varied
        )

        results = simulate_floating_pool_impact(
            config=line_config,
            pool_sizes=pool_sizes,
            duration_hours=duration_hours,
            random_seed=random_seed
        )

        # Calculate optimal pool size
        optimal = max(results, key=lambda r: r["throughput_per_hour"]) if results else None

        return {
            "pool_size_comparison": results,
            "optimal_pool_size": optimal["floating_pool_size"] if optimal else 0,
            "optimal_throughput": optimal["throughput_per_hour"] if optimal else 0,
            "recommendations": [
                f"Optimal floating pool size is {optimal['floating_pool_size']} workers" if optimal else "No data",
                f"This provides throughput of {optimal['throughput_per_hour']:.1f} units/hour" if optimal else ""
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error analyzing floating pool impact: {str(e)}")
