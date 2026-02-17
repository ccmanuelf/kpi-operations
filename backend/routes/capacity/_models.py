"""
Pydantic request/response models shared across capacity planning sub-modules.

These models were extracted from the monolithic capacity.py to be shared
by all sub-routers without duplication.
"""

from typing import List, Optional, Dict, Any
from datetime import date
from pydantic import BaseModel, Field

from backend.constants import DEFAULT_MAX_OPERATORS
from backend.schemas.capacity.orders import OrderPriority, OrderStatus
from backend.schemas.capacity.schedule import ScheduleStatus


# =============================================================================
# Generic Responses
# =============================================================================


class MessageResponse(BaseModel):
    """Standard response for delete and bulk operations."""

    message: str = Field(description="Human-readable result message")


class WorksheetSaveResponse(BaseModel):
    """Response for worksheet bulk-save operations."""

    message: str = Field(description="Human-readable result message")
    rows_processed: int = Field(description="Number of rows processed in the bulk save")


# =============================================================================
# Calendar Models
# =============================================================================


class CalendarEntryCreate(BaseModel):
    calendar_date: date = Field(description="Calendar date for this entry")
    is_working_day: bool = Field(default=True, description="Whether this date is a working day")
    shifts_available: int = Field(default=1, description="Number of shifts available (1-3)")
    shift1_hours: float = Field(default=8.0, description="Duration of first shift in hours")
    shift2_hours: float = Field(default=0, description="Duration of second shift in hours")
    shift3_hours: float = Field(default=0, description="Duration of third shift in hours")
    holiday_name: Optional[str] = Field(default=None, description="Holiday name if non-working day")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class CalendarEntryUpdate(BaseModel):
    is_working_day: Optional[bool] = Field(default=None, description="Whether this date is a working day")
    shifts_available: Optional[int] = Field(default=None, description="Number of shifts available (1-3)")
    shift1_hours: Optional[float] = Field(default=None, description="Duration of first shift in hours")
    shift2_hours: Optional[float] = Field(default=None, description="Duration of second shift in hours")
    shift3_hours: Optional[float] = Field(default=None, description="Duration of third shift in hours")
    holiday_name: Optional[str] = Field(default=None, description="Holiday name if non-working day")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class CalendarEntryResponse(BaseModel):
    id: int = Field(description="Unique record identifier")
    client_id: str = Field(description="Tenant identifier")
    calendar_date: date = Field(description="Calendar date for this entry")
    is_working_day: bool = Field(description="Whether this date is a working day")
    shifts_available: int = Field(description="Number of shifts available (1-3)")
    shift1_hours: float = Field(description="Duration of first shift in hours")
    shift2_hours: float = Field(description="Duration of second shift in hours")
    shift3_hours: float = Field(description="Duration of third shift in hours")
    holiday_name: Optional[str] = Field(description="Holiday name if non-working day")
    notes: Optional[str] = Field(description="Free-text notes")

    class Config:
        from_attributes = True


# =============================================================================
# Production Line Models
# =============================================================================


class ProductionLineCreate(BaseModel):
    line_code: str = Field(description="Unique code identifying the production line")
    line_name: str = Field(description="Human-readable line name")
    department: Optional[str] = Field(default=None, description="Department this line belongs to")
    standard_capacity_units_per_hour: float = Field(default=0, description="Rated output units per hour")
    max_operators: int = Field(default=DEFAULT_MAX_OPERATORS, description="Maximum operators that can be assigned")
    efficiency_factor: float = Field(default=0.85, description="Line efficiency as a decimal (0.0-1.0)")
    absenteeism_factor: float = Field(default=0.05, description="Expected absenteeism rate as a decimal (0.0-1.0)")
    is_active: bool = Field(default=True, description="Whether the line is currently active")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class ProductionLineUpdate(BaseModel):
    line_name: Optional[str] = Field(default=None, description="Human-readable line name")
    department: Optional[str] = Field(default=None, description="Department this line belongs to")
    standard_capacity_units_per_hour: Optional[float] = Field(default=None, description="Rated output units per hour")
    max_operators: Optional[int] = Field(default=None, description="Maximum operators that can be assigned")
    efficiency_factor: Optional[float] = Field(default=None, description="Line efficiency as a decimal (0.0-1.0)")
    absenteeism_factor: Optional[float] = Field(default=None, description="Expected absenteeism rate as a decimal (0.0-1.0)")
    is_active: Optional[bool] = Field(default=None, description="Whether the line is currently active")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class ProductionLineResponse(BaseModel):
    id: int = Field(description="Unique record identifier")
    client_id: str = Field(description="Tenant identifier")
    line_code: str = Field(description="Unique code identifying the production line")
    line_name: str = Field(description="Human-readable line name")
    department: Optional[str] = Field(description="Department this line belongs to")
    standard_capacity_units_per_hour: float = Field(description="Rated output units per hour")
    max_operators: int = Field(description="Maximum operators that can be assigned")
    efficiency_factor: float = Field(description="Line efficiency as a decimal (0.0-1.0)")
    absenteeism_factor: float = Field(description="Expected absenteeism rate as a decimal (0.0-1.0)")
    is_active: bool = Field(description="Whether the line is currently active")
    notes: Optional[str] = Field(description="Free-text notes")

    class Config:
        from_attributes = True


# =============================================================================
# Order Models
# =============================================================================


class OrderCreate(BaseModel):
    order_number: str = Field(description="Unique order reference number")
    style_code: str = Field(description="Product style code linked to production standards")
    order_quantity: int = Field(description="Total units ordered")
    required_date: date = Field(description="Customer-required delivery date")
    customer_name: Optional[str] = Field(default=None, description="Customer or buyer name")
    style_description: Optional[str] = Field(default=None, description="Descriptive name for the style")
    order_date: Optional[date] = Field(default=None, description="Date the order was placed")
    planned_start_date: Optional[date] = Field(default=None, description="Planned production start date")
    planned_end_date: Optional[date] = Field(default=None, description="Planned production end date")
    priority: OrderPriority = Field(default=OrderPriority.NORMAL, description="Order priority level")
    status: OrderStatus = Field(default=OrderStatus.DRAFT, description="Current order status")
    order_sam_minutes: Optional[float] = Field(default=None, description="Total SAM minutes for the order")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class OrderUpdate(BaseModel):
    customer_name: Optional[str] = Field(default=None, description="Customer or buyer name")
    style_description: Optional[str] = Field(default=None, description="Descriptive name for the style")
    order_quantity: Optional[int] = Field(default=None, description="Total units ordered")
    order_date: Optional[date] = Field(default=None, description="Date the order was placed")
    required_date: Optional[date] = Field(default=None, description="Customer-required delivery date")
    planned_start_date: Optional[date] = Field(default=None, description="Planned production start date")
    planned_end_date: Optional[date] = Field(default=None, description="Planned production end date")
    priority: Optional[OrderPriority] = Field(default=None, description="Order priority level")
    status: Optional[OrderStatus] = Field(default=None, description="Current order status")
    order_sam_minutes: Optional[float] = Field(default=None, description="Total SAM minutes for the order")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class OrderResponse(BaseModel):
    id: int = Field(description="Unique record identifier")
    client_id: str = Field(description="Tenant identifier")
    order_number: str = Field(description="Unique order reference number")
    customer_name: Optional[str] = Field(description="Customer or buyer name")
    style_code: str = Field(description="Product style code linked to production standards")
    style_description: Optional[str] = Field(description="Descriptive name for the style")
    order_quantity: int = Field(description="Total units ordered")
    completed_quantity: int = Field(description="Units completed so far")
    order_date: Optional[date] = Field(description="Date the order was placed")
    required_date: date = Field(description="Customer-required delivery date")
    planned_start_date: Optional[date] = Field(description="Planned production start date")
    planned_end_date: Optional[date] = Field(description="Planned production end date")
    priority: OrderPriority = Field(description="Order priority level")
    status: OrderStatus = Field(description="Current order status")
    order_sam_minutes: Optional[float] = Field(description="Total SAM minutes for the order")
    notes: Optional[str] = Field(description="Free-text notes")

    class Config:
        from_attributes = True


# =============================================================================
# Standards Models
# =============================================================================


class StandardCreate(BaseModel):
    style_code: str = Field(description="Style code this standard applies to")
    operation_code: str = Field(description="Unique operation code within the style")
    sam_minutes: float = Field(description="Standard Allowed Minutes for this operation")
    operation_name: Optional[str] = Field(default=None, description="Human-readable operation name")
    department: Optional[str] = Field(default=None, description="Department performing this operation")
    setup_time_minutes: float = Field(default=0, description="Machine setup time in minutes")
    machine_time_minutes: float = Field(default=0, description="Machine-cycle time in minutes")
    manual_time_minutes: float = Field(default=0, description="Manual (hand) time in minutes")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class StandardUpdate(BaseModel):
    operation_name: Optional[str] = Field(default=None, description="Human-readable operation name")
    department: Optional[str] = Field(default=None, description="Department performing this operation")
    sam_minutes: Optional[float] = Field(default=None, description="Standard Allowed Minutes for this operation")
    setup_time_minutes: Optional[float] = Field(default=None, description="Machine setup time in minutes")
    machine_time_minutes: Optional[float] = Field(default=None, description="Machine-cycle time in minutes")
    manual_time_minutes: Optional[float] = Field(default=None, description="Manual (hand) time in minutes")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class StandardResponse(BaseModel):
    id: int = Field(description="Unique record identifier")
    client_id: str = Field(description="Tenant identifier")
    style_code: str = Field(description="Style code this standard applies to")
    operation_code: str = Field(description="Unique operation code within the style")
    operation_name: Optional[str] = Field(description="Human-readable operation name")
    department: Optional[str] = Field(description="Department performing this operation")
    sam_minutes: float = Field(description="Standard Allowed Minutes for this operation")
    setup_time_minutes: float = Field(description="Machine setup time in minutes")
    machine_time_minutes: float = Field(description="Machine-cycle time in minutes")
    manual_time_minutes: float = Field(description="Manual (hand) time in minutes")
    notes: Optional[str] = Field(description="Free-text notes")

    class Config:
        from_attributes = True


class TotalSAMResponse(BaseModel):
    """Response for total SAM lookup by style."""

    style_code: str = Field(description="Style code queried")
    total_sam_minutes: float = Field(description="Sum of SAM minutes for all operations")
    department: Optional[str] = Field(description="Department filter applied, if any")


# =============================================================================
# BOM Models
# =============================================================================


class BOMHeaderCreate(BaseModel):
    parent_item_code: str = Field(description="Top-level item code for the bill of materials")
    parent_item_description: Optional[str] = Field(default=None, description="Description of the parent item")
    style_code: Optional[str] = Field(default=None, description="Associated style code")
    revision: str = Field(default="1.0", description="BOM revision number")
    is_active: bool = Field(default=True, description="Whether this BOM revision is active")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class BOMHeaderUpdate(BaseModel):
    parent_item_description: Optional[str] = Field(default=None, description="Description of the parent item")
    style_code: Optional[str] = Field(default=None, description="Associated style code")
    revision: Optional[str] = Field(default=None, description="BOM revision number")
    is_active: Optional[bool] = Field(default=None, description="Whether this BOM revision is active")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class BOMDetailCreate(BaseModel):
    component_item_code: str = Field(description="Component / raw-material item code")
    quantity_per: float = Field(default=1.0, description="Quantity of component required per parent unit")
    component_description: Optional[str] = Field(default=None, description="Description of the component")
    unit_of_measure: str = Field(default="EA", description="Unit of measure (EA, M, KG, etc.)")
    waste_percentage: float = Field(default=0, description="Expected waste percentage (0-100)")
    component_type: Optional[str] = Field(default=None, description="Category of component (fabric, trim, etc.)")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class BOMDetailUpdate(BaseModel):
    component_description: Optional[str] = Field(default=None, description="Description of the component")
    quantity_per: Optional[float] = Field(default=None, description="Quantity of component required per parent unit")
    unit_of_measure: Optional[str] = Field(default=None, description="Unit of measure (EA, M, KG, etc.)")
    waste_percentage: Optional[float] = Field(default=None, description="Expected waste percentage (0-100)")
    component_type: Optional[str] = Field(default=None, description="Category of component (fabric, trim, etc.)")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class BOMHeaderResponse(BaseModel):
    id: int = Field(description="Unique record identifier")
    client_id: str = Field(description="Tenant identifier")
    parent_item_code: str = Field(description="Top-level item code for the bill of materials")
    parent_item_description: Optional[str] = Field(description="Description of the parent item")
    style_code: Optional[str] = Field(description="Associated style code")
    revision: str = Field(description="BOM revision number")
    is_active: bool = Field(description="Whether this BOM revision is active")
    notes: Optional[str] = Field(description="Free-text notes")

    class Config:
        from_attributes = True


class BOMDetailResponse(BaseModel):
    id: int = Field(description="Unique record identifier")
    header_id: int = Field(description="Parent BOM header ID")
    client_id: str = Field(description="Tenant identifier")
    component_item_code: str = Field(description="Component / raw-material item code")
    component_description: Optional[str] = Field(description="Description of the component")
    quantity_per: float = Field(description="Quantity of component required per parent unit")
    unit_of_measure: str = Field(description="Unit of measure (EA, M, KG, etc.)")
    waste_percentage: float = Field(description="Expected waste percentage (0-100)")
    component_type: Optional[str] = Field(description="Category of component (fabric, trim, etc.)")
    notes: Optional[str] = Field(description="Free-text notes")

    class Config:
        from_attributes = True


class BOMExplosionRequest(BaseModel):
    parent_item_code: str = Field(description="Item code to explode")
    quantity: float = Field(description="Number of parent units to explode")


class BOMExplosionResponse(BaseModel):
    parent_item_code: str = Field(description="Item code that was exploded")
    quantity_requested: float = Field(description="Quantity that was requested")
    components: List[Dict[str, Any]] = Field(description="Exploded component list with quantities")
    total_components: int = Field(description="Total number of distinct components")


# =============================================================================
# Stock Models
# =============================================================================


class StockSnapshotCreate(BaseModel):
    snapshot_date: date = Field(description="Date this stock position was recorded")
    item_code: str = Field(description="Material / component item code")
    on_hand_quantity: float = Field(default=0, description="Physical stock on hand")
    allocated_quantity: float = Field(default=0, description="Quantity already allocated to orders")
    on_order_quantity: float = Field(default=0, description="Quantity on purchase order (incoming)")
    item_description: Optional[str] = Field(default=None, description="Description of the item")
    unit_of_measure: str = Field(default="EA", description="Unit of measure (EA, M, KG, etc.)")
    location: Optional[str] = Field(default=None, description="Warehouse or storage location")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class StockSnapshotUpdate(BaseModel):
    on_hand_quantity: Optional[float] = Field(default=None, description="Physical stock on hand")
    allocated_quantity: Optional[float] = Field(default=None, description="Quantity already allocated to orders")
    on_order_quantity: Optional[float] = Field(default=None, description="Quantity on purchase order (incoming)")
    item_description: Optional[str] = Field(default=None, description="Description of the item")
    unit_of_measure: Optional[str] = Field(default=None, description="Unit of measure (EA, M, KG, etc.)")
    location: Optional[str] = Field(default=None, description="Warehouse or storage location")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class StockSnapshotResponse(BaseModel):
    id: int = Field(description="Unique record identifier")
    client_id: str = Field(description="Tenant identifier")
    snapshot_date: date = Field(description="Date this stock position was recorded")
    item_code: str = Field(description="Material / component item code")
    item_description: Optional[str] = Field(description="Description of the item")
    on_hand_quantity: float = Field(description="Physical stock on hand")
    allocated_quantity: float = Field(description="Quantity already allocated to orders")
    on_order_quantity: float = Field(description="Quantity on purchase order (incoming)")
    available_quantity: float = Field(description="Computed available quantity (on_hand - allocated + on_order)")
    unit_of_measure: str = Field(description="Unit of measure (EA, M, KG, etc.)")
    location: Optional[str] = Field(description="Warehouse or storage location")
    notes: Optional[str] = Field(description="Free-text notes")

    class Config:
        from_attributes = True


class AvailableStockResponse(BaseModel):
    """Response for available stock quantity lookup."""

    item_code: str = Field(description="Item code queried")
    available_quantity: float = Field(description="Computed available quantity")
    as_of_date: Optional[date] = Field(description="Date the availability was computed for")


# =============================================================================
# Component Check Models
# =============================================================================


class ComponentCheckRequest(BaseModel):
    order_ids: Optional[List[int]] = Field(default=None, description="Specific order IDs to check (mutually exclusive with date range)")
    start_date: Optional[date] = Field(default=None, description="Period start for confirmed-order lookup")
    end_date: Optional[date] = Field(default=None, description="Period end for confirmed-order lookup")


class ComponentCheckResult(BaseModel):
    order_id: int = Field(description="Order that requires this component")
    order_number: str = Field(description="Order reference number")
    component_item_code: str = Field(description="Required component item code")
    component_description: Optional[str] = Field(description="Component description")
    required_quantity: float = Field(description="Gross quantity required for the order")
    available_quantity: float = Field(description="Current available stock quantity")
    shortage_quantity: float = Field(description="Shortfall quantity (positive means shortage)")
    status: str = Field(description="Component status: OK, SHORT, or CRITICAL")
    coverage_percent: float = Field(description="Percentage of requirement covered by stock (0-100)")


# =============================================================================
# Analysis Models
# =============================================================================


class AnalysisRequest(BaseModel):
    start_date: date = Field(description="Analysis period start date")
    end_date: date = Field(description="Analysis period end date")
    line_ids: Optional[List[int]] = Field(default=None, description="Specific line IDs to analyze (all if omitted)")
    department: Optional[str] = Field(default=None, description="Filter analysis to a single department")


class AnalysisResult(BaseModel):
    line_id: int = Field(description="Production line ID")
    line_code: str = Field(description="Production line code")
    department: Optional[str] = Field(description="Department the line belongs to")
    analysis_date: date = Field(description="Date the analysis covers")
    working_days: int = Field(description="Number of working days in the period")
    gross_hours: float = Field(description="Total gross hours before efficiency adjustment")
    capacity_hours: float = Field(description="Net available capacity hours after efficiency and absenteeism")
    demand_hours: float = Field(description="Total demand hours from scheduled orders")
    utilization_percent: float = Field(description="Demand / capacity as a percentage")
    is_bottleneck: bool = Field(description="True if utilization exceeds the bottleneck threshold")


# =============================================================================
# Schedule Models
# =============================================================================


class ScheduleCreate(BaseModel):
    schedule_name: str = Field(description="Human-readable schedule name")
    period_start: date = Field(description="First date of the scheduling period")
    period_end: date = Field(description="Last date of the scheduling period")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class ScheduleUpdate(BaseModel):
    schedule_name: Optional[str] = Field(default=None, description="Human-readable schedule name")
    period_start: Optional[date] = Field(default=None, description="First date of the scheduling period")
    period_end: Optional[date] = Field(default=None, description="Last date of the scheduling period")
    status: Optional[ScheduleStatus] = Field(default=None, description="Schedule lifecycle status")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class ScheduleDetailCreate(BaseModel):
    order_id: Optional[int] = Field(default=None, description="Order assigned to this slot")
    line_id: Optional[int] = Field(default=None, description="Production line assigned to this slot")
    scheduled_date: date = Field(description="Date this production slot is scheduled for")
    scheduled_quantity: int = Field(default=0, description="Quantity planned for this slot")
    sequence: int = Field(default=1, description="Processing order on the line for this date")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class ScheduleResponse(BaseModel):
    id: int = Field(description="Unique record identifier")
    client_id: str = Field(description="Tenant identifier")
    schedule_name: str = Field(description="Human-readable schedule name")
    period_start: date = Field(description="First date of the scheduling period")
    period_end: date = Field(description="Last date of the scheduling period")
    status: ScheduleStatus = Field(description="Schedule lifecycle status (DRAFT, COMMITTED, ARCHIVED)")
    committed_at: Optional[date] = Field(description="Date the schedule was committed")
    committed_by: Optional[int] = Field(description="User ID who committed the schedule")
    notes: Optional[str] = Field(description="Free-text notes")

    class Config:
        from_attributes = True


class ScheduleCommitRequest(BaseModel):
    kpi_commitments: Dict[str, float] = Field(
        default_factory=dict, description="KPI commitments e.g. {'efficiency': 85.0, 'quality': 98.5}"
    )


# =============================================================================
# Scenario Models
# =============================================================================


class ScenarioCreate(BaseModel):
    scenario_name: str = Field(description="Descriptive name for the what-if scenario")
    scenario_type: Optional[str] = Field(default=None, description="Scenario type (OVERTIME, SETUP_REDUCTION, SUBCONTRACT, NEW_LINE, THREE_SHIFT, LEAD_TIME_DELAY, ABSENTEEISM_SPIKE, MULTI_CONSTRAINT)")
    base_schedule_id: Optional[int] = Field(default=None, description="Schedule ID used as the baseline for comparison")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Scenario-specific parameter dictionary")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class ScenarioUpdate(BaseModel):
    scenario_name: Optional[str] = Field(default=None, description="Descriptive name for the what-if scenario")
    scenario_type: Optional[str] = Field(default=None, description="Scenario type (OVERTIME, SETUP_REDUCTION, etc.)")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="Scenario-specific parameter dictionary")
    is_active: Optional[bool] = Field(default=None, description="Whether this scenario is active")
    notes: Optional[str] = Field(default=None, description="Free-text notes")


class ScenarioResponse(BaseModel):
    id: int = Field(description="Unique record identifier")
    client_id: str = Field(description="Tenant identifier")
    scenario_name: str = Field(description="Descriptive name for the what-if scenario")
    scenario_type: Optional[str] = Field(description="Scenario type (OVERTIME, SETUP_REDUCTION, etc.)")
    base_schedule_id: Optional[int] = Field(description="Schedule ID used as the baseline for comparison")
    parameters_json: Optional[Dict[str, Any]] = Field(description="Scenario-specific parameter dictionary")
    results_json: Optional[Dict[str, Any]] = Field(description="Results from the last scenario run")
    is_active: bool = Field(description="Whether this scenario is active")
    notes: Optional[str] = Field(description="Free-text notes")

    class Config:
        from_attributes = True


class ScenarioCompareRequest(BaseModel):
    scenario_ids: List[int] = Field(description="List of scenario IDs to compare side-by-side")


class ScenarioRunRequest(BaseModel):
    period_start: Optional[date] = Field(default=None, description="Override analysis period start (defaults to base schedule or today)")
    period_end: Optional[date] = Field(default=None, description="Override analysis period end (defaults to base schedule or today+30d)")


class ScenarioRunResponse(BaseModel):
    """Response for scenario run/evaluation."""

    scenario_id: int = Field(description="ID of the scenario that was run")
    scenario_name: str = Field(description="Name of the scenario")
    original_metrics: Dict[str, Any] = Field(description="Baseline capacity metrics before scenario changes")
    modified_metrics: Dict[str, Any] = Field(description="Projected capacity metrics after scenario changes")
    impact_summary: Dict[str, Any] = Field(description="Summary of deltas between original and modified metrics")


# =============================================================================
# KPI Models
# =============================================================================


class KPICommitmentResponse(BaseModel):
    id: int = Field(description="Unique record identifier")
    client_id: str = Field(description="Tenant identifier")
    schedule_id: int = Field(description="Schedule this commitment belongs to")
    kpi_key: str = Field(description="KPI identifier key (e.g. 'efficiency', 'quality')")
    kpi_name: Optional[str] = Field(description="Human-readable KPI name")
    period_start: date = Field(description="Start of the measurement period")
    period_end: date = Field(description="End of the measurement period")
    committed_value: float = Field(description="Target value committed during planning")
    actual_value: Optional[float] = Field(description="Actual achieved value (null until measured)")
    variance: Optional[float] = Field(description="Absolute variance (actual - committed)")
    variance_percent: Optional[float] = Field(description="Percentage variance from committed target")

    class Config:
        from_attributes = True
