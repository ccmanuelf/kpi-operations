"""
Production Line Simulation v2.0 - Pydantic Data Models

All models are designed for stateless operation with no database dependencies.
This module defines input schemas, validation schemas, and output schemas
for the 8 result blocks specified in the technical specification.
"""

from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator

from .constants import (
    DEFAULT_SEQUENCE,
    DEFAULT_GROUPING,
    DEFAULT_OPERATORS,
    DEFAULT_VARIABILITY,
    DEFAULT_REWORK_PCT,
    DEFAULT_GRADE_PCT,
    DEFAULT_FPD_PCT,
    DEFAULT_BUNDLE_SIZE,
    DEFAULT_HORIZON_DAYS,
    MAX_PRODUCTS,
    MAX_OPERATORS_PER_STATION,
    MAX_BUNDLE_SIZE,
    MAX_HORIZON_DAYS,
    ENGINE_VERSION,
)


# =============================================================================
# ENUMS
# =============================================================================


class VariabilityType(str, Enum):
    """Processing time variability modes."""

    DETERMINISTIC = "deterministic"
    TRIANGULAR = "triangular"


class DemandMode(str, Enum):
    """Simulation demand specification mode."""

    DEMAND_DRIVEN = "demand-driven"
    MIX_DRIVEN = "mix-driven"


class ValidationSeverity(str, Enum):
    """Validation issue severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class CoverageStatus(str, Enum):
    """Demand coverage status classification."""

    OK = "OK"
    TIGHT = "Tight"
    SHORTFALL = "Shortfall"


class RebalanceRole(str, Enum):
    """Role in rebalancing suggestion."""

    BOTTLENECK = "Bottleneck"
    DONOR = "Donor"


# =============================================================================
# INPUT MODELS
# =============================================================================


class OperationInput(BaseModel):
    """
    Single operation in a product's production sequence.

    Represents one step in the manufacturing process with timing,
    resource requirements, and quality parameters.
    """

    product: str = Field(
        ..., min_length=1, max_length=100, description="Product identifier - must match across operations and demands"
    )
    step: int = Field(..., gt=0, le=999, description="Sequence order within product (1-based, sequential, no gaps)")
    operation: str = Field(
        ..., min_length=1, max_length=200, description="Operation description (e.g., 'Join shoulder seams')"
    )
    machine_tool: str = Field(
        ..., min_length=1, max_length=100, description="Required resource identifier (e.g., '4-thread overlock')"
    )
    sam_min: float = Field(..., gt=0, le=999, description="Standard Allowed Minutes per piece")

    # Optional fields with defaults
    sequence: str = Field(
        default=DEFAULT_SEQUENCE,
        max_length=50,
        description="Operation phase category (e.g., Cutting, Assembly, Finishing)",
    )
    grouping: str = Field(
        default=DEFAULT_GROUPING, max_length=50, description="Additional categorization for reporting"
    )
    operators: int = Field(
        default=DEFAULT_OPERATORS,
        ge=1,
        le=MAX_OPERATORS_PER_STATION,
        description="Number of workers assigned to this station",
    )
    variability: VariabilityType = Field(
        default=VariabilityType.TRIANGULAR, description="Processing time variability mode"
    )
    rework_pct: float = Field(
        default=DEFAULT_REWORK_PCT, ge=0, le=100, description="Percentage of pieces requiring rework at this operation"
    )
    grade_pct: float = Field(
        default=DEFAULT_GRADE_PCT, ge=0, le=100, description="Operator skill level (100 = fully trained)"
    )
    fpd_pct: float = Field(default=DEFAULT_FPD_PCT, ge=0, le=100, description="Fatigue and Personal Delay percentage")

    class Config:
        json_schema_extra = {
            "example": {
                "product": "HV_TSHIRT",
                "step": 1,
                "operation": "Cut fabric panels",
                "machine_tool": "Cutting table",
                "sam_min": 2.30,
                "sequence": "Cutting",
                "grouping": "CUTTING",
                "operators": 1,
                "variability": "triangular",
                "rework_pct": 0,
                "grade_pct": 85,
                "fpd_pct": 15,
            }
        }


class ScheduleConfig(BaseModel):
    """
    Production schedule configuration.

    Defines working hours across shifts and days, including overtime options.
    """

    shifts_enabled: int = Field(..., ge=1, le=3, description="Number of shifts per day (1-3)")
    shift1_hours: float = Field(..., gt=0, le=12, description="Shift 1 duration in hours")
    shift2_hours: float = Field(default=0.0, ge=0, le=12, description="Shift 2 duration in hours")
    shift3_hours: float = Field(default=0.0, ge=0, le=12, description="Shift 3 duration in hours")
    work_days: int = Field(..., ge=1, le=7, description="Work days per week")

    # Overtime configuration
    ot_enabled: bool = Field(default=False, description="Enable overtime calculation")
    weekday_ot_hours: float = Field(default=0.0, ge=0, le=8, description="Additional overtime hours per weekday")
    weekend_ot_days: int = Field(default=0, ge=0, le=2, description="Number of weekend days with overtime")
    weekend_ot_hours: float = Field(default=0.0, ge=0, le=12, description="Hours per weekend overtime day")

    @model_validator(mode="after")
    def validate_total_hours(self):
        """Ensure total daily hours don't exceed 24."""
        total = self.shift1_hours + self.shift2_hours + self.shift3_hours
        if total > 24:
            raise ValueError(f"Total shift hours ({total:.1f}) cannot exceed 24 hours per day")
        return self

    @model_validator(mode="after")
    def validate_overtime_hours(self):
        """Ensure overtime doesn't create impossible schedules."""
        if self.ot_enabled:
            max_shift = max(self.shift1_hours, self.shift2_hours, self.shift3_hours)
            if max_shift + self.weekday_ot_hours > 24:
                raise ValueError(
                    f"Longest shift ({max_shift:.1f}h) + weekday OT " f"({self.weekday_ot_hours:.1f}h) exceeds 24 hours"
                )
        return self

    @property
    def daily_planned_hours(self) -> float:
        """Calculate total hours per day across enabled shifts."""
        hours = self.shift1_hours
        if self.shifts_enabled >= 2:
            hours += self.shift2_hours
        if self.shifts_enabled >= 3:
            hours += self.shift3_hours
        return hours

    @property
    def weekly_base_hours(self) -> float:
        """Calculate weekly hours before overtime."""
        return self.daily_planned_hours * self.work_days

    @property
    def weekly_total_hours(self) -> float:
        """Calculate weekly hours including overtime."""
        base = self.weekly_base_hours
        if not self.ot_enabled:
            return base
        weekday_ot = self.weekday_ot_hours * self.work_days
        weekend_ot = self.weekend_ot_hours * self.weekend_ot_days
        return base + weekday_ot + weekend_ot

    class Config:
        json_schema_extra = {
            "example": {
                "shifts_enabled": 2,
                "shift1_hours": 9.0,
                "shift2_hours": 8.0,
                "shift3_hours": 0.0,
                "work_days": 5,
                "ot_enabled": False,
            }
        }


class DemandInput(BaseModel):
    """
    Product demand configuration.

    Specifies demand quantities and bundle sizes for each product.
    Supports both demand-driven and mix-driven modes.
    """

    product: str = Field(
        ..., min_length=1, max_length=100, description="Must exactly match a product from operations list"
    )
    bundle_size: int = Field(default=DEFAULT_BUNDLE_SIZE, ge=1, le=MAX_BUNDLE_SIZE, description="Pieces per bundle")
    daily_demand: Optional[float] = Field(default=None, ge=0, description="Target pieces per day (demand-driven mode)")
    weekly_demand: Optional[float] = Field(
        default=None, ge=0, description="Target pieces per week (demand-driven mode)"
    )
    mix_share_pct: Optional[float] = Field(
        default=None, ge=0, le=100, description="Percentage of total production (mix-driven mode)"
    )

    class Config:
        json_schema_extra = {
            "example": {"product": "HV_TSHIRT", "bundle_size": 10, "daily_demand": 500, "weekly_demand": 2500}
        }


class BreakdownInput(BaseModel):
    """
    Equipment breakdown configuration.

    Defines failure probability for specific machine/tool types.
    """

    machine_tool: str = Field(
        ..., min_length=1, max_length=100, description="Must match a machine_tool from operations"
    )
    breakdown_pct: float = Field(
        default=0.0, ge=0, le=100, description="Probability of breakdown during each operation (%)"
    )

    class Config:
        json_schema_extra = {"example": {"machine_tool": "4-thread overlock", "breakdown_pct": 2.5}}


class SimulationConfig(BaseModel):
    """
    Complete simulation configuration.

    Combines all input components into a single configuration object
    for the simulation engine.
    """

    operations: List[OperationInput] = Field(
        ..., min_length=1, description="List of operations defining production processes"
    )
    schedule: ScheduleConfig = Field(..., description="Production schedule configuration")
    demands: List[DemandInput] = Field(..., min_length=1, description="Demand configuration per product")
    breakdowns: Optional[List[BreakdownInput]] = Field(
        default=None, description="Optional equipment breakdown configuration"
    )
    mode: DemandMode = Field(default=DemandMode.DEMAND_DRIVEN, description="Demand specification mode")
    total_demand: Optional[float] = Field(
        default=None, ge=0, description="Total daily demand (required for mix-driven mode)"
    )
    horizon_days: int = Field(
        default=DEFAULT_HORIZON_DAYS, ge=1, le=MAX_HORIZON_DAYS, description="Simulation horizon in days"
    )

    @model_validator(mode="after")
    def validate_mix_mode_total_demand(self):
        """Ensure total_demand is provided in mix-driven mode."""
        if self.mode == DemandMode.MIX_DRIVEN and not self.total_demand:
            raise ValueError("total_demand is required when mode is 'mix-driven'")
        return self


# =============================================================================
# VALIDATION MODELS
# =============================================================================


class ValidationIssue(BaseModel):
    """Single validation error, warning, or info message."""

    severity: ValidationSeverity
    category: str = Field(..., description="Validation category (e.g., 'sequence', 'demand', 'capacity')")
    message: str = Field(..., description="Human-readable description of the issue")
    field: Optional[str] = Field(default=None, description="Specific field that caused the issue")
    product: Optional[str] = Field(default=None, description="Product associated with the issue")
    recommendation: Optional[str] = Field(default=None, description="Suggested action to resolve the issue")


class ValidationReport(BaseModel):
    """Complete validation result with errors, warnings, and statistics."""

    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)
    info: List[ValidationIssue] = Field(default_factory=list)

    products_count: int = Field(default=0)
    operations_count: int = Field(default=0)
    machine_tools_count: int = Field(default=0)

    is_valid: bool = Field(default=True)
    can_proceed: bool = Field(default=True)

    @property
    def has_errors(self) -> bool:
        """Check if any errors exist."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if any warnings exist."""
        return len(self.warnings) > 0


# =============================================================================
# OUTPUT MODELS - 8 RESULT BLOCKS
# =============================================================================


class WeeklyDemandCapacityRow(BaseModel):
    """Block 1: Weekly Demand vs Capacity - single row."""

    product: str
    weekly_demand_pcs: int
    max_weekly_capacity_pcs: int
    demand_coverage_pct: float
    status: CoverageStatus


class DailySummary(BaseModel):
    """Block 2: Daily Simulation Summary - aggregate metrics."""

    total_shifts_per_day: int
    daily_planned_hours: float
    daily_throughput_pcs: int
    daily_demand_pcs: int
    daily_coverage_pct: float
    avg_cycle_time_min: float
    avg_wip_pcs: float
    bundles_processed_per_day: int
    bundle_size_pcs: str  # "10" or "mixed"


class StationPerformanceRow(BaseModel):
    """Block 3: Station and Operation Performance - single row."""

    product: str
    step: int
    operation: str
    machine_tool: str
    sequence: str
    grouping: str
    operators: int
    total_pieces_processed: int
    total_busy_time_min: float
    avg_processing_time_min: float
    util_pct: float
    queue_wait_time_min: float
    is_bottleneck: bool
    is_donor: bool


class FreeCapacityAnalysis(BaseModel):
    """Block 4: Free Capacity Analysis."""

    daily_demand_pcs: int
    daily_max_capacity_pcs: int
    demand_usage_pct: float
    free_line_hours_per_day: float
    free_operator_hours_at_bottleneck_per_day: float
    equivalent_free_operators_full_shift: float


class BundleMetricsRow(BaseModel):
    """Block 5: Bundle Behavior Metrics - single row."""

    product: str
    bundle_size_pcs: int
    bundles_arriving_per_day: int
    avg_bundles_in_system: Optional[float] = None
    max_bundles_in_system: Optional[int] = None
    avg_bundle_cycle_time_min: Optional[float] = None


class PerProductSummaryRow(BaseModel):
    """Block 6: Per-Product Summary - single row."""

    product: str
    bundle_size_pcs: int
    mix_share_pct: Optional[float] = None
    daily_demand_pcs: int
    daily_throughput_pcs: int
    daily_coverage_pct: float
    weekly_demand_pcs: int
    weekly_throughput_pcs: int
    weekly_coverage_pct: float


class RebalancingSuggestionRow(BaseModel):
    """Block 7: Rebalancing Suggestions - single row."""

    product: str  # "ALL" for cross-product suggestions
    step: int
    operation: str
    machine_tool: str
    grouping: str
    operators_before: int
    operators_after: int
    util_before_pct: float
    util_after_pct: float
    role: RebalanceRole
    comment: str


class AssumptionLog(BaseModel):
    """Block 8: Complete assumption and configuration record."""

    timestamp: datetime
    simulation_engine_version: str = ENGINE_VERSION
    configuration_mode: str

    schedule: Dict[str, Any]
    products: List[Dict[str, Any]]
    operations_defaults_applied: List[Dict[str, Any]]
    breakdowns_configuration: Dict[str, Any]
    formula_implementations: Dict[str, str]
    limitations_and_caveats: List[str]


class SimulationResults(BaseModel):
    """Complete simulation output - all 8 blocks."""

    # Block 1
    weekly_demand_capacity: List[WeeklyDemandCapacityRow]

    # Block 2
    daily_summary: DailySummary

    # Block 3
    station_performance: List[StationPerformanceRow]

    # Block 4
    free_capacity: FreeCapacityAnalysis

    # Block 5
    bundle_metrics: List[BundleMetricsRow]

    # Block 6
    per_product_summary: List[PerProductSummaryRow]

    # Block 7
    rebalancing_suggestions: List[RebalancingSuggestionRow]

    # Block 8
    assumption_log: AssumptionLog

    # Metadata
    validation_report: ValidationReport
    simulation_duration_seconds: float


# =============================================================================
# API REQUEST/RESPONSE MODELS
# =============================================================================


class SimulationRequest(BaseModel):
    """API request for running simulation."""

    config: SimulationConfig


class SimulationResponse(BaseModel):
    """API response with results or validation errors."""

    success: bool
    results: Optional[SimulationResults] = None
    validation_report: ValidationReport
    message: str = ""
