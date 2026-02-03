# Production Line Simulation Tool v2.0 - Implementation Plan

**Project**: ClawMFG Suite - Production Line Simulation Module
**Version**: 2.0 Implementation Plan
**Date**: February 1, 2026
**Status**: Ready for Implementation

---

## Executive Summary

This plan details the implementation of the Production Line Simulation Tool v2.0 as specified in the technical specification. The implementation replaces the existing simulation functionality with a new ephemeral, stateless capacity planning tool that provides "insight, not decisions."

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Build new, don't refactor** | v2.0 spec fundamentally differs from existing simulation (no DB integration, different input model, 8 output blocks) |
| **Parallel deployment** | New endpoints coexist with existing during transition |
| **Client-side Excel export** | Matches spec's ephemeral philosophy; no server storage |
| **Phased rollout** | Minimize risk; deliver value incrementally |

### Timeline Overview

| Phase | Duration | Focus |
|-------|----------|-------|
| Phase 1 | 2 weeks | Core SimPy engine, basic UI, 5 output blocks |
| Phase 2 | 1 week | Stochastic variability, full validation |
| Phase 3 | 1-2 weeks | Rework, breakdowns, all 8 blocks, visualizations |
| Phase 4 | 1 week | Integration, permissions, deployment |

**Total: 5-6 weeks**

---

## 1. Architecture Overview

### 1.1 System Context

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Vue 3 + Vuetify)                          │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  SimulationView  │  │  Input Components │  │ Results Dashboard │          │
│  │     (Router)     │──│  (Grids, Forms)   │──│   (8 Blocks)     │          │
│  └────────┬─────────┘  └──────────────────┘  └──────────────────┘          │
│           │                                                                  │
│  ┌────────▼─────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ simulationStore  │  │  File Importers  │  │  Excel Exporter  │          │
│  │     (Pinia)      │  │  (CSV/XLSX)      │  │   (SheetJS)      │          │
│  └────────┬─────────┘  └──────────────────┘  └──────────────────┘          │
└───────────┼─────────────────────────────────────────────────────────────────┘
            │ HTTP POST /api/v2/simulation/run
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                                    │
│                                                                              │
│  ┌──────────────────┐                                                       │
│  │ routes/          │                                                       │
│  │ simulation_v2.py │  ◄── New router (coexists with existing)              │
│  └────────┬─────────┘                                                       │
│           │                                                                  │
│  ┌────────▼─────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ simulation_v2/   │  │ simulation_v2/   │  │ simulation_v2/   │          │
│  │ validation.py    │──│ engine.py        │──│ calculations.py  │          │
│  │ (Input checks)   │  │ (SimPy DES)      │  │ (Output blocks)  │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │ simulation_v2/models.py - Pydantic schemas for all I/O       │          │
│  └──────────────────────────────────────────────────────────────┘          │
│                                                                              │
│  *** NO DATABASE ACCESS - COMPLETELY STATELESS ***                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow

```
User Input (CSV/Form)
       │
       ▼
┌──────────────────┐
│ Schema Validation │ ◄── Pydantic BaseModel validation
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Domain Validation │ ◄── Manufacturing-specific rules
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Validation Report │ ──► Return if errors exist
└────────┬─────────┘
         │ (no errors)
         ▼
┌──────────────────┐
│  SimPy Engine    │ ◄── Discrete-event simulation
│  - Create env    │
│  - Build resources│
│  - Run processes │
│  - Collect metrics│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Output Calculations│ ◄── Aggregate into 8 blocks
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ SimulationResults │ ──► JSON response to frontend
└──────────────────┘
         │
         ▼
┌──────────────────┐
│ Excel Export     │ ◄── Client-side (SheetJS)
│ (User downloads) │
└──────────────────┘
```

---

## 2. File Structure

### 2.1 Backend File Tree

```
backend/
├── simulation_v2/                    # NEW: v2.0 simulation module
│   ├── __init__.py                   # Module exports
│   ├── models.py                     # Pydantic input/output schemas
│   ├── validation.py                 # Schema + domain validation
│   ├── engine.py                     # SimPy discrete-event engine
│   ├── calculations.py               # Output block calculations
│   ├── constants.py                  # Default values, thresholds
│   └── README.md                     # Module documentation
│
├── routes/
│   ├── simulation.py                 # EXISTING: Keep for backward compat
│   └── simulation_v2.py              # NEW: v2.0 endpoints
│
├── tests/
│   └── test_simulation_v2/           # NEW: v2.0 test suite
│       ├── __init__.py
│       ├── conftest.py               # Shared fixtures
│       ├── test_models.py            # Schema validation tests
│       ├── test_validation.py        # Domain validation tests
│       ├── test_engine.py            # SimPy engine tests
│       ├── test_calculations.py      # Output calculation tests
│       └── test_integration.py       # End-to-end tests
│
└── main.py                           # ADD: Include simulation_v2 router
```

### 2.2 Frontend File Tree

```
frontend/
├── src/
│   ├── views/
│   │   ├── SimulationView.vue        # EXISTING: Keep for transition
│   │   └── SimulationV2View.vue      # NEW: v2.0 main view
│   │
│   ├── components/
│   │   └── simulation-v2/            # NEW: v2.0 components
│   │       ├── index.js              # Barrel exports
│   │       ├── OperationsGrid.vue    # AG Grid for operations
│   │       ├── ScheduleForm.vue      # Shift/OT configuration
│   │       ├── DemandGrid.vue        # Product demand entry
│   │       ├── BreakdownsGrid.vue    # Equipment breakdowns
│   │       ├── ValidationReport.vue  # Error/warning display
│   │       ├── ResultsDashboard.vue  # 8 output blocks
│   │       ├── ResultsBlock.vue      # Generic block renderer
│   │       ├── StationPerformance.vue# Block 3 specialized view
│   │       ├── RebalancingSuggestions.vue # Block 7 view
│   │       ├── AssumptionLog.vue     # Block 8 collapsible view
│   │       └── ExportDialog.vue      # Export configuration
│   │
│   ├── stores/
│   │   └── simulationV2Store.js      # NEW: v2.0 state management
│   │
│   ├── services/api/
│   │   └── simulationV2.js           # NEW: v2.0 API client
│   │
│   └── utils/
│       └── excelExport.js            # NEW: SheetJS wrapper
│
├── package.json                      # ADD: xlsx dependency
└── vite.config.js                    # ADD: xlsx chunk configuration
```

---

## 3. Backend Specifications

### 3.1 Pydantic Models (`simulation_v2/models.py`)

```python
"""
Production Line Simulation v2.0 - Data Models

All models are designed for stateless operation with no database dependencies.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# ENUMS
# ============================================================================

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


# ============================================================================
# INPUT MODELS
# ============================================================================

class OperationInput(BaseModel):
    """Single operation in a product's production sequence."""

    product: str = Field(..., min_length=1, description="Product identifier")
    step: int = Field(..., gt=0, description="Sequence order (1-based)")
    operation: str = Field(..., min_length=1, description="Operation description")
    machine_tool: str = Field(..., min_length=1, description="Required resource")
    sam_min: float = Field(..., gt=0, description="Standard Allowed Minutes per piece")

    # Optional with defaults
    sequence: str = Field(default="Assembly", description="Operation phase category")
    grouping: str = Field(default="", description="Additional categorization")
    operators: int = Field(default=1, ge=1, le=20, description="Workers at station")
    variability: VariabilityType = Field(default=VariabilityType.TRIANGULAR)
    rework_pct: float = Field(default=0.0, ge=0, le=100, description="Rework percentage")
    grade_pct: float = Field(default=85.0, ge=0, le=100, description="Operator skill %")
    fpd_pct: float = Field(default=15.0, ge=0, le=100, description="Fatigue/personal delay %")

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
                "fpd_pct": 15
            }
        }


class ScheduleConfig(BaseModel):
    """Production schedule configuration."""

    shifts_enabled: int = Field(..., ge=1, le=3, description="Number of shifts per day")
    shift1_hours: float = Field(..., gt=0, le=12, description="Shift 1 duration")
    shift2_hours: float = Field(default=0.0, ge=0, le=12, description="Shift 2 duration")
    shift3_hours: float = Field(default=0.0, ge=0, le=12, description="Shift 3 duration")
    work_days: int = Field(..., ge=1, le=7, description="Work days per week")

    # Overtime configuration
    ot_enabled: bool = Field(default=False, description="Enable overtime")
    weekday_ot_hours: float = Field(default=0.0, ge=0, le=8)
    weekend_ot_days: int = Field(default=0, ge=0, le=2)
    weekend_ot_hours: float = Field(default=0.0, ge=0, le=12)

    @model_validator(mode='after')
    def validate_total_hours(self):
        """Ensure total daily hours don't exceed 24."""
        total = self.shift1_hours + self.shift2_hours + self.shift3_hours
        if total > 24:
            raise ValueError(f"Total shift hours ({total}) cannot exceed 24")
        return self

    @property
    def daily_planned_hours(self) -> float:
        """Calculate total hours per day across all shifts."""
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


class DemandInput(BaseModel):
    """Product demand configuration."""

    product: str = Field(..., min_length=1, description="Must match operations product")
    bundle_size: int = Field(default=1, ge=1, le=100, description="Pieces per bundle")
    daily_demand: Optional[float] = Field(default=None, ge=0)
    weekly_demand: Optional[float] = Field(default=None, ge=0)
    mix_share_pct: Optional[float] = Field(default=None, ge=0, le=100)


class BreakdownInput(BaseModel):
    """Equipment breakdown configuration."""

    machine_tool: str = Field(..., min_length=1, description="Must match operations machine_tool")
    breakdown_pct: float = Field(default=0.0, ge=0, le=100, description="Breakdown probability %")


class SimulationConfig(BaseModel):
    """Complete simulation configuration."""

    operations: List[OperationInput] = Field(..., min_length=1)
    schedule: ScheduleConfig
    demands: List[DemandInput] = Field(..., min_length=1)
    breakdowns: Optional[List[BreakdownInput]] = Field(default=None)
    mode: DemandMode = Field(default=DemandMode.DEMAND_DRIVEN)
    total_demand: Optional[float] = Field(default=None, ge=0, description="For mix-driven mode")
    horizon_days: int = Field(default=1, ge=1, le=7, description="Simulation horizon in days")


# ============================================================================
# VALIDATION MODELS
# ============================================================================

class ValidationIssue(BaseModel):
    """Single validation error or warning."""

    severity: ValidationSeverity
    category: str = Field(..., description="e.g., 'sequence', 'demand', 'capacity'")
    message: str
    field: Optional[str] = None
    product: Optional[str] = None
    recommendation: Optional[str] = None


class ValidationReport(BaseModel):
    """Complete validation result."""

    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)
    info: List[ValidationIssue] = Field(default_factory=list)

    products_count: int = 0
    operations_count: int = 0
    machine_tools_count: int = 0

    is_valid: bool = True
    can_proceed: bool = True

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


# ============================================================================
# OUTPUT MODELS - 8 BLOCKS
# ============================================================================

class WeeklyDemandCapacityRow(BaseModel):
    """Block 1: Weekly Demand vs Capacity - single row."""
    product: str
    weekly_demand_pcs: int
    max_weekly_capacity_pcs: int
    demand_coverage_pct: float
    status: Literal["OK", "Tight", "Shortfall"]


class DailySummary(BaseModel):
    """Block 2: Daily Simulation Summary."""
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
    role: Literal["Bottleneck", "Donor"]
    comment: str


class AssumptionLog(BaseModel):
    """Block 8: Assumption Log - complete configuration record."""
    timestamp: datetime
    simulation_engine_version: str = "2.0.0"
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


# ============================================================================
# API REQUEST/RESPONSE
# ============================================================================

class SimulationRequest(BaseModel):
    """API request for running simulation."""
    config: SimulationConfig


class SimulationResponse(BaseModel):
    """API response with results or validation errors."""
    success: bool
    results: Optional[SimulationResults] = None
    validation_report: ValidationReport
    message: str = ""
```

### 3.2 Validation Module (`simulation_v2/validation.py`)

```python
"""
Production Line Simulation v2.0 - Input Validation

Implements two-phase validation:
1. Schema validation (Pydantic) - data types, required fields, basic constraints
2. Domain validation - manufacturing-specific rules and consistency checks
"""

from typing import List, Dict, Set, Tuple
from collections import defaultdict
import difflib

from .models import (
    SimulationConfig,
    ValidationReport,
    ValidationIssue,
    ValidationSeverity,
    DemandMode,
)


def validate_simulation_config(config: SimulationConfig) -> ValidationReport:
    """
    Perform comprehensive validation of simulation configuration.

    Returns ValidationReport with errors, warnings, and summary statistics.
    """
    report = ValidationReport()

    # Collect statistics
    products = set()
    machine_tools = set()
    operations_by_product: Dict[str, List] = defaultdict(list)

    for op in config.operations:
        products.add(op.product)
        machine_tools.add(op.machine_tool)
        operations_by_product[op.product].append(op)

    report.products_count = len(products)
    report.operations_count = len(config.operations)
    report.machine_tools_count = len(machine_tools)

    # Run validation checks
    _validate_operation_sequences(operations_by_product, report)
    _validate_product_consistency(operations_by_product, config.demands, report)
    _validate_machine_tool_consistency(config.operations, report)
    _validate_demand_configuration(config, report)
    _validate_schedule_reasonableness(config.schedule, report)
    _validate_breakdown_configuration(config, machine_tools, report)
    _validate_theoretical_capacity(config, operations_by_product, report)

    # Set final status
    report.is_valid = len(report.errors) == 0
    report.can_proceed = report.is_valid

    return report


def _validate_operation_sequences(
    operations_by_product: Dict[str, List],
    report: ValidationReport
) -> None:
    """Validate operation step sequences are sequential without gaps."""

    for product, ops in operations_by_product.items():
        steps = sorted([op.step for op in ops])

        # Check for duplicates
        if len(steps) != len(set(steps)):
            report.errors.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="sequence",
                product=product,
                message=f"Product '{product}' has duplicate step numbers",
                recommendation="Ensure each step number is unique within the product"
            ))
            continue

        # Check for gaps
        expected = list(range(steps[0], steps[0] + len(steps)))
        if steps != expected:
            missing = set(expected) - set(steps)
            report.errors.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="sequence",
                product=product,
                message=f"Product '{product}' has gaps in step sequence. Missing: {sorted(missing)}",
                recommendation="Steps must be sequential without gaps"
            ))


def _validate_product_consistency(
    operations_by_product: Dict[str, List],
    demands: List,
    report: ValidationReport
) -> None:
    """Validate products in operations match products in demand."""

    ops_products = set(operations_by_product.keys())
    demand_products = {d.product for d in demands}

    # Products in demand but not in operations
    orphan_demand = demand_products - ops_products
    for product in orphan_demand:
        report.errors.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category="product_consistency",
            product=product,
            message=f"Product '{product}' has demand specified but no operations defined",
            recommendation="Add operations for this product or remove from demand"
        ))

    # Products in operations but not in demand
    orphan_ops = ops_products - demand_products
    for product in orphan_ops:
        report.warnings.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            category="product_consistency",
            product=product,
            message=f"Product '{product}' has operations but no demand specified",
            recommendation="This product will be excluded from simulation"
        ))


def _validate_machine_tool_consistency(
    operations: List,
    report: ValidationReport
) -> None:
    """Check for potential typos in machine tool names."""

    tool_counts: Dict[str, int] = defaultdict(int)
    for op in operations:
        tool_counts[op.machine_tool] += 1

    tools = list(tool_counts.keys())

    for i, tool1 in enumerate(tools):
        for tool2 in tools[i+1:]:
            # Check similarity using difflib
            ratio = difflib.SequenceMatcher(None, tool1.lower(), tool2.lower()).ratio()
            if ratio > 0.8 and ratio < 1.0:  # Similar but not identical
                report.warnings.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="machine_tool",
                    message=f"Similar machine names found: '{tool1}' ({tool_counts[tool1]} uses) and '{tool2}' ({tool_counts[tool2]} uses)",
                    recommendation="If these are the same machine, standardize the name"
                ))


def _validate_demand_configuration(
    config: SimulationConfig,
    report: ValidationReport
) -> None:
    """Validate demand values and mode consistency."""

    if config.mode == DemandMode.MIX_DRIVEN:
        # Validate mix percentages sum to 100
        total_mix = sum(d.mix_share_pct or 0 for d in config.demands)
        if abs(total_mix - 100.0) > 0.1:
            report.errors.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="demand",
                message=f"Mix percentages sum to {total_mix:.1f}%, must equal 100%",
                recommendation="Adjust mix_share_pct values to sum to 100"
            ))

        # Validate total demand is specified
        if not config.total_demand:
            report.errors.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="demand",
                message="Mix-driven mode requires total_demand to be specified",
                recommendation="Set total_demand in configuration"
            ))

    else:  # Demand-driven
        for demand in config.demands:
            if demand.daily_demand and demand.weekly_demand:
                # Check consistency
                expected_weekly = demand.daily_demand * config.schedule.work_days
                diff_pct = abs(expected_weekly - demand.weekly_demand) / demand.weekly_demand * 100
                if diff_pct > 5:
                    report.warnings.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="demand",
                        product=demand.product,
                        message=f"Daily demand ({demand.daily_demand}) × work days ({config.schedule.work_days}) = {expected_weekly}, but weekly demand is {demand.weekly_demand}",
                        recommendation="Weekly demand will be used as authoritative"
                    ))


def _validate_schedule_reasonableness(schedule, report: ValidationReport) -> None:
    """Validate schedule is physically possible."""

    # Check overtime doesn't exceed daily limits
    if schedule.ot_enabled:
        max_shift = max(schedule.shift1_hours, schedule.shift2_hours, schedule.shift3_hours)
        if max_shift + schedule.weekday_ot_hours > 24:
            report.errors.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="schedule",
                message=f"Shift hours ({max_shift}) + weekday OT ({schedule.weekday_ot_hours}) exceeds 24 hours",
                recommendation="Reduce overtime or shift hours"
            ))


def _validate_breakdown_configuration(
    config: SimulationConfig,
    machine_tools: Set[str],
    report: ValidationReport
) -> None:
    """Validate breakdown configuration matches operations."""

    if not config.breakdowns:
        return

    for breakdown in config.breakdowns:
        if breakdown.machine_tool not in machine_tools:
            report.warnings.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="breakdown",
                message=f"Breakdown configured for '{breakdown.machine_tool}' which is not used in any operation",
                recommendation="This breakdown configuration will have no effect"
            ))


def _validate_theoretical_capacity(
    config: SimulationConfig,
    operations_by_product: Dict[str, List],
    report: ValidationReport
) -> None:
    """Pre-check if demand is theoretically achievable."""

    daily_hours = config.schedule.daily_planned_hours

    for demand in config.demands:
        if demand.product not in operations_by_product:
            continue

        ops = operations_by_product[demand.product]

        # Calculate total SAM per unit (adjusted for grade/FPD)
        total_sam = 0
        for op in ops:
            base_sam = op.sam_min
            # Apply average adjustments
            fpd_multiplier = op.fpd_pct / 100
            grade_multiplier = (100 - op.grade_pct) / 100
            adjusted_sam = base_sam * (1 + fpd_multiplier + grade_multiplier)
            total_sam += adjusted_sam

        # Get demand
        daily_demand = demand.daily_demand
        if not daily_demand and demand.weekly_demand:
            daily_demand = demand.weekly_demand / config.schedule.work_days

        if not daily_demand:
            continue

        # Calculate theoretical hours needed
        hours_needed = (total_sam * daily_demand) / 60  # Convert minutes to hours

        if hours_needed > daily_hours * 1.1:  # 10% buffer
            report.warnings.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="theoretical_capacity",
                product=demand.product,
                message=f"Theoretical hours needed ({hours_needed:.1f}h) exceeds available hours ({daily_hours:.1f}h)",
                recommendation="Demand may be unachievable even under optimal conditions"
            ))
```

### 3.3 SimPy Engine (`simulation_v2/engine.py`)

```python
"""
Production Line Simulation v2.0 - SimPy Discrete-Event Engine

Implements the core simulation logic using SimPy's process-based approach.
Each bundle flows through operations as a generator function, yielding
events for resource requests, timeouts, and state changes.
"""

import simpy
import random
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

from .models import (
    SimulationConfig,
    OperationInput,
    VariabilityType,
)


@dataclass
class SimulationMetrics:
    """Accumulated metrics during simulation run."""

    # Throughput tracking
    throughput_by_product: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    bundles_completed: int = 0

    # Cycle time tracking
    cycle_times: List[float] = field(default_factory=list)

    # Station metrics
    station_busy_time: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    station_pieces_processed: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    station_queue_waits: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))

    # WIP tracking
    wip_samples: List[int] = field(default_factory=list)
    current_wip: int = 0

    # Rework tracking
    rework_count: int = 0


class ProductionLineSimulator:
    """
    SimPy-based discrete-event simulation for labor-intensive production lines.
    """

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.env = simpy.Environment()
        self.metrics = SimulationMetrics()

        # Build data structures
        self.operations_by_product = self._group_operations_by_product()
        self.demands_by_product = {d.product: d for d in config.demands}
        self.breakdowns_by_tool = {b.machine_tool: b.breakdown_pct for b in (config.breakdowns or [])}

        # Create SimPy resources (machine/tool pools)
        self.resources = self._create_resources()

        # Calculate simulation horizon in minutes
        self.horizon_minutes = config.schedule.daily_planned_hours * 60 * config.horizon_days

    def _group_operations_by_product(self) -> Dict[str, List[OperationInput]]:
        """Group operations by product, sorted by step."""
        grouped = defaultdict(list)
        for op in self.config.operations:
            grouped[op.product].append(op)

        # Sort each product's operations by step
        for product in grouped:
            grouped[product].sort(key=lambda x: x.step)

        return grouped

    def _create_resources(self) -> Dict[str, simpy.Resource]:
        """Create SimPy Resource for each unique machine/tool."""

        # Sum operators across all operations using the same tool
        tool_capacity: Dict[str, int] = defaultdict(int)
        for op in self.config.operations:
            tool_capacity[op.machine_tool] += op.operators

        resources = {}
        for tool, capacity in tool_capacity.items():
            resources[tool] = simpy.Resource(self.env, capacity=capacity)

        return resources

    def _calculate_process_time(self, op: OperationInput) -> float:
        """
        Calculate actual processing time for a single piece.

        Formula: Actual = SAM + (SAM × Variability) + (SAM × FPD) + (SAM × Grade_penalty)
        """
        base_sam = op.sam_min

        # Variability factor
        if op.variability == VariabilityType.TRIANGULAR:
            # Symmetric triangular distribution: -10% to +10%
            variability_factor = random.triangular(-0.10, 0.10, 0)
        else:
            variability_factor = 0

        # FPD multiplier (directly from percentage)
        fpd_multiplier = op.fpd_pct / 100

        # Grade multiplier (penalty for less than 100% skill)
        grade_multiplier = (100 - op.grade_pct) / 100

        actual_time = base_sam * (1 + variability_factor + fpd_multiplier + grade_multiplier)

        return max(0.01, actual_time)  # Minimum 0.01 minutes

    def _get_bundle_transition_time(self, bundle_size: int) -> float:
        """Get transition time in minutes based on bundle size."""
        if bundle_size <= 5:
            return 1 / 60  # 1 second = 1/60 minutes
        else:
            return 5 / 60  # 5 seconds = 5/60 minutes

    def _bundle_process(
        self,
        bundle_id: int,
        product: str,
        bundle_size: int,
        operations: List[OperationInput]
    ):
        """
        Generator function representing a bundle flowing through operations.
        This is the core SimPy process.
        """
        start_time = self.env.now
        self.metrics.current_wip += bundle_size

        transition_time = self._get_bundle_transition_time(bundle_size)

        for op in operations:
            # Entry transition delay
            yield self.env.timeout(transition_time)

            arrival_time = self.env.now

            # Request the machine/tool resource
            with self.resources[op.machine_tool].request() as request:
                yield request  # Wait for availability

                # Record queue wait time
                wait_time = self.env.now - arrival_time
                self.metrics.station_queue_waits[op.machine_tool].append(wait_time)

                # Process each piece in the bundle
                pieces_to_process = bundle_size
                for piece_idx in range(pieces_to_process):
                    process_time = self._calculate_process_time(op)
                    yield self.env.timeout(process_time)

                    # Accumulate busy time
                    self.metrics.station_busy_time[op.machine_tool] += process_time
                    self.metrics.station_pieces_processed[op.machine_tool] += 1

                    # Check for rework
                    if random.random() * 100 < op.rework_pct:
                        self.metrics.rework_count += 1
                        # Simplified: rework adds another cycle at this station
                        rework_time = self._calculate_process_time(op)
                        yield self.env.timeout(rework_time)
                        self.metrics.station_busy_time[op.machine_tool] += rework_time

            # Exit transition delay
            yield self.env.timeout(transition_time)

        # Bundle completed
        end_time = self.env.now
        cycle_time = end_time - start_time

        self.metrics.cycle_times.append(cycle_time)
        self.metrics.throughput_by_product[product] += bundle_size
        self.metrics.bundles_completed += 1
        self.metrics.current_wip -= bundle_size

    def _wip_sampler(self, interval_minutes: float = 5.0):
        """Background process to sample WIP periodically."""
        while True:
            yield self.env.timeout(interval_minutes)
            self.metrics.wip_samples.append(self.metrics.current_wip)

    def _generate_bundles(self):
        """Generate all bundles at simulation start."""

        for product, demand in self.demands_by_product.items():
            if product not in self.operations_by_product:
                continue

            operations = self.operations_by_product[product]
            bundle_size = demand.bundle_size

            # Calculate demand
            daily_demand = demand.daily_demand
            if not daily_demand and demand.weekly_demand:
                daily_demand = demand.weekly_demand / self.config.schedule.work_days

            if not daily_demand:
                continue

            # Scale by horizon
            total_demand = daily_demand * self.config.horizon_days

            # Calculate bundles needed
            bundles_needed = math.ceil(total_demand / bundle_size)

            # Create bundle processes
            for bundle_id in range(bundles_needed):
                self.env.process(
                    self._bundle_process(bundle_id, product, bundle_size, operations)
                )

    def run(self) -> SimulationMetrics:
        """Execute the simulation and return collected metrics."""

        # Start WIP sampler
        self.env.process(self._wip_sampler())

        # Generate all bundles
        self._generate_bundles()

        # Run simulation
        self.env.run(until=self.horizon_minutes)

        return self.metrics


def run_simulation(config: SimulationConfig) -> Tuple[SimulationMetrics, float]:
    """
    Execute simulation and return metrics with duration.

    Returns:
        Tuple of (SimulationMetrics, duration_seconds)
    """
    start_time = datetime.now()

    simulator = ProductionLineSimulator(config)
    metrics = simulator.run()

    end_time = datetime.now()
    duration_seconds = (end_time - start_time).total_seconds()

    return metrics, duration_seconds
```

### 3.4 Output Calculations (`simulation_v2/calculations.py`)

```python
"""
Production Line Simulation v2.0 - Output Block Calculations

Transforms raw simulation metrics into the 8 structured output blocks.
All functions are pure (no side effects) and stateless.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import statistics

from .models import (
    SimulationConfig,
    WeeklyDemandCapacityRow,
    DailySummary,
    StationPerformanceRow,
    FreeCapacityAnalysis,
    BundleMetricsRow,
    PerProductSummaryRow,
    RebalancingSuggestionRow,
    AssumptionLog,
    SimulationResults,
    ValidationReport,
)
from .engine import SimulationMetrics


# Thresholds
BOTTLENECK_THRESHOLD = 95.0  # Utilization % to flag as bottleneck
DONOR_THRESHOLD = 70.0       # Utilization % to flag as potential donor


def calculate_all_blocks(
    config: SimulationConfig,
    metrics: SimulationMetrics,
    validation_report: ValidationReport,
    duration_seconds: float,
    defaults_applied: List[Dict[str, Any]]
) -> SimulationResults:
    """
    Calculate all 8 output blocks from simulation metrics.
    """

    # Calculate intermediates
    horizon_minutes = config.schedule.daily_planned_hours * 60 * config.horizon_days

    # Build block data
    weekly_demand_capacity = _calculate_block1_weekly_capacity(config, metrics)
    daily_summary = _calculate_block2_daily_summary(config, metrics)
    station_performance = _calculate_block3_station_performance(config, metrics, horizon_minutes)
    free_capacity = _calculate_block4_free_capacity(config, metrics, station_performance)
    bundle_metrics = _calculate_block5_bundle_metrics(config, metrics)
    per_product_summary = _calculate_block6_per_product(config, metrics)
    rebalancing_suggestions = _calculate_block7_rebalancing(station_performance, config)
    assumption_log = _calculate_block8_assumption_log(config, defaults_applied)

    return SimulationResults(
        weekly_demand_capacity=weekly_demand_capacity,
        daily_summary=daily_summary,
        station_performance=station_performance,
        free_capacity=free_capacity,
        bundle_metrics=bundle_metrics,
        per_product_summary=per_product_summary,
        rebalancing_suggestions=rebalancing_suggestions,
        assumption_log=assumption_log,
        validation_report=validation_report,
        simulation_duration_seconds=duration_seconds
    )


def _calculate_block1_weekly_capacity(
    config: SimulationConfig,
    metrics: SimulationMetrics
) -> List[WeeklyDemandCapacityRow]:
    """Block 1: Weekly Demand vs Capacity comparison."""

    rows = []

    for demand in config.demands:
        product = demand.product

        # Get demand
        weekly_demand = demand.weekly_demand
        if not weekly_demand and demand.daily_demand:
            weekly_demand = demand.daily_demand * config.schedule.work_days

        if not weekly_demand:
            continue

        # Get throughput (scale to weekly if horizon is daily)
        daily_throughput = metrics.throughput_by_product.get(product, 0) / config.horizon_days
        weekly_capacity = int(daily_throughput * config.schedule.work_days)

        # Calculate coverage
        coverage_pct = (weekly_capacity / weekly_demand * 100) if weekly_demand > 0 else 0

        # Determine status
        if coverage_pct >= 110:
            status = "OK"
        elif coverage_pct >= 90:
            status = "Tight"
        else:
            status = "Shortfall"

        rows.append(WeeklyDemandCapacityRow(
            product=product,
            weekly_demand_pcs=int(weekly_demand),
            max_weekly_capacity_pcs=weekly_capacity,
            demand_coverage_pct=round(coverage_pct, 1),
            status=status
        ))

    return rows


def _calculate_block2_daily_summary(
    config: SimulationConfig,
    metrics: SimulationMetrics
) -> DailySummary:
    """Block 2: Daily aggregate summary."""

    total_throughput = sum(metrics.throughput_by_product.values())
    daily_throughput = int(total_throughput / config.horizon_days)

    # Calculate daily demand
    total_daily_demand = 0
    for demand in config.demands:
        if demand.daily_demand:
            total_daily_demand += demand.daily_demand
        elif demand.weekly_demand:
            total_daily_demand += demand.weekly_demand / config.schedule.work_days

    coverage_pct = (daily_throughput / total_daily_demand * 100) if total_daily_demand > 0 else 0

    # Cycle time
    avg_cycle_time = statistics.mean(metrics.cycle_times) if metrics.cycle_times else 0

    # WIP
    avg_wip = statistics.mean(metrics.wip_samples) if metrics.wip_samples else 0

    # Bundle size
    bundle_sizes = set(d.bundle_size for d in config.demands if d.product in metrics.throughput_by_product)
    bundle_size_str = str(list(bundle_sizes)[0]) if len(bundle_sizes) == 1 else "mixed"

    return DailySummary(
        total_shifts_per_day=config.schedule.shifts_enabled,
        daily_planned_hours=config.schedule.daily_planned_hours,
        daily_throughput_pcs=daily_throughput,
        daily_demand_pcs=int(total_daily_demand),
        daily_coverage_pct=round(coverage_pct, 1),
        avg_cycle_time_min=round(avg_cycle_time, 1),
        avg_wip_pcs=round(avg_wip, 0),
        bundles_processed_per_day=int(metrics.bundles_completed / config.horizon_days),
        bundle_size_pcs=bundle_size_str
    )


def _calculate_block3_station_performance(
    config: SimulationConfig,
    metrics: SimulationMetrics,
    horizon_minutes: float
) -> List[StationPerformanceRow]:
    """Block 3: Per-station performance metrics."""

    rows = []

    # Group operations by machine_tool to get total capacity
    tool_operators: Dict[str, int] = defaultdict(int)
    for op in config.operations:
        tool_operators[op.machine_tool] += op.operators

    for op in config.operations:
        machine_tool = op.machine_tool

        # Available time for this station
        total_operators = tool_operators[machine_tool]
        available_minutes = horizon_minutes * total_operators

        # Get metrics for this tool
        busy_time = metrics.station_busy_time.get(machine_tool, 0)
        pieces = metrics.station_pieces_processed.get(machine_tool, 0)
        queue_waits = metrics.station_queue_waits.get(machine_tool, [])

        # Calculate utilization
        util_pct = (busy_time / available_minutes * 100) if available_minutes > 0 else 0

        # Average processing time
        avg_process_time = (busy_time / pieces) if pieces > 0 else op.sam_min

        # Average queue wait
        avg_queue_wait = statistics.mean(queue_waits) if queue_waits else 0

        # Flags
        is_bottleneck = util_pct >= BOTTLENECK_THRESHOLD
        is_donor = util_pct <= DONOR_THRESHOLD and op.operators > 1

        rows.append(StationPerformanceRow(
            product=op.product,
            step=op.step,
            operation=op.operation,
            machine_tool=machine_tool,
            sequence=op.sequence,
            grouping=op.grouping,
            operators=op.operators,
            total_pieces_processed=pieces,
            total_busy_time_min=round(busy_time, 1),
            avg_processing_time_min=round(avg_process_time, 2),
            util_pct=round(util_pct, 1),
            queue_wait_time_min=round(avg_queue_wait, 1),
            is_bottleneck=is_bottleneck,
            is_donor=is_donor
        ))

    return rows


def _calculate_block4_free_capacity(
    config: SimulationConfig,
    metrics: SimulationMetrics,
    station_performance: List[StationPerformanceRow]
) -> FreeCapacityAnalysis:
    """Block 4: Free capacity analysis."""

    # Find bottleneck utilization
    bottleneck_util = max((s.util_pct for s in station_performance), default=0)

    # Daily figures
    total_throughput = sum(metrics.throughput_by_product.values())
    daily_throughput = total_throughput / config.horizon_days

    total_daily_demand = sum(
        d.daily_demand or (d.weekly_demand / config.schedule.work_days if d.weekly_demand else 0)
        for d in config.demands
    )

    # Max capacity based on bottleneck
    daily_max_capacity = int(daily_throughput / (bottleneck_util / 100)) if bottleneck_util > 0 else int(daily_throughput)

    demand_usage_pct = (total_daily_demand / daily_max_capacity * 100) if daily_max_capacity > 0 else 100

    free_pct = max(0, 100 - demand_usage_pct)
    free_line_hours = config.schedule.daily_planned_hours * (free_pct / 100)
    free_bottleneck_hours = config.schedule.daily_planned_hours * ((100 - bottleneck_util) / 100)

    return FreeCapacityAnalysis(
        daily_demand_pcs=int(total_daily_demand),
        daily_max_capacity_pcs=daily_max_capacity,
        demand_usage_pct=round(demand_usage_pct, 1),
        free_line_hours_per_day=round(free_line_hours, 2),
        free_operator_hours_at_bottleneck_per_day=round(free_bottleneck_hours, 2),
        equivalent_free_operators_full_shift=round(free_bottleneck_hours / config.schedule.shift1_hours, 2)
    )


def _calculate_block5_bundle_metrics(
    config: SimulationConfig,
    metrics: SimulationMetrics
) -> List[BundleMetricsRow]:
    """Block 5: Bundle behavior metrics."""

    rows = []

    for demand in config.demands:
        product = demand.product
        if product not in metrics.throughput_by_product:
            continue

        daily_demand = demand.daily_demand or (demand.weekly_demand / config.schedule.work_days if demand.weekly_demand else 0)
        bundles_per_day = int(daily_demand / demand.bundle_size) if demand.bundle_size > 0 else 0

        rows.append(BundleMetricsRow(
            product=product,
            bundle_size_pcs=demand.bundle_size,
            bundles_arriving_per_day=bundles_per_day,
            avg_bundles_in_system=None,  # Future enhancement
            max_bundles_in_system=None,
            avg_bundle_cycle_time_min=None
        ))

    return rows


def _calculate_block6_per_product(
    config: SimulationConfig,
    metrics: SimulationMetrics
) -> List[PerProductSummaryRow]:
    """Block 6: Per-product summary."""

    rows = []

    for demand in config.demands:
        product = demand.product
        throughput = metrics.throughput_by_product.get(product, 0)

        daily_demand = demand.daily_demand or (demand.weekly_demand / config.schedule.work_days if demand.weekly_demand else 0)
        weekly_demand = demand.weekly_demand or (demand.daily_demand * config.schedule.work_days if demand.daily_demand else 0)

        daily_throughput = int(throughput / config.horizon_days)
        weekly_throughput = int(daily_throughput * config.schedule.work_days)

        daily_coverage = (daily_throughput / daily_demand * 100) if daily_demand > 0 else 0
        weekly_coverage = (weekly_throughput / weekly_demand * 100) if weekly_demand > 0 else 0

        rows.append(PerProductSummaryRow(
            product=product,
            bundle_size_pcs=demand.bundle_size,
            mix_share_pct=demand.mix_share_pct,
            daily_demand_pcs=int(daily_demand),
            daily_throughput_pcs=daily_throughput,
            daily_coverage_pct=round(daily_coverage, 1),
            weekly_demand_pcs=int(weekly_demand),
            weekly_throughput_pcs=weekly_throughput,
            weekly_coverage_pct=round(weekly_coverage, 1)
        ))

    return rows


def _calculate_block7_rebalancing(
    station_performance: List[StationPerformanceRow],
    config: SimulationConfig
) -> List[RebalancingSuggestionRow]:
    """Block 7: Rebalancing suggestions."""

    suggestions = []

    # Find bottlenecks and donors
    bottlenecks = [s for s in station_performance if s.is_bottleneck]
    donors = [s for s in station_performance if s.is_donor]

    # Pair bottlenecks with donors
    for bottleneck, donor in zip(bottlenecks, donors):
        # Suggest adding to bottleneck
        new_operators = bottleneck.operators + 1
        new_util = bottleneck.util_pct * bottleneck.operators / new_operators

        suggestions.append(RebalancingSuggestionRow(
            product="ALL",
            step=bottleneck.step,
            operation=bottleneck.operation,
            machine_tool=bottleneck.machine_tool,
            grouping=bottleneck.grouping,
            operators_before=bottleneck.operators,
            operators_after=new_operators,
            util_before_pct=bottleneck.util_pct,
            util_after_pct=round(new_util, 1),
            role="Bottleneck",
            comment="Add 1 operator"
        ))

        # Suggest removing from donor
        if donor.operators > 1:
            new_operators = donor.operators - 1
            new_util = donor.util_pct * donor.operators / new_operators

            suggestions.append(RebalancingSuggestionRow(
                product="ALL",
                step=donor.step,
                operation=donor.operation,
                machine_tool=donor.machine_tool,
                grouping=donor.grouping,
                operators_before=donor.operators,
                operators_after=new_operators,
                util_before_pct=donor.util_pct,
                util_after_pct=round(new_util, 1),
                role="Donor",
                comment=f"Move 1 operator to Step {bottleneck.step}"
            ))

    return suggestions


def _calculate_block8_assumption_log(
    config: SimulationConfig,
    defaults_applied: List[Dict[str, Any]]
) -> AssumptionLog:
    """Block 8: Complete assumption log."""

    return AssumptionLog(
        timestamp=datetime.utcnow(),
        simulation_engine_version="2.0.0",
        configuration_mode=config.mode.value,
        schedule={
            "shifts_enabled": config.schedule.shifts_enabled,
            "shift1_hours": config.schedule.shift1_hours,
            "shift2_hours": config.schedule.shift2_hours,
            "shift3_hours": config.schedule.shift3_hours,
            "work_days": config.schedule.work_days,
            "ot_enabled": config.schedule.ot_enabled,
            "weekday_ot_hours": config.schedule.weekday_ot_hours,
            "weekend_ot_days": config.schedule.weekend_ot_days,
            "weekend_ot_hours": config.schedule.weekend_ot_hours,
            "daily_planned_hours": config.schedule.daily_planned_hours,
            "weekly_base_hours": config.schedule.weekly_base_hours
        },
        products=[
            {
                "product": d.product,
                "bundle_size": d.bundle_size,
                "daily_demand": d.daily_demand,
                "weekly_demand": d.weekly_demand,
                "mix_share_pct": d.mix_share_pct
            }
            for d in config.demands
        ],
        operations_defaults_applied=defaults_applied,
        breakdowns_configuration={
            "enabled": bool(config.breakdowns),
            "message": "Perfect equipment reliability assumed" if not config.breakdowns else f"{len(config.breakdowns)} breakdown rules configured"
        },
        formula_implementations={
            "processing_time": "SAM + (SAM × Variability) + (SAM × FPD_pct/100) + (SAM × (100-Grade_pct)/100)",
            "bundle_transition": "1 second if bundle_size ≤ 5, else 5 seconds",
            "utilization": "(Busy_Time / Available_Time) × 100"
        },
        limitations_and_caveats=[
            "Single replication run - results represent one possible outcome",
            "Weekly capacity assumes uniform daily production",
            "Learning curves not modeled",
            "Material availability assumed perfect",
            "Quality costs included but not second-order effects"
        ]
    )
```

### 3.5 Router (`routes/simulation_v2.py`)

```python
"""
Production Line Simulation v2.0 - API Endpoints

Provides REST endpoints for the ephemeral simulation tool.
All endpoints are stateless with no database dependencies.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from backend.auth.jwt import get_current_user
from backend.models.user import User

from backend.simulation_v2.models import (
    SimulationConfig,
    SimulationRequest,
    SimulationResponse,
    ValidationReport,
)
from backend.simulation_v2.validation import validate_simulation_config
from backend.simulation_v2.engine import run_simulation
from backend.simulation_v2.calculations import calculate_all_blocks


router = APIRouter(
    prefix="/api/v2/simulation",
    tags=["simulation-v2"],
    responses={404: {"description": "Not found"}},
)


def _check_simulation_permission(user: User) -> None:
    """Verify user has permission to run simulations."""
    allowed_roles = {"admin", "poweruser", "leader"}
    if user.role.lower() not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulation access requires Leader, PowerUser, or Admin role"
        )


@router.get("/")
async def simulation_info():
    """Get simulation tool information and capabilities."""
    return {
        "name": "Production Line Simulation Tool",
        "version": "2.0.0",
        "description": "Ephemeral capacity planning and line behavior simulation",
        "capabilities": [
            "Multi-product discrete-event simulation",
            "Stochastic variability modeling",
            "Bottleneck detection and rebalancing suggestions",
            "8 comprehensive output blocks",
            "Excel export support"
        ],
        "limitations": [
            "No persistent storage of scenarios",
            "No database integration",
            "Single replication per run"
        ],
        "max_products": 5,
        "max_operations_per_product": 50
    }


@router.post("/validate", response_model=ValidationReport)
async def validate_configuration(
    request: SimulationRequest,
    current_user: User = Depends(get_current_user)
) -> ValidationReport:
    """
    Validate simulation configuration without running simulation.

    Use this endpoint to check inputs before committing to a full simulation run.
    """
    _check_simulation_permission(current_user)

    report = validate_simulation_config(request.config)
    return report


@router.post("/run", response_model=SimulationResponse)
async def run_simulation_endpoint(
    request: SimulationRequest,
    current_user: User = Depends(get_current_user)
) -> SimulationResponse:
    """
    Run complete simulation and return results.

    This endpoint validates inputs, runs the SimPy simulation, and returns
    all 8 output blocks. Results are not stored - export to Excel for persistence.
    """
    _check_simulation_permission(current_user)

    config = request.config

    # Validate first
    validation_report = validate_simulation_config(config)

    if validation_report.has_errors:
        return SimulationResponse(
            success=False,
            results=None,
            validation_report=validation_report,
            message="Validation failed. Please correct errors and retry."
        )

    try:
        # Track defaults applied
        defaults_applied = _track_defaults(config)

        # Run simulation
        metrics, duration = run_simulation(config)

        # Calculate output blocks
        results = calculate_all_blocks(
            config=config,
            metrics=metrics,
            validation_report=validation_report,
            duration_seconds=duration,
            defaults_applied=defaults_applied
        )

        return SimulationResponse(
            success=True,
            results=results,
            validation_report=validation_report,
            message=f"Simulation completed in {duration:.2f} seconds"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(e)}"
        )


def _track_defaults(config: SimulationConfig) -> list:
    """Track which operations used default values."""
    defaults = []

    for op in config.operations:
        applied = []

        # Check each optional field against defaults
        if op.sequence == "Assembly":
            applied.append("Sequence: Assembly")
        if op.operators == 1:
            applied.append("Operators: 1")
        if op.variability.value == "triangular":
            applied.append("Variability: triangular")
        if op.rework_pct == 0.0:
            applied.append("Rework_pct: 0")
        if op.grade_pct == 85.0:
            applied.append("Grade_pct: 85")
        if op.fpd_pct == 15.0:
            applied.append("FPD_pct: 15")

        if applied:
            defaults.append({
                "product": op.product,
                "step": op.step,
                "operation": op.operation,
                "defaults": applied
            })

    return defaults
```

---

## 4. Frontend Specifications

### 4.1 Pinia Store (`stores/simulationV2Store.js`)

```javascript
/**
 * Production Line Simulation v2.0 - State Management
 *
 * Manages all simulation state including inputs, validation, and results.
 * State is ephemeral - cleared on page navigation or browser refresh.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  validateSimulationConfig,
  runSimulation
} from '@/services/api/simulationV2'

export const useSimulationV2Store = defineStore('simulationV2', () => {
  // ============================================================
  // STATE
  // ============================================================

  // Input state
  const operations = ref([])
  const schedule = ref({
    shifts_enabled: 1,
    shift1_hours: 8,
    shift2_hours: 0,
    shift3_hours: 0,
    work_days: 5,
    ot_enabled: false,
    weekday_ot_hours: 0,
    weekend_ot_days: 0,
    weekend_ot_hours: 0
  })
  const demands = ref([])
  const breakdowns = ref([])
  const mode = ref('demand-driven')
  const totalDemand = ref(null)
  const horizonDays = ref(1)

  // Validation state
  const validationReport = ref(null)
  const isValidating = ref(false)

  // Results state
  const results = ref(null)
  const isRunning = ref(false)

  // UI state
  const currentStep = ref('input') // 'input' | 'validating' | 'running' | 'results'
  const error = ref(null)

  // ============================================================
  // COMPUTED
  // ============================================================

  const canValidate = computed(() => {
    return operations.value.length > 0 && demands.value.length > 0
  })

  const canRun = computed(() => {
    return canValidate.value &&
           validationReport.value?.is_valid !== false
  })

  const hasErrors = computed(() => {
    return validationReport.value?.errors?.length > 0
  })

  const hasWarnings = computed(() => {
    return validationReport.value?.warnings?.length > 0
  })

  const productsInOperations = computed(() => {
    return [...new Set(operations.value.map(op => op.product))]
  })

  const machineToolsInOperations = computed(() => {
    return [...new Set(operations.value.map(op => op.machine_tool))]
  })

  // ============================================================
  // ACTIONS
  // ============================================================

  /**
   * Build configuration object for API calls
   */
  function buildConfig() {
    return {
      operations: operations.value,
      schedule: schedule.value,
      demands: demands.value,
      breakdowns: breakdowns.value.length > 0 ? breakdowns.value : null,
      mode: mode.value,
      total_demand: mode.value === 'mix-driven' ? totalDemand.value : null,
      horizon_days: horizonDays.value
    }
  }

  /**
   * Validate inputs without running simulation
   */
  async function validate() {
    isValidating.value = true
    error.value = null
    currentStep.value = 'validating'

    try {
      const response = await validateSimulationConfig({ config: buildConfig() })
      validationReport.value = response.data

      if (validationReport.value.is_valid) {
        currentStep.value = 'input' // Return to input, ready to run
      }
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      currentStep.value = 'input'
    } finally {
      isValidating.value = false
    }
  }

  /**
   * Run full simulation
   */
  async function run() {
    isRunning.value = true
    error.value = null
    currentStep.value = 'running'

    try {
      const response = await runSimulation({ config: buildConfig() })

      if (response.data.success) {
        results.value = response.data.results
        validationReport.value = response.data.validation_report
        currentStep.value = 'results'
      } else {
        validationReport.value = response.data.validation_report
        currentStep.value = 'input'
      }
    } catch (err) {
      error.value = err.response?.data?.detail || err.message
      currentStep.value = 'input'
    } finally {
      isRunning.value = false
    }
  }

  /**
   * Import operations from parsed CSV/Excel data
   */
  function importOperations(data) {
    operations.value = data.map((row, index) => ({
      product: row.Product || row.product || '',
      step: parseInt(row.Step || row.step || index + 1),
      operation: row.Operation || row.operation || '',
      machine_tool: row.Machine_Tool || row.machine_tool || '',
      sam_min: parseFloat(row.SAM_min || row.sam_min || 0),
      sequence: row.Sequence || row.sequence || 'Assembly',
      grouping: row.Grouping || row.grouping || '',
      operators: parseInt(row.Operators || row.operators || 1),
      variability: row.Variability || row.variability || 'triangular',
      rework_pct: parseFloat(row.Rework_pct || row.rework_pct || 0),
      grade_pct: parseFloat(row.Grade_pct || row.grade_pct || 85),
      fpd_pct: parseFloat(row.FPD_pct || row.fpd_pct || 15)
    }))

    // Clear validation when inputs change
    validationReport.value = null
  }

  /**
   * Import demands from parsed CSV/Excel data
   */
  function importDemands(data) {
    demands.value = data.map(row => ({
      product: row.Product || row.product || '',
      bundle_size: parseInt(row.Bundle_Size || row.bundle_size || 1),
      daily_demand: row.Daily_Demand || row.daily_demand ? parseFloat(row.Daily_Demand || row.daily_demand) : null,
      weekly_demand: row.Weekly_Demand || row.weekly_demand ? parseFloat(row.Weekly_Demand || row.weekly_demand) : null,
      mix_share_pct: row.Mix_Share_pct || row.mix_share_pct ? parseFloat(row.Mix_Share_pct || row.mix_share_pct) : null
    }))

    validationReport.value = null
  }

  /**
   * Reset all state
   */
  function reset() {
    operations.value = []
    schedule.value = {
      shifts_enabled: 1,
      shift1_hours: 8,
      shift2_hours: 0,
      shift3_hours: 0,
      work_days: 5,
      ot_enabled: false,
      weekday_ot_hours: 0,
      weekend_ot_days: 0,
      weekend_ot_hours: 0
    }
    demands.value = []
    breakdowns.value = []
    mode.value = 'demand-driven'
    totalDemand.value = null
    horizonDays.value = 1
    validationReport.value = null
    results.value = null
    currentStep.value = 'input'
    error.value = null
  }

  /**
   * Return to input step from results
   */
  function backToInput() {
    currentStep.value = 'input'
    results.value = null
  }

  return {
    // State
    operations,
    schedule,
    demands,
    breakdowns,
    mode,
    totalDemand,
    horizonDays,
    validationReport,
    isValidating,
    results,
    isRunning,
    currentStep,
    error,

    // Computed
    canValidate,
    canRun,
    hasErrors,
    hasWarnings,
    productsInOperations,
    machineToolsInOperations,

    // Actions
    buildConfig,
    validate,
    run,
    importOperations,
    importDemands,
    reset,
    backToInput
  }
})
```

### 4.2 API Client (`services/api/simulationV2.js`)

```javascript
/**
 * Production Line Simulation v2.0 - API Client
 */

import api from './index'

const BASE_URL = '/api/v2/simulation'

/**
 * Get simulation tool info and capabilities
 */
export const getSimulationInfo = () => api.get(`${BASE_URL}/`)

/**
 * Validate simulation configuration without running
 * @param {Object} data - { config: SimulationConfig }
 */
export const validateSimulationConfig = (data) => api.post(`${BASE_URL}/validate`, data)

/**
 * Run full simulation
 * @param {Object} data - { config: SimulationConfig }
 */
export const runSimulation = (data) => api.post(`${BASE_URL}/run`, data)

export default {
  getSimulationInfo,
  validateSimulationConfig,
  runSimulation
}
```

### 4.3 Excel Export Utility (`utils/excelExport.js`)

```javascript
/**
 * Production Line Simulation v2.0 - Excel Export
 *
 * Client-side Excel generation using SheetJS (xlsx library).
 * Creates comprehensive workbook with all simulation data.
 */

import * as XLSX from 'xlsx'

/**
 * Export simulation results to Excel workbook
 * @param {Object} results - SimulationResults from API
 * @param {Object} config - Original SimulationConfig
 * @param {string} filename - Output filename (without extension)
 */
export function exportSimulationToExcel(results, config, filename = 'simulation_results') {
  const wb = XLSX.utils.book_new()

  // Sheet 1: Summary
  const summaryData = buildSummarySheet(results, config)
  const summaryWs = XLSX.utils.aoa_to_sheet(summaryData)
  XLSX.utils.book_append_sheet(wb, summaryWs, 'Summary')

  // Sheet 2: Assumption Log
  const assumptionData = buildAssumptionSheet(results.assumption_log)
  const assumptionWs = XLSX.utils.aoa_to_sheet(assumptionData)
  XLSX.utils.book_append_sheet(wb, assumptionWs, 'Assumptions')

  // Sheet 3: Operations Input
  const opsWs = XLSX.utils.json_to_sheet(config.operations)
  XLSX.utils.book_append_sheet(wb, opsWs, 'Operations Input')

  // Sheet 4: Schedule Input
  const scheduleData = buildScheduleSheet(config.schedule)
  const scheduleWs = XLSX.utils.aoa_to_sheet(scheduleData)
  XLSX.utils.book_append_sheet(wb, scheduleWs, 'Schedule Input')

  // Sheet 5: Demand Input
  const demandWs = XLSX.utils.json_to_sheet(config.demands)
  XLSX.utils.book_append_sheet(wb, demandWs, 'Demand Input')

  // Sheet 6: Weekly Demand vs Capacity (Block 1)
  const block1Ws = XLSX.utils.json_to_sheet(results.weekly_demand_capacity)
  XLSX.utils.book_append_sheet(wb, block1Ws, 'Weekly Capacity')

  // Sheet 7: Daily Summary (Block 2)
  const block2Data = buildDailySummarySheet(results.daily_summary)
  const block2Ws = XLSX.utils.aoa_to_sheet(block2Data)
  XLSX.utils.book_append_sheet(wb, block2Ws, 'Daily Summary')

  // Sheet 8: Station Performance (Block 3)
  const block3Ws = XLSX.utils.json_to_sheet(results.station_performance)
  XLSX.utils.book_append_sheet(wb, block3Ws, 'Station Performance')

  // Sheet 9: Free Capacity (Block 4)
  const block4Data = buildFreeCapacitySheet(results.free_capacity)
  const block4Ws = XLSX.utils.aoa_to_sheet(block4Data)
  XLSX.utils.book_append_sheet(wb, block4Ws, 'Free Capacity')

  // Sheet 10: Bundle Metrics (Block 5)
  const block5Ws = XLSX.utils.json_to_sheet(results.bundle_metrics)
  XLSX.utils.book_append_sheet(wb, block5Ws, 'Bundle Metrics')

  // Sheet 11: Per-Product Summary (Block 6)
  const block6Ws = XLSX.utils.json_to_sheet(results.per_product_summary)
  XLSX.utils.book_append_sheet(wb, block6Ws, 'Per-Product Summary')

  // Sheet 12: Rebalancing Suggestions (Block 7)
  const block7Ws = XLSX.utils.json_to_sheet(results.rebalancing_suggestions)
  XLSX.utils.book_append_sheet(wb, block7Ws, 'Rebalancing')

  // Generate timestamp for filename
  const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')
  const fullFilename = `${filename}_${timestamp}.xlsx`

  // Trigger download
  XLSX.writeFile(wb, fullFilename)

  return fullFilename
}

function buildSummarySheet(results, config) {
  const ds = results.daily_summary
  return [
    ['Production Line Simulation Results'],
    [''],
    ['Generated', new Date().toISOString()],
    ['Engine Version', results.assumption_log.simulation_engine_version],
    ['Configuration Mode', results.assumption_log.configuration_mode],
    [''],
    ['=== KEY RESULTS ==='],
    ['Daily Throughput (pcs)', ds.daily_throughput_pcs],
    ['Daily Demand (pcs)', ds.daily_demand_pcs],
    ['Coverage %', ds.daily_coverage_pct],
    ['Avg Cycle Time (min)', ds.avg_cycle_time_min],
    ['Avg WIP (pcs)', ds.avg_wip_pcs],
    [''],
    ['=== SCHEDULE ==='],
    ['Shifts per Day', ds.total_shifts_per_day],
    ['Daily Planned Hours', ds.daily_planned_hours],
    ['Bundles Processed', ds.bundles_processed_per_day],
    [''],
    ['=== PRODUCTS ==='],
    ['Products Count', config.demands.length],
    ['Operations Count', config.operations.length]
  ]
}

function buildAssumptionSheet(log) {
  const rows = [
    ['Assumption Log'],
    [''],
    ['Timestamp', log.timestamp],
    ['Engine Version', log.simulation_engine_version],
    ['Mode', log.configuration_mode],
    [''],
    ['=== SCHEDULE ==='],
    ...Object.entries(log.schedule).map(([k, v]) => [k, v]),
    [''],
    ['=== FORMULAS ==='],
    ...Object.entries(log.formula_implementations).map(([k, v]) => [k, v]),
    [''],
    ['=== LIMITATIONS ==='],
    ...log.limitations_and_caveats.map(l => ['•', l])
  ]
  return rows
}

function buildScheduleSheet(schedule) {
  return [
    ['Schedule Configuration'],
    [''],
    ['Shifts Enabled', schedule.shifts_enabled],
    ['Shift 1 Hours', schedule.shift1_hours],
    ['Shift 2 Hours', schedule.shift2_hours],
    ['Shift 3 Hours', schedule.shift3_hours],
    ['Work Days per Week', schedule.work_days],
    [''],
    ['Overtime Enabled', schedule.ot_enabled ? 'Yes' : 'No'],
    ['Weekday OT Hours', schedule.weekday_ot_hours],
    ['Weekend OT Days', schedule.weekend_ot_days],
    ['Weekend OT Hours', schedule.weekend_ot_hours]
  ]
}

function buildDailySummarySheet(ds) {
  return [
    ['Daily Simulation Summary'],
    [''],
    ['Metric', 'Value'],
    ['Total Shifts per Day', ds.total_shifts_per_day],
    ['Daily Planned Hours', ds.daily_planned_hours],
    ['Daily Throughput (pcs)', ds.daily_throughput_pcs],
    ['Daily Demand (pcs)', ds.daily_demand_pcs],
    ['Daily Coverage %', ds.daily_coverage_pct],
    ['Avg Cycle Time (min)', ds.avg_cycle_time_min],
    ['Avg WIP (pcs)', ds.avg_wip_pcs],
    ['Bundles Processed', ds.bundles_processed_per_day],
    ['Bundle Size', ds.bundle_size_pcs]
  ]
}

function buildFreeCapacitySheet(fc) {
  return [
    ['Free Capacity Analysis'],
    [''],
    ['Metric', 'Value'],
    ['Daily Demand (pcs)', fc.daily_demand_pcs],
    ['Daily Max Capacity (pcs)', fc.daily_max_capacity_pcs],
    ['Demand Usage %', fc.demand_usage_pct],
    ['Free Line Hours/Day', fc.free_line_hours_per_day],
    ['Free Operator Hours at Bottleneck', fc.free_operator_hours_at_bottleneck_per_day],
    ['Equivalent Free Operators (full shift)', fc.equivalent_free_operators_full_shift]
  ]
}

export default {
  exportSimulationToExcel
}
```

---

## 5. Test Specifications

### 5.1 Backend Test Cases

#### `test_simulation_v2/test_models.py`

```python
"""Test Pydantic model validation."""

import pytest
from pydantic import ValidationError
from backend.simulation_v2.models import (
    OperationInput,
    ScheduleConfig,
    DemandInput,
    SimulationConfig,
)


class TestOperationInput:
    """Tests for OperationInput model."""

    def test_valid_operation(self):
        """Valid operation should pass validation."""
        op = OperationInput(
            product="TSHIRT",
            step=1,
            operation="Cut panels",
            machine_tool="Cutting table",
            sam_min=2.5
        )
        assert op.product == "TSHIRT"
        assert op.grade_pct == 85.0  # Default

    def test_sam_must_be_positive(self):
        """SAM must be greater than zero."""
        with pytest.raises(ValidationError) as exc:
            OperationInput(
                product="X", step=1, operation="Y",
                machine_tool="Z", sam_min=0
            )
        assert "sam_min" in str(exc.value)

    def test_step_must_be_positive(self):
        """Step must be at least 1."""
        with pytest.raises(ValidationError):
            OperationInput(
                product="X", step=0, operation="Y",
                machine_tool="Z", sam_min=1.0
            )

    def test_variability_enum_validation(self):
        """Variability must be valid enum value."""
        with pytest.raises(ValidationError):
            OperationInput(
                product="X", step=1, operation="Y",
                machine_tool="Z", sam_min=1.0,
                variability="invalid"
            )


class TestScheduleConfig:
    """Tests for ScheduleConfig model."""

    def test_valid_schedule(self):
        """Valid schedule passes validation."""
        schedule = ScheduleConfig(
            shifts_enabled=2,
            shift1_hours=9,
            shift2_hours=8,
            work_days=5
        )
        assert schedule.daily_planned_hours == 17.0
        assert schedule.weekly_base_hours == 85.0

    def test_total_hours_exceed_24(self):
        """Should reject schedules exceeding 24 hours."""
        with pytest.raises(ValidationError) as exc:
            ScheduleConfig(
                shifts_enabled=3,
                shift1_hours=10,
                shift2_hours=10,
                shift3_hours=10,
                work_days=5
            )
        assert "24" in str(exc.value)

    def test_single_shift_ignores_others(self):
        """Single shift should only count shift1 hours."""
        schedule = ScheduleConfig(
            shifts_enabled=1,
            shift1_hours=8,
            shift2_hours=8,  # Should be ignored
            shift3_hours=8,  # Should be ignored
            work_days=5
        )
        assert schedule.daily_planned_hours == 8.0
```

#### `test_simulation_v2/test_validation.py`

```python
"""Test domain validation logic."""

import pytest
from backend.simulation_v2.models import (
    SimulationConfig, OperationInput, ScheduleConfig, DemandInput, DemandMode
)
from backend.simulation_v2.validation import validate_simulation_config


@pytest.fixture
def valid_config():
    """Fixture providing valid minimal configuration."""
    return SimulationConfig(
        operations=[
            OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
            OperationInput(product="A", step=2, operation="Op2", machine_tool="M2", sam_min=1.5),
        ],
        schedule=ScheduleConfig(shifts_enabled=1, shift1_hours=8, work_days=5),
        demands=[DemandInput(product="A", daily_demand=100)],
        mode=DemandMode.DEMAND_DRIVEN
    )


class TestSequenceValidation:
    """Tests for operation sequence validation."""

    def test_valid_sequence(self, valid_config):
        """Sequential steps should pass."""
        report = validate_simulation_config(valid_config)
        assert report.is_valid
        assert len(report.errors) == 0

    def test_gap_in_sequence(self):
        """Missing step should generate error."""
        config = SimulationConfig(
            operations=[
                OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
                OperationInput(product="A", step=3, operation="Op3", machine_tool="M3", sam_min=1.0),  # Step 2 missing
            ],
            schedule=ScheduleConfig(shifts_enabled=1, shift1_hours=8, work_days=5),
            demands=[DemandInput(product="A", daily_demand=100)],
            mode=DemandMode.DEMAND_DRIVEN
        )
        report = validate_simulation_config(config)
        assert not report.is_valid
        assert any("gap" in e.message.lower() for e in report.errors)

    def test_duplicate_steps(self):
        """Duplicate steps should generate error."""
        config = SimulationConfig(
            operations=[
                OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
                OperationInput(product="A", step=1, operation="Op2", machine_tool="M2", sam_min=1.0),  # Duplicate
            ],
            schedule=ScheduleConfig(shifts_enabled=1, shift1_hours=8, work_days=5),
            demands=[DemandInput(product="A", daily_demand=100)],
            mode=DemandMode.DEMAND_DRIVEN
        )
        report = validate_simulation_config(config)
        assert not report.is_valid


class TestProductConsistency:
    """Tests for product consistency validation."""

    def test_demand_without_operations(self):
        """Product in demand but not operations should error."""
        config = SimulationConfig(
            operations=[
                OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
            ],
            schedule=ScheduleConfig(shifts_enabled=1, shift1_hours=8, work_days=5),
            demands=[
                DemandInput(product="A", daily_demand=100),
                DemandInput(product="B", daily_demand=50),  # No operations for B
            ],
            mode=DemandMode.DEMAND_DRIVEN
        )
        report = validate_simulation_config(config)
        assert not report.is_valid
        assert any("B" in e.product for e in report.errors)


class TestMixModeValidation:
    """Tests for mix-driven mode validation."""

    def test_mix_percentages_must_sum_to_100(self):
        """Mix shares not summing to 100 should error."""
        config = SimulationConfig(
            operations=[
                OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
                OperationInput(product="B", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
            ],
            schedule=ScheduleConfig(shifts_enabled=1, shift1_hours=8, work_days=5),
            demands=[
                DemandInput(product="A", mix_share_pct=40),
                DemandInput(product="B", mix_share_pct=40),  # Total 80, not 100
            ],
            mode=DemandMode.MIX_DRIVEN,
            total_demand=1000
        )
        report = validate_simulation_config(config)
        assert not report.is_valid
        assert any("100" in e.message for e in report.errors)
```

#### `test_simulation_v2/test_engine.py`

```python
"""Test SimPy simulation engine."""

import pytest
from backend.simulation_v2.models import (
    SimulationConfig, OperationInput, ScheduleConfig, DemandInput,
    DemandMode, VariabilityType
)
from backend.simulation_v2.engine import run_simulation, ProductionLineSimulator


@pytest.fixture
def simple_config():
    """Single product, two operations, deterministic."""
    return SimulationConfig(
        operations=[
            OperationInput(
                product="TEST", step=1, operation="Op1", machine_tool="M1",
                sam_min=1.0, variability=VariabilityType.DETERMINISTIC,
                grade_pct=100, fpd_pct=0, rework_pct=0
            ),
            OperationInput(
                product="TEST", step=2, operation="Op2", machine_tool="M2",
                sam_min=1.0, variability=VariabilityType.DETERMINISTIC,
                grade_pct=100, fpd_pct=0, rework_pct=0
            ),
        ],
        schedule=ScheduleConfig(shifts_enabled=1, shift1_hours=8, work_days=5),
        demands=[DemandInput(product="TEST", bundle_size=1, daily_demand=10)],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1
    )


class TestSimulationExecution:
    """Tests for basic simulation execution."""

    def test_simulation_completes(self, simple_config):
        """Simulation should complete without error."""
        metrics, duration = run_simulation(simple_config)
        assert duration > 0
        assert metrics is not None

    def test_deterministic_throughput(self, simple_config):
        """Deterministic config should produce predictable throughput."""
        metrics, _ = run_simulation(simple_config)

        # With 10 units demanded, 2 min each (1+1), 8 hours = 480 min
        # Can process 480/2 = 240 units max, so all 10 should complete
        assert metrics.throughput_by_product["TEST"] == 10

    def test_bundles_tracked(self, simple_config):
        """Bundle completion should be tracked."""
        metrics, _ = run_simulation(simple_config)
        assert metrics.bundles_completed == 10  # 10 units, bundle size 1


class TestProcessingTime:
    """Tests for processing time calculation."""

    def test_grade_penalty(self, simple_config):
        """Lower grade should increase processing time."""
        # Modify to 50% grade
        simple_config.operations[0].grade_pct = 50

        simulator = ProductionLineSimulator(simple_config)
        process_time = simulator._calculate_process_time(simple_config.operations[0])

        # Grade penalty = (100-50)/100 = 0.5
        # Expected: 1.0 * (1 + 0 + 0 + 0.5) = 1.5
        assert process_time == pytest.approx(1.5, rel=0.01)

    def test_fpd_addition(self, simple_config):
        """FPD should add to processing time."""
        simple_config.operations[0].fpd_pct = 20

        simulator = ProductionLineSimulator(simple_config)
        process_time = simulator._calculate_process_time(simple_config.operations[0])

        # FPD = 20/100 = 0.2
        # Expected: 1.0 * (1 + 0 + 0.2 + 0) = 1.2
        assert process_time == pytest.approx(1.2, rel=0.01)


class TestBundleTransition:
    """Tests for bundle transition times."""

    def test_small_bundle_transition(self, simple_config):
        """Bundle ≤5 should have 1 second transition."""
        simulator = ProductionLineSimulator(simple_config)
        transition = simulator._get_bundle_transition_time(5)
        assert transition == pytest.approx(1/60, rel=0.01)  # 1 second in minutes

    def test_large_bundle_transition(self, simple_config):
        """Bundle >5 should have 5 second transition."""
        simulator = ProductionLineSimulator(simple_config)
        transition = simulator._get_bundle_transition_time(10)
        assert transition == pytest.approx(5/60, rel=0.01)  # 5 seconds in minutes
```

### 5.2 Frontend Test Cases

```javascript
// tests/unit/simulationV2Store.spec.js

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSimulationV2Store } from '@/stores/simulationV2Store'

describe('SimulationV2Store', () => {
  let store

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useSimulationV2Store()
  })

  describe('initial state', () => {
    it('has empty operations', () => {
      expect(store.operations).toEqual([])
    })

    it('has default schedule', () => {
      expect(store.schedule.shifts_enabled).toBe(1)
      expect(store.schedule.shift1_hours).toBe(8)
    })

    it('is in input step', () => {
      expect(store.currentStep).toBe('input')
    })
  })

  describe('computed properties', () => {
    it('canValidate is false when no data', () => {
      expect(store.canValidate).toBe(false)
    })

    it('canValidate is true with operations and demands', () => {
      store.operations = [{ product: 'A', step: 1 }]
      store.demands = [{ product: 'A', daily_demand: 100 }]
      expect(store.canValidate).toBe(true)
    })

    it('productsInOperations extracts unique products', () => {
      store.operations = [
        { product: 'A', step: 1 },
        { product: 'A', step: 2 },
        { product: 'B', step: 1 }
      ]
      expect(store.productsInOperations).toEqual(['A', 'B'])
    })
  })

  describe('importOperations', () => {
    it('parses CSV-style data correctly', () => {
      const csvData = [
        { Product: 'SHIRT', Step: '1', Operation: 'Cut', Machine_Tool: 'Cutter', SAM_min: '2.5' }
      ]
      store.importOperations(csvData)

      expect(store.operations.length).toBe(1)
      expect(store.operations[0].product).toBe('SHIRT')
      expect(store.operations[0].step).toBe(1)
      expect(store.operations[0].sam_min).toBe(2.5)
      expect(store.operations[0].grade_pct).toBe(85) // Default
    })

    it('clears validation when importing', () => {
      store.validationReport = { is_valid: true }
      store.importOperations([])
      expect(store.validationReport).toBeNull()
    })
  })

  describe('reset', () => {
    it('clears all state', () => {
      store.operations = [{ product: 'A' }]
      store.results = { some: 'data' }
      store.currentStep = 'results'

      store.reset()

      expect(store.operations).toEqual([])
      expect(store.results).toBeNull()
      expect(store.currentStep).toBe('input')
    })
  })

  describe('buildConfig', () => {
    it('builds correct config structure', () => {
      store.operations = [{ product: 'A', step: 1 }]
      store.demands = [{ product: 'A', daily_demand: 100 }]
      store.mode = 'demand-driven'

      const config = store.buildConfig()

      expect(config.operations).toEqual(store.operations)
      expect(config.demands).toEqual(store.demands)
      expect(config.mode).toBe('demand-driven')
      expect(config.breakdowns).toBeNull()
    })
  })
})
```

---

## 6. Migration Strategy

### 6.1 Parallel Deployment Timeline

```
Week 1-2: Development
├── Backend: simulation_v2 module complete
├── Frontend: SimulationV2View.vue complete
└── Tests: 80%+ coverage

Week 3: Integration Testing
├── Deploy to staging with v1 routes active
├── New v2 routes coexist
├── QA testing of both versions
└── Performance comparison

Week 4: Soft Launch
├── Feature flag: simulation_v2_enabled
├── Opt-in for power users
├── Collect feedback
└── Bug fixes

Week 5: General Availability
├── Navigation updated to v2 as default
├── v1 routes marked deprecated
├── Documentation updated
└── Training materials published

Week 6+: Deprecation
├── v1 routes return deprecation warnings
├── Monitor v1 usage
├── Remove v1 after 30 days of zero usage
```

### 6.2 Code Changes for Migration

#### `backend/main.py` - Add v2 Router

```python
# Add import
from backend.routes import simulation_v2

# Add router (after existing simulation router)
app.include_router(simulation_v2.router)
```

#### `frontend/src/router/index.js` - Add v2 Route

```javascript
// Add route
{
  path: '/simulation-v2',
  name: 'simulation-v2',
  component: () => import('@/views/SimulationV2View.vue'),
  meta: { requiresAuth: true, roles: ['admin', 'poweruser', 'leader'] }
}
```

#### Navigation Update (After GA)

```javascript
// In navigation config, replace:
{ title: 'Simulation', to: '/simulation' }
// With:
{ title: 'Line Simulation', to: '/simulation-v2' }
```

### 6.3 Deprecation Headers for v1

```python
# In routes/simulation.py, add to all endpoints:
@router.post("/capacity-requirements")
async def calculate_capacity_requirements_endpoint(...):
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-03-15"
    response.headers["Link"] = "</api/v2/simulation/run>; rel=\"successor-version\""
    # ... existing logic
```

---

## 7. Dependencies to Add

### 7.1 Backend

No new dependencies required - SimPy 4.1.1 already installed.

### 7.2 Frontend

```bash
# Add xlsx for client-side Excel generation
npm install xlsx
```

#### Update `vite.config.js`

```javascript
// In manualChunks function, add:
if (id.includes('xlsx')) {
  return 'vendor-xlsx'
}

// In optimizeDeps.include, add:
'xlsx'
```

#### Update `package.json` (reference)

```json
{
  "dependencies": {
    "xlsx": "^0.18.5"
  }
}
```

---

## 8. Acceptance Criteria

### 8.1 Phase 1 Completion Criteria

- [ ] Backend `/api/v2/simulation/run` endpoint returns valid JSON
- [ ] SimPy engine processes single product with deterministic times
- [ ] Output blocks 1, 2, 3, 6, 8 are populated correctly
- [ ] Frontend displays results in tabular format
- [ ] CSV import for operations works
- [ ] Basic validation catches missing required fields

### 8.2 Phase 2 Completion Criteria

- [ ] Triangular variability produces realistic distributions
- [ ] All validation rules from spec implemented
- [ ] Validation report displays errors and warnings
- [ ] Users cannot run simulation with errors
- [ ] Users can proceed with warnings acknowledged

### 8.3 Phase 3 Completion Criteria

- [ ] Rework logic correctly separates pieces
- [ ] Breakdowns create station delays
- [ ] All 8 output blocks complete and accurate
- [ ] Excel export includes all sheets
- [ ] Results dashboard uses tabs/sections effectively

### 8.4 Phase 4 Completion Criteria

- [ ] Role-based access control enforced
- [ ] Feature deployed to production
- [ ] Existing simulation routes marked deprecated
- [ ] User documentation complete
- [ ] Training video created

---

## 9. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| SimPy performance on large configs | Implement max operations limit (50); add progress indicators |
| Browser memory with large exports | Chunk data; test with 5 products × 50 operations |
| Users expect DB integration | Prominent messaging; FAQ in help section |
| Existing simulation users confused | Parallel deployment; training materials |
| Excel formatting issues | Test across Excel versions; fallback to CSV |

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Simulation completion rate | >95% | API success responses / total requests |
| Average simulation time | <15 seconds | Backend timing logs |
| Export success rate | >99% | Frontend error tracking |
| User adoption (Week 1) | 20+ unique users | Analytics |
| User retention (Week 4) | 50%+ return usage | Analytics |
| Support tickets | <5 per week | Helpdesk tracking |

---

*Document Version: 1.0*
*Last Updated: February 1, 2026*
*Author: Claude Code Implementation Planning*
