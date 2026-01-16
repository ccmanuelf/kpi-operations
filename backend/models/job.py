"""
Pydantic models for JOB (Work Order Line Items) API requests/responses
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class JobBase(BaseModel):
    """Base job fields"""
    work_order_id: str = Field(..., description="Parent work order ID")
    client_id_fk: str = Field(..., description="Client ID for multi-tenant isolation")
    operation_name: str = Field(..., description="Operation name")
    operation_code: Optional[str] = Field(None, description="Operation code")
    sequence_number: int = Field(..., description="Order within work order")
    part_number: Optional[str] = Field(None, description="Part number")
    part_description: Optional[str] = Field(None, description="Part description")
    planned_quantity: Optional[int] = Field(None, description="Planned quantity")
    completed_quantity: Optional[int] = Field(0, description="Completed quantity")
    quantity_scrapped: Optional[int] = Field(0, description="Quantity scrapped for quality metrics")
    planned_hours: Optional[Decimal] = Field(None, description="Planned hours")
    actual_hours: Optional[Decimal] = Field(None, description="Actual hours")
    is_completed: int = Field(0, description="Completion status (0/1)")
    completed_date: Optional[datetime] = Field(None, description="Completion date")
    assigned_employee_id: Optional[int] = Field(None, description="Assigned employee ID")
    assigned_shift_id: Optional[int] = Field(None, description="Assigned shift ID")
    notes: Optional[str] = Field(None, description="Additional notes")


class JobCreate(JobBase):
    """Create new job"""
    job_id: str = Field(..., description="Unique job identifier")


class JobUpdate(BaseModel):
    """Update existing job (all fields optional)"""
    operation_name: Optional[str] = None
    operation_code: Optional[str] = None
    sequence_number: Optional[int] = None
    part_number: Optional[str] = None
    part_description: Optional[str] = None
    planned_quantity: Optional[int] = None
    completed_quantity: Optional[int] = None
    quantity_scrapped: Optional[int] = None
    planned_hours: Optional[Decimal] = None
    actual_hours: Optional[Decimal] = None
    is_completed: Optional[int] = None
    completed_date: Optional[datetime] = None
    assigned_employee_id: Optional[int] = None
    assigned_shift_id: Optional[int] = None
    notes: Optional[str] = None


class JobComplete(BaseModel):
    """Complete a job with actual quantities and hours"""
    completed_quantity: int = Field(..., description="Actual quantity completed")
    actual_hours: Decimal = Field(..., description="Actual hours spent")


class JobResponse(JobBase):
    """Job response with all fields"""
    job_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
