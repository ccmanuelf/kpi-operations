"""
Capacity Planning Schema Models
Phase B.1: Database schema for capacity planning module with 12 new tables

Tables:
- capacity_calendar: Working days, shifts, holidays
- capacity_production_lines: Line capacity specifications
- capacity_orders: Planning orders (separate from Work Orders)
- capacity_production_standards: SAM per operation per style
- capacity_bom_header: Bill of Materials headers
- capacity_bom_detail: Bill of Materials components
- capacity_stock_snapshot: Weekly inventory positions
- capacity_component_check: MRP explosion results
- capacity_analysis: Utilization calculations per line/week
- capacity_schedule: Production schedule headers
- capacity_schedule_detail: Production schedule line items
- capacity_scenario: What-if scenario configurations
- capacity_kpi_commitment: KPI targets and actuals tracking
"""
from backend.schemas.capacity.calendar import CapacityCalendar
from backend.schemas.capacity.production_lines import CapacityProductionLine
from backend.schemas.capacity.orders import CapacityOrder, OrderPriority, OrderStatus
from backend.schemas.capacity.standards import CapacityProductionStandard
from backend.schemas.capacity.bom import CapacityBOMHeader, CapacityBOMDetail
from backend.schemas.capacity.stock import CapacityStockSnapshot
from backend.schemas.capacity.component_check import CapacityComponentCheck, ComponentStatus
from backend.schemas.capacity.analysis import CapacityAnalysis
from backend.schemas.capacity.schedule import CapacitySchedule, CapacityScheduleDetail, ScheduleStatus
from backend.schemas.capacity.scenario import CapacityScenario
from backend.schemas.capacity.kpi_commitment import CapacityKPICommitment

__all__ = [
    # Calendar
    "CapacityCalendar",
    # Production Lines
    "CapacityProductionLine",
    # Orders
    "CapacityOrder",
    "OrderPriority",
    "OrderStatus",
    # Standards
    "CapacityProductionStandard",
    # BOM
    "CapacityBOMHeader",
    "CapacityBOMDetail",
    # Stock
    "CapacityStockSnapshot",
    # Component Check
    "CapacityComponentCheck",
    "ComponentStatus",
    # Analysis
    "CapacityAnalysis",
    # Schedule
    "CapacitySchedule",
    "CapacityScheduleDetail",
    "ScheduleStatus",
    # Scenario
    "CapacityScenario",
    # KPI Commitment
    "CapacityKPICommitment",
]
