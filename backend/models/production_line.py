"""
Pydantic models for Production Line API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ProductionLineCreate(BaseModel):
    """Create a new production line for a client."""

    client_id: str = Field(..., min_length=1, max_length=50)
    line_code: str = Field(..., min_length=1, max_length=50)
    line_name: str = Field(..., min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=50)
    line_type: str = Field(default="DEDICATED", pattern=r"^(DEDICATED|SHARED|SECTION)$")
    parent_line_id: Optional[int] = None
    max_operators: Optional[int] = Field(None, ge=1)
    capacity_line_id: Optional[int] = None

    model_config = {"from_attributes": True}


class ProductionLineUpdate(BaseModel):
    """Update a production line entry (partial update)."""

    line_name: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=50)
    line_type: Optional[str] = Field(None, pattern=r"^(DEDICATED|SHARED|SECTION)$")
    parent_line_id: Optional[int] = None
    max_operators: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

    model_config = {"from_attributes": True}


class ProductionLineResponse(BaseModel):
    """Response schema for a production line."""

    line_id: int
    client_id: str
    line_code: str
    line_name: str
    department: Optional[str] = None
    line_type: str
    parent_line_id: Optional[int] = None
    max_operators: Optional[int] = None
    capacity_line_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductionLineTreeResponse(ProductionLineResponse):
    """Response schema for a production line with nested children."""

    children: List["ProductionLineTreeResponse"] = []
