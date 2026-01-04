"""
Work Order Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class WorkOrderCreate(BaseModel):
    """Work order creation model"""
    work_order_id: str = Field(..., min_length=1, max_length=50, description="Unique work order ID")
    client_id: str = Field(..., min_length=1, max_length=50, description="Client ID")
    style_model: str = Field(..., min_length=1, max_length=100, description="Style/Model designation")
    planned_quantity: int = Field(..., gt=0, description="Planned production quantity")
    actual_quantity: Optional[int] = Field(default=0, ge=0, description="Actual quantity produced")
    planned_start_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    planned_ship_date: Optional[datetime] = Field(None, description="Required for OTD calculation")
    required_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = Field(None, description="Required for OTD calculation")
    ideal_cycle_time: Optional[Decimal] = Field(None, ge=0, description="Ideal cycle time in hours")
    calculated_cycle_time: Optional[Decimal] = Field(None, ge=0, description="Calculated from production")
    status: Optional[str] = Field(default="ACTIVE", pattern="^(ACTIVE|ON_HOLD|COMPLETED|REJECTED|CANCELLED)$")
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
    planned_start_date: Optional[datetime] = None
    actual_start_date: Optional[datetime] = None
    planned_ship_date: Optional[datetime] = None
    required_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    ideal_cycle_time: Optional[Decimal] = Field(None, ge=0)
    calculated_cycle_time: Optional[Decimal] = Field(None, ge=0)
    status: Optional[str] = Field(None, pattern="^(ACTIVE|ON_HOLD|COMPLETED|REJECTED|CANCELLED)$")
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
    planned_start_date: Optional[datetime]
    actual_start_date: Optional[datetime]
    planned_ship_date: Optional[datetime]
    required_date: Optional[datetime]
    actual_delivery_date: Optional[datetime]
    ideal_cycle_time: Optional[Decimal]
    calculated_cycle_time: Optional[Decimal]
    status: str
    priority: Optional[str]
    qc_approved: int
    qc_approved_by: Optional[int]
    qc_approved_date: Optional[datetime]
    rejection_reason: Optional[str]
    rejected_by: Optional[int]
    rejected_date: Optional[datetime]
    total_run_time_hours: Optional[Decimal]
    total_employees_assigned: Optional[int]
    notes: Optional[str]
    customer_po_number: Optional[str]
    internal_notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class WorkOrderWithMetrics(WorkOrderResponse):
    """Work order with calculated OTD and performance metrics"""
    is_on_time: Optional[bool] = None
    days_early_late: Optional[int] = None
    completion_percentage: Optional[float] = None
    efficiency_percentage: Optional[Decimal] = None
