"""
Capacity Planning Service
Phase B.2: Backend Services for Capacity Planning

Main orchestration service that coordinates all capacity planning operations.
Provides unified interface for:
- BOM explosion
- Component checking (MRP)
- Capacity analysis
- Scheduling
- What-if scenarios
- KPI integration
"""

from decimal import Decimal
from typing import List, Dict, Optional, Any
from datetime import date
from sqlalchemy.orm import Session
from fastapi import Depends

from backend.database import get_db
from backend.services.capacity.bom_service import BOMService, BOMExplosionResult
from backend.services.capacity.mrp_service import MRPService, MRPRunResult
from backend.services.capacity.analysis_service import (
    CapacityAnalysisService,
    CapacityAnalysisResult,
    LineCapacityResult,
)
from backend.services.capacity.scheduling_service import SchedulingService, GeneratedSchedule, ScheduleSummary
from backend.services.capacity.scenario_service import ScenarioService, ScenarioResult, ScenarioComparison
from backend.services.capacity.kpi_integration_service import KPIIntegrationService, KPIActual, KPIVariance
from backend.schemas.capacity.schedule import CapacitySchedule, ScheduleStatus
from backend.schemas.capacity.scenario import CapacityScenario


class CapacityPlanningService:
    """
    Main service for capacity planning operations.

    Provides unified interface that coordinates:
    - BOMService: BOM explosion
    - MRPService: Component availability checking
    - CapacityAnalysisService: 12-step capacity calculation
    - SchedulingService: Schedule generation and management
    - ScenarioService: What-if analysis
    - KPIIntegrationService: KPI tracking and variance

    Multi-tenant isolation via client_id on all operations.
    """

    def __init__(self, db: Session):
        """
        Initialize capacity planning service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.bom_service = BOMService(db)
        self.mrp_service = MRPService(db)
        self.analysis_service = CapacityAnalysisService(db)
        self.scheduling_service = SchedulingService(db)
        self.scenario_service = ScenarioService(db)
        self.kpi_service = KPIIntegrationService(db)

    # =========================================================================
    # BOM Operations
    # =========================================================================

    def explode_bom(self, client_id: str, parent_item_code: str, quantity: Decimal) -> BOMExplosionResult:
        """
        Explode a BOM to get required components.

        Args:
            client_id: Client ID for tenant isolation
            parent_item_code: Parent item to explode
            quantity: Quantity of parent being produced

        Returns:
            BOMExplosionResult with all components
        """
        return self.bom_service.explode_bom(client_id, parent_item_code, quantity)

    def get_bom_structure(self, client_id: str, parent_item_code: str) -> Optional[Dict]:
        """Get BOM structure without explosion."""
        return self.bom_service.get_bom_structure(client_id, parent_item_code)

    # =========================================================================
    # MRP / Component Check Operations
    # =========================================================================

    def run_component_check(self, client_id: str, order_ids: Optional[List[int]] = None) -> MRPRunResult:
        """
        Run component availability check (Mini-MRP).

        Args:
            client_id: Client ID for tenant isolation
            order_ids: Optional list of specific order IDs to check

        Returns:
            MRPRunResult with component statuses
        """
        return self.mrp_service.run_component_check(client_id, order_ids)

    def get_shortages_by_order(self, client_id: str, order_number: str) -> List:
        """Get component shortages for a specific order."""
        return self.mrp_service.get_shortages_by_order(client_id, order_number)

    # =========================================================================
    # Capacity Analysis Operations
    # =========================================================================

    def analyze_capacity(
        self,
        client_id: str,
        period_start: date,
        period_end: date,
        line_ids: Optional[List[int]] = None,
        schedule_id: Optional[int] = None,
    ) -> CapacityAnalysisResult:
        """
        Run capacity analysis for specified period.

        Implements the 12-step capacity calculation methodology.

        Args:
            client_id: Client ID for tenant isolation
            period_start: Start date of analysis period
            period_end: End date of analysis period
            line_ids: Optional list of specific line IDs to analyze
            schedule_id: Optional schedule ID to get demand from

        Returns:
            CapacityAnalysisResult with all line analyses
        """
        return self.analysis_service.analyze_capacity(client_id, period_start, period_end, line_ids, schedule_id)

    def get_line_capacity(
        self, client_id: str, line_id: int, period_start: date, period_end: date
    ) -> Optional[LineCapacityResult]:
        """Get capacity for a single line."""
        return self.analysis_service.get_line_capacity(client_id, line_id, period_start, period_end)

    def identify_bottlenecks(
        self, client_id: str, period_start: date, period_end: date, threshold: Optional[Decimal] = None
    ) -> List[LineCapacityResult]:
        """Identify bottleneck lines for a period."""
        return self.analysis_service.identify_bottlenecks(client_id, period_start, period_end, threshold)

    # =========================================================================
    # Scheduling Operations
    # =========================================================================

    def generate_schedule(
        self,
        client_id: str,
        schedule_name: str,
        period_start: date,
        period_end: date,
        order_ids: Optional[List[int]] = None,
        line_ids: Optional[List[int]] = None,
        prioritize_by: str = "required_date",
    ) -> GeneratedSchedule:
        """
        Auto-generate schedule based on orders and capacity.

        Args:
            client_id: Client ID for tenant isolation
            schedule_name: Name for the schedule
            period_start: Start date of schedule period
            period_end: End date of schedule period
            order_ids: Optional list of specific order IDs to schedule
            line_ids: Optional list of specific line IDs to use
            prioritize_by: "required_date" or "priority"

        Returns:
            GeneratedSchedule with scheduled items
        """
        return self.scheduling_service.generate_schedule(
            client_id, schedule_name, period_start, period_end, order_ids, line_ids, prioritize_by
        )

    def create_schedule(
        self, client_id: str, schedule_name: str, period_start: date, period_end: date, items: List[Dict]
    ) -> CapacitySchedule:
        """Create a new schedule with specified items."""
        return self.scheduling_service.create_schedule(client_id, schedule_name, period_start, period_end, items)

    def commit_schedule(
        self, client_id: str, schedule_id: int, committed_by: int, kpi_commitments: Optional[Dict] = None
    ) -> CapacitySchedule:
        """
        Commit a schedule for KPI tracking.

        Args:
            client_id: Client ID for tenant isolation
            schedule_id: Schedule ID to commit
            committed_by: User ID committing the schedule
            kpi_commitments: Optional KPI targets to commit

        Returns:
            Updated CapacitySchedule
        """
        schedule = self.scheduling_service.commit_schedule(client_id, schedule_id, committed_by, kpi_commitments)

        # Store KPI commitments if provided
        if kpi_commitments:
            self.kpi_service.store_kpi_commitments(
                client_id, schedule_id, {k: Decimal(str(v)) for k, v in kpi_commitments.items()}
            )

        return schedule

    def get_schedule_summary(self, client_id: str, schedule_id: int) -> Optional[ScheduleSummary]:
        """Get summary of a schedule."""
        return self.scheduling_service.get_schedule_summary(client_id, schedule_id)

    def list_schedules(
        self,
        client_id: str,
        status: Optional[ScheduleStatus] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
    ) -> List[CapacitySchedule]:
        """List schedules with optional filters."""
        return self.scheduling_service.list_schedules(client_id, status, period_start, period_end)

    # =========================================================================
    # Scenario Operations
    # =========================================================================

    def create_scenario(
        self,
        client_id: str,
        scenario_name: str,
        scenario_type: str,
        base_schedule_id: Optional[int] = None,
        parameters: Optional[Dict] = None,
        notes: Optional[str] = None,
    ) -> CapacityScenario:
        """
        Create a new what-if scenario.

        Args:
            client_id: Client ID for tenant isolation
            scenario_name: Name for the scenario
            scenario_type: Type (OVERTIME, SHIFT_ADD, EFFICIENCY_IMPROVEMENT, etc.)
            base_schedule_id: Optional base schedule to modify
            parameters: Scenario parameters
            notes: Optional notes

        Returns:
            Created CapacityScenario
        """
        return self.scenario_service.create_scenario(
            client_id, scenario_name, scenario_type, base_schedule_id, parameters, notes
        )

    def analyze_scenario(
        self, client_id: str, scenario_id: int, period_start: date, period_end: date
    ) -> ScenarioResult:
        """Apply scenario parameters and analyze impact."""
        return self.scenario_service.apply_scenario_parameters(client_id, scenario_id, period_start, period_end)

    def compare_scenarios(
        self, client_id: str, scenario_ids: List[int], period_start: date, period_end: date
    ) -> List[ScenarioComparison]:
        """Compare multiple scenarios."""
        return self.scenario_service.compare_scenarios(client_id, scenario_ids, period_start, period_end)

    def list_scenarios(
        self,
        client_id: str,
        scenario_type: Optional[str] = None,
        base_schedule_id: Optional[int] = None,
        active_only: bool = True,
    ) -> List[CapacityScenario]:
        """List scenarios with optional filters."""
        return self.scenario_service.list_scenarios(client_id, scenario_type, base_schedule_id, active_only)

    # =========================================================================
    # KPI Operations
    # =========================================================================

    def get_actual_kpis(
        self, client_id: str, period_start: date, period_end: date, kpi_keys: Optional[List[str]] = None
    ) -> List[KPIActual]:
        """
        Get actual KPI values from production data.

        Args:
            client_id: Client ID for tenant isolation
            period_start: Start date of period
            period_end: End date of period
            kpi_keys: Optional list of specific KPIs to retrieve

        Returns:
            List of KPIActual values
        """
        return self.kpi_service.get_actual_kpis(client_id, period_start, period_end, kpi_keys)

    def calculate_kpi_variance(self, client_id: str, schedule_id: int) -> List[KPIVariance]:
        """
        Calculate variance between committed and actual KPIs.

        Args:
            client_id: Client ID for tenant isolation
            schedule_id: Schedule ID

        Returns:
            List of KPIVariance
        """
        return self.kpi_service.calculate_variance(client_id, schedule_id)

    def check_kpi_alerts(
        self, client_id: str, schedule_id: int, threshold: Optional[Decimal] = None
    ) -> List[KPIVariance]:
        """Check for KPI variance alerts."""
        return self.kpi_service.check_variance_alerts(client_id, schedule_id, threshold)

    def get_kpi_history(
        self, client_id: str, kpi_key: str, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[Dict]:
        """Get historical KPI values over time."""
        return self.kpi_service.get_kpi_history(client_id, kpi_key, start_date, end_date)

    # =========================================================================
    # Dashboard / Summary Operations
    # =========================================================================

    def get_planning_dashboard(self, client_id: str, period_start: date, period_end: date) -> Dict[str, Any]:
        """
        Get comprehensive planning dashboard data.

        Args:
            client_id: Client ID for tenant isolation
            period_start: Start date
            period_end: End date

        Returns:
            Dict with dashboard metrics
        """
        # Run capacity analysis
        analysis = self.analyze_capacity(client_id, period_start, period_end)

        # Run component check
        mrp_result = self.run_component_check(client_id)

        # Get active schedules
        schedules = self.list_schedules(
            client_id, status=ScheduleStatus.ACTIVE, period_start=period_start, period_end=period_end
        )

        # Get KPIs
        kpis = self.get_actual_kpis(client_id, period_start, period_end)

        return {
            "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
            "capacity": {
                "total_capacity_hours": float(analysis.total_capacity_hours),
                "total_demand_hours": float(analysis.total_demand_hours),
                "overall_utilization": float(analysis.overall_utilization),
                "bottleneck_count": analysis.bottleneck_count,
                "lines_analyzed": analysis.lines_analyzed,
            },
            "materials": {
                "components_checked": mrp_result.total_components_checked,
                "components_ok": mrp_result.components_ok,
                "components_short": mrp_result.components_short,
                "orders_affected": mrp_result.orders_affected,
            },
            "schedules": {
                "active_count": len(schedules),
                "schedules": [
                    {
                        "id": s.id,
                        "name": s.schedule_name,
                        "period_start": s.period_start.isoformat(),
                        "period_end": s.period_end.isoformat(),
                    }
                    for s in schedules
                ],
            },
            "kpis": [
                {"key": kpi.kpi_key, "name": kpi.kpi_name, "value": float(kpi.actual_value), "source": kpi.source}
                for kpi in kpis
            ],
        }


def get_capacity_planning_service(db: Session = Depends(get_db)) -> CapacityPlanningService:
    """
    FastAPI dependency to get CapacityPlanningService instance.

    Usage:
        @router.get("/capacity/analysis")
        def get_analysis(
            service: CapacityPlanningService = Depends(get_capacity_planning_service),
            current_user: User = Depends(get_current_user)
        ):
            return service.analyze_capacity(...)
    """
    return CapacityPlanningService(db)
