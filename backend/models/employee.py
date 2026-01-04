"""
Employee Pydantic models for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class EmployeeCreate(BaseModel):
    """Employee creation model"""
    employee_code: str = Field(..., min_length=1, max_length=50, description="Unique employee code")
    employee_name: str = Field(..., min_length=1, max_length=255, description="Employee full name")
    client_id_assigned: Optional[str] = Field(
        None,
        description="Comma-separated client IDs, NULL for floating pool"
    )
    is_floating_pool: Optional[int] = Field(
        default=0,
        ge=0,
        le=1,
        description="Boolean: 0=regular, 1=floating pool"
    )
    contact_phone: Optional[str] = Field(None, max_length=50)
    contact_email: Optional[str] = Field(None, max_length=255)
    position: Optional[str] = Field(None, max_length=100)
    hire_date: Optional[datetime] = None


class EmployeeUpdate(BaseModel):
    """Employee update model (all fields optional)"""
    employee_code: Optional[str] = Field(None, min_length=1, max_length=50)
    employee_name: Optional[str] = Field(None, min_length=1, max_length=255)
    client_id_assigned: Optional[str] = None
    is_floating_pool: Optional[int] = Field(None, ge=0, le=1)
    contact_phone: Optional[str] = Field(None, max_length=50)
    contact_email: Optional[str] = Field(None, max_length=255)
    position: Optional[str] = Field(None, max_length=100)
    hire_date: Optional[datetime] = None


class EmployeeResponse(BaseModel):
    """Employee response model"""
    employee_id: int
    employee_code: str
    employee_name: str
    client_id_assigned: Optional[str]
    is_floating_pool: int
    contact_phone: Optional[str]
    contact_email: Optional[str]
    position: Optional[str]
    hire_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class EmployeeWithClients(EmployeeResponse):
    """Employee with parsed client list"""
    assigned_clients: list[str] = []


class EmployeeAssignmentRequest(BaseModel):
    """Request to assign employee to client"""
    employee_id: int = Field(..., gt=0)
    client_id: str = Field(..., min_length=1, max_length=50)


class FloatingPoolAssignmentRequest(BaseModel):
    """Request to assign/unassign floating pool employee"""
    employee_id: int = Field(..., gt=0)
    action: str = Field(..., pattern="^(assign|remove)$", description="assign or remove from floating pool")
