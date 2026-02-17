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
    client_contact: Optional[str] = Field(None, max_length=255, description="Primary contact person name for the client")
    client_email: Optional[str] = Field(None, max_length=255, description="Client email address for communication")
    client_phone: Optional[str] = Field(None, max_length=50, description="Client phone number for contact")
    location: Optional[str] = Field(None, max_length=255, description="Physical location or address of the client facility")
    supervisor_id: Optional[str] = Field(None, max_length=50, description="User ID of the assigned production supervisor")
    planner_id: Optional[str] = Field(None, max_length=50, description="User ID of the assigned production planner")
    engineering_id: Optional[str] = Field(None, max_length=50, description="User ID of the assigned engineering contact")
    client_type: Optional[str] = Field(default="Piece Rate", pattern="^(Hourly Rate|Piece Rate|Hybrid|Service|Other)$", description="Billing model: Hourly Rate, Piece Rate, Hybrid, Service, or Other")
    timezone: Optional[str] = Field(default="America/New_York", max_length=50, description="IANA timezone for shift scheduling and report generation")
    is_active: Optional[int] = Field(default=1, ge=0, le=1, description="Boolean: 1=active, 0=inactive")


class ClientUpdate(BaseModel):
    """Client update model (all fields optional)"""

    client_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated client display name")
    client_contact: Optional[str] = Field(None, max_length=255, description="Updated primary contact person name")
    client_email: Optional[str] = Field(None, max_length=255, description="Updated client email address")
    client_phone: Optional[str] = Field(None, max_length=50, description="Updated client phone number")
    location: Optional[str] = Field(None, max_length=255, description="Updated facility location or address")
    supervisor_id: Optional[str] = Field(None, max_length=50, description="Updated supervisor user ID assignment")
    planner_id: Optional[str] = Field(None, max_length=50, description="Updated planner user ID assignment")
    engineering_id: Optional[str] = Field(None, max_length=50, description="Updated engineering contact user ID")
    client_type: Optional[str] = Field(None, pattern="^(Hourly Rate|Piece Rate|Hybrid|Service|Other)$", description="Updated billing model type")
    timezone: Optional[str] = Field(None, max_length=50, description="Updated IANA timezone for scheduling")
    is_active: Optional[int] = Field(None, ge=0, le=1, description="Updated active status: 1=active, 0=inactive")


class ClientResponse(BaseModel):
    """Client response model"""

    client_id: str = Field(..., description="Unique client identifier used for tenant isolation")
    client_name: str = Field(..., description="Client display name")
    client_contact: Optional[str] = Field(None, description="Primary contact person name")
    client_email: Optional[str] = Field(None, description="Client email address")
    client_phone: Optional[str] = Field(None, description="Client phone number")
    location: Optional[str] = Field(None, description="Physical facility location or address")
    supervisor_id: Optional[str] = Field(None, description="Assigned production supervisor user ID")
    planner_id: Optional[str] = Field(None, description="Assigned production planner user ID")
    engineering_id: Optional[str] = Field(None, description="Assigned engineering contact user ID")
    client_type: str = Field(..., description="Billing model: Hourly Rate, Piece Rate, Hybrid, Service, or Other")
    timezone: str = Field(..., description="IANA timezone for shift scheduling and reports")
    is_active: int = Field(..., description="Active status flag: 1=active, 0=inactive")
    created_at: datetime = Field(..., description="Timestamp when the client was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp of the last client modification")

    class Config:
        from_attributes = True


class ClientSummary(BaseModel):
    """Client summary with statistics"""

    client_id: str = Field(..., description="Unique client identifier")
    client_name: str = Field(..., description="Client display name")
    client_type: str = Field(..., description="Billing model type")
    is_active: int = Field(..., description="Active status flag: 1=active, 0=inactive")
    total_work_orders: Optional[int] = Field(0, description="Total number of work orders for this client")
    active_work_orders: Optional[int] = Field(0, description="Number of currently active work orders")
    total_employees: Optional[int] = Field(0, description="Total number of employees assigned to this client")
