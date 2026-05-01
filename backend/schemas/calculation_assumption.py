"""
Pydantic schemas for the calculation assumption registry (Phase 2).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AssumptionStatusEnum(str, Enum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    RETIRED = "retired"


class AssumptionProposalCreate(BaseModel):
    """Body for `POST /api/assumptions` (poweruser+)."""

    client_id: str = Field(..., min_length=1, max_length=50)
    assumption_name: str = Field(..., min_length=1, max_length=100)
    value: Any = Field(..., description="JSON-serialisable value; validated against catalog.")
    rationale: Optional[str] = Field(None, description="Why this adjustment exists.")
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None


class AssumptionProposalUpdate(BaseModel):
    """Body for `PATCH /api/assumptions/{id}`. Only PROPOSED records can be updated."""

    value: Optional[Any] = None
    rationale: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    change_reason: Optional[str] = None


class AssumptionApproveRequest(BaseModel):
    """Body for `POST /api/assumptions/{id}/approve` (admin only)."""

    change_reason: Optional[str] = None


class AssumptionRetireRequest(BaseModel):
    """Body for `POST /api/assumptions/{id}/retire` (admin only)."""

    change_reason: Optional[str] = None


class AssumptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assumption_id: int
    client_id: str
    assumption_name: str
    value: Any  # parsed from value_json
    rationale: Optional[str]
    effective_date: Optional[datetime]
    expiration_date: Optional[datetime]
    status: AssumptionStatusEnum
    proposed_by: str
    proposed_at: datetime
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    retired_by: Optional[str]
    retired_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]


class AssumptionChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    change_id: int
    assumption_id: int
    changed_by: str
    changed_at: datetime
    previous_value: Optional[Any]
    new_value: Optional[Any]
    previous_status: Optional[str]
    new_status: Optional[str]
    change_reason: Optional[str]
    trigger_source: Optional[str]


class EffectiveAssumptionSet(BaseModel):
    """`GET /api/assumptions/effective?client_id=…&as_of=…` response."""

    client_id: str
    as_of: datetime
    assumptions: dict[str, Any]  # assumption_name -> current value
    metadata: dict[str, AssumptionResponse]  # assumption_name -> full record


class VarianceRow(BaseModel):
    """One row of the Phase 5 Adjustment Variance Report."""

    assumption_id: int
    client_id: str
    assumption_name: str
    description: Optional[str] = None  # from catalog
    value: Any
    default_value: Any
    deviates_from_default: bool
    deviation_magnitude: float  # for sortable column
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    days_since_review: Optional[int]
    is_stale: bool  # True if approved >12 months ago

    rationale: Optional[str] = None


class MetricAssumptionDependencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dependency_id: int
    metric_name: str
    assumption_name: str
    usage_notes: Optional[str]
    created_at: datetime


class CatalogEntry(BaseModel):
    """`GET /api/assumptions/catalog` — list of registered assumption names."""

    name: str
    description: str
    allowed_values: Optional[list[Any]]
