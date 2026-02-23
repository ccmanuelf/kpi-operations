"""
Pydantic models for Equipment API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date


class EquipmentCreate(BaseModel):
    """Create a new equipment entry for a client."""

    client_id: str = Field(..., min_length=1, max_length=50, description="Client this equipment belongs to")
    line_id: Optional[int] = Field(None, description="Production line ID (NULL for shared equipment)")
    equipment_code: str = Field(..., min_length=1, max_length=50, description="Unique equipment code, e.g. MCH-001")
    equipment_name: str = Field(..., min_length=1, max_length=100, description="Equipment display name")
    equipment_type: Optional[str] = Field(None, max_length=50, description="Equipment category, e.g. Sewing Machine")
    is_shared: bool = Field(default=False, description="True = common resource across lines")
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|MAINTENANCE|RETIRED)$", description="Equipment status")
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)

    model_config = {"from_attributes": True}


class EquipmentUpdate(BaseModel):
    """Update an equipment entry (partial update)."""

    line_id: Optional[int] = None
    equipment_name: Optional[str] = Field(None, min_length=1, max_length=100)
    equipment_type: Optional[str] = Field(None, max_length=50)
    is_shared: Optional[bool] = None
    status: Optional[str] = Field(None, pattern="^(ACTIVE|MAINTENANCE|RETIRED)$")
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

    model_config = {"from_attributes": True}


class EquipmentResponse(BaseModel):
    """Response schema for an equipment entry."""

    equipment_id: int
    client_id: str
    line_id: Optional[int]
    equipment_code: str
    equipment_name: str
    equipment_type: Optional[str]
    is_shared: bool
    status: str
    last_maintenance_date: Optional[date]
    next_maintenance_date: Optional[date]
    notes: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
