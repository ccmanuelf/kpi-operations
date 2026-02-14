"""
Scenario Service - Complete What-If Scenarios
Phase B.9: Complete What-If Scenarios for Capacity Planning

Provides what-if scenario analysis capabilities with 8 pre-configured scenarios:
1. Overtime +20%
2. Setup Time Reduction -30%
3. Subcontract Cutting 40%
4. New Sewing Line
5. 3-Shift Operation
6. Material Lead Time Delay
7. Absenteeism Spike 15%
8. Multi-Constraint Combined
"""

from decimal import Decimal
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.schemas.capacity.scenario import CapacityScenario
from backend.schemas.capacity.schedule import CapacitySchedule, ScheduleStatus
from backend.schemas.capacity.production_lines import CapacityProductionLine
from backend.schemas.capacity.analysis import CapacityAnalysis
from backend.services.capacity.analysis_service import CapacityAnalysisService, CapacityAnalysisResult
from backend.events.bus import event_bus
from backend.events.domain_events import CapacityScenarioCreated, CapacityScenarioCompared


# =============================================================================
# Scenario Type Enumeration
# =============================================================================


class ScenarioType(str, Enum):
    """Enumeration of pre-configured scenario types."""

    OVERTIME = "OVERTIME"
    SETUP_REDUCTION = "SETUP_REDUCTION"
    SUBCONTRACT = "SUBCONTRACT"
    NEW_LINE = "NEW_LINE"
    THREE_SHIFT = "THREE_SHIFT"
    LEAD_TIME_DELAY = "LEAD_TIME_DELAY"
    ABSENTEEISM_SPIKE = "ABSENTEEISM_SPIKE"
    MULTI_CONSTRAINT = "MULTI_CONSTRAINT"
    # Legacy types for backward compatibility
    SHIFT_ADD = "SHIFT_ADD"
    EFFICIENCY_IMPROVEMENT = "EFFICIENCY_IMPROVEMENT"
    LABOR_ADD = "LABOR_ADD"


# =============================================================================
# Default Parameters for Each Scenario Type
# =============================================================================

SCENARIO_DEFAULTS: Dict[ScenarioType, Dict[str, Any]] = {
    ScenarioType.OVERTIME: {
        "overtime_percent": 20,
        "affected_departments": ["SEWING", "FINISHING"],
        "affected_lines": [],  # Empty means all lines
        "overtime_days": ["MON", "TUE", "WED", "THU", "FRI"],
        "cost_per_hour": Decimal("15.00"),
        "description": "Add 20% overtime to increase capacity",
    },
    ScenarioType.SETUP_REDUCTION: {
        "reduction_percent": 30,
        "affected_operations": ["all"],
        "setup_time_portion": Decimal("0.10"),  # Assume 10% of time is setup
        "investment_required": Decimal("5000.00"),
        "description": "Reduce setup times by 30% through process improvement",
    },
    ScenarioType.SUBCONTRACT: {
        "subcontract_percent": 40,
        "department": "CUTTING",
        "cost_per_unit": Decimal("2.50"),
        "lead_time_days": 5,
        "quality_factor": Decimal("0.95"),
        "description": "Subcontract 40% of cutting operations",
    },
    ScenarioType.NEW_LINE: {
        "new_line_code": "SEWING_NEW",
        "department": "SEWING",
        "capacity_units_per_hour": 50,
        "operators": 12,
        "hours_per_shift": Decimal("8.0"),
        "shifts_per_day": 1,
        "efficiency": Decimal("0.75"),
        "ramp_up_weeks": 4,
        "investment_cost": Decimal("50000.00"),
        "description": "Add new sewing line with 12 operators",
    },
    ScenarioType.THREE_SHIFT: {
        "shifts_enabled": 3,
        "shift1_hours": Decimal("8.0"),
        "shift2_hours": Decimal("8.0"),
        "shift3_hours": Decimal("8.0"),
        "shift3_efficiency": Decimal("0.80"),  # Night shift typically less efficient
        "affected_lines": ["all"],
        "additional_supervision_cost": Decimal("2000.00"),
        "description": "Enable 3-shift operation across all lines",
    },
    ScenarioType.LEAD_TIME_DELAY: {
        "delay_days": 7,
        "affected_components": ["FABRIC"],
        "demand_pile_factor": Decimal("1.15"),  # Demand piles up during delay
        "expedite_cost_per_day": Decimal("500.00"),
        "description": "Simulate 7-day material lead time delay",
    },
    ScenarioType.ABSENTEEISM_SPIKE: {
        "absenteeism_percent": 15,
        "duration_days": 5,
        "affected_departments": ["all"],
        "overtime_to_compensate": True,
        "temp_labor_cost_per_day": Decimal("800.00"),
        "description": "Simulate 15% absenteeism spike for 5 days",
    },
    ScenarioType.MULTI_CONSTRAINT: {
        "overtime_percent": 10,
        "setup_reduction_percent": 15,
        "absenteeism_percent": 8,
        "new_operators": 5,
        "efficiency_improvement_percent": 5,
        "description": "Combined scenario with multiple factors",
    },
    # Legacy types
    ScenarioType.SHIFT_ADD: {"hours": 8, "affected_lines": [], "description": "Add additional shift hours"},
    ScenarioType.EFFICIENCY_IMPROVEMENT: {
        "target_efficiency": 90,
        "current_efficiency": 85,
        "description": "Improve efficiency factor",
    },
    ScenarioType.LABOR_ADD: {
        "operators": 5,
        "affected_lines": [],
        "cost_per_operator": 150,
        "description": "Add additional operators",
    },
}


# =============================================================================
# Data Classes for Results
# =============================================================================


@dataclass
class ScenarioComparison:
    """Comparison result between scenarios."""

    scenario_id: int
    scenario_name: str
    scenario_type: Optional[str]
    original_capacity_hours: Decimal
    modified_capacity_hours: Decimal
    capacity_increase_percent: Decimal
    original_utilization: Decimal
    modified_utilization: Decimal
    bottlenecks_resolved: int
    cost_impact: Decimal
    notes: Optional[str]


@dataclass
class ScenarioResult:
    """Result of scenario analysis."""

    scenario_id: int
    scenario_name: str
    original_metrics: Dict[str, Any]
    modified_metrics: Dict[str, Any]
    impact_summary: Dict[str, Any]


@dataclass
class DetailedScenarioResult:
    """Detailed result of scenario analysis with full breakdown."""

    scenario_id: int
    scenario_name: str
    scenario_type: str

    # Capacity impact
    original_capacity_hours: Decimal
    adjusted_capacity_hours: Decimal
    capacity_change_percent: Decimal

    # Utilization impact
    original_utilization: Decimal
    adjusted_utilization: Decimal

    # Bottleneck changes
    original_bottlenecks: List[str] = field(default_factory=list)
    adjusted_bottlenecks: List[str] = field(default_factory=list)

    # Cost/benefit
    estimated_cost_impact: Optional[Decimal] = None
    estimated_output_change: Optional[int] = None
    roi_estimate: Optional[Decimal] = None

    # Details
    parameters_applied: Dict[str, Any] = field(default_factory=dict)
    affected_lines: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ScenarioService:
    """
    Service for what-if scenario analysis.

    Supports 8 pre-configured scenario types:
    1. OVERTIME: Add 20% overtime to increase capacity
    2. SETUP_REDUCTION: Reduce setup times by 30%
    3. SUBCONTRACT: Subcontract 40% of cutting operations
    4. NEW_LINE: Add new sewing line with 12 operators
    5. THREE_SHIFT: Enable 3-shift operation
    6. LEAD_TIME_DELAY: Simulate material delay
    7. ABSENTEEISM_SPIKE: Simulate 15% absenteeism spike
    8. MULTI_CONSTRAINT: Combined scenario with multiple factors

    Also supports legacy types:
    - SHIFT_ADD: Add additional shifts
    - EFFICIENCY_IMPROVEMENT: Improve efficiency factors
    - LABOR_ADD: Add operators/workers

    Multi-tenant isolation via client_id on all operations.
    """

    def __init__(self, db: Session):
        """
        Initialize scenario service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.analysis_service = CapacityAnalysisService(db)

    # =========================================================================
    # Scenario Type Management
    # =========================================================================

    def get_available_scenario_types(self) -> List[Dict[str, Any]]:
        """
        Get list of available pre-configured scenario types with defaults.

        Returns:
            List of scenario type definitions with default parameters
        """
        result = []
        for scenario_type in ScenarioType:
            defaults = SCENARIO_DEFAULTS.get(scenario_type, {})
            # Convert Decimals to floats for JSON serialization
            serializable_defaults = self._serialize_params(defaults)
            result.append(
                {
                    "type": scenario_type.value,
                    "name": scenario_type.name.replace("_", " ").title(),
                    "description": defaults.get("description", ""),
                    "default_parameters": serializable_defaults,
                }
            )
        return result

    def get_scenario_type_defaults(self, scenario_type: Union[ScenarioType, str]) -> Dict[str, Any]:
        """
        Get default parameters for a scenario type.

        Args:
            scenario_type: ScenarioType enum or string

        Returns:
            Default parameters dictionary
        """
        if isinstance(scenario_type, str):
            try:
                scenario_type = ScenarioType(scenario_type)
            except ValueError:
                return {}
        return SCENARIO_DEFAULTS.get(scenario_type, {}).copy()

    # =========================================================================
    # Scenario CRUD Operations
    # =========================================================================

    def create_scenario(
        self,
        client_id: str,
        scenario_name: str,
        scenario_type: Union[ScenarioType, str],
        base_schedule_id: Optional[int] = None,
        parameters: Optional[Dict] = None,
        notes: Optional[str] = None,
    ) -> CapacityScenario:
        """
        Create a new what-if scenario.

        Uses default parameters for the scenario type, merged with custom parameters.

        Args:
            client_id: Client ID for tenant isolation
            scenario_name: Name for the scenario
            scenario_type: Type of scenario (ScenarioType enum or string)
            base_schedule_id: Optional base schedule to modify
            parameters: Custom parameters (merged with defaults)
            notes: Optional notes

        Returns:
            Created CapacityScenario
        """
        # Normalize scenario type to string
        type_str = scenario_type.value if isinstance(scenario_type, ScenarioType) else scenario_type

        # Get default parameters for type
        default_params = self.get_scenario_type_defaults(type_str)

        # Merge with custom parameters (custom takes precedence)
        merged_params = {**default_params}
        if parameters:
            merged_params.update(parameters)

        # Serialize for storage
        serializable_params = self._serialize_params(merged_params)

        scenario = CapacityScenario(
            client_id=client_id,
            scenario_name=scenario_name,
            scenario_type=type_str,
            base_schedule_id=base_schedule_id,
            parameters_json=serializable_params,
            notes=notes,
            is_active=True,
        )
        self.db.add(scenario)
        self.db.flush()

        # Emit event
        event = CapacityScenarioCreated(
            aggregate_id=f"scenario_{scenario.id}",
            client_id=client_id,
            scenario_id=scenario.id,
            scenario_name=scenario_name,
            base_schedule_id=base_schedule_id,
            scenario_type=type_str,
        )
        event_bus.collect(event)

        self.db.commit()
        return scenario

    def create_preconfigured_scenario(
        self,
        client_id: str,
        scenario_type: ScenarioType,
        custom_name: Optional[str] = None,
        parameter_overrides: Optional[Dict] = None,
        base_schedule_id: Optional[int] = None,
    ) -> CapacityScenario:
        """
        Create a scenario from a pre-configured type with optional overrides.

        Args:
            client_id: Client ID for tenant isolation
            scenario_type: Pre-configured scenario type
            custom_name: Optional custom name (defaults to type description)
            parameter_overrides: Optional parameters to override defaults
            base_schedule_id: Optional base schedule to modify

        Returns:
            Created CapacityScenario
        """
        defaults = SCENARIO_DEFAULTS.get(scenario_type, {})
        name = custom_name or defaults.get("description", scenario_type.value)

        return self.create_scenario(
            client_id=client_id,
            scenario_name=name,
            scenario_type=scenario_type,
            base_schedule_id=base_schedule_id,
            parameters=parameter_overrides,
        )

    def apply_scenario_parameters(
        self, client_id: str, scenario_id: int, period_start: date, period_end: date
    ) -> ScenarioResult:
        """
        Apply scenario parameters and analyze impact.

        Args:
            client_id: Client ID for tenant isolation
            scenario_id: Scenario ID to analyze
            period_start: Start date of analysis period
            period_end: End date of analysis period

        Returns:
            ScenarioResult with original and modified metrics
        """
        scenario = (
            self.db.query(CapacityScenario)
            .filter(CapacityScenario.client_id == client_id, CapacityScenario.id == scenario_id)
            .first()
        )

        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")

        # Get original capacity analysis
        original_analysis = self.analysis_service.analyze_capacity(
            client_id=client_id, period_start=period_start, period_end=period_end, schedule_id=scenario.base_schedule_id
        )

        original_metrics = {
            "total_capacity_hours": float(original_analysis.total_capacity_hours),
            "total_demand_hours": float(original_analysis.total_demand_hours),
            "overall_utilization": float(original_analysis.overall_utilization),
            "bottleneck_count": original_analysis.bottleneck_count,
            "lines": [
                {
                    "line_id": l.line_id,
                    "line_code": l.line_code,
                    "department": l.department,
                    "capacity_hours": float(l.capacity_hours),
                    "demand_hours": float(l.demand_hours),
                    "utilization_percent": float(l.utilization_percent),
                    "is_bottleneck": l.is_bottleneck,
                }
                for l in original_analysis.lines
            ],
        }

        # Apply scenario modifications using the enhanced handler
        modified_metrics = self._apply_scenario_type(
            scenario=scenario, original_metrics=original_metrics, period_start=period_start, period_end=period_end
        )

        # Calculate impact
        impact_summary = self._calculate_impact(original_metrics, modified_metrics, scenario)

        # Store results
        scenario.results_json = {
            "original_capacity_hours": original_metrics["total_capacity_hours"],
            "new_capacity_hours": modified_metrics["total_capacity_hours"],
            "capacity_increase_percent": impact_summary["capacity_increase_percent"],
            "cost_impact": impact_summary.get("cost_impact", 0),
            "utilization_before": original_metrics["overall_utilization"],
            "utilization_after": modified_metrics["overall_utilization"],
            "bottlenecks_resolved": impact_summary["bottlenecks_resolved"],
            "affected_lines": modified_metrics.get("affected_lines", []),
            "warnings": modified_metrics.get("warnings", []),
        }
        self.db.commit()

        return ScenarioResult(
            scenario_id=scenario.id,
            scenario_name=scenario.scenario_name,
            original_metrics=original_metrics,
            modified_metrics=modified_metrics,
            impact_summary=impact_summary,
        )

    def apply_scenario_detailed(
        self, client_id: str, scenario_id: int, period_start: date, period_end: date
    ) -> DetailedScenarioResult:
        """
        Apply scenario and return detailed results.

        Args:
            client_id: Client ID for tenant isolation
            scenario_id: Scenario ID to analyze
            period_start: Start date of analysis period
            period_end: End date of analysis period

        Returns:
            DetailedScenarioResult with full breakdown
        """
        result = self.apply_scenario_parameters(client_id, scenario_id, period_start, period_end)

        scenario = self.db.query(CapacityScenario).filter(CapacityScenario.id == scenario_id).first()

        # Extract bottleneck line codes
        original_bottlenecks = [
            l["line_code"] for l in result.original_metrics.get("lines", []) if l.get("is_bottleneck")
        ]
        adjusted_bottlenecks = [
            l["line_code"] for l in result.modified_metrics.get("lines", []) if l.get("is_bottleneck")
        ]

        # Calculate ROI if cost impact is available
        roi = None
        cost_impact = result.impact_summary.get("cost_impact", 0)
        capacity_added = result.impact_summary.get("capacity_hours_added", 0)
        if cost_impact > 0 and capacity_added > 0:
            # Simple ROI: hours gained per dollar spent
            roi = Decimal(str(capacity_added)) / Decimal(str(cost_impact))

        return DetailedScenarioResult(
            scenario_id=scenario.id,
            scenario_name=scenario.scenario_name,
            scenario_type=scenario.scenario_type,
            original_capacity_hours=Decimal(str(result.original_metrics["total_capacity_hours"])),
            adjusted_capacity_hours=Decimal(str(result.modified_metrics["total_capacity_hours"])),
            capacity_change_percent=Decimal(str(result.impact_summary["capacity_increase_percent"])),
            original_utilization=Decimal(str(result.original_metrics["overall_utilization"])),
            adjusted_utilization=Decimal(str(result.modified_metrics["overall_utilization"])),
            original_bottlenecks=original_bottlenecks,
            adjusted_bottlenecks=adjusted_bottlenecks,
            estimated_cost_impact=Decimal(str(cost_impact)) if cost_impact else None,
            estimated_output_change=int(capacity_added * 10) if capacity_added else None,  # Rough estimate
            roi_estimate=roi,
            parameters_applied=scenario.parameters_json or {},
            affected_lines=result.modified_metrics.get("affected_lines", []),
            warnings=result.modified_metrics.get("warnings", []),
        )

    def compare_scenarios(
        self, client_id: str, scenario_ids: List[int], period_start: date, period_end: date
    ) -> List[ScenarioComparison]:
        """
        Compare multiple scenarios.

        Args:
            client_id: Client ID for tenant isolation
            scenario_ids: List of scenario IDs to compare
            period_start: Start date of analysis period
            period_end: End date of analysis period

        Returns:
            List of ScenarioComparison for each scenario
        """
        comparisons: List[ScenarioComparison] = []

        # Get baseline analysis (no scenario)
        baseline = self.analysis_service.analyze_capacity(
            client_id=client_id, period_start=period_start, period_end=period_end
        )

        for scenario_id in scenario_ids:
            result = self.apply_scenario_parameters(
                client_id=client_id, scenario_id=scenario_id, period_start=period_start, period_end=period_end
            )

            scenario = self.db.query(CapacityScenario).filter(CapacityScenario.id == scenario_id).first()

            comparisons.append(
                ScenarioComparison(
                    scenario_id=scenario_id,
                    scenario_name=scenario.scenario_name,
                    scenario_type=scenario.scenario_type,
                    original_capacity_hours=Decimal(str(result.original_metrics["total_capacity_hours"])),
                    modified_capacity_hours=Decimal(str(result.modified_metrics["total_capacity_hours"])),
                    capacity_increase_percent=Decimal(str(result.impact_summary["capacity_increase_percent"])),
                    original_utilization=Decimal(str(result.original_metrics["overall_utilization"])),
                    modified_utilization=Decimal(str(result.modified_metrics["overall_utilization"])),
                    bottlenecks_resolved=result.impact_summary["bottlenecks_resolved"],
                    cost_impact=Decimal(str(result.impact_summary.get("cost_impact", 0))),
                    notes=scenario.notes,
                )
            )

        # Emit comparison event
        event = CapacityScenarioCompared(
            aggregate_id=f"comparison_{client_id}_{date.today()}",
            client_id=client_id,
            scenario_ids=scenario_ids,
            comparison_metrics={
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "scenarios_compared": len(scenario_ids),
                "best_capacity_increase": (
                    max(float(c.capacity_increase_percent) for c in comparisons) if comparisons else 0
                ),
            },
        )
        event_bus.collect(event)

        return comparisons

    def get_scenario_results(self, client_id: str, scenario_id: int) -> Optional[Dict]:
        """
        Get analysis results for a scenario.

        Args:
            client_id: Client ID for tenant isolation
            scenario_id: Scenario ID

        Returns:
            Results dict or None if not found/not analyzed
        """
        scenario = (
            self.db.query(CapacityScenario)
            .filter(CapacityScenario.client_id == client_id, CapacityScenario.id == scenario_id)
            .first()
        )

        if not scenario:
            return None

        return scenario.results_json

    def list_scenarios(
        self,
        client_id: str,
        scenario_type: Optional[str] = None,
        base_schedule_id: Optional[int] = None,
        active_only: bool = True,
    ) -> List[CapacityScenario]:
        """
        List scenarios with optional filters.

        Args:
            client_id: Client ID for tenant isolation
            scenario_type: Optional type filter
            base_schedule_id: Optional base schedule filter
            active_only: If True, only return active scenarios

        Returns:
            List of CapacityScenario
        """
        query = self.db.query(CapacityScenario).filter(CapacityScenario.client_id == client_id)

        if scenario_type:
            query = query.filter(CapacityScenario.scenario_type == scenario_type)
        if base_schedule_id:
            query = query.filter(CapacityScenario.base_schedule_id == base_schedule_id)
        if active_only:
            query = query.filter(CapacityScenario.is_active == True)

        return query.order_by(CapacityScenario.created_at.desc()).all()

    def _apply_scenario_type(
        self, scenario: CapacityScenario, original_metrics: Dict, period_start: date, period_end: date
    ) -> Dict:
        """
        Apply scenario type modifications to metrics.

        Dispatches to specific handlers for each of the 8 pre-configured scenarios.

        Args:
            scenario: The scenario to apply
            original_metrics: Original capacity metrics
            period_start: Start date
            period_end: End date

        Returns:
            Modified metrics dict
        """
        params = scenario.parameters_json or {}
        scenario_type = scenario.scenario_type

        modified = dict(original_metrics)
        modified_lines = [dict(l) for l in original_metrics.get("lines", [])]
        affected_lines_list = []
        warnings = []
        days_in_period = (period_end - period_start).days + 1

        # =====================================================================
        # Scenario Type: OVERTIME (+20%)
        # =====================================================================
        if scenario_type == ScenarioType.OVERTIME.value:
            overtime_percent = Decimal(str(params.get("overtime_percent", 20)))
            affected_departments = params.get("affected_departments", ["SEWING", "FINISHING"])
            affected_lines_param = params.get("affected_lines", [])

            for line in modified_lines:
                # Check if line should be affected
                dept_match = not affected_departments or line.get("department") in affected_departments
                line_match = not affected_lines_param or line["line_code"] in affected_lines_param

                if dept_match or line_match:
                    original_capacity = line["capacity_hours"]
                    line["capacity_hours"] = float(Decimal(str(original_capacity)) * (1 + overtime_percent / 100))
                    affected_lines_list.append(line["line_code"])

            modified["total_capacity_hours"] = sum(l["capacity_hours"] for l in modified_lines)
            modified["cost_estimate"] = float(
                Decimal(str(modified["total_capacity_hours"] - original_metrics["total_capacity_hours"]))
                * Decimal(str(params.get("cost_per_hour", 15)))
            )

        # =====================================================================
        # Scenario Type: SETUP_REDUCTION (-30%)
        # =====================================================================
        elif scenario_type == ScenarioType.SETUP_REDUCTION.value:
            reduction_percent = Decimal(str(params.get("reduction_percent", 30))) / 100
            setup_portion = Decimal(str(params.get("setup_time_portion", "0.10")))
            affected_ops = params.get("affected_operations", ["all"])

            # Reducing setup time frees up capacity
            capacity_gain_factor = setup_portion * reduction_percent

            for line in modified_lines:
                capacity_gain = float(Decimal(str(line["capacity_hours"])) * capacity_gain_factor)
                line["capacity_hours"] += capacity_gain
                affected_lines_list.append(line["line_code"])

            modified["total_capacity_hours"] = sum(l["capacity_hours"] for l in modified_lines)
            modified["cost_estimate"] = float(params.get("investment_required", 5000))

        # =====================================================================
        # Scenario Type: SUBCONTRACT (40% of department)
        # =====================================================================
        elif scenario_type == ScenarioType.SUBCONTRACT.value:
            subcontract_percent = Decimal(str(params.get("subcontract_percent", 40))) / 100
            target_department = params.get("department", "CUTTING")

            # Calculate demand reduction from subcontracting
            department_demand = Decimal("0")
            for line in modified_lines:
                if line.get("department") == target_department:
                    department_demand += Decimal(str(line.get("demand_hours", 0)))

            demand_reduction = department_demand * subcontract_percent

            # Reduce effective demand
            modified["total_demand_hours"] = float(
                Decimal(str(original_metrics["total_demand_hours"])) - demand_reduction
            )

            # Update line-level demand for the affected department
            for line in modified_lines:
                if line.get("department") == target_department:
                    line["demand_hours"] = float(Decimal(str(line.get("demand_hours", 0))) * (1 - subcontract_percent))
                    affected_lines_list.append(line["line_code"])

            # Calculate subcontracting cost
            cost_per_unit = Decimal(str(params.get("cost_per_unit", "2.50")))
            # Estimate units from demand hours (rough: 1 hour = 10 units)
            estimated_units = demand_reduction * 10
            modified["cost_estimate"] = float(estimated_units * cost_per_unit)

        # =====================================================================
        # Scenario Type: NEW_LINE (Add sewing line)
        # =====================================================================
        elif scenario_type == ScenarioType.NEW_LINE.value:
            new_line_code = params.get("new_line_code", "SEWING_NEW")
            operators = params.get("operators", 12)
            hours_per_shift = Decimal(str(params.get("hours_per_shift", "8.0")))
            shifts_per_day = params.get("shifts_per_day", 1)
            efficiency = Decimal(str(params.get("efficiency", "0.75")))

            # Calculate new line capacity
            # Gross hours = days * shifts * hours
            gross_hours = Decimal(str(days_in_period * shifts_per_day)) * hours_per_shift
            # Net hours = gross * efficiency * operators
            net_hours = gross_hours * efficiency * Decimal(str(operators))
            additional_hours = float(net_hours)

            # Add virtual new line to metrics
            new_line = {
                "line_id": -1,  # Virtual line
                "line_code": new_line_code,
                "department": params.get("department", "SEWING"),
                "capacity_hours": additional_hours,
                "demand_hours": 0,
                "utilization_percent": 0,
                "is_bottleneck": False,
            }
            modified_lines.append(new_line)
            affected_lines_list.append(new_line_code)

            modified["total_capacity_hours"] = sum(l["capacity_hours"] for l in modified_lines)
            modified["cost_estimate"] = float(params.get("investment_cost", 50000))

            # Add ramp-up warning
            ramp_up_weeks = params.get("ramp_up_weeks", 4)
            if ramp_up_weeks > 0:
                warnings.append(f"New line requires {ramp_up_weeks} weeks ramp-up to full efficiency")

        # =====================================================================
        # Scenario Type: THREE_SHIFT (Add 3rd shift)
        # =====================================================================
        elif scenario_type == ScenarioType.THREE_SHIFT.value:
            shifts_enabled = params.get("shifts_enabled", 3)
            shift3_hours = Decimal(str(params.get("shift3_hours", "8.0")))
            shift3_efficiency = Decimal(str(params.get("shift3_efficiency", "0.80")))
            affected_lines_param = params.get("affected_lines", ["all"])

            # Adding a 3rd shift increases capacity by ~50% (adjusted for night shift efficiency)
            # Assume currently 2 shifts, so adding 1 more = 50% increase before efficiency
            capacity_increase_factor = (shift3_hours / Decimal("16")) * shift3_efficiency

            for line in modified_lines:
                if affected_lines_param == ["all"] or line["line_code"] in affected_lines_param:
                    additional_capacity = float(Decimal(str(line["capacity_hours"])) * capacity_increase_factor)
                    line["capacity_hours"] += additional_capacity
                    affected_lines_list.append(line["line_code"])

            modified["total_capacity_hours"] = sum(l["capacity_hours"] for l in modified_lines)
            modified["cost_estimate"] = float(
                Decimal(str(params.get("additional_supervision_cost", 2000))) * days_in_period / 30
            )

        # =====================================================================
        # Scenario Type: LEAD_TIME_DELAY (Material delay)
        # =====================================================================
        elif scenario_type == ScenarioType.LEAD_TIME_DELAY.value:
            delay_days = params.get("delay_days", 7)
            demand_pile_factor = Decimal(str(params.get("demand_pile_factor", "1.15")))
            affected_components = params.get("affected_components", ["FABRIC"])

            # Material delay causes demand to pile up, increasing utilization
            # This is a negative scenario - utilization increases
            for line in modified_lines:
                line["demand_hours"] = float(Decimal(str(line.get("demand_hours", 0))) * demand_pile_factor)
                affected_lines_list.append(line["line_code"])

            modified["total_demand_hours"] = sum(l.get("demand_hours", 0) for l in modified_lines)

            # Calculate expediting cost
            expedite_cost = Decimal(str(params.get("expedite_cost_per_day", 500))) * delay_days
            modified["cost_estimate"] = float(expedite_cost)

            warnings.append(f"Material delay of {delay_days} days will create backlog")
            warnings.append(f"Affected components: {', '.join(affected_components)}")

        # =====================================================================
        # Scenario Type: ABSENTEEISM_SPIKE (15% spike)
        # =====================================================================
        elif scenario_type == ScenarioType.ABSENTEEISM_SPIKE.value:
            absenteeism_percent = Decimal(str(params.get("absenteeism_percent", 15))) / 100
            duration_days = params.get("duration_days", 5)
            affected_departments = params.get("affected_departments", ["all"])

            # Absenteeism reduces capacity
            capacity_reduction_factor = 1 - absenteeism_percent

            for line in modified_lines:
                if affected_departments == ["all"] or line.get("department") in affected_departments:
                    # Apply reduction proportionally to duration
                    period_impact = Decimal(str(duration_days)) / Decimal(str(days_in_period))
                    reduction_factor = 1 - (absenteeism_percent * period_impact)
                    line["capacity_hours"] = float(Decimal(str(line["capacity_hours"])) * reduction_factor)
                    affected_lines_list.append(line["line_code"])

            modified["total_capacity_hours"] = sum(l["capacity_hours"] for l in modified_lines)

            # Calculate temp labor cost if compensating
            if params.get("overtime_to_compensate", True):
                temp_labor_cost = Decimal(str(params.get("temp_labor_cost_per_day", 800))) * duration_days
                modified["cost_estimate"] = float(temp_labor_cost)
            else:
                modified["cost_estimate"] = 0

            warnings.append(f"Absenteeism spike of {int(absenteeism_percent * 100)}% for {duration_days} days")

        # =====================================================================
        # Scenario Type: MULTI_CONSTRAINT (Combined factors)
        # =====================================================================
        elif scenario_type == ScenarioType.MULTI_CONSTRAINT.value:
            # Apply multiple factors
            overtime_pct = Decimal(str(params.get("overtime_percent", 10))) / 100
            setup_reduction_pct = Decimal(str(params.get("setup_reduction_percent", 15))) / 100
            absenteeism_pct = Decimal(str(params.get("absenteeism_percent", 8))) / 100
            efficiency_improvement_pct = Decimal(str(params.get("efficiency_improvement_percent", 5))) / 100

            # Calculate net capacity factor
            # Overtime adds capacity
            overtime_factor = 1 + overtime_pct
            # Setup reduction adds capacity (setup is ~10% of time)
            setup_factor = 1 + (setup_reduction_pct * Decimal("0.1"))
            # Efficiency improvement adds capacity
            efficiency_factor = 1 + efficiency_improvement_pct
            # Absenteeism reduces capacity
            absenteeism_factor = 1 - absenteeism_pct

            net_factor = overtime_factor * setup_factor * efficiency_factor * absenteeism_factor

            for line in modified_lines:
                line["capacity_hours"] = float(Decimal(str(line["capacity_hours"])) * net_factor)
                affected_lines_list.append(line["line_code"])

            modified["total_capacity_hours"] = sum(l["capacity_hours"] for l in modified_lines)

            # Combined cost estimate
            modified["cost_estimate"] = 0  # Complex to calculate, would need more info

        # =====================================================================
        # Legacy Scenario Types (backward compatibility)
        # =====================================================================
        elif scenario_type == ScenarioType.SHIFT_ADD.value:
            shift_hours = Decimal(str(params.get("hours", 8)))
            affected_lines_param = params.get("affected_lines", [])

            for line in modified_lines:
                if not affected_lines_param or line["line_code"] in affected_lines_param:
                    additional_hours = float(shift_hours * days_in_period)
                    line["capacity_hours"] += additional_hours
                    affected_lines_list.append(line["line_code"])

            modified["total_capacity_hours"] = sum(l["capacity_hours"] for l in modified_lines)

        elif scenario_type == ScenarioType.EFFICIENCY_IMPROVEMENT.value:
            target_efficiency = Decimal(str(params.get("target_efficiency", 90))) / 100
            current_efficiency = Decimal(str(params.get("current_efficiency", 85))) / 100

            efficiency_multiplier = target_efficiency / current_efficiency

            for line in modified_lines:
                line["capacity_hours"] = float(Decimal(str(line["capacity_hours"])) * efficiency_multiplier)
                affected_lines_list.append(line["line_code"])

            modified["total_capacity_hours"] = sum(l["capacity_hours"] for l in modified_lines)

        elif scenario_type == ScenarioType.LABOR_ADD.value:
            additional_operators = params.get("operators", 5)
            affected_lines_param = params.get("affected_lines", [])

            for line in modified_lines:
                if not affected_lines_param or line["line_code"] in affected_lines_param:
                    # Assume ~10% capacity increase per additional operator (simplified)
                    increase_factor = 1 + (additional_operators * 0.02)
                    line["capacity_hours"] = float(Decimal(str(line["capacity_hours"])) * Decimal(str(increase_factor)))
                    affected_lines_list.append(line["line_code"])

            modified["total_capacity_hours"] = sum(l["capacity_hours"] for l in modified_lines)

        # =====================================================================
        # Recalculate Derived Metrics
        # =====================================================================
        total_capacity = modified["total_capacity_hours"]
        total_demand = modified["total_demand_hours"]

        if total_capacity > 0:
            modified["overall_utilization"] = (total_demand / total_capacity) * 100
        else:
            modified["overall_utilization"] = 0

        # Recalculate line-level utilization and bottlenecks
        for line in modified_lines:
            line_capacity = line["capacity_hours"]
            line_demand = line.get("demand_hours", 0)

            if line_capacity > 0:
                line["utilization_percent"] = (line_demand / line_capacity) * 100
            else:
                line["utilization_percent"] = 0

            line["is_bottleneck"] = line["utilization_percent"] >= 95

        modified["bottleneck_count"] = sum(1 for l in modified_lines if l["is_bottleneck"])
        modified["lines"] = modified_lines
        modified["affected_lines"] = list(set(affected_lines_list))
        modified["warnings"] = warnings

        return modified

    def _calculate_impact(self, original: Dict, modified: Dict, scenario: Optional[CapacityScenario] = None) -> Dict:
        """
        Calculate impact between original and modified metrics.

        Args:
            original: Original metrics
            modified: Modified metrics
            scenario: Optional scenario for cost calculation

        Returns:
            Impact summary dictionary
        """
        original_capacity = original["total_capacity_hours"]
        modified_capacity = modified["total_capacity_hours"]
        original_demand = original["total_demand_hours"]
        modified_demand = modified["total_demand_hours"]

        # Calculate capacity change
        capacity_increase = 0
        if original_capacity > 0:
            capacity_increase = ((modified_capacity - original_capacity) / original_capacity) * 100

        # Calculate demand change (for subcontracting scenarios)
        demand_change = 0
        if original_demand > 0:
            demand_change = ((modified_demand - original_demand) / original_demand) * 100

        # Bottleneck impact
        original_bottleneck_count = original.get("bottleneck_count", 0)
        modified_bottleneck_count = modified.get("bottleneck_count", 0)
        bottlenecks_resolved = max(0, original_bottleneck_count - modified_bottleneck_count)
        bottlenecks_added = max(0, modified_bottleneck_count - original_bottleneck_count)

        # Utilization change
        utilization_change = modified["overall_utilization"] - original["overall_utilization"]

        # Cost impact from scenario
        cost_impact = modified.get("cost_estimate", 0)

        # Calculate efficiency gain
        efficiency_gain = 0
        if original["overall_utilization"] > 0:
            efficiency_gain = (
                (original["overall_utilization"] - modified["overall_utilization"]) / original["overall_utilization"]
            ) * 100

        return {
            "capacity_increase_percent": capacity_increase,
            "capacity_hours_added": modified_capacity - original_capacity,
            "demand_change_percent": demand_change,
            "bottlenecks_resolved": bottlenecks_resolved,
            "bottlenecks_added": bottlenecks_added,
            "utilization_change": utilization_change,
            "efficiency_gain_percent": efficiency_gain,
            "cost_impact": cost_impact,
            "affected_lines_count": len(modified.get("affected_lines", [])),
            "warnings_count": len(modified.get("warnings", [])),
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _serialize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize parameters for JSON storage.

        Converts Decimal to float for JSON serialization.
        """
        result = {}
        for key, value in params.items():
            if isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, list):
                result[key] = [float(v) if isinstance(v, Decimal) else v for v in value]
            elif isinstance(value, dict):
                result[key] = self._serialize_params(value)
            else:
                result[key] = value
        return result

    def _get_current_capacity_summary(self, client_id: str) -> Dict[str, Any]:
        """
        Get current capacity summary for baseline.

        Args:
            client_id: Client ID for tenant isolation

        Returns:
            Summary with capacity, demand, utilization, and bottlenecks
        """
        # Get latest analysis results
        analyses = self.db.query(CapacityAnalysis).filter(CapacityAnalysis.client_id == client_id).all()

        if not analyses:
            # Return defaults if no analysis exists
            return {
                "total_capacity_hours": Decimal("1000"),
                "total_demand_hours": Decimal("800"),
                "avg_utilization": Decimal("80"),
                "bottleneck_lines": [],
            }

        total_capacity = sum(Decimal(str(a.capacity_hours or 0)) for a in analyses)
        total_demand = sum(Decimal(str(a.demand_hours or 0)) for a in analyses)
        avg_util = (total_demand / total_capacity * 100) if total_capacity > 0 else Decimal(0)
        bottlenecks = [a.line_code for a in analyses if a.is_bottleneck]

        return {
            "total_capacity_hours": total_capacity,
            "total_demand_hours": total_demand,
            "avg_utilization": avg_util,
            "bottleneck_lines": bottlenecks,
        }

    def _calc_change_percent(self, original: Decimal, adjusted: Decimal) -> Decimal:
        """Calculate percentage change between two values."""
        if original == 0:
            return Decimal("0")
        return ((adjusted - original) / original) * 100
