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
    client_id_assigned: Optional[str] = Field(None, description="Comma-separated client IDs, NULL for floating pool")
    is_floating_pool: Optional[int] = Field(default=0, ge=0, le=1, description="Boolean: 0=regular, 1=floating pool")
    is_active: Optional[int] = Field(default=1, ge=0, le=1, description="Boolean: 1=active, 0=inactive (soft delete)")
    department: Optional[str] = Field(None, max_length=50, description="Department classification")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Employee phone number for contact")
    contact_email: Optional[str] = Field(None, max_length=255, description="Employee email address for notifications")
    position: Optional[str] = Field(None, max_length=100, description="Job title or position within the organization")
    hire_date: Optional[datetime] = Field(None, description="Date the employee was hired")


class EmployeeUpdate(BaseModel):
    """Employee update model (all fields optional)"""

    employee_code: Optional[str] = Field(None, min_length=1, max_length=50, description="Updated unique employee code")
    employee_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated employee full name")
    client_id_assigned: Optional[str] = Field(None, description="Updated comma-separated client IDs assignment")
    is_floating_pool: Optional[int] = Field(None, ge=0, le=1, description="Updated floating pool flag: 0=regular, 1=floating pool")
    is_active: Optional[int] = Field(None, ge=0, le=1, description="Updated active status: 1=active, 0=inactive")
    department: Optional[str] = Field(None, max_length=50, description="Updated department classification")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Updated employee phone number")
    contact_email: Optional[str] = Field(None, max_length=255, description="Updated employee email address")
    position: Optional[str] = Field(None, max_length=100, description="Updated job title or position")
    hire_date: Optional[datetime] = Field(None, description="Updated hire date")


class EmployeeResponse(BaseModel):
    """Employee response model"""

    employee_id: int = Field(..., description="Unique database identifier for the employee")
    employee_code: str = Field(..., description="Unique employee code used across the system")
    employee_name: str = Field(..., description="Employee full name")
    client_id_assigned: Optional[str] = Field(None, description="Comma-separated client IDs the employee is assigned to")
    is_floating_pool: int = Field(..., description="Floating pool flag: 0=regular assignment, 1=floating pool")
    is_active: Optional[int] = Field(1, description="Active status: 1=active, 0=inactive (soft deleted)")
    department: Optional[str] = Field(None, description="Department the employee belongs to")
    contact_phone: Optional[str] = Field(None, description="Employee phone number")
    contact_email: Optional[str] = Field(None, description="Employee email address")
    position: Optional[str] = Field(None, description="Job title or position within the organization")
    hire_date: Optional[datetime] = Field(None, description="Date the employee was hired")
    created_at: datetime = Field(..., description="Timestamp when the employee record was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp of the last employee record modification")

    class Config:
        from_attributes = True


class EmployeeWithClients(EmployeeResponse):
    """Employee with parsed client list"""

    assigned_clients: list[str] = Field(default=[], description="Parsed list of client IDs from client_id_assigned")


class EmployeeAssignmentRequest(BaseModel):
    """Request to assign employee to client"""

    employee_id: int = Field(..., gt=0, description="Database ID of the employee to assign")
    client_id: str = Field(..., min_length=1, max_length=50, description="Client ID to assign the employee to")


class FloatingPoolAssignmentRequest(BaseModel):
    """Request to assign/unassign floating pool employee"""

    employee_id: int = Field(..., gt=0, description="Database ID of the employee to modify")
    action: str = Field(..., pattern="^(assign|remove)$", description="assign or remove from floating pool")
