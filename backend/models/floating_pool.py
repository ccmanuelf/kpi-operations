"""
Floating Pool Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FloatingPoolCreate(BaseModel):
    """Floating pool entry creation model"""
    client_id: Optional[str] = Field(None, max_length=50)
    employee_id: int = Field(..., gt=0, description="Employee ID (must be in floating pool)")
    available_from: Optional[datetime] = Field(None, description="Start of availability period")
    available_to: Optional[datetime] = Field(None, description="End of availability period")
    current_assignment: Optional[str] = Field(None, max_length=255, description="Current client ID or NULL")
    notes: Optional[str] = None


class FloatingPoolUpdate(BaseModel):
    """Floating pool entry update model (all fields optional)"""
    available_from: Optional[datetime] = None
    available_to: Optional[datetime] = None
    current_assignment: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None


class FloatingPoolResponse(BaseModel):
    """Floating pool entry response model"""
    pool_id: int
    employee_id: int
    available_from: Optional[datetime]
    available_to: Optional[datetime]
    current_assignment: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class FloatingPoolAssignmentRequest(BaseModel):
    """Request to assign floating pool employee to client"""
    employee_id: int = Field(..., gt=0, description="Employee ID in floating pool")
    client_id: str = Field(..., min_length=1, max_length=50, description="Client ID to assign to")
    available_from: Optional[datetime] = Field(None, description="Start date of assignment")
    available_to: Optional[datetime] = Field(None, description="End date of assignment")
    notes: Optional[str] = Field(None, description="Assignment notes")


class FloatingPoolUnassignmentRequest(BaseModel):
    """Request to unassign floating pool employee from client"""
    pool_id: int = Field(..., gt=0, description="Floating pool entry ID")


class FloatingPoolAvailability(BaseModel):
    """Floating pool employee availability"""
    pool_id: int
    employee_id: int
    employee_code: str
    employee_name: str
    position: Optional[str]
    available_from: Optional[datetime]
    available_to: Optional[datetime]
    notes: Optional[str]
    is_available: bool = True


class FloatingPoolSummary(BaseModel):
    """Floating pool summary statistics"""
    total_floating_pool_employees: int
    currently_available: int
    currently_assigned: int
    available_employees: list[FloatingPoolAvailability] = []
