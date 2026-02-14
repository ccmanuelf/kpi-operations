"""
Client Pydantic models for request/response validation
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class ClientCreate(BaseModel):
    """Client creation model"""

    client_id: str = Field(..., min_length=1, max_length=50, description="Unique client ID")
    client_name: str = Field(..., min_length=1, max_length=255, description="Client name")
    client_contact: Optional[str] = Field(None, max_length=255)
    client_email: Optional[str] = Field(None, max_length=255)
    client_phone: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=255)
    supervisor_id: Optional[str] = Field(None, max_length=50)
    planner_id: Optional[str] = Field(None, max_length=50)
    engineering_id: Optional[str] = Field(None, max_length=50)
    client_type: Optional[str] = Field(default="Piece Rate", pattern="^(Hourly Rate|Piece Rate|Hybrid|Service|Other)$")
    timezone: Optional[str] = Field(default="America/New_York", max_length=50)
    is_active: Optional[int] = Field(default=1, ge=0, le=1, description="Boolean: 1=active, 0=inactive")


class ClientUpdate(BaseModel):
    """Client update model (all fields optional)"""

    client_name: Optional[str] = Field(None, min_length=1, max_length=255)
    client_contact: Optional[str] = Field(None, max_length=255)
    client_email: Optional[str] = Field(None, max_length=255)
    client_phone: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=255)
    supervisor_id: Optional[str] = Field(None, max_length=50)
    planner_id: Optional[str] = Field(None, max_length=50)
    engineering_id: Optional[str] = Field(None, max_length=50)
    client_type: Optional[str] = Field(None, pattern="^(Hourly Rate|Piece Rate|Hybrid|Service|Other)$")
    timezone: Optional[str] = Field(None, max_length=50)
    is_active: Optional[int] = Field(None, ge=0, le=1)


class ClientResponse(BaseModel):
    """Client response model"""

    client_id: str
    client_name: str
    client_contact: Optional[str]
    client_email: Optional[str]
    client_phone: Optional[str]
    location: Optional[str]
    supervisor_id: Optional[str]
    planner_id: Optional[str]
    engineering_id: Optional[str]
    client_type: str
    timezone: str
    is_active: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ClientSummary(BaseModel):
    """Client summary with statistics"""

    client_id: str
    client_name: str
    client_type: str
    is_active: int
    total_work_orders: Optional[int] = 0
    active_work_orders: Optional[int] = 0
    total_employees: Optional[int] = 0
