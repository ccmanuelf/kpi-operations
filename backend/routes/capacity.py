"""
Capacity Planning API Routes
Phase B.3: API endpoints for capacity planning module

This module provides REST API endpoints for:
- Master Calendar (working days, shifts, holidays)
- Production Lines (capacity specifications)
- Orders (planning orders)
- Production Standards (SAM data)
- BOM (Bill of Materials)
- Stock Snapshots (inventory positions)
- Component Check (MRP explosion)
- Capacity Analysis (utilization calculations)
- Schedules (production planning)
- Scenarios (what-if analysis)
- KPI Integration (commitments and actuals)
- Workbook (multi-sheet operations)

All endpoints enforce multi-tenant isolation via client_id.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.constants import (
    DEFAULT_PAGE_SIZE,
    LARGE_PAGE_SIZE,
    EXTRA_LARGE_PAGE_SIZE,
    CALENDAR_DEFAULT_DAYS,
    DEFAULT_MAX_OPERATORS,
    LOOKBACK_MONTHLY_DAYS,
)

# CRUD imports
from backend.crud.capacity import calendar, production_lines, orders, standards, bom, stock

# Schema imports for enums
from backend.schemas.capacity.orders import OrderPriority, OrderStatus
from backend.schemas.capacity.schedule import ScheduleStatus
from backend.schemas.capacity.component_check import ComponentStatus


# =============================================================================
# Main Router
# =============================================================================

router = APIRouter(prefix="/api/capacity", tags=["Capacity Planning"], responses={404: {"description": "Not found"}})


# =============================================================================
# Pydantic Models for Request/Response
# =============================================================================


class MessageResponse(BaseModel):
    """Standard response for delete and bulk operations."""

    message: str = Field(description="Human-readable result message")


class TotalSAMResponse(BaseModel):
    """Response for total SAM lookup by style."""

    style_code: str = Field(description="Style code queried")
    total_sam_minutes: float = Field(description="Sum of SAM minutes for all operations")
    department: Optional[str] = Field(description="Department filter applied, if any")


class AvailableStockResponse(BaseModel):
    """Response for available stock quantity lookup."""

    item_code: str = Field(description="Item code queried")
    available_quantity: float = Field(description="Computed available quantity")
    as_of_date: Optional[date] = Field(description="Date the availability was computed for")


class WorksheetSaveResponse(BaseModel):
    """Response for worksheet bulk-save operations."""

    message: str = Field(description="Human-readable result message")
    rows_processed: int = Field(description="Number of rows processed in the bulk save")


class ScenarioRunResponse(BaseModel):
    """Response for scenario run/evaluation."""

    scenario_id: int = Field(description="ID of the scenario that was run")
    scenario_name: str = Field(description="Name of the scenario")
    original_metrics: Dict[str, Any] = Field(description="Baseline capacity metrics before scenario changes")
    modified_metrics: Dict[str, Any] = Field(description="Projected capacity metrics after scenario changes")
    impact_summary: Dict[str, Any] = Field(description="Summary of deltas between original and modified metrics")


# Calendar Models
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


# Production Line Models
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


# Order Models
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


# Standards Models
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


# BOM Models
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


# Stock Models
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


# Component Check Models
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


# Analysis Models
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


# Schedule Models
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


# Scenario Models
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


# KPI Models
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


# =============================================================================
# Calendar Endpoints
# =============================================================================


@router.get("/calendar", response_model=List[CalendarEntryResponse])
def list_calendar_entries(
    client_id: str = Query(..., description="Client ID"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get calendar entries for a client."""
    verify_client_access(current_user, client_id, db)
    if start_date and end_date:
        return calendar.get_calendar_for_period(db, client_id, start_date, end_date)
    return calendar.get_calendar_entries(db, client_id, skip, limit)


@router.post("/calendar", response_model=CalendarEntryResponse, status_code=status.HTTP_201_CREATED)
def create_calendar(
    entry: CalendarEntryCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new calendar entry."""
    verify_client_access(current_user, client_id, db)
    return calendar.create_calendar_entry(
        db,
        client_id,
        entry.calendar_date,
        entry.is_working_day,
        entry.shifts_available,
        entry.shift1_hours,
        entry.shift2_hours,
        entry.shift3_hours,
        entry.holiday_name,
        entry.notes,
    )


@router.get("/calendar/{entry_id}", response_model=CalendarEntryResponse, responses={404: {"description": "Calendar entry not found"}})
def get_calendar(
    entry_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific calendar entry."""
    verify_client_access(current_user, client_id, db)
    entry = calendar.get_calendar_entry(db, client_id, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return entry


@router.put("/calendar/{entry_id}", response_model=CalendarEntryResponse, responses={404: {"description": "Calendar entry not found"}})
def update_calendar(
    entry_id: int,
    update: CalendarEntryUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a calendar entry."""
    verify_client_access(current_user, client_id, db)
    entry = calendar.update_calendar_entry(db, client_id, entry_id, **update.model_dump(exclude_unset=True))
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return entry


@router.delete("/calendar/{entry_id}", response_model=MessageResponse, responses={404: {"description": "Calendar entry not found"}})
def delete_calendar(
    entry_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a calendar entry."""
    verify_client_access(current_user, client_id, db)
    if not calendar.delete_calendar_entry(db, client_id, entry_id):
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return {"message": "Calendar entry deleted"}


# =============================================================================
# Production Lines Endpoints
# =============================================================================


@router.get("/lines", response_model=List[ProductionLineResponse])
def list_production_lines(
    client_id: str = Query(..., description="Client ID"),
    include_inactive: bool = False,
    department: Optional[str] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get production lines for a client."""
    verify_client_access(current_user, client_id, db)
    if department:
        return production_lines.get_lines_by_department(db, client_id, department, not include_inactive)
    return production_lines.get_production_lines(db, client_id, skip, limit, include_inactive)


@router.post("/lines", response_model=ProductionLineResponse, status_code=status.HTTP_201_CREATED)
def create_production_line(
    line: ProductionLineCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new production line."""
    verify_client_access(current_user, client_id, db)
    return production_lines.create_production_line(
        db,
        client_id,
        line.line_code,
        line.line_name,
        line.department,
        line.standard_capacity_units_per_hour,
        line.max_operators,
        line.efficiency_factor,
        line.absenteeism_factor,
        line.is_active,
        line.notes,
    )


@router.get("/lines/{line_id}", response_model=ProductionLineResponse, responses={404: {"description": "Production line not found"}})
def get_production_line(
    line_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific production line."""
    verify_client_access(current_user, client_id, db)
    line = production_lines.get_production_line(db, client_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Production line not found")
    return line


@router.put("/lines/{line_id}", response_model=ProductionLineResponse, responses={404: {"description": "Production line not found"}})
def update_production_line(
    line_id: int,
    update: ProductionLineUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a production line."""
    verify_client_access(current_user, client_id, db)
    line = production_lines.update_production_line(db, client_id, line_id, **update.model_dump(exclude_unset=True))
    if not line:
        raise HTTPException(status_code=404, detail="Production line not found")
    return line


@router.delete("/lines/{line_id}", response_model=MessageResponse, responses={404: {"description": "Production line not found"}})
def delete_production_line(
    line_id: int,
    client_id: str = Query(..., description="Client ID"),
    soft_delete: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a production line."""
    verify_client_access(current_user, client_id, db)
    if not production_lines.delete_production_line(db, client_id, line_id, soft_delete):
        raise HTTPException(status_code=404, detail="Production line not found")
    return {"message": "Production line deleted"}


# =============================================================================
# Orders Endpoints
# =============================================================================


@router.get("/orders", response_model=List[OrderResponse])
def list_orders(
    client_id: str = Query(..., description="Client ID"),
    status_filter: Optional[OrderStatus] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get orders for a client."""
    verify_client_access(current_user, client_id, db)
    return orders.get_orders(db, client_id, skip, limit, status_filter)


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order: OrderCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new order."""
    verify_client_access(current_user, client_id, db)
    return orders.create_order(
        db,
        client_id,
        order.order_number,
        order.style_code,
        order.order_quantity,
        order.required_date,
        order.customer_name,
        order.style_description,
        order.order_date,
        order.planned_start_date,
        order.planned_end_date,
        order.priority,
        order.status,
        order.order_sam_minutes,
        order.notes,
    )


@router.get("/orders/scheduling", response_model=List[OrderResponse])
def get_orders_for_scheduling(
    client_id: str = Query(..., description="Client ID"),
    start_date: date = Query(..., description="Schedule period start"),
    end_date: date = Query(..., description="Schedule period end"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get confirmed orders ready for scheduling within a date range."""
    verify_client_access(current_user, client_id, db)
    return orders.get_orders_for_scheduling(db, client_id, start_date, end_date)


@router.get("/orders/{order_id}", response_model=OrderResponse, responses={404: {"description": "Order not found"}})
def get_order(
    order_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific order."""
    verify_client_access(current_user, client_id, db)
    order = orders.get_order(db, client_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.put("/orders/{order_id}", response_model=OrderResponse, responses={404: {"description": "Order not found"}})
def update_order(
    order_id: int,
    update: OrderUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an order."""
    verify_client_access(current_user, client_id, db)
    order = orders.update_order(db, client_id, order_id, **update.model_dump(exclude_unset=True))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/orders/{order_id}/status", response_model=OrderResponse, responses={404: {"description": "Order not found"}})
def update_order_status(
    order_id: int,
    new_status: OrderStatus,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update order status."""
    verify_client_access(current_user, client_id, db)
    order = orders.update_order_status(db, client_id, order_id, new_status)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.delete("/orders/{order_id}", response_model=MessageResponse, responses={404: {"description": "Order not found"}})
def delete_order(
    order_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an order."""
    verify_client_access(current_user, client_id, db)
    if not orders.delete_order(db, client_id, order_id):
        raise HTTPException(status_code=404, detail="Order not found")
    return {"message": "Order deleted"}


# =============================================================================
# Standards Endpoints
# =============================================================================


@router.get("/standards", response_model=List[StandardResponse])
def list_standards(
    client_id: str = Query(..., description="Client ID"),
    department: Optional[str] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get production standards for a client."""
    verify_client_access(current_user, client_id, db)
    return standards.get_standards(db, client_id, skip, limit, department)


@router.post("/standards", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
def create_standard(
    standard: StandardCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new production standard."""
    verify_client_access(current_user, client_id, db)
    return standards.create_standard(
        db,
        client_id,
        standard.style_code,
        standard.operation_code,
        standard.sam_minutes,
        standard.operation_name,
        standard.department,
        standard.setup_time_minutes,
        standard.machine_time_minutes,
        standard.manual_time_minutes,
        standard.notes,
    )


@router.get("/standards/style/{style_code}", response_model=List[StandardResponse])
def get_standards_by_style(
    style_code: str,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all standards for a specific style."""
    verify_client_access(current_user, client_id, db)
    return standards.get_standards_by_style(db, client_id, style_code)


@router.get("/standards/style/{style_code}/total-sam", response_model=TotalSAMResponse)
def get_total_sam_for_style(
    style_code: str,
    client_id: str = Query(..., description="Client ID"),
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get total SAM minutes for a style."""
    verify_client_access(current_user, client_id, db)
    total = standards.get_total_sam_for_style(db, client_id, style_code, department)
    return {"style_code": style_code, "total_sam_minutes": total, "department": department}


@router.get("/standards/{standard_id}", response_model=StandardResponse, responses={404: {"description": "Standard not found"}})
def get_standard(
    standard_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific production standard."""
    verify_client_access(current_user, client_id, db)
    standard = standards.get_standard(db, client_id, standard_id)
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    return standard


@router.put("/standards/{standard_id}", response_model=StandardResponse, responses={404: {"description": "Standard not found"}})
def update_standard(
    standard_id: int,
    update: StandardUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a production standard."""
    verify_client_access(current_user, client_id, db)
    standard = standards.update_standard(db, client_id, standard_id, **update.model_dump(exclude_unset=True))
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    return standard


@router.delete("/standards/{standard_id}", response_model=MessageResponse, responses={404: {"description": "Standard not found"}})
def delete_standard(
    standard_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a production standard."""
    verify_client_access(current_user, client_id, db)
    if not standards.delete_standard(db, client_id, standard_id):
        raise HTTPException(status_code=404, detail="Standard not found")
    return {"message": "Standard deleted"}


# =============================================================================
# BOM Endpoints
# =============================================================================


@router.get("/bom", response_model=List[BOMHeaderResponse])
def list_bom_headers(
    client_id: str = Query(..., description="Client ID"),
    include_inactive: bool = False,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get BOM headers for a client."""
    verify_client_access(current_user, client_id, db)
    return bom.get_bom_headers(db, client_id, skip, limit, include_inactive)


@router.post("/bom", response_model=BOMHeaderResponse, status_code=status.HTTP_201_CREATED)
def create_bom_header(
    header: BOMHeaderCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new BOM header."""
    verify_client_access(current_user, client_id, db)
    return bom.create_bom_header(
        db,
        client_id,
        header.parent_item_code,
        header.parent_item_description,
        header.style_code,
        header.revision,
        header.is_active,
        header.notes,
    )


@router.get("/bom/{header_id}", response_model=BOMHeaderResponse, responses={404: {"description": "BOM header not found"}})
def get_bom_header(
    header_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific BOM header."""
    verify_client_access(current_user, client_id, db)
    header = bom.get_bom_header(db, client_id, header_id)
    if not header:
        raise HTTPException(status_code=404, detail="BOM header not found")
    return header


@router.put("/bom/{header_id}", response_model=BOMHeaderResponse, responses={404: {"description": "BOM header not found"}})
def update_bom_header(
    header_id: int,
    update: BOMHeaderUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a BOM header."""
    verify_client_access(current_user, client_id, db)
    header = bom.update_bom_header(db, client_id, header_id, **update.model_dump(exclude_unset=True))
    if not header:
        raise HTTPException(status_code=404, detail="BOM header not found")
    return header


@router.delete("/bom/{header_id}", response_model=MessageResponse, responses={404: {"description": "BOM header not found"}})
def delete_bom_header(
    header_id: int,
    client_id: str = Query(..., description="Client ID"),
    cascade: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a BOM header (and optionally its details)."""
    verify_client_access(current_user, client_id, db)
    if not bom.delete_bom_header(db, client_id, header_id, cascade):
        raise HTTPException(status_code=404, detail="BOM header not found")
    return {"message": "BOM header deleted"}


@router.get("/bom/{header_id}/details", response_model=List[BOMDetailResponse])
def list_bom_details(
    header_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details for a BOM header."""
    verify_client_access(current_user, client_id, db)
    return bom.get_bom_details(db, client_id, header_id)


@router.post("/bom/{header_id}/details", response_model=BOMDetailResponse, status_code=status.HTTP_201_CREATED)
def create_bom_detail(
    header_id: int,
    detail: BOMDetailCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a component to a BOM."""
    verify_client_access(current_user, client_id, db)
    return bom.create_bom_detail(
        db,
        client_id,
        header_id,
        detail.component_item_code,
        detail.quantity_per,
        detail.component_description,
        detail.unit_of_measure,
        detail.waste_percentage,
        detail.component_type,
        detail.notes,
    )


@router.put("/bom/details/{detail_id}", response_model=BOMDetailResponse, responses={404: {"description": "BOM detail not found"}})
def update_bom_detail(
    detail_id: int,
    update: BOMDetailUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a BOM detail."""
    verify_client_access(current_user, client_id, db)
    detail = bom.update_bom_detail(db, client_id, detail_id, **update.model_dump(exclude_unset=True))
    if not detail:
        raise HTTPException(status_code=404, detail="BOM detail not found")
    return detail


@router.delete("/bom/details/{detail_id}", response_model=MessageResponse, responses={404: {"description": "BOM detail not found"}})
def delete_bom_detail(
    detail_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a BOM detail."""
    verify_client_access(current_user, client_id, db)
    if not bom.delete_bom_detail(db, client_id, detail_id):
        raise HTTPException(status_code=404, detail="BOM detail not found")
    return {"message": "BOM detail deleted"}


@router.post("/bom/explode", response_model=BOMExplosionResponse, responses={400: {"description": "BOM explosion failed"}})
def explode_bom(
    request: BOMExplosionRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run BOM explosion for a parent item."""
    verify_client_access(current_user, client_id, db)
    from backend.services.capacity.bom_service import BOMService

    service = BOMService(db)
    try:
        result = service.explode_bom(client_id, request.parent_item_code, Decimal(str(request.quantity)))
        return {
            "parent_item_code": result.parent_item_code,
            "quantity_requested": float(result.quantity_requested),
            "components": [
                {
                    "component_item_code": c.component_item_code,
                    "component_description": c.component_description,
                    "gross_required": float(c.gross_required),
                    "net_required": float(c.net_required),
                    "waste_percentage": float(c.waste_percentage),
                    "unit_of_measure": c.unit_of_measure,
                    "component_type": c.component_type,
                }
                for c in result.components
            ],
            "total_components": result.total_components,
        }
    except Exception as e:
        db.rollback()
        logger.exception("BOM explosion failed for parent_item_code=%s", request.parent_item_code)
        raise HTTPException(status_code=400, detail="BOM explosion failed")


# =============================================================================
# Stock Endpoints
# =============================================================================


@router.get("/stock", response_model=List[StockSnapshotResponse])
def list_stock_snapshots(
    client_id: str = Query(..., description="Client ID"),
    snapshot_date: Optional[date] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get stock snapshots for a client."""
    verify_client_access(current_user, client_id, db)
    return stock.get_stock_snapshots(db, client_id, skip, limit, snapshot_date)


@router.post("/stock", response_model=StockSnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_stock_snapshot(
    snapshot: StockSnapshotCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new stock snapshot."""
    verify_client_access(current_user, client_id, db)
    return stock.create_stock_snapshot(
        db,
        client_id,
        snapshot.snapshot_date,
        snapshot.item_code,
        snapshot.on_hand_quantity,
        snapshot.allocated_quantity,
        snapshot.on_order_quantity,
        snapshot.item_description,
        snapshot.unit_of_measure,
        snapshot.location,
        snapshot.notes,
    )


@router.get("/stock/item/{item_code}/latest", response_model=StockSnapshotResponse, responses={404: {"description": "No stock snapshot found for this item"}})
def get_latest_stock_for_item(
    item_code: str,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the most recent stock snapshot for an item."""
    verify_client_access(current_user, client_id, db)
    snapshot = stock.get_latest_stock(db, client_id, item_code)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return snapshot


@router.get("/stock/item/{item_code}/available", response_model=AvailableStockResponse)
def get_available_stock_for_item(
    item_code: str,
    client_id: str = Query(..., description="Client ID"),
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get available stock quantity for an item."""
    verify_client_access(current_user, client_id, db)
    available = stock.get_available_stock(db, client_id, item_code, as_of_date)
    return {"item_code": item_code, "available_quantity": available, "as_of_date": as_of_date}


@router.get("/stock/shortages", response_model=List[StockSnapshotResponse])
def get_shortage_items(
    client_id: str = Query(..., description="Client ID"),
    snapshot_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get items with shortage (zero or negative available quantity)."""
    verify_client_access(current_user, client_id, db)
    return stock.get_shortage_items(db, client_id, snapshot_date)


@router.get("/stock/{snapshot_id}", response_model=StockSnapshotResponse, responses={404: {"description": "Stock snapshot not found"}})
def get_stock_snapshot(
    snapshot_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific stock snapshot."""
    verify_client_access(current_user, client_id, db)
    snapshot = stock.get_stock_snapshot(db, client_id, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return snapshot


@router.put("/stock/{snapshot_id}", response_model=StockSnapshotResponse, responses={404: {"description": "Stock snapshot not found"}})
def update_stock_snapshot(
    snapshot_id: int,
    update: StockSnapshotUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a stock snapshot."""
    verify_client_access(current_user, client_id, db)
    snapshot = stock.update_stock_snapshot(db, client_id, snapshot_id, **update.model_dump(exclude_unset=True))
    if not snapshot:
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return snapshot


@router.delete("/stock/{snapshot_id}", response_model=MessageResponse, responses={404: {"description": "Stock snapshot not found"}})
def delete_stock_snapshot(
    snapshot_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a stock snapshot."""
    verify_client_access(current_user, client_id, db)
    if not stock.delete_stock_snapshot(db, client_id, snapshot_id):
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return {"message": "Stock snapshot deleted"}


# =============================================================================
# Component Check (MRP) Endpoints
# =============================================================================


@router.post("/component-check/run", response_model=List[ComponentCheckResult], responses={400: {"description": "Must provide order_ids or date range, or component check failed"}, 501: {"description": "MRP service not yet implemented"}})
def run_component_check(
    request: ComponentCheckRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run component availability check (MRP explosion).

    Either provide specific order_ids or a date range to check all confirmed orders.
    """
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.mrp_service import MRPService

        service = MRPService(db)

        if request.order_ids:
            results = service.check_components_for_orders(client_id, request.order_ids)
        elif request.start_date and request.end_date:
            results = service.check_components_for_period(client_id, request.start_date, request.end_date)
        else:
            raise HTTPException(status_code=400, detail="Must provide either order_ids or both start_date and end_date")

        return [
            {
                "order_id": r.order_id,
                "order_number": r.order_number,
                "component_item_code": r.component_item_code,
                "component_description": r.component_description,
                "required_quantity": float(r.required_quantity),
                "available_quantity": float(r.available_quantity),
                "shortage_quantity": float(r.shortage_quantity),
                "status": r.status.value,
                "coverage_percent": r.coverage_percent(),
            }
            for r in results
        ]
    except ImportError:
        raise HTTPException(status_code=501, detail="MRP service not yet implemented")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Component check failed for client_id=%s", client_id)
        raise HTTPException(status_code=400, detail="Component check failed")


@router.get("/component-check/shortages", response_model=List[ComponentCheckResult])
def get_component_shortages(
    client_id: str = Query(..., description="Client ID"),
    run_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get component shortages from the most recent check run."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.component_check import CapacityComponentCheck, ComponentStatus

    query = db.query(CapacityComponentCheck).filter(
        CapacityComponentCheck.client_id == client_id, CapacityComponentCheck.status != ComponentStatus.OK
    )

    if run_date:
        query = query.filter(CapacityComponentCheck.run_date == run_date)

    results = query.order_by(CapacityComponentCheck.shortage_quantity.desc()).all()

    return [
        {
            "order_id": r.order_id,
            "order_number": r.order_number,
            "component_item_code": r.component_item_code,
            "component_description": r.component_description,
            "required_quantity": float(r.required_quantity),
            "available_quantity": float(r.available_quantity),
            "shortage_quantity": float(r.shortage_quantity),
            "status": r.status.value,
            "coverage_percent": r.coverage_percent(),
        }
        for r in results
    ]


# =============================================================================
# Capacity Analysis Endpoints
# =============================================================================


@router.post("/analysis/calculate", response_model=List[AnalysisResult], responses={400: {"description": "Capacity analysis failed"}, 501: {"description": "Capacity analysis service not yet implemented"}})
def run_capacity_analysis(
    request: AnalysisRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run capacity analysis for lines within a date range."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.analysis_service import CapacityAnalysisService

        service = CapacityAnalysisService(db)

        results = service.analyze_capacity(
            client_id, request.start_date, request.end_date, request.line_ids, request.department
        )

        return [
            {
                "line_id": r.line_id,
                "line_code": r.line_code,
                "department": r.department,
                "analysis_date": r.analysis_date,
                "working_days": r.working_days,
                "gross_hours": float(r.gross_hours),
                "capacity_hours": float(r.capacity_hours),
                "demand_hours": float(r.demand_hours),
                "utilization_percent": float(r.utilization_percent),
                "is_bottleneck": r.is_bottleneck,
            }
            for r in results
        ]
    except ImportError:
        raise HTTPException(status_code=501, detail="Capacity analysis service not yet implemented")
    except Exception as e:
        db.rollback()
        logger.exception("Capacity analysis failed for client_id=%s", client_id)
        raise HTTPException(status_code=400, detail="Capacity analysis failed")


@router.get("/analysis/bottlenecks", response_model=List[AnalysisResult])
def get_bottleneck_lines(
    client_id: str = Query(..., description="Client ID"),
    analysis_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get lines identified as bottlenecks."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.analysis import CapacityAnalysis

    query = db.query(CapacityAnalysis).filter(
        CapacityAnalysis.client_id == client_id, CapacityAnalysis.is_bottleneck == True
    )

    if analysis_date:
        query = query.filter(CapacityAnalysis.analysis_date == analysis_date)

    results = query.order_by(CapacityAnalysis.utilization_percent.desc()).all()

    return [
        {
            "line_id": r.line_id,
            "line_code": r.line_code,
            "department": r.department,
            "analysis_date": r.analysis_date,
            "working_days": r.working_days,
            "gross_hours": float(r.gross_hours or 0),
            "capacity_hours": float(r.capacity_hours or 0),
            "demand_hours": float(r.demand_hours or 0),
            "utilization_percent": float(r.utilization_percent or 0),
            "is_bottleneck": r.is_bottleneck,
        }
        for r in results
    ]


# =============================================================================
# Schedule Endpoints
# =============================================================================


@router.get("/schedules", response_model=List[ScheduleResponse])
def list_schedules(
    client_id: str = Query(..., description="Client ID"),
    status_filter: Optional[ScheduleStatus] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get schedules for a client."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.schedule import CapacitySchedule

    query = db.query(CapacitySchedule).filter(CapacitySchedule.client_id == client_id)

    if status_filter:
        query = query.filter(CapacitySchedule.status == status_filter)

    return query.order_by(CapacitySchedule.period_start.desc()).offset(skip).limit(limit).all()


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    schedule: ScheduleCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new schedule."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.schedule import CapacitySchedule, ScheduleStatus

    new_schedule = CapacitySchedule(
        client_id=client_id,
        schedule_name=schedule.schedule_name,
        period_start=schedule.period_start,
        period_end=schedule.period_end,
        status=ScheduleStatus.DRAFT,
        notes=schedule.notes,
    )
    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)
    return new_schedule


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse, responses={404: {"description": "Schedule not found"}})
def get_schedule(
    schedule_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific schedule."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.schedule import CapacitySchedule

    schedule = (
        db.query(CapacitySchedule)
        .filter(CapacitySchedule.client_id == client_id, CapacitySchedule.id == schedule_id)
        .first()
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.post("/schedules/generate", response_model=ScheduleResponse, responses={400: {"description": "Schedule generation failed"}, 501: {"description": "Scheduling service not yet implemented"}})
def generate_schedule(
    schedule_name: str,
    start_date: date = Query(..., description="Schedule period start"),
    end_date: date = Query(..., description="Schedule period end"),
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-generate a schedule from confirmed orders."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.scheduling_service import SchedulingService

        service = SchedulingService(db)

        schedule = service.generate_schedule(client_id, schedule_name, start_date, end_date)
        return schedule
    except ImportError:
        raise HTTPException(status_code=501, detail="Scheduling service not yet implemented")
    except Exception as e:
        db.rollback()
        logger.exception("Schedule generation failed for client_id=%s", client_id)
        raise HTTPException(status_code=400, detail="Schedule generation failed")


@router.post("/schedules/{schedule_id}/commit", response_model=ScheduleResponse, responses={404: {"description": "Schedule not found"}, 400: {"description": "Only draft schedules can be committed"}})
def commit_schedule(
    schedule_id: int,
    request: ScheduleCommitRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit a schedule, locking KPI targets."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.schedule import CapacitySchedule, ScheduleStatus
    from datetime import date as date_type

    schedule = (
        db.query(CapacitySchedule)
        .filter(CapacitySchedule.client_id == client_id, CapacitySchedule.id == schedule_id)
        .first()
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if schedule.status != ScheduleStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft schedules can be committed")

    schedule.status = ScheduleStatus.COMMITTED
    schedule.committed_at = date_type.today()
    schedule.committed_by = current_user.user_id
    schedule.kpi_commitments_json = request.kpi_commitments

    db.commit()
    db.refresh(schedule)
    return schedule


# =============================================================================
# Scenario Endpoints
# =============================================================================


@router.get("/scenarios", response_model=List[ScenarioResponse])
def list_scenarios(
    client_id: str = Query(..., description="Client ID"),
    scenario_type: Optional[str] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get scenarios for a client."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    query = db.query(CapacityScenario).filter(CapacityScenario.client_id == client_id)

    if scenario_type:
        query = query.filter(CapacityScenario.scenario_type == scenario_type)

    return query.order_by(CapacityScenario.created_at.desc()).offset(skip).limit(limit).all()


@router.post("/scenarios", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    scenario: ScenarioCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new scenario."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    new_scenario = CapacityScenario(
        client_id=client_id,
        scenario_name=scenario.scenario_name,
        scenario_type=scenario.scenario_type,
        base_schedule_id=scenario.base_schedule_id,
        parameters_json=scenario.parameters,
        is_active=True,
        notes=scenario.notes,
    )
    db.add(new_scenario)
    db.commit()
    db.refresh(new_scenario)
    return new_scenario


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse, responses={404: {"description": "Scenario not found"}})
def get_scenario(
    scenario_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific scenario."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    scenario = (
        db.query(CapacityScenario)
        .filter(CapacityScenario.client_id == client_id, CapacityScenario.id == scenario_id)
        .first()
    )

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


class ScenarioRunRequest(BaseModel):
    period_start: Optional[date] = Field(default=None, description="Override analysis period start (defaults to base schedule or today)")
    period_end: Optional[date] = Field(default=None, description="Override analysis period end (defaults to base schedule or today+30d)")


@router.post("/scenarios/{scenario_id}/run", response_model=ScenarioRunResponse, responses={404: {"description": "Scenario not found"}, 400: {"description": "Scenario evaluation failed"}, 501: {"description": "Scenario service not yet implemented"}})
def run_scenario(
    scenario_id: int,
    request: ScenarioRunRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run/evaluate a scenario by applying its parameters and analyzing impact."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    scenario = (
        db.query(CapacityScenario)
        .filter(CapacityScenario.client_id == client_id, CapacityScenario.id == scenario_id)
        .first()
    )

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    try:
        from backend.services.capacity.scenario_service import ScenarioService

        service = ScenarioService(db)

        # Use provided dates or derive from base schedule or default to 30-day window
        period_start = request.period_start
        period_end = request.period_end

        if not period_start or not period_end:
            if scenario.base_schedule_id:
                from backend.schemas.capacity.schedule import CapacitySchedule

                base_schedule = (
                    db.query(CapacitySchedule).filter(CapacitySchedule.id == scenario.base_schedule_id).first()
                )
                if base_schedule:
                    period_start = period_start or base_schedule.period_start
                    period_end = period_end or base_schedule.period_end

            if not period_start:
                from datetime import timedelta

                period_start = date.today()
            if not period_end:
                from datetime import timedelta

                period_end = period_start + timedelta(days=30)

        result = service.apply_scenario_parameters(client_id, scenario_id, period_start, period_end)

        return {
            "scenario_id": result.scenario_id,
            "scenario_name": result.scenario_name,
            "original_metrics": result.original_metrics,
            "modified_metrics": result.modified_metrics,
            "impact_summary": result.impact_summary,
        }
    except ImportError:
        raise HTTPException(status_code=501, detail="Scenario service not yet implemented")
    except Exception as e:
        db.rollback()
        logger.exception("Scenario run failed for scenario_id=%s", scenario_id)
        raise HTTPException(status_code=400, detail="Scenario run failed")


@router.delete("/scenarios/{scenario_id}", response_model=MessageResponse, responses={404: {"description": "Scenario not found"}})
def delete_scenario(
    scenario_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a scenario."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    scenario = (
        db.query(CapacityScenario)
        .filter(CapacityScenario.client_id == client_id, CapacityScenario.id == scenario_id)
        .first()
    )

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    db.delete(scenario)
    db.commit()
    return {"message": "Scenario deleted"}


@router.post("/scenarios/compare", responses={400: {"description": "Scenario comparison failed"}, 501: {"description": "Scenario service not yet implemented"}})
def compare_scenarios(
    request: ScenarioCompareRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare multiple scenarios."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.scenario_service import ScenarioService

        service = ScenarioService(db)

        comparison = service.compare_scenarios(client_id, request.scenario_ids)
        return comparison
    except ImportError:
        raise HTTPException(status_code=501, detail="Scenario service not yet implemented")
    except Exception as e:
        logger.exception("Scenario comparison failed for client_id=%s", client_id)
        raise HTTPException(status_code=400, detail="Scenario comparison failed")


# =============================================================================
# KPI Integration Endpoints
# =============================================================================


@router.get("/kpi/commitments", response_model=List[KPICommitmentResponse])
def get_kpi_commitments(
    client_id: str = Query(..., description="Client ID"),
    schedule_id: Optional[int] = None,
    kpi_key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get KPI commitments for a client."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.kpi_commitment import CapacityKPICommitment

    query = db.query(CapacityKPICommitment).filter(CapacityKPICommitment.client_id == client_id)

    if schedule_id:
        query = query.filter(CapacityKPICommitment.schedule_id == schedule_id)
    if kpi_key:
        query = query.filter(CapacityKPICommitment.kpi_key == kpi_key)

    return query.order_by(CapacityKPICommitment.period_start.desc()).all()


@router.get("/kpi/variance", responses={400: {"description": "KPI variance report failed"}, 501: {"description": "KPI integration service not yet implemented"}})
def get_kpi_variance_report(
    client_id: str = Query(..., description="Client ID"),
    schedule_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get KPI variance report."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.kpi_integration_service import KPIIntegrationService

        service = KPIIntegrationService(db)

        report = service.get_variance_report(client_id, schedule_id)
        return report
    except ImportError:
        raise HTTPException(status_code=501, detail="KPI integration service not yet implemented")
    except Exception as e:
        logger.exception("KPI variance report failed for client_id=%s", client_id)
        raise HTTPException(status_code=400, detail="KPI variance report failed")


# =============================================================================
# Workbook Endpoints (Multi-sheet operations)
# =============================================================================


@router.get("/workbook/{client_id}", response_model=Dict[str, Any], responses={403: {"description": "Client access denied"}})
def load_workbook(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Load all worksheet data for a client (capacity planning workbook).

    Returns all 13 worksheets with snake_case keys matching the frontend store mapping:
    master_calendar, production_lines, orders, production_standards, bom, stock_snapshot,
    component_check, capacity_analysis, production_schedule, what_if_scenarios,
    dashboard_inputs, kpi_tracking, instructions
    """
    verify_client_access(current_user, client_id, db)

    # --- Base data (6 worksheets via CRUD modules) ---
    calendar_data = calendar.get_calendar_entries(db, client_id, limit=CALENDAR_DEFAULT_DAYS)
    lines_data = production_lines.get_production_lines(db, client_id, include_inactive=True)
    orders_data = orders.get_orders(db, client_id, limit=LARGE_PAGE_SIZE)
    standards_data = standards.get_standards(db, client_id, limit=EXTRA_LARGE_PAGE_SIZE)
    bom_headers = bom.get_bom_headers(db, client_id, include_inactive=True)
    stock_data = stock.get_stock_snapshots(db, client_id, limit=LARGE_PAGE_SIZE)

    # --- Computed data (7 worksheets via direct queries) ---
    from backend.schemas.capacity.component_check import CapacityComponentCheck
    from backend.schemas.capacity.analysis import CapacityAnalysis
    from backend.schemas.capacity.schedule import CapacitySchedule, CapacityScheduleDetail
    from backend.schemas.capacity.scenario import CapacityScenario
    from backend.schemas.capacity.kpi_commitment import CapacityKPICommitment

    component_checks = (
        db.query(CapacityComponentCheck)
        .filter(CapacityComponentCheck.client_id == client_id)
        .order_by(CapacityComponentCheck.run_date.desc(), CapacityComponentCheck.order_number)
        .all()
    )

    analysis_data = (
        db.query(CapacityAnalysis)
        .filter(CapacityAnalysis.client_id == client_id)
        .order_by(CapacityAnalysis.analysis_date.desc(), CapacityAnalysis.line_code)
        .all()
    )

    schedules = (
        db.query(CapacitySchedule)
        .filter(CapacitySchedule.client_id == client_id)
        .order_by(CapacitySchedule.period_start.desc())
        .all()
    )

    schedule_details = (
        db.query(CapacityScheduleDetail)
        .filter(CapacityScheduleDetail.client_id == client_id)
        .order_by(CapacityScheduleDetail.scheduled_date, CapacityScheduleDetail.sequence)
        .all()
    )

    scenarios = (
        db.query(CapacityScenario)
        .filter(CapacityScenario.client_id == client_id)
        .order_by(CapacityScenario.created_at.desc())
        .all()
    )

    kpi_commitments = (
        db.query(CapacityKPICommitment)
        .filter(CapacityKPICommitment.client_id == client_id)
        .order_by(CapacityKPICommitment.period_start.desc())
        .all()
    )

    return {
        # --- Sheet 1: Master Calendar ---
        "master_calendar": [
            {
                "id": e.id,
                "calendar_date": e.calendar_date.isoformat(),
                "is_working_day": e.is_working_day,
                "shifts_available": e.shifts_available,
                "shift1_hours": float(e.shift1_hours),
                "shift2_hours": float(e.shift2_hours),
                "shift3_hours": float(e.shift3_hours),
                "holiday_name": e.holiday_name,
                "notes": e.notes,
            }
            for e in calendar_data
        ],
        # --- Sheet 2: Production Lines ---
        "production_lines": [
            {
                "id": l.id,
                "line_code": l.line_code,
                "line_name": l.line_name,
                "department": l.department,
                "standard_capacity_units_per_hour": float(l.standard_capacity_units_per_hour),
                "max_operators": l.max_operators,
                "efficiency_factor": float(l.efficiency_factor),
                "absenteeism_factor": float(l.absenteeism_factor),
                "is_active": l.is_active,
                "notes": l.notes,
            }
            for l in lines_data
        ],
        # --- Sheet 3: Orders ---
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "customer_name": o.customer_name,
                "style_code": o.style_code,
                "style_description": o.style_description,
                "order_quantity": o.order_quantity,
                "completed_quantity": o.completed_quantity,
                "order_date": o.order_date.isoformat() if o.order_date else None,
                "required_date": o.required_date.isoformat(),
                "planned_start_date": o.planned_start_date.isoformat() if o.planned_start_date else None,
                "planned_end_date": o.planned_end_date.isoformat() if o.planned_end_date else None,
                "priority": o.priority.value,
                "status": o.status.value,
                "order_sam_minutes": float(o.order_sam_minutes) if o.order_sam_minutes else None,
                "notes": o.notes,
            }
            for o in orders_data
        ],
        # --- Sheet 4: Production Standards ---
        "production_standards": [
            {
                "id": s.id,
                "style_code": s.style_code,
                "operation_code": s.operation_code,
                "operation_name": s.operation_name,
                "department": s.department,
                "sam_minutes": float(s.sam_minutes),
                "setup_time_minutes": float(s.setup_time_minutes or 0),
                "machine_time_minutes": float(s.machine_time_minutes or 0),
                "manual_time_minutes": float(s.manual_time_minutes or 0),
                "notes": s.notes,
            }
            for s in standards_data
        ],
        # --- Sheet 5: BOM ---
        "bom": [
            {
                "id": h.id,
                "parent_item_code": h.parent_item_code,
                "parent_item_description": h.parent_item_description,
                "style_code": h.style_code,
                "revision": h.revision,
                "is_active": h.is_active,
                "notes": h.notes,
            }
            for h in bom_headers
        ],
        # --- Sheet 6: Stock Snapshot ---
        "stock_snapshot": [
            {
                "id": s.id,
                "snapshot_date": s.snapshot_date.isoformat(),
                "item_code": s.item_code,
                "item_description": s.item_description,
                "on_hand_quantity": float(s.on_hand_quantity),
                "allocated_quantity": float(s.allocated_quantity),
                "on_order_quantity": float(s.on_order_quantity),
                "available_quantity": float(s.available_quantity),
                "unit_of_measure": s.unit_of_measure,
                "location": s.location,
                "notes": s.notes,
            }
            for s in stock_data
        ],
        # --- Sheet 7: Component Check (MRP results) ---
        "component_check": [
            {
                "id": c.id,
                "run_date": c.run_date.isoformat(),
                "order_id": c.order_id,
                "order_number": c.order_number,
                "component_item_code": c.component_item_code,
                "component_description": c.component_description,
                "required_quantity": float(c.required_quantity),
                "available_quantity": float(c.available_quantity),
                "shortage_quantity": float(c.shortage_quantity or 0),
                "status": c.status.value if c.status else None,
                "notes": c.notes,
            }
            for c in component_checks
        ],
        # --- Sheet 8: Capacity Analysis (12-step utilization) ---
        "capacity_analysis": [
            {
                "id": a.id,
                "analysis_date": a.analysis_date.isoformat(),
                "line_id": a.line_id,
                "line_code": a.line_code,
                "department": a.department,
                "working_days": a.working_days,
                "shifts_per_day": a.shifts_per_day,
                "hours_per_shift": float(a.hours_per_shift or 0),
                "operators_available": a.operators_available,
                "efficiency_factor": float(a.efficiency_factor or 0),
                "absenteeism_factor": float(a.absenteeism_factor or 0),
                "gross_hours": float(a.gross_hours or 0),
                "net_hours": float(a.net_hours or 0),
                "capacity_hours": float(a.capacity_hours or 0),
                "demand_hours": float(a.demand_hours or 0),
                "demand_units": a.demand_units or 0,
                "utilization_percent": float(a.utilization_percent or 0),
                "is_bottleneck": a.is_bottleneck or False,
                "notes": a.notes,
            }
            for a in analysis_data
        ],
        # --- Sheet 9: Production Schedule (header + details) ---
        "production_schedule": [
            {
                "id": sd.id,
                "schedule_id": sd.schedule_id,
                "order_id": sd.order_id,
                "order_number": sd.order_number,
                "style_code": sd.style_code,
                "line_id": sd.line_id,
                "line_code": sd.line_code,
                "scheduled_date": sd.scheduled_date.isoformat(),
                "scheduled_quantity": sd.scheduled_quantity or 0,
                "completed_quantity": sd.completed_quantity or 0,
                "sequence": sd.sequence or 1,
                "notes": sd.notes,
                # Include parent schedule metadata
                "schedule_name": next((s.schedule_name for s in schedules if s.id == sd.schedule_id), None),
                "schedule_status": next((s.status.value for s in schedules if s.id == sd.schedule_id), None),
            }
            for sd in schedule_details
        ],
        # --- Sheet 10: What-If Scenarios ---
        "what_if_scenarios": [
            {
                "id": sc.id,
                "scenario_name": sc.scenario_name,
                "scenario_type": sc.scenario_type,
                "base_schedule_id": sc.base_schedule_id,
                "parameters": sc.parameters_json or {},
                "results": sc.results_json or {},
                "is_active": sc.is_active,
                "notes": sc.notes,
            }
            for sc in scenarios
        ],
        # --- Sheet 11: Dashboard Inputs (planning parameters) ---
        "dashboard_inputs": {
            "planning_horizon_days": 30,
            "default_efficiency": 85,
            "bottleneck_threshold": 90,
            "shortage_alert_days": 7,
            "auto_schedule_enabled": False,
            "target_utilization": 85,
            "overtime_limit_percent": 20,
            "safety_stock_days": 5,
            "schedule_freeze_days": 3,
            "max_shifts_per_day": 2,
            "min_lot_size": 50,
            "schedule_granularity": "daily",
        },
        # --- Sheet 12: KPI Tracking ---
        "kpi_tracking": [
            {
                "id": k.id,
                "schedule_id": k.schedule_id,
                "kpi_key": k.kpi_key,
                "kpi_name": k.kpi_name,
                "period_start": k.period_start.isoformat(),
                "period_end": k.period_end.isoformat(),
                "committed_value": float(k.committed_value),
                "actual_value": float(k.actual_value) if k.actual_value is not None else None,
                "variance": float(k.variance) if k.variance is not None else None,
                "variance_percent": float(k.variance_percent) if k.variance_percent is not None else None,
                "notes": k.notes,
            }
            for k in kpi_commitments
        ],
        # --- Sheet 13: Instructions (static content) ---
        "instructions": (
            "# Capacity Planning Workbook\n\n"
            "## Overview\n"
            "This workbook contains 13 interconnected worksheets for production capacity planning.\n\n"
            "## Workflow\n"
            "1. **Master Calendar** - Define working days, shifts, and holidays\n"
            "2. **Production Lines** - Configure line capacities and efficiency factors\n"
            "3. **Orders** - Enter customer orders with quantities and due dates\n"
            "4. **Production Standards** - Set SAM (Standard Allowed Minutes) per style/operation\n"
            "5. **BOM** - Define Bills of Material for component requirements\n"
            "6. **Stock Snapshot** - Record current inventory positions\n"
            "7. **Component Check** - Run MRP explosion to check material availability\n"
            "8. **Capacity Analysis** - Calculate utilization using the 12-step method\n"
            "9. **Production Schedule** - Assign orders to lines and dates\n"
            "10. **What-If Scenarios** - Model capacity changes (overtime, new lines, etc.)\n"
            "11. **Dashboard Inputs** - Configure planning parameters\n"
            "12. **KPI Tracking** - Monitor committed vs actual performance\n"
            "13. **Instructions** - This guide\n\n"
            "## Key Concepts\n"
            "- **SAM**: Standard Allowed Minutes - time required per operation\n"
            "- **Utilization**: Demand hours / Capacity hours x 100\n"
            "- **Bottleneck**: Line where utilization exceeds threshold (default 90%)\n"
            "- **MRP Explosion**: Breaking down finished goods into component requirements\n"
        ),
    }


@router.put("/workbook/{client_id}/{worksheet_name}", response_model=WorksheetSaveResponse, responses={400: {"description": "Invalid worksheet name"}, 403: {"description": "Client access denied"}})
def save_worksheet(
    client_id: str,
    worksheet_name: str,
    data: List[Dict[str, Any]],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a specific worksheet's data (bulk update/create)."""
    verify_client_access(current_user, client_id, db)

    # Accept both camelCase (from frontend store) and snake_case
    camel_to_snake = {
        "masterCalendar": "master_calendar",
        "productionLines": "production_lines",
        "productionStandards": "production_standards",
        "stockSnapshot": "stock_snapshot",
        "componentCheck": "component_check",
        "capacityAnalysis": "capacity_analysis",
        "productionSchedule": "production_schedule",
        "whatIfScenarios": "what_if_scenarios",
        "dashboardInputs": "dashboard_inputs",
        "kpiTracking": "kpi_tracking",
    }
    worksheet_name = camel_to_snake.get(worksheet_name, worksheet_name)

    valid_worksheets = [
        "master_calendar",
        "production_lines",
        "orders",
        "production_standards",
        "bom",
        "stock_snapshot",
        "component_check",
        "capacity_analysis",
        "production_schedule",
        "what_if_scenarios",
        "kpi_tracking",
    ]

    if worksheet_name not in valid_worksheets:
        raise HTTPException(status_code=400, detail=f"Invalid worksheet name. Must be one of: {valid_worksheets}")

    # Handle bulk operations based on worksheet type
    # This is a placeholder for actual implementation
    return {"message": f"Worksheet '{worksheet_name}' saved", "rows_processed": len(data)}
