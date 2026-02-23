"""
Simulation & Capacity Planning Pydantic schemas
Phase 11: Request/response models for simulation API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class SimulationScenarioType(str, Enum):
    """Types of simulation scenarios"""

    STAFFING = "staffing"
    PRODUCTION = "production"
    CAPACITY = "capacity"
    EFFICIENCY = "efficiency"
    FLOATING_POOL = "floating_pool"
    SHIFT_COVERAGE = "shift_coverage"


class OptimizationGoal(str, Enum):
    """Optimization goals for capacity planning"""

    MINIMIZE_COST = "minimize_cost"
    MAXIMIZE_PRODUCTION = "maximize_production"
    BALANCE_WORKLOAD = "balance_workload"
    MEET_TARGET = "meet_target"


# =============================================================================
# Request Models
# =============================================================================


class CapacityRequirementRequest(BaseModel):
    """Request for capacity requirement calculation"""

    target_units: int = Field(..., gt=0, description="Target production units")
    target_date: Optional[date] = Field(None, description="Target date for production")
    cycle_time_hours: Optional[float] = Field(
        None, gt=0, description="Hours per unit (uses client config if not provided)"
    )
    shift_hours: float = Field(default=8.0, gt=0, le=24, description="Hours per shift")
    target_efficiency: float = Field(default=85.0, ge=0, le=100, description="Target efficiency percentage")
    absenteeism_rate: float = Field(default=5.0, ge=0, le=100, description="Expected absenteeism percentage")
    include_buffer: bool = Field(default=True, description="Include buffer for absenteeism")


class ProductionCapacityRequest(BaseModel):
    """Request for production capacity calculation"""

    employees: int = Field(..., ge=1, description="Number of employees")
    shift_hours: float = Field(default=8.0, gt=0, le=24, description="Hours per shift")
    cycle_time_hours: float = Field(default=0.25, gt=0, description="Hours per unit")
    efficiency_percent: float = Field(default=85.0, ge=0, le=100, description="Expected efficiency percentage")


class StaffingSimulationRequest(BaseModel):
    """Request for staffing simulation"""

    base_employees: int = Field(..., ge=1, description="Current/baseline employee count")
    scenarios: List[int] = Field(..., min_length=1, description="List of employee counts to simulate")
    shift_hours: float = Field(default=8.0, gt=0, le=24, description="Hours per shift")
    cycle_time_hours: float = Field(default=0.25, gt=0, description="Hours per unit")
    base_efficiency: float = Field(default=85.0, ge=0, le=100, description="Baseline efficiency percentage")
    efficiency_scaling: bool = Field(default=True, description="Apply efficiency scaling for team size changes")


class EfficiencySimulationRequest(BaseModel):
    """Request for efficiency simulation"""

    employees: int = Field(..., ge=1, description="Number of employees")
    efficiency_scenarios: List[float] = Field(
        ..., min_length=1, description="List of efficiency percentages to simulate"
    )
    shift_hours: float = Field(default=8.0, gt=0, le=24, description="Hours per shift")
    cycle_time_hours: float = Field(default=0.25, gt=0, description="Hours per unit")
    base_efficiency: float = Field(default=85.0, ge=0, le=100, description="Baseline efficiency for comparison")


class ShiftCoverageSimulationRequest(BaseModel):
    """Request for shift coverage simulation"""

    shift_id: int = Field(default=0, description="Shift ID")
    shift_name: str = Field(default="Default Shift", description="Shift name")
    regular_employees: int = Field(..., ge=0, description="Number of regular shift employees")
    floating_pool_available: int = Field(default=0, ge=0, description="Available floating pool employees")
    required_employees: int = Field(..., ge=1, description="Required employees for the shift")
    target_date: Optional[date] = Field(None, description="Target date for simulation")


class ShiftRequirement(BaseModel):
    """Shift requirement for multi-shift simulation"""

    shift_id: int = Field(..., description="Shift ID")
    shift_name: str = Field(default="", description="Shift name")
    regular_employees: int = Field(default=0, ge=0, description="Regular employees available")
    required: int = Field(..., ge=1, description="Required employees")
    target_date: Optional[date] = Field(None, description="Target date")


class MultiShiftCoverageRequest(BaseModel):
    """Request for multi-shift coverage simulation"""

    shifts: List[ShiftRequirement] = Field(..., min_length=1, description="List of shift configurations")
    floating_pool_total: int = Field(..., ge=0, description="Total floating pool employees available")


class FloatingPoolEmployee(BaseModel):
    """Floating pool employee for allocation"""

    employee_id: int = Field(..., gt=0)
    employee_code: Optional[str] = None
    skills: List[str] = Field(default_factory=list)


class FloatingPoolOptimizationRequest(BaseModel):
    """Request for floating pool optimization"""

    available_pool_employees: List[FloatingPoolEmployee] = Field(..., min_length=1)
    shift_requirements: List[ShiftRequirement] = Field(..., min_length=1)
    optimization_goal: OptimizationGoal = Field(default=OptimizationGoal.BALANCE_WORKLOAD)
    target_date: Optional[date] = None


class ComprehensiveSimulationRequest(BaseModel):
    """Request for comprehensive capacity simulation"""

    target_units: int = Field(..., gt=0, description="Production target")
    current_employees: int = Field(..., ge=1, description="Current staffing level")
    shift_hours: float = Field(default=8.0, gt=0, le=24, description="Hours per shift")
    cycle_time_hours: float = Field(default=0.25, gt=0, description="Time per unit")
    efficiency: float = Field(default=85.0, ge=0, le=100, description="Current efficiency")
    staffing_scenarios: Optional[List[int]] = Field(None, description="Employee counts to simulate")
    efficiency_scenarios: Optional[List[float]] = Field(None, description="Efficiency levels to simulate")


# =============================================================================
# Response Models
# =============================================================================


class CapacityRequirementResponse(BaseModel):
    """Response for capacity requirement calculation"""

    target_units: int
    required_employees: int
    required_hours: float
    required_shifts: int
    estimated_efficiency: float
    buffer_employees: int
    total_recommended: int
    cost_estimate: Optional[float] = None
    confidence_score: float
    notes: List[str]


class ProductionCapacityResponse(BaseModel):
    """Response for production capacity calculation"""

    employees: int
    shift_hours: float
    cycle_time_hours: float
    efficiency_percent: float
    units_capacity: int
    hourly_rate: float
    effective_production_hours: float


class SimulationResultResponse(BaseModel):
    """Response for a single simulation result"""

    scenario_name: str
    scenario_type: SimulationScenarioType
    input_parameters: Dict[str, Any]
    projected_output: Dict[str, Any]
    kpi_impact: Dict[str, float]
    recommendations: List[str]
    confidence_score: float
    comparison_to_baseline: Optional[Dict[str, float]] = None


class ShiftCoverageSimulationResponse(BaseModel):
    """Response for shift coverage simulation"""

    shift_id: int
    shift_name: str
    date: date
    required_employees: int
    available_regular: int
    available_floating_pool: int
    coverage_gap: int
    coverage_percent: float
    recommendations: List[str]


class AllocationSuggestion(BaseModel):
    """Allocation suggestion for floating pool"""

    shift_id: int
    shift_name: str
    employees_assigned: int
    employee_ids: List[int]
    gap_remaining: int


class FloatingPoolOptimizationResponse(BaseModel):
    """Response for floating pool optimization"""

    total_available: int
    total_needed: int
    allocation_suggestions: List[AllocationSuggestion]
    utilization_rate: float
    cost_savings: Optional[float] = None
    efficiency_gain: Optional[float] = None


class MultiShiftCoverageSummary(BaseModel):
    """Summary for multi-shift coverage"""

    total_shifts: int
    total_required: int
    total_covered: int
    total_gap: int
    overall_coverage_percent: float
    floating_pool_total: int
    floating_pool_allocated: int
    floating_pool_remaining: int
    allocations: List[Dict[str, Any]]


class MultiShiftCoverageResponse(BaseModel):
    """Response for multi-shift coverage simulation"""

    shift_simulations: List[ShiftCoverageSimulationResponse]
    summary: MultiShiftCoverageSummary


class GapAnalysis(BaseModel):
    """Gap analysis between current capacity and target"""

    capacity_gap_units: int
    gap_percent: float
    meets_target: bool


class ComprehensiveSimulationResponse(BaseModel):
    """Response for comprehensive capacity simulation"""

    simulation_date: datetime
    client_id: str
    configuration: Dict[str, Any]
    capacity_requirements: Dict[str, Any]
    current_capacity: ProductionCapacityResponse
    gap_analysis: GapAnalysis
    staffing_simulations: List[Dict[str, Any]]
    efficiency_simulations: List[Dict[str, Any]]
    recommendations: List[str]


class SimulationSummary(BaseModel):
    """Summary of simulation capabilities"""

    available_simulation_types: List[str]
    description: str
    example_use_cases: List[str]
