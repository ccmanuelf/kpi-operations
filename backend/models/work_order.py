"""
Work Order Pydantic models for request/response validation
Implements Phase 10: Flexible Workflow Foundation
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from enum import Enum


class WorkOrderStatusEnum(str, Enum):
    """Work order status options for validation"""
    RECEIVED = "RECEIVED"
    RELEASED = "RELEASED"
    DEMOTED = "DEMOTED"
    ACTIVE = "ACTIVE"           # Legacy alias for IN_PROGRESS
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    SHIPPED = "SHIPPED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


# Valid status pattern for regex validation
VALID_STATUS_PATTERN = "^(RECEIVED|RELEASED|DEMOTED|ACTIVE|IN_PROGRESS|ON_HOLD|COMPLETED|SHIPPED|CLOSED|REJECTED|CANCELLED)$"


class WorkOrderCreate(BaseModel):
    """Work order creation model"""
    work_order_id: str = Field(..., min_length=1, max_length=50, description="Unique work order ID")
    client_id: str = Field(..., min_length=1, max_length=50, description="Client ID")
    style_model: str = Field(..., min_length=1, max_length=100, description="Style/Model designation")
    planned_quantity: int = Field(..., gt=0, description="Planned production quantity")
    actual_quantity: Optional[int] = Field(default=0, ge=0, description="Actual quantity produced")

    # Workflow lifecycle dates (Phase 10)
    received_date: Optional[datetime] = Field(None, description="When order was received/acknowledged")
    planned_date: Optional[datetime] = Field(None, description="When work is planned to start")
    expected_date: Optional[datetime] = Field(None, description="Expected completion date")
    dispatch_date: Optional[datetime] = Field(None, description="When released/dispatched to shopfloor")
    shipped_date: Optional[datetime] = Field(None, description="When shipped to client")
    closure_date: Optional[datetime] = Field(None, description="When formally closed")
    closed_by: Optional[int] = Field(None, description="User ID who closed the order")

    # Legacy date fields (OTD calculation)
    planned_start_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    planned_ship_date: Optional[datetime] = Field(None, description="Required for OTD calculation")
    required_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = Field(None, description="Required for OTD calculation")

    ideal_cycle_time: Optional[Decimal] = Field(None, ge=0, description="Ideal cycle time in hours")
    calculated_cycle_time: Optional[Decimal] = Field(None, ge=0, description="Calculated from production")

    # Status with expanded options (Phase 10)
    status: Optional[str] = Field(default="RECEIVED", pattern=VALID_STATUS_PATTERN)
    previous_status: Optional[str] = Field(None, pattern=VALID_STATUS_PATTERN, description="For ON_HOLD resume tracking")
    priority: Optional[str] = Field(None, pattern="^(HIGH|MEDIUM|LOW)$")

    qc_approved: Optional[int] = Field(default=0, ge=0, le=1, description="Boolean: 0=not approved, 1=approved")
    qc_approved_by: Optional[int] = None
    qc_approved_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    rejected_by: Optional[int] = None
    rejected_date: Optional[datetime] = None
    total_run_time_hours: Optional[Decimal] = Field(None, ge=0)
    total_employees_assigned: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    customer_po_number: Optional[str] = Field(None, max_length=100)
    internal_notes: Optional[str] = None


class WorkOrderUpdate(BaseModel):
    """Work order update model (all fields optional)"""
    style_model: Optional[str] = Field(None, min_length=1, max_length=100)
    planned_quantity: Optional[int] = Field(None, gt=0)
    actual_quantity: Optional[int] = Field(None, ge=0)

    # Workflow lifecycle dates (Phase 10)
    received_date: Optional[datetime] = None
    planned_date: Optional[datetime] = None
    expected_date: Optional[datetime] = None
    dispatch_date: Optional[datetime] = None
    shipped_date: Optional[datetime] = None
    closure_date: Optional[datetime] = None
    closed_by: Optional[int] = None

    # Legacy date fields
    planned_start_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    planned_ship_date: Optional[datetime] = None
    required_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None

    ideal_cycle_time: Optional[Decimal] = Field(None, ge=0)
    calculated_cycle_time: Optional[Decimal] = Field(None, ge=0)

    # Status with expanded options (Phase 10)
    status: Optional[str] = Field(None, pattern=VALID_STATUS_PATTERN)
    previous_status: Optional[str] = Field(None, pattern=VALID_STATUS_PATTERN)
    priority: Optional[str] = Field(None, pattern="^(HIGH|MEDIUM|LOW)$")

    qc_approved: Optional[int] = Field(None, ge=0, le=1)
    qc_approved_by: Optional[int] = None
    qc_approved_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    rejected_by: Optional[int] = None
    rejected_date: Optional[datetime] = None
    total_run_time_hours: Optional[Decimal] = Field(None, ge=0)
    total_employees_assigned: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    customer_po_number: Optional[str] = Field(None, max_length=100)
    internal_notes: Optional[str] = None


class WorkOrderResponse(BaseModel):
    """Work order response model"""
    work_order_id: str
    client_id: str
    style_model: str
    planned_quantity: int
    actual_quantity: int

    # Workflow lifecycle dates (Phase 10)
    received_date: Optional[datetime] = None
    planned_date: Optional[datetime] = None
    expected_date: Optional[datetime] = None
    dispatch_date: Optional[datetime] = None
    shipped_date: Optional[datetime] = None
    closure_date: Optional[datetime] = None
    closed_by: Optional[int] = None

    # Legacy date fields
    planned_start_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    planned_ship_date: Optional[datetime] = None
    required_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None

    ideal_cycle_time: Optional[Decimal] = None
    calculated_cycle_time: Optional[Decimal] = None

    # Status fields (Phase 10)
    status: str
    previous_status: Optional[str] = None
    priority: Optional[str] = None

    qc_approved: int = 0
    qc_approved_by: Optional[int] = None
    qc_approved_date: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    rejected_by: Optional[int] = None
    rejected_date: Optional[datetime] = None
    total_run_time_hours: Optional[Decimal] = None
    total_employees_assigned: Optional[int] = None
    notes: Optional[str] = None
    customer_po_number: Optional[str] = None
    internal_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkOrderWithMetrics(WorkOrderResponse):
    """Work order with calculated OTD and performance metrics"""
    is_on_time: Optional[bool] = None
    days_early_late: Optional[int] = None
    completion_percentage: Optional[float] = None
    efficiency_percentage: Optional[Decimal] = None
