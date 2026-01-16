"""
Filter Pydantic models for request/response validation
Saved Filters feature - user-specific filter configurations
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
import json


class DateRangeType(str, Enum):
    """Date range type enum"""
    RELATIVE = "relative"
    ABSOLUTE = "absolute"


class FilterType(str, Enum):
    """Filter type enum for categorization"""
    DASHBOARD = "dashboard"
    PRODUCTION = "production"
    QUALITY = "quality"
    ATTENDANCE = "attendance"
    DOWNTIME = "downtime"
    HOLD = "hold"
    COVERAGE = "coverage"
    CUSTOM = "custom"


class DateRangeConfig(BaseModel):
    """
    Date range configuration for filters

    Supports both relative (last N days) and absolute (specific dates) ranges
    """
    type: DateRangeType = Field(
        default=DateRangeType.RELATIVE,
        description="Date range type: relative (last N days) or absolute (specific dates)"
    )
    relative_days: Optional[int] = Field(
        default=7,
        ge=1,
        le=365,
        description="Number of days for relative range (1-365)"
    )
    start_date: Optional[date] = Field(
        default=None,
        description="Start date for absolute range"
    )
    end_date: Optional[date] = Field(
        default=None,
        description="End date for absolute range"
    )

    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v, info):
        """Ensure end_date is after start_date when both are provided"""
        if v is not None and info.data.get('start_date') is not None:
            if v < info.data['start_date']:
                raise ValueError('end_date must be after start_date')
        return v

    class Config:
        json_schema_extra = {
            "examples": [
                {"type": "relative", "relative_days": 7},
                {"type": "absolute", "start_date": "2026-01-01", "end_date": "2026-01-15"}
            ]
        }


class KPIThresholds(BaseModel):
    """
    KPI threshold configuration for filtering

    Allows filtering data based on KPI performance thresholds
    """
    efficiency_min: Optional[float] = Field(
        default=None,
        ge=0,
        le=200,
        description="Minimum efficiency percentage"
    )
    efficiency_max: Optional[float] = Field(
        default=None,
        ge=0,
        le=200,
        description="Maximum efficiency percentage"
    )
    quality_rate_min: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum quality rate percentage"
    )
    defect_rate_max: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Maximum defect rate percentage"
    )
    absenteeism_max: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Maximum absenteeism rate percentage"
    )
    otd_min: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum on-time delivery percentage"
    )


class FilterConfig(BaseModel):
    """
    Complete filter configuration model

    Contains all filterable parameters for KPI dashboards
    """
    client_id: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Filter by specific client ID"
    )
    date_range: Optional[DateRangeConfig] = Field(
        default_factory=lambda: DateRangeConfig(),
        description="Date range configuration"
    )
    shift_ids: Optional[List[int]] = Field(
        default=None,
        description="List of shift IDs to include"
    )
    product_ids: Optional[List[int]] = Field(
        default=None,
        description="List of product IDs to include"
    )
    work_order_ids: Optional[List[str]] = Field(
        default=None,
        description="List of work order IDs to include"
    )
    employee_ids: Optional[List[int]] = Field(
        default=None,
        description="List of employee IDs to include"
    )
    status_filter: Optional[List[str]] = Field(
        default=None,
        description="List of statuses to include"
    )
    kpi_thresholds: Optional[KPIThresholds] = Field(
        default=None,
        description="KPI threshold filters"
    )
    custom_fields: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom filter fields for extensibility"
    )

    def to_json_string(self) -> str:
        """Serialize config to JSON string for database storage"""
        return self.model_dump_json(exclude_none=False)

    @classmethod
    def from_json_string(cls, json_str: str) -> "FilterConfig":
        """Deserialize config from JSON string"""
        data = json.loads(json_str)
        return cls.model_validate(data)

    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "BOOT-LINE-A",
                "date_range": {"type": "relative", "relative_days": 7},
                "shift_ids": [1, 2],
                "product_ids": [101, 102],
                "kpi_thresholds": {"efficiency_min": 85, "quality_rate_min": 95}
            }
        }


class SavedFilterCreate(BaseModel):
    """
    Create request model for saved filters

    SECURITY: user_id is set from authenticated user, not from request
    """
    filter_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable filter name"
    )
    filter_type: FilterType = Field(
        ...,
        description="Filter category/type"
    )
    filter_config: FilterConfig = Field(
        ...,
        description="Filter configuration"
    )
    is_default: bool = Field(
        default=False,
        description="Set as default filter for this type"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "filter_name": "Weekly Production Overview",
                "filter_type": "production",
                "filter_config": {
                    "client_id": "BOOT-LINE-A",
                    "date_range": {"type": "relative", "relative_days": 7},
                    "shift_ids": [1, 2]
                },
                "is_default": True
            }
        }


class SavedFilterUpdate(BaseModel):
    """
    Update request model for saved filters

    All fields are optional - only provided fields will be updated
    """
    filter_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Human-readable filter name"
    )
    filter_type: Optional[FilterType] = Field(
        default=None,
        description="Filter category/type"
    )
    filter_config: Optional[FilterConfig] = Field(
        default=None,
        description="Filter configuration"
    )
    is_default: Optional[bool] = Field(
        default=None,
        description="Set as default filter for this type"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "filter_name": "Updated Filter Name",
                "filter_config": {
                    "date_range": {"type": "relative", "relative_days": 14}
                }
            }
        }


class SavedFilterResponse(BaseModel):
    """
    Response model for saved filters

    Includes all filter data with metadata
    """
    filter_id: int = Field(..., description="Unique filter identifier")
    user_id: str = Field(..., description="Owner user ID")
    filter_name: str = Field(..., description="Human-readable filter name")
    filter_type: str = Field(..., description="Filter category/type")
    filter_config: FilterConfig = Field(..., description="Filter configuration")
    is_default: bool = Field(..., description="Whether this is the default filter for its type")
    usage_count: int = Field(..., description="Number of times filter has been applied")
    last_used_at: Optional[datetime] = Field(None, description="Last time filter was applied")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "filter_id": 1,
                "user_id": "user-123",
                "filter_name": "Weekly Production Overview",
                "filter_type": "production",
                "filter_config": {
                    "client_id": "BOOT-LINE-A",
                    "date_range": {"type": "relative", "relative_days": 7}
                },
                "is_default": True,
                "usage_count": 15,
                "last_used_at": "2026-01-15T10:30:00Z",
                "created_at": "2026-01-01T08:00:00Z",
                "updated_at": "2026-01-10T14:20:00Z"
            }
        }


class FilterHistoryResponse(BaseModel):
    """
    Response model for filter history entries
    """
    history_id: int = Field(..., description="Unique history entry identifier")
    user_id: str = Field(..., description="Owner user ID")
    filter_config: FilterConfig = Field(..., description="Applied filter configuration")
    applied_at: datetime = Field(..., description="When the filter was applied")

    class Config:
        from_attributes = True


class FilterHistoryCreate(BaseModel):
    """
    Create request model for filter history

    SECURITY: user_id is set from authenticated user
    """
    filter_config: FilterConfig = Field(
        ...,
        description="Filter configuration that was applied"
    )


class ApplyFilterResponse(BaseModel):
    """
    Response model for applying a filter

    Returns the filter details along with updated usage statistics
    """
    filter_id: int
    filter_name: str
    filter_config: FilterConfig
    usage_count: int
    last_used_at: datetime
    message: str = "Filter applied successfully"


class SetDefaultResponse(BaseModel):
    """
    Response model for setting default filter
    """
    filter_id: int
    filter_name: str
    filter_type: str
    is_default: bool
    message: str
