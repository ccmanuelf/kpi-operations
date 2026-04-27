"""
Pydantic models for Hold Status and Hold Reason Catalogs.
Used for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# =============================================================================
# Hold Status Catalog
# =============================================================================


class HoldStatusCatalogCreate(BaseModel):
    """Create a new hold status for a client."""

    client_id: str = Field(..., min_length=1, max_length=50, description="Client this status belongs to")
    status_code: str = Field(..., min_length=1, max_length=50, description="Status code, e.g. ON_HOLD")
    display_name: str = Field(..., min_length=1, max_length=100, description="Display name, e.g. On Hold")
    is_default: bool = Field(default=False, description="Whether this is a system-seeded default")
    sort_order: int = Field(default=0, ge=0, description="Display order in UI")


class HoldStatusCatalogUpdate(BaseModel):
    """Update a hold status catalog entry."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)


class HoldStatusCatalogResponse(BaseModel):
    """Response schema for hold status catalog entry."""

    catalog_id: int
    client_id: str
    status_code: str
    display_name: str
    is_default: bool
    is_active: bool
    sort_order: int
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Hold Reason Catalog
# =============================================================================


class HoldReasonCatalogCreate(BaseModel):
    """Create a new hold reason for a client."""

    client_id: str = Field(..., min_length=1, max_length=50, description="Client this reason belongs to")
    reason_code: str = Field(..., min_length=1, max_length=50, description="Reason code, e.g. QUALITY_ISSUE")
    display_name: str = Field(..., min_length=1, max_length=100, description="Display name, e.g. Quality Issue")
    is_default: bool = Field(default=False, description="Whether this is a system-seeded default")
    sort_order: int = Field(default=0, ge=0, description="Display order in UI")


class HoldReasonCatalogUpdate(BaseModel):
    """Update a hold reason catalog entry."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)


class HoldReasonCatalogResponse(BaseModel):
    """Response schema for hold reason catalog entry."""

    catalog_id: int
    client_id: str
    reason_code: str
    display_name: str
    is_default: bool
    is_active: bool
    sort_order: int
    created_at: datetime

    class Config:
        from_attributes = True
