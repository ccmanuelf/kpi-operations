"""
KPI Threshold Pydantic models for API request/response
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class KPIThresholdBase(BaseModel):
    """Base KPI threshold model"""
    kpi_key: str = Field(..., description="KPI identifier (e.g., 'efficiency', 'quality')")
    target_value: float = Field(..., description="Target value for the KPI")
    warning_threshold: Optional[float] = Field(None, description="Warning level threshold")
    critical_threshold: Optional[float] = Field(None, description="Critical level threshold")
    unit: str = Field(default='%', description="Unit of measurement")
    higher_is_better: str = Field(default='Y', pattern="^[YN]$", description="Y if higher values are better")


class KPIThresholdCreate(KPIThresholdBase):
    """Create KPI threshold - client_id is optional (NULL = global)"""
    client_id: Optional[str] = Field(None, description="Client ID (NULL for global default)")


class KPIThresholdUpdate(BaseModel):
    """Update KPI threshold - all fields optional"""
    target_value: Optional[float] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    unit: Optional[str] = None
    higher_is_better: Optional[str] = Field(None, pattern="^[YN]$")


class KPIThresholdResponse(KPIThresholdBase):
    """KPI threshold response model"""
    threshold_id: str
    client_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class KPIThresholdSet(BaseModel):
    """Complete set of KPI thresholds for a client or global"""
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    thresholds: List[KPIThresholdResponse] = []


class KPIThresholdsBulkUpdate(BaseModel):
    """Bulk update thresholds for a client"""
    client_id: Optional[str] = Field(None, description="Client ID (NULL for global)")
    thresholds: List[KPIThresholdCreate]
