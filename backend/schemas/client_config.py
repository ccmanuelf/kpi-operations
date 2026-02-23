"""
Client Configuration Pydantic models for request/response validation
Implements Phase 7.2: Client-Level Calculation Overrides
Implements Phase 10: Flexible Workflow Foundation
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json


class OTDModeEnum(str, Enum):
    """OTD calculation mode options"""

    STANDARD = "STANDARD"
    TRUE = "TRUE"
    BOTH = "BOTH"


class ClientConfigCreate(BaseModel):
    """Client configuration creation model"""

    client_id: str = Field(..., min_length=1, max_length=50, description="Client ID to configure")

    # OTD Configuration
    otd_mode: OTDModeEnum = Field(default=OTDModeEnum.STANDARD, description="OTD calculation mode")

    # Efficiency Configuration
    default_cycle_time_hours: float = Field(default=0.25, ge=0.01, le=24.0, description="Default cycle time in hours")
    efficiency_target_percent: float = Field(default=85.0, ge=0.0, le=100.0, description="Efficiency target percentage")

    # Quality Configuration
    quality_target_ppm: float = Field(default=10000.0, ge=0.0, description="Quality PPM target")
    fpy_target_percent: float = Field(default=95.0, ge=0.0, le=100.0, description="FPY target percentage")
    dpmo_opportunities_default: int = Field(default=1, ge=1, description="Default opportunities per unit for DPMO")

    # Availability Configuration
    availability_target_percent: float = Field(
        default=90.0, ge=0.0, le=100.0, description="Availability target percentage"
    )

    # Performance Configuration
    performance_target_percent: float = Field(
        default=95.0, ge=0.0, le=100.0, description="Performance target percentage"
    )

    # OEE Configuration
    oee_target_percent: float = Field(default=85.0, ge=0.0, le=100.0, description="OEE target percentage")

    # Absenteeism Configuration
    absenteeism_target_percent: float = Field(
        default=3.0, ge=0.0, le=100.0, description="Absenteeism target percentage"
    )

    # WIP Aging Configuration
    wip_aging_threshold_days: int = Field(default=7, ge=1, description="Days before WIP is flagged as aging")
    wip_critical_threshold_days: int = Field(default=14, ge=1, description="Days before WIP is flagged as critical")

    # Workflow Configuration (Phase 10)
    workflow_statuses: Optional[List[str]] = Field(
        default=["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED"],
        description="Ordered list of workflow statuses for this client",
    )
    workflow_transitions: Optional[Dict[str, List[str]]] = Field(
        default=None, description="Map of TO_STATUS to list of allowed FROM_STATUS values"
    )
    workflow_optional_statuses: Optional[List[str]] = Field(
        default=["SHIPPED", "DEMOTED"], description="Statuses that can be skipped"
    )
    workflow_closure_trigger: Optional[str] = Field(
        default="at_shipment",
        pattern="^(at_shipment|at_client_receipt|at_completion|manual)$",
        description="When to close orders",
    )


class ClientConfigUpdate(BaseModel):
    """Client configuration update model (all fields optional)"""

    otd_mode: Optional[OTDModeEnum] = None
    default_cycle_time_hours: Optional[float] = Field(None, ge=0.01, le=24.0)
    efficiency_target_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    quality_target_ppm: Optional[float] = Field(None, ge=0.0)
    fpy_target_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    dpmo_opportunities_default: Optional[int] = Field(None, ge=1)
    availability_target_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    performance_target_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    oee_target_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    absenteeism_target_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    wip_aging_threshold_days: Optional[int] = Field(None, ge=1)
    wip_critical_threshold_days: Optional[int] = Field(None, ge=1)

    # Workflow Configuration (Phase 10)
    workflow_statuses: Optional[List[str]] = None
    workflow_transitions: Optional[Dict[str, List[str]]] = None
    workflow_optional_statuses: Optional[List[str]] = None
    workflow_closure_trigger: Optional[str] = Field(
        None, pattern="^(at_shipment|at_client_receipt|at_completion|manual)$"
    )


class ClientConfigResponse(BaseModel):
    """Client configuration response model"""

    config_id: int
    client_id: str
    otd_mode: str
    default_cycle_time_hours: float
    efficiency_target_percent: float
    quality_target_ppm: float
    fpy_target_percent: float
    dpmo_opportunities_default: int
    availability_target_percent: float
    performance_target_percent: float
    oee_target_percent: float
    absenteeism_target_percent: float
    wip_aging_threshold_days: int
    wip_critical_threshold_days: int

    # Workflow Configuration (Phase 10)
    workflow_statuses: Optional[List[str]] = None
    workflow_transitions: Optional[Dict[str, List[str]]] = None
    workflow_optional_statuses: Optional[List[str]] = None
    workflow_closure_trigger: Optional[str] = None
    workflow_version: Optional[int] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Validators to parse JSON strings from database
    @field_validator("workflow_statuses", mode="before")
    @classmethod
    def parse_workflow_statuses(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    @field_validator("workflow_transitions", mode="before")
    @classmethod
    def parse_workflow_transitions(cls, v: Any) -> Optional[Dict[str, List[str]]]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    @field_validator("workflow_optional_statuses", mode="before")
    @classmethod
    def parse_workflow_optional_statuses(cls, v: Any) -> Optional[List[str]]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    class Config:
        from_attributes = True


class ClientConfigWithDefaults(BaseModel):
    """Client configuration with default values indicator"""

    config: ClientConfigResponse
    is_default: bool = False  # True if config was auto-created with defaults


class GlobalDefaults(BaseModel):
    """Global default configuration values"""

    otd_mode: str = "STANDARD"
    default_cycle_time_hours: float = 0.25
    efficiency_target_percent: float = 85.0
    quality_target_ppm: float = 10000.0
    fpy_target_percent: float = 95.0
    dpmo_opportunities_default: int = 1
    availability_target_percent: float = 90.0
    performance_target_percent: float = 95.0
    oee_target_percent: float = 85.0
    absenteeism_target_percent: float = 3.0
    wip_aging_threshold_days: int = 7
    wip_critical_threshold_days: int = 14

    # Workflow defaults (Phase 10)
    workflow_statuses: List[str] = ["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED"]
    workflow_transitions: Dict[str, List[str]] = {
        "RELEASED": ["RECEIVED"],
        "IN_PROGRESS": ["RELEASED"],
        "COMPLETED": ["IN_PROGRESS"],
        "SHIPPED": ["COMPLETED"],
        "CLOSED": ["SHIPPED", "COMPLETED"],
        "ON_HOLD": ["RECEIVED", "RELEASED", "IN_PROGRESS"],
        "DEMOTED": ["RELEASED"],
        "CANCELLED": ["RECEIVED", "RELEASED", "IN_PROGRESS", "ON_HOLD", "DEMOTED"],
        "REJECTED": ["IN_PROGRESS", "COMPLETED"],
    }
    workflow_optional_statuses: List[str] = ["SHIPPED", "DEMOTED"]
    workflow_closure_trigger: str = "at_shipment"
    workflow_version: int = 1
