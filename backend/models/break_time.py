"""
Break Time Pydantic models
Validation schemas for break time CRUD operations.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BreakTimeCreate(BaseModel):
    """Create a new break time entry for a shift."""

    shift_id: int
    client_id: str = Field(..., max_length=50)
    break_name: str = Field(..., max_length=100)
    start_offset_minutes: int = Field(..., ge=0, le=1440)
    duration_minutes: int = Field(..., ge=1, le=480)
    applies_to: str = Field(default="ALL", pattern="^(ALL|EMPLOYEE|LINE)$")

    model_config = {"from_attributes": True}


class BreakTimeUpdate(BaseModel):
    """Update an existing break time entry (partial)."""

    break_name: Optional[str] = Field(None, max_length=100)
    start_offset_minutes: Optional[int] = Field(None, ge=0, le=1440)
    duration_minutes: Optional[int] = Field(None, ge=1, le=480)
    applies_to: Optional[str] = Field(None, pattern="^(ALL|EMPLOYEE|LINE)$")
    is_active: Optional[bool] = None

    model_config = {"from_attributes": True}


class BreakTimeResponse(BaseModel):
    """Response model for a break time entry."""

    break_id: int
    shift_id: int
    client_id: str
    break_name: str
    start_offset_minutes: int
    duration_minutes: int
    applies_to: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
