"""
Pydantic models for Shift API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import time, datetime


class ShiftCreate(BaseModel):
    """Create a new shift for a client."""

    client_id: str = Field(..., min_length=1, max_length=50, description="Client this shift belongs to")
    shift_name: str = Field(..., min_length=1, max_length=100, description="Shift display name")
    start_time: time = Field(..., description="Shift start time")
    end_time: time = Field(..., description="Shift end time")

    model_config = {"from_attributes": True}


class ShiftUpdate(BaseModel):
    """Update a shift entry (partial update)."""

    shift_name: Optional[str] = Field(None, min_length=1, max_length=100)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_active: Optional[bool] = None

    model_config = {"from_attributes": True}


class ShiftResponse(BaseModel):
    """Response schema for a shift entry."""

    shift_id: int
    client_id: str
    shift_name: str
    start_time: time
    end_time: time
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
