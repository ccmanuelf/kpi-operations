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
from typing import List, Optional, Dict, Any
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access

# CRUD imports
from backend.crud.capacity import calendar, production_lines, orders, standards, bom, stock

# Schema imports for enums
from backend.schemas.capacity.orders import OrderPriority, OrderStatus
from backend.schemas.capacity.schedule import ScheduleStatus
from backend.schemas.capacity.component_check import ComponentStatus


# =============================================================================
# Main Router
# =============================================================================

router = APIRouter(
    prefix="/api/capacity",
    tags=["Capacity Planning"],
    responses={404: {"description": "Not found"}}
)


# =============================================================================
# Pydantic Models for Request/Response
# =============================================================================

# Calendar Models
class CalendarEntryCreate(BaseModel):
    calendar_date: date
    is_working_day: bool = True
    shifts_available: int = 1
    shift1_hours: float = 8.0
    shift2_hours: float = 0
    shift3_hours: float = 0
    holiday_name: Optional[str] = None
    notes: Optional[str] = None


class CalendarEntryUpdate(BaseModel):
    is_working_day: Optional[bool] = None
    shifts_available: Optional[int] = None
    shift1_hours: Optional[float] = None
    shift2_hours: Optional[float] = None
    shift3_hours: Optional[float] = None
    holiday_name: Optional[str] = None
    notes: Optional[str] = None


class CalendarEntryResponse(BaseModel):
    id: int
    client_id: str
    calendar_date: date
    is_working_day: bool
    shifts_available: int
    shift1_hours: float
    shift2_hours: float
    shift3_hours: float
    holiday_name: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


# Production Line Models
class ProductionLineCreate(BaseModel):
    line_code: str
    line_name: str
    department: Optional[str] = None
    standard_capacity_units_per_hour: float = 0
    max_operators: int = 10
    efficiency_factor: float = 0.85
    absenteeism_factor: float = 0.05
    is_active: bool = True
    notes: Optional[str] = None


class ProductionLineUpdate(BaseModel):
    line_name: Optional[str] = None
    department: Optional[str] = None
    standard_capacity_units_per_hour: Optional[float] = None
    max_operators: Optional[int] = None
    efficiency_factor: Optional[float] = None
    absenteeism_factor: Optional[float] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class ProductionLineResponse(BaseModel):
    id: int
    client_id: str
    line_code: str
    line_name: str
    department: Optional[str]
    standard_capacity_units_per_hour: float
    max_operators: int
    efficiency_factor: float
    absenteeism_factor: float
    is_active: bool
    notes: Optional[str]

    class Config:
        from_attributes = True


# Order Models
class OrderCreate(BaseModel):
    order_number: str
    style_code: str
    order_quantity: int
    required_date: date
    customer_name: Optional[str] = None
    style_description: Optional[str] = None
    order_date: Optional[date] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    priority: OrderPriority = OrderPriority.NORMAL
    status: OrderStatus = OrderStatus.DRAFT
    order_sam_minutes: Optional[float] = None
    notes: Optional[str] = None


class OrderUpdate(BaseModel):
    customer_name: Optional[str] = None
    style_description: Optional[str] = None
    order_quantity: Optional[int] = None
    order_date: Optional[date] = None
    required_date: Optional[date] = None
    planned_start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    priority: Optional[OrderPriority] = None
    status: Optional[OrderStatus] = None
    order_sam_minutes: Optional[float] = None
    notes: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    client_id: str
    order_number: str
    customer_name: Optional[str]
    style_code: str
    style_description: Optional[str]
    order_quantity: int
    completed_quantity: int
    order_date: Optional[date]
    required_date: date
    planned_start_date: Optional[date]
    planned_end_date: Optional[date]
    priority: OrderPriority
    status: OrderStatus
    order_sam_minutes: Optional[float]
    notes: Optional[str]

    class Config:
        from_attributes = True


# Standards Models
class StandardCreate(BaseModel):
    style_code: str
    operation_code: str
    sam_minutes: float
    operation_name: Optional[str] = None
    department: Optional[str] = None
    setup_time_minutes: float = 0
    machine_time_minutes: float = 0
    manual_time_minutes: float = 0
    notes: Optional[str] = None


class StandardUpdate(BaseModel):
    operation_name: Optional[str] = None
    department: Optional[str] = None
    sam_minutes: Optional[float] = None
    setup_time_minutes: Optional[float] = None
    machine_time_minutes: Optional[float] = None
    manual_time_minutes: Optional[float] = None
    notes: Optional[str] = None


class StandardResponse(BaseModel):
    id: int
    client_id: str
    style_code: str
    operation_code: str
    operation_name: Optional[str]
    department: Optional[str]
    sam_minutes: float
    setup_time_minutes: float
    machine_time_minutes: float
    manual_time_minutes: float
    notes: Optional[str]

    class Config:
        from_attributes = True


# BOM Models
class BOMHeaderCreate(BaseModel):
    parent_item_code: str
    parent_item_description: Optional[str] = None
    style_code: Optional[str] = None
    revision: str = "1.0"
    is_active: bool = True
    notes: Optional[str] = None


class BOMHeaderUpdate(BaseModel):
    parent_item_description: Optional[str] = None
    style_code: Optional[str] = None
    revision: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class BOMDetailCreate(BaseModel):
    component_item_code: str
    quantity_per: float = 1.0
    component_description: Optional[str] = None
    unit_of_measure: str = "EA"
    waste_percentage: float = 0
    component_type: Optional[str] = None
    notes: Optional[str] = None


class BOMDetailUpdate(BaseModel):
    component_description: Optional[str] = None
    quantity_per: Optional[float] = None
    unit_of_measure: Optional[str] = None
    waste_percentage: Optional[float] = None
    component_type: Optional[str] = None
    notes: Optional[str] = None


class BOMHeaderResponse(BaseModel):
    id: int
    client_id: str
    parent_item_code: str
    parent_item_description: Optional[str]
    style_code: Optional[str]
    revision: str
    is_active: bool
    notes: Optional[str]

    class Config:
        from_attributes = True


class BOMDetailResponse(BaseModel):
    id: int
    header_id: int
    client_id: str
    component_item_code: str
    component_description: Optional[str]
    quantity_per: float
    unit_of_measure: str
    waste_percentage: float
    component_type: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


class BOMExplosionRequest(BaseModel):
    parent_item_code: str
    quantity: float


class BOMExplosionResponse(BaseModel):
    parent_item_code: str
    quantity_requested: float
    components: List[Dict[str, Any]]
    total_components: int


# Stock Models
class StockSnapshotCreate(BaseModel):
    snapshot_date: date
    item_code: str
    on_hand_quantity: float = 0
    allocated_quantity: float = 0
    on_order_quantity: float = 0
    item_description: Optional[str] = None
    unit_of_measure: str = "EA"
    location: Optional[str] = None
    notes: Optional[str] = None


class StockSnapshotUpdate(BaseModel):
    on_hand_quantity: Optional[float] = None
    allocated_quantity: Optional[float] = None
    on_order_quantity: Optional[float] = None
    item_description: Optional[str] = None
    unit_of_measure: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None


class StockSnapshotResponse(BaseModel):
    id: int
    client_id: str
    snapshot_date: date
    item_code: str
    item_description: Optional[str]
    on_hand_quantity: float
    allocated_quantity: float
    on_order_quantity: float
    available_quantity: float
    unit_of_measure: str
    location: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


# Component Check Models
class ComponentCheckRequest(BaseModel):
    order_ids: Optional[List[int]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ComponentCheckResult(BaseModel):
    order_id: int
    order_number: str
    component_item_code: str
    component_description: Optional[str]
    required_quantity: float
    available_quantity: float
    shortage_quantity: float
    status: str
    coverage_percent: float


# Analysis Models
class AnalysisRequest(BaseModel):
    start_date: date
    end_date: date
    line_ids: Optional[List[int]] = None
    department: Optional[str] = None


class AnalysisResult(BaseModel):
    line_id: int
    line_code: str
    department: Optional[str]
    analysis_date: date
    working_days: int
    gross_hours: float
    capacity_hours: float
    demand_hours: float
    utilization_percent: float
    is_bottleneck: bool


# Schedule Models
class ScheduleCreate(BaseModel):
    schedule_name: str
    period_start: date
    period_end: date
    notes: Optional[str] = None


class ScheduleUpdate(BaseModel):
    schedule_name: Optional[str] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    status: Optional[ScheduleStatus] = None
    notes: Optional[str] = None


class ScheduleDetailCreate(BaseModel):
    order_id: Optional[int] = None
    line_id: Optional[int] = None
    scheduled_date: date
    scheduled_quantity: int = 0
    sequence: int = 1
    notes: Optional[str] = None


class ScheduleResponse(BaseModel):
    id: int
    client_id: str
    schedule_name: str
    period_start: date
    period_end: date
    status: ScheduleStatus
    committed_at: Optional[date]
    committed_by: Optional[int]
    notes: Optional[str]

    class Config:
        from_attributes = True


class ScheduleCommitRequest(BaseModel):
    kpi_commitments: Dict[str, float] = Field(
        default_factory=dict,
        description="KPI commitments e.g. {'efficiency': 85.0, 'quality': 98.5}"
    )


# Scenario Models
class ScenarioCreate(BaseModel):
    scenario_name: str
    scenario_type: Optional[str] = None
    base_schedule_id: Optional[int] = None
    parameters: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ScenarioUpdate(BaseModel):
    scenario_name: Optional[str] = None
    scenario_type: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class ScenarioResponse(BaseModel):
    id: int
    client_id: str
    scenario_name: str
    scenario_type: Optional[str]
    base_schedule_id: Optional[int]
    parameters_json: Optional[Dict[str, Any]]
    results_json: Optional[Dict[str, Any]]
    is_active: bool
    notes: Optional[str]

    class Config:
        from_attributes = True


class ScenarioCompareRequest(BaseModel):
    scenario_ids: List[int]


# KPI Models
class KPICommitmentResponse(BaseModel):
    id: int
    client_id: str
    schedule_id: int
    kpi_key: str
    kpi_name: Optional[str]
    period_start: date
    period_end: date
    committed_value: float
    actual_value: Optional[float]
    variance: Optional[float]
    variance_percent: Optional[float]

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
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
):
    """Create a new calendar entry."""
    verify_client_access(current_user, client_id, db)
    return calendar.create_calendar_entry(
        db, client_id,
        entry.calendar_date,
        entry.is_working_day,
        entry.shifts_available,
        entry.shift1_hours,
        entry.shift2_hours,
        entry.shift3_hours,
        entry.holiday_name,
        entry.notes
    )


@router.get("/calendar/{entry_id}", response_model=CalendarEntryResponse)
def get_calendar(
    entry_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific calendar entry."""
    verify_client_access(current_user, client_id, db)
    entry = calendar.get_calendar_entry(db, client_id, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return entry


@router.put("/calendar/{entry_id}", response_model=CalendarEntryResponse)
def update_calendar(
    entry_id: int,
    update: CalendarEntryUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a calendar entry."""
    verify_client_access(current_user, client_id, db)
    entry = calendar.update_calendar_entry(
        db, client_id, entry_id,
        **update.model_dump(exclude_unset=True)
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return entry


@router.delete("/calendar/{entry_id}")
def delete_calendar(
    entry_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
):
    """Create a new production line."""
    verify_client_access(current_user, client_id, db)
    return production_lines.create_production_line(
        db, client_id,
        line.line_code,
        line.line_name,
        line.department,
        line.standard_capacity_units_per_hour,
        line.max_operators,
        line.efficiency_factor,
        line.absenteeism_factor,
        line.is_active,
        line.notes
    )


@router.get("/lines/{line_id}", response_model=ProductionLineResponse)
def get_production_line(
    line_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific production line."""
    verify_client_access(current_user, client_id, db)
    line = production_lines.get_production_line(db, client_id, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Production line not found")
    return line


@router.put("/lines/{line_id}", response_model=ProductionLineResponse)
def update_production_line(
    line_id: int,
    update: ProductionLineUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a production line."""
    verify_client_access(current_user, client_id, db)
    line = production_lines.update_production_line(
        db, client_id, line_id,
        **update.model_dump(exclude_unset=True)
    )
    if not line:
        raise HTTPException(status_code=404, detail="Production line not found")
    return line


@router.delete("/lines/{line_id}")
def delete_production_line(
    line_id: int,
    client_id: str = Query(..., description="Client ID"),
    soft_delete: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get orders for a client."""
    verify_client_access(current_user, client_id, db)
    return orders.get_orders(db, client_id, skip, limit, status_filter)


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order: OrderCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new order."""
    verify_client_access(current_user, client_id, db)
    return orders.create_order(
        db, client_id,
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
        order.notes
    )


@router.get("/orders/scheduling", response_model=List[OrderResponse])
def get_orders_for_scheduling(
    client_id: str = Query(..., description="Client ID"),
    start_date: date = Query(..., description="Schedule period start"),
    end_date: date = Query(..., description="Schedule period end"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get confirmed orders ready for scheduling within a date range."""
    verify_client_access(current_user, client_id, db)
    return orders.get_orders_for_scheduling(db, client_id, start_date, end_date)


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific order."""
    verify_client_access(current_user, client_id, db)
    order = orders.get_order(db, client_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.put("/orders/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: int,
    update: OrderUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an order."""
    verify_client_access(current_user, client_id, db)
    order = orders.update_order(
        db, client_id, order_id,
        **update.model_dump(exclude_unset=True)
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    new_status: OrderStatus,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update order status."""
    verify_client_access(current_user, client_id, db)
    order = orders.update_order_status(db, client_id, order_id, new_status)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.delete("/orders/{order_id}")
def delete_order(
    order_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get production standards for a client."""
    verify_client_access(current_user, client_id, db)
    return standards.get_standards(db, client_id, skip, limit, department)


@router.post("/standards", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
def create_standard(
    standard: StandardCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new production standard."""
    verify_client_access(current_user, client_id, db)
    return standards.create_standard(
        db, client_id,
        standard.style_code,
        standard.operation_code,
        standard.sam_minutes,
        standard.operation_name,
        standard.department,
        standard.setup_time_minutes,
        standard.machine_time_minutes,
        standard.manual_time_minutes,
        standard.notes
    )


@router.get("/standards/style/{style_code}", response_model=List[StandardResponse])
def get_standards_by_style(
    style_code: str,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all standards for a specific style."""
    verify_client_access(current_user, client_id, db)
    return standards.get_standards_by_style(db, client_id, style_code)


@router.get("/standards/style/{style_code}/total-sam")
def get_total_sam_for_style(
    style_code: str,
    client_id: str = Query(..., description="Client ID"),
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get total SAM minutes for a style."""
    verify_client_access(current_user, client_id, db)
    total = standards.get_total_sam_for_style(db, client_id, style_code, department)
    return {"style_code": style_code, "total_sam_minutes": total, "department": department}


@router.get("/standards/{standard_id}", response_model=StandardResponse)
def get_standard(
    standard_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific production standard."""
    verify_client_access(current_user, client_id, db)
    standard = standards.get_standard(db, client_id, standard_id)
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    return standard


@router.put("/standards/{standard_id}", response_model=StandardResponse)
def update_standard(
    standard_id: int,
    update: StandardUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a production standard."""
    verify_client_access(current_user, client_id, db)
    standard = standards.update_standard(
        db, client_id, standard_id,
        **update.model_dump(exclude_unset=True)
    )
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    return standard


@router.delete("/standards/{standard_id}")
def delete_standard(
    standard_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get BOM headers for a client."""
    verify_client_access(current_user, client_id, db)
    return bom.get_bom_headers(db, client_id, skip, limit, include_inactive)


@router.post("/bom", response_model=BOMHeaderResponse, status_code=status.HTTP_201_CREATED)
def create_bom_header(
    header: BOMHeaderCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new BOM header."""
    verify_client_access(current_user, client_id, db)
    return bom.create_bom_header(
        db, client_id,
        header.parent_item_code,
        header.parent_item_description,
        header.style_code,
        header.revision,
        header.is_active,
        header.notes
    )


@router.get("/bom/{header_id}", response_model=BOMHeaderResponse)
def get_bom_header(
    header_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific BOM header."""
    verify_client_access(current_user, client_id, db)
    header = bom.get_bom_header(db, client_id, header_id)
    if not header:
        raise HTTPException(status_code=404, detail="BOM header not found")
    return header


@router.put("/bom/{header_id}", response_model=BOMHeaderResponse)
def update_bom_header(
    header_id: int,
    update: BOMHeaderUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a BOM header."""
    verify_client_access(current_user, client_id, db)
    header = bom.update_bom_header(
        db, client_id, header_id,
        **update.model_dump(exclude_unset=True)
    )
    if not header:
        raise HTTPException(status_code=404, detail="BOM header not found")
    return header


@router.delete("/bom/{header_id}")
def delete_bom_header(
    header_id: int,
    client_id: str = Query(..., description="Client ID"),
    cascade: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
):
    """Add a component to a BOM."""
    verify_client_access(current_user, client_id, db)
    return bom.create_bom_detail(
        db, client_id, header_id,
        detail.component_item_code,
        detail.quantity_per,
        detail.component_description,
        detail.unit_of_measure,
        detail.waste_percentage,
        detail.component_type,
        detail.notes
    )


@router.put("/bom/details/{detail_id}", response_model=BOMDetailResponse)
def update_bom_detail(
    detail_id: int,
    update: BOMDetailUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a BOM detail."""
    verify_client_access(current_user, client_id, db)
    detail = bom.update_bom_detail(
        db, client_id, detail_id,
        **update.model_dump(exclude_unset=True)
    )
    if not detail:
        raise HTTPException(status_code=404, detail="BOM detail not found")
    return detail


@router.delete("/bom/details/{detail_id}")
def delete_bom_detail(
    detail_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a BOM detail."""
    verify_client_access(current_user, client_id, db)
    if not bom.delete_bom_detail(db, client_id, detail_id):
        raise HTTPException(status_code=404, detail="BOM detail not found")
    return {"message": "BOM detail deleted"}


@router.post("/bom/explode", response_model=BOMExplosionResponse)
def explode_bom(
    request: BOMExplosionRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
                    "component_type": c.component_type
                }
                for c in result.components
            ],
            "total_components": result.total_components
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Stock Endpoints
# =============================================================================

@router.get("/stock", response_model=List[StockSnapshotResponse])
def list_stock_snapshots(
    client_id: str = Query(..., description="Client ID"),
    snapshot_date: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get stock snapshots for a client."""
    verify_client_access(current_user, client_id, db)
    return stock.get_stock_snapshots(db, client_id, skip, limit, snapshot_date)


@router.post("/stock", response_model=StockSnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_stock_snapshot(
    snapshot: StockSnapshotCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new stock snapshot."""
    verify_client_access(current_user, client_id, db)
    return stock.create_stock_snapshot(
        db, client_id,
        snapshot.snapshot_date,
        snapshot.item_code,
        snapshot.on_hand_quantity,
        snapshot.allocated_quantity,
        snapshot.on_order_quantity,
        snapshot.item_description,
        snapshot.unit_of_measure,
        snapshot.location,
        snapshot.notes
    )


@router.get("/stock/item/{item_code}/latest", response_model=StockSnapshotResponse)
def get_latest_stock_for_item(
    item_code: str,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the most recent stock snapshot for an item."""
    verify_client_access(current_user, client_id, db)
    snapshot = stock.get_latest_stock(db, client_id, item_code)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return snapshot


@router.get("/stock/item/{item_code}/available")
def get_available_stock_for_item(
    item_code: str,
    client_id: str = Query(..., description="Client ID"),
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
):
    """Get items with shortage (zero or negative available quantity)."""
    verify_client_access(current_user, client_id, db)
    return stock.get_shortage_items(db, client_id, snapshot_date)


@router.get("/stock/{snapshot_id}", response_model=StockSnapshotResponse)
def get_stock_snapshot(
    snapshot_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific stock snapshot."""
    verify_client_access(current_user, client_id, db)
    snapshot = stock.get_stock_snapshot(db, client_id, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return snapshot


@router.put("/stock/{snapshot_id}", response_model=StockSnapshotResponse)
def update_stock_snapshot(
    snapshot_id: int,
    update: StockSnapshotUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a stock snapshot."""
    verify_client_access(current_user, client_id, db)
    snapshot = stock.update_stock_snapshot(
        db, client_id, snapshot_id,
        **update.model_dump(exclude_unset=True)
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return snapshot


@router.delete("/stock/{snapshot_id}")
def delete_stock_snapshot(
    snapshot_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a stock snapshot."""
    verify_client_access(current_user, client_id, db)
    if not stock.delete_stock_snapshot(db, client_id, snapshot_id):
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return {"message": "Stock snapshot deleted"}


# =============================================================================
# Component Check (MRP) Endpoints
# =============================================================================

@router.post("/component-check/run", response_model=List[ComponentCheckResult])
def run_component_check(
    request: ComponentCheckRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
            results = service.check_components_for_period(
                client_id, request.start_date, request.end_date
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Must provide either order_ids or both start_date and end_date"
            )

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
                "coverage_percent": r.coverage_percent()
            }
            for r in results
        ]
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="MRP service not yet implemented"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/component-check/shortages", response_model=List[ComponentCheckResult])
def get_component_shortages(
    client_id: str = Query(..., description="Client ID"),
    run_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get component shortages from the most recent check run."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.component_check import CapacityComponentCheck, ComponentStatus

    query = db.query(CapacityComponentCheck).filter(
        CapacityComponentCheck.client_id == client_id,
        CapacityComponentCheck.status != ComponentStatus.OK
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
            "coverage_percent": r.coverage_percent()
        }
        for r in results
    ]


# =============================================================================
# Capacity Analysis Endpoints
# =============================================================================

@router.post("/analysis/calculate", response_model=List[AnalysisResult])
def run_capacity_analysis(
    request: AnalysisRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Run capacity analysis for lines within a date range."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.analysis_service import CapacityAnalysisService
        service = CapacityAnalysisService(db)

        results = service.analyze_capacity(
            client_id,
            request.start_date,
            request.end_date,
            request.line_ids,
            request.department
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
                "is_bottleneck": r.is_bottleneck
            }
            for r in results
        ]
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Capacity analysis service not yet implemented"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/analysis/bottlenecks", response_model=List[AnalysisResult])
def get_bottleneck_lines(
    client_id: str = Query(..., description="Client ID"),
    analysis_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get lines identified as bottlenecks."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.analysis import CapacityAnalysis

    query = db.query(CapacityAnalysis).filter(
        CapacityAnalysis.client_id == client_id,
        CapacityAnalysis.is_bottleneck == True
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
            "is_bottleneck": r.is_bottleneck
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
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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
        notes=schedule.notes
    )
    db.add(new_schedule)
    db.commit()
    db.refresh(new_schedule)
    return new_schedule


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(
    schedule_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific schedule."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.schedule import CapacitySchedule

    schedule = db.query(CapacitySchedule).filter(
        CapacitySchedule.client_id == client_id,
        CapacitySchedule.id == schedule_id
    ).first()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.post("/schedules/generate", response_model=ScheduleResponse)
def generate_schedule(
    schedule_name: str,
    start_date: date = Query(..., description="Schedule period start"),
    end_date: date = Query(..., description="Schedule period end"),
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Auto-generate a schedule from confirmed orders."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.scheduling_service import SchedulingService
        service = SchedulingService(db)

        schedule = service.generate_schedule(
            client_id, schedule_name, start_date, end_date
        )
        return schedule
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Scheduling service not yet implemented"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/schedules/{schedule_id}/commit", response_model=ScheduleResponse)
def commit_schedule(
    schedule_id: int,
    request: ScheduleCommitRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Commit a schedule, locking KPI targets."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.schedule import CapacitySchedule, ScheduleStatus
    from datetime import date as date_type

    schedule = db.query(CapacitySchedule).filter(
        CapacitySchedule.client_id == client_id,
        CapacitySchedule.id == schedule_id
    ).first()

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
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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
        notes=scenario.notes
    )
    db.add(new_scenario)
    db.commit()
    db.refresh(new_scenario)
    return new_scenario


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific scenario."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    scenario = db.query(CapacityScenario).filter(
        CapacityScenario.client_id == client_id,
        CapacityScenario.id == scenario_id
    ).first()

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


class ScenarioRunRequest(BaseModel):
    period_start: Optional[date] = None
    period_end: Optional[date] = None


@router.post("/scenarios/{scenario_id}/run")
def run_scenario(
    scenario_id: int,
    request: ScenarioRunRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Run/evaluate a scenario by applying its parameters and analyzing impact."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    scenario = db.query(CapacityScenario).filter(
        CapacityScenario.client_id == client_id,
        CapacityScenario.id == scenario_id
    ).first()

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
                base_schedule = db.query(CapacitySchedule).filter(
                    CapacitySchedule.id == scenario.base_schedule_id
                ).first()
                if base_schedule:
                    period_start = period_start or base_schedule.period_start
                    period_end = period_end or base_schedule.period_end

            if not period_start:
                from datetime import timedelta
                period_start = date.today()
            if not period_end:
                from datetime import timedelta
                period_end = period_start + timedelta(days=30)

        result = service.apply_scenario_parameters(
            client_id, scenario_id, period_start, period_end
        )

        return {
            "scenario_id": result.scenario_id,
            "scenario_name": result.scenario_name,
            "original_metrics": result.original_metrics,
            "modified_metrics": result.modified_metrics,
            "impact_summary": result.impact_summary
        }
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Scenario service not yet implemented"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(
    scenario_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a scenario."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.scenario import CapacityScenario

    scenario = db.query(CapacityScenario).filter(
        CapacityScenario.client_id == client_id,
        CapacityScenario.id == scenario_id
    ).first()

    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    db.delete(scenario)
    db.commit()
    return {"message": "Scenario deleted"}


@router.post("/scenarios/compare")
def compare_scenarios(
    request: ScenarioCompareRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compare multiple scenarios."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.scenario_service import ScenarioService
        service = ScenarioService(db)

        comparison = service.compare_scenarios(client_id, request.scenario_ids)
        return comparison
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Scenario service not yet implemented"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# KPI Integration Endpoints
# =============================================================================

@router.get("/kpi/commitments", response_model=List[KPICommitmentResponse])
def get_kpi_commitments(
    client_id: str = Query(..., description="Client ID"),
    schedule_id: Optional[int] = None,
    kpi_key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get KPI commitments for a client."""
    verify_client_access(current_user, client_id, db)

    from backend.schemas.capacity.kpi_commitment import CapacityKPICommitment

    query = db.query(CapacityKPICommitment).filter(
        CapacityKPICommitment.client_id == client_id
    )

    if schedule_id:
        query = query.filter(CapacityKPICommitment.schedule_id == schedule_id)
    if kpi_key:
        query = query.filter(CapacityKPICommitment.kpi_key == kpi_key)

    return query.order_by(CapacityKPICommitment.period_start.desc()).all()


@router.get("/kpi/variance")
def get_kpi_variance_report(
    client_id: str = Query(..., description="Client ID"),
    schedule_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get KPI variance report."""
    verify_client_access(current_user, client_id, db)

    try:
        from backend.services.capacity.kpi_integration_service import KPIIntegrationService
        service = KPIIntegrationService(db)

        report = service.get_variance_report(client_id, schedule_id)
        return report
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="KPI integration service not yet implemented"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Workbook Endpoints (Multi-sheet operations)
# =============================================================================

@router.get("/workbook/{client_id}")
def load_workbook(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Load all worksheet data for a client (capacity planning workbook)."""
    verify_client_access(current_user, client_id, db)

    # Load all data for frontend
    calendar_data = calendar.get_calendar_entries(db, client_id, limit=365)
    lines_data = production_lines.get_production_lines(db, client_id, include_inactive=True)
    orders_data = orders.get_orders(db, client_id, limit=500)
    standards_data = standards.get_standards(db, client_id, limit=1000)
    bom_headers = bom.get_bom_headers(db, client_id, include_inactive=True)
    stock_data = stock.get_stock_snapshots(db, client_id, limit=500)

    return {
        "masterCalendar": [
            {
                "id": e.id,
                "calendar_date": e.calendar_date.isoformat(),
                "is_working_day": e.is_working_day,
                "shifts_available": e.shifts_available,
                "shift1_hours": float(e.shift1_hours),
                "shift2_hours": float(e.shift2_hours),
                "shift3_hours": float(e.shift3_hours),
                "holiday_name": e.holiday_name,
                "notes": e.notes
            }
            for e in calendar_data
        ],
        "productionLines": [
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
                "notes": l.notes
            }
            for l in lines_data
        ],
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
                "notes": o.notes
            }
            for o in orders_data
        ],
        "productionStandards": [
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
                "notes": s.notes
            }
            for s in standards_data
        ],
        "bom": [
            {
                "id": h.id,
                "parent_item_code": h.parent_item_code,
                "parent_item_description": h.parent_item_description,
                "style_code": h.style_code,
                "revision": h.revision,
                "is_active": h.is_active,
                "notes": h.notes
            }
            for h in bom_headers
        ],
        "stockSnapshot": [
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
                "notes": s.notes
            }
            for s in stock_data
        ]
    }


@router.put("/workbook/{client_id}/{worksheet_name}")
def save_worksheet(
    client_id: str,
    worksheet_name: str,
    data: List[Dict[str, Any]],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Save a specific worksheet's data (bulk update/create)."""
    verify_client_access(current_user, client_id, db)

    valid_worksheets = [
        "masterCalendar", "productionLines", "orders",
        "productionStandards", "bom", "stockSnapshot"
    ]

    if worksheet_name not in valid_worksheets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid worksheet name. Must be one of: {valid_worksheets}"
        )

    # Handle bulk operations based on worksheet type
    # This is a placeholder for actual implementation
    return {
        "message": f"Worksheet '{worksheet_name}' saved",
        "rows_processed": len(data)
    }
