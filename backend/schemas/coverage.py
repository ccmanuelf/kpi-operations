"""
Shift coverage models (Pydantic)
PHASE 3: Shift coverage and capacity tracking
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from decimal import Decimal


class ShiftCoverageCreate(BaseModel):
    """Create shift coverage record"""

    client_id: str = Field(..., min_length=1, max_length=50, description="Tenant client identifier for multi-tenant isolation")
    shift_id: int = Field(..., gt=0, description="Reference to the shift definition being covered")
    coverage_date: date = Field(..., description="Calendar date of the shift coverage record")
    required_employees: int = Field(..., gt=0, description="Number of employees needed to fully staff the shift")
    actual_employees: int = Field(..., ge=0, description="Number of employees actually present for the shift")
    notes: Optional[str] = Field(None, description="Additional context or comments about coverage")


class ShiftCoverageUpdate(BaseModel):
    """Update shift coverage"""

    required_employees: Optional[int] = Field(None, gt=0, description="Updated headcount requirement for the shift")
    actual_employees: Optional[int] = Field(None, ge=0, description="Updated count of employees actually present")
    notes: Optional[str] = Field(None, description="Updated notes about coverage")


class ShiftCoverageResponse(BaseModel):
    """Shift coverage response"""

    coverage_id: int = Field(..., description="Unique identifier for this coverage record")
    shift_id: int = Field(..., description="Reference to the shift definition")
    coverage_date: date = Field(..., description="Calendar date of the coverage record")
    required_employees: int = Field(..., description="Number of employees needed to fully staff the shift")
    actual_employees: int = Field(..., description="Number of employees actually present")
    coverage_percentage: Decimal = Field(..., description="Ratio of actual to required employees as a percentage")
    notes: Optional[str] = Field(None, description="Additional context or comments about coverage")
    entered_by: int = Field(..., description="User ID of the person who recorded this entry")
    created_at: datetime = Field(..., description="Timestamp when the record was created")
    updated_at: datetime = Field(..., description="Timestamp of the last modification")

    class Config:
        from_attributes = True
