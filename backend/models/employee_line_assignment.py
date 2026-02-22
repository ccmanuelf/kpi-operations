"""
Pydantic models for Employee Line Assignment API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


class EmployeeLineAssignmentCreate(BaseModel):
    """Create a new employee-to-production-line assignment."""

    employee_id: int
    line_id: int
    client_id: str = Field(..., min_length=1, max_length=50)
    allocation_percentage: Decimal = Field(
        default=Decimal("100.00"),
        ge=Decimal("1.00"),
        le=Decimal("100.00"),
    )
    is_primary: bool = True
    effective_date: date
    end_date: Optional[date] = None

    model_config = {"from_attributes": True}


class EmployeeLineAssignmentUpdate(BaseModel):
    """Update an existing employee line assignment (partial update)."""

    allocation_percentage: Optional[Decimal] = Field(
        None,
        ge=Decimal("1.00"),
        le=Decimal("100.00"),
    )
    is_primary: Optional[bool] = None
    end_date: Optional[date] = None

    model_config = {"from_attributes": True}


class EmployeeLineAssignmentResponse(BaseModel):
    """Response schema for an employee line assignment."""

    assignment_id: int
    employee_id: int
    line_id: int
    client_id: str
    allocation_percentage: Decimal
    is_primary: bool
    effective_date: date
    end_date: Optional[date] = None
    created_at: datetime

    model_config = {"from_attributes": True}
