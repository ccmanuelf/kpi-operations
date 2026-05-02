"""
Production Line Simulation v2.0 Module

Ephemeral capacity planning and line behavior simulation for labor-intensive manufacturing.
This module operates completely stateless with no database dependencies.

Components:
- models: Pydantic schemas for input/output validation
- validation: Schema and domain validation logic
- engine: SimPy discrete-event simulation engine
- calculations: Output block calculations
- constants: Default values and thresholds
"""

from .models import (
    # Enums
    VariabilityType,
    DemandMode,
    ValidationSeverity,
    # Input models
    OperationInput,
    ScheduleConfig,
    DemandInput,
    BreakdownInput,
    SimulationConfig,
    # Validation models
    ValidationIssue,
    ValidationReport,
    # Output models
    WeeklyDemandCapacityRow,
    DailySummary,
    StationPerformanceRow,
    FreeCapacityAnalysis,
    BundleMetricsRow,
    PerProductSummaryRow,
    RebalancingSuggestionRow,
    AssumptionLog,
    SimulationResults,
    # API models
    SimulationRequest,
    SimulationResponse,
    MonteCarloRequest,
    MonteCarloResponse,
    MonteCarloStat,
)

from .validation import validate_simulation_config
from .engine import run_simulation, ProductionLineSimulator
from .calculations import calculate_all_blocks
from .monte_carlo import run_monte_carlo, aggregate_runs, compute_stat

__version__ = "2.0.0"
__all__ = [
    # Version
    "__version__",
    # Enums
    "VariabilityType",
    "DemandMode",
    "ValidationSeverity",
    # Input models
    "OperationInput",
    "ScheduleConfig",
    "DemandInput",
    "BreakdownInput",
    "SimulationConfig",
    # Validation
    "ValidationIssue",
    "ValidationReport",
    "validate_simulation_config",
    # Output models
    "WeeklyDemandCapacityRow",
    "DailySummary",
    "StationPerformanceRow",
    "FreeCapacityAnalysis",
    "BundleMetricsRow",
    "PerProductSummaryRow",
    "RebalancingSuggestionRow",
    "AssumptionLog",
    "SimulationResults",
    # API
    "SimulationRequest",
    "SimulationResponse",
    "MonteCarloRequest",
    "MonteCarloResponse",
    "MonteCarloStat",
    # Engine
    "run_simulation",
    "ProductionLineSimulator",
    "calculate_all_blocks",
    # Monte Carlo
    "run_monte_carlo",
    "aggregate_runs",
    "compute_stat",
]
