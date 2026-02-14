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

    client_id: str = Field(..., min_length=1, max_length=50)
    shift_id: int = Field(..., gt=0)
    coverage_date: date
    required_employees: int = Field(..., gt=0)
    actual_employees: int = Field(..., ge=0)
    notes: Optional[str] = None


class ShiftCoverageUpdate(BaseModel):
    """Update shift coverage"""

    required_employees: Optional[int] = Field(None, gt=0)
    actual_employees: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class ShiftCoverageResponse(BaseModel):
    """Shift coverage response"""

    coverage_id: int
    shift_id: int
    coverage_date: date
    required_employees: int
    actual_employees: int
    coverage_percentage: Decimal
    notes: Optional[str]
    entered_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
