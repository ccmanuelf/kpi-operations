"""
Alert Pydantic models for API request/response
Intelligent alerting system for proactive KPI management
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from decimal import Decimal
from enum import Enum


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"           # Informational, no action needed
    LOW = "low"             # Low priority, for monitoring
    WARNING = "warning"     # Trending toward issue, monitor
    MEDIUM = "medium"       # Medium priority, needs attention soon
    CRITICAL = "critical"   # Requires immediate attention
    URGENT = "urgent"       # Immediate action required


class AlertCategory(str, Enum):
    """Categories of alerts"""
    OTD = "otd"                    # On-Time Delivery alerts
    DELIVERY = "delivery"         # Delivery-related alerts
    QUALITY = "quality"           # FPY, RTY, DPMO alerts
    EFFICIENCY = "efficiency"     # Production efficiency alerts
    CAPACITY = "capacity"         # Load%, bottleneck alerts
    ATTENDANCE = "attendance"     # Absenteeism, coverage alerts
    DOWNTIME = "downtime"         # Equipment/unplanned downtime
    MAINTENANCE = "maintenance"   # Equipment maintenance alerts
    AVAILABILITY = "availability" # Resource availability alerts
    HOLD = "hold"                 # Holds pending approval
    TREND = "trend"               # KPI trending alerts


class AlertStatus(str, Enum):
    """Alert lifecycle status"""
    ACTIVE = "active"             # Currently active
    ACKNOWLEDGED = "acknowledged"  # Seen but not resolved
    RESOLVED = "resolved"         # Issue addressed
    DISMISSED = "dismissed"       # False positive or no longer relevant


class AlertBase(BaseModel):
    """Base alert model"""
    category: AlertCategory
    severity: AlertSeverity
    title: str = Field(..., max_length=200, description="Short alert title")
    message: str = Field(..., description="Detailed alert message")
    recommendation: Optional[str] = Field(None, description="Suggested action")


class AlertCreate(AlertBase):
    """Create new alert"""
    client_id: Optional[str] = Field(None, description="Client ID (NULL for global)")
    kpi_key: Optional[str] = Field(None, description="Related KPI (efficiency, quality, etc.)")
    work_order_id: Optional[str] = Field(None, description="Related work order if applicable")
    current_value: Optional[Decimal] = Field(None, description="Current KPI value triggering alert")
    threshold_value: Optional[Decimal] = Field(None, description="Threshold that was crossed")
    predicted_value: Optional[Decimal] = Field(None, description="Predicted value if based on forecast")
    confidence: Optional[Decimal] = Field(None, ge=0, le=100, description="Prediction confidence %")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional context")


class AlertResponse(AlertBase):
    """Alert response model"""
    alert_id: str
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    kpi_key: Optional[str] = None
    work_order_id: Optional[str] = None
    current_value: Optional[Decimal] = None
    threshold_value: Optional[Decimal] = None
    predicted_value: Optional[Decimal] = None
    confidence: Optional[Decimal] = None
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    metadata: Optional[dict] = Field(None, alias="alert_metadata")

    class Config:
        from_attributes = True
        populate_by_name = True


class AlertUpdate(BaseModel):
    """Update alert status"""
    status: Optional[AlertStatus] = None
    resolution_notes: Optional[str] = None


class AlertAcknowledge(BaseModel):
    """Acknowledge alert"""
    notes: Optional[str] = None


class AlertResolve(BaseModel):
    """Resolve alert"""
    resolution_notes: str = Field(..., description="How the issue was resolved")


class AlertSummary(BaseModel):
    """Summary of alerts by category and severity"""
    total_active: int = 0
    by_severity: dict = Field(default_factory=dict)
    by_category: dict = Field(default_factory=dict)
    critical_count: int = 0
    urgent_count: int = 0


class AlertFilter(BaseModel):
    """Filter parameters for listing alerts"""
    client_id: Optional[str] = None
    category: Optional[AlertCategory] = None
    severity: Optional[AlertSeverity] = None
    status: Optional[AlertStatus] = None
    kpi_key: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


class AlertDashboard(BaseModel):
    """Dashboard view of alerts"""
    summary: AlertSummary
    urgent_alerts: List[AlertResponse] = []
    critical_alerts: List[AlertResponse] = []
    recent_alerts: List[AlertResponse] = []


# Specific alert types for different scenarios

class OTDRiskAlert(BaseModel):
    """OTD-specific alert details"""
    work_order_id: str
    client_name: str
    due_date: datetime
    current_completion: Decimal
    required_completion: Decimal
    risk_score: Decimal = Field(..., ge=0, le=100, description="0-100 risk score")
    days_remaining: int
    recommended_actions: List[str] = []


class QualityTrendAlert(BaseModel):
    """Quality trend alert details"""
    kpi_type: Literal["fpy", "rty", "dpmo", "ppm"]
    current_value: Decimal
    trend_direction: Literal["improving", "stable", "declining"]
    change_percent: Decimal
    period_days: int
    affected_product_lines: List[str] = []


class CapacityAlert(BaseModel):
    """Capacity planning alert details"""
    load_percent: Decimal
    status: Literal["underutilized", "optimal", "overloaded"]
    recommended_action: str
    idle_days_predicted: Optional[int] = None
    overtime_hours_needed: Optional[Decimal] = None
    bottleneck_station: Optional[str] = None


class AlertConfigBase(BaseModel):
    """Alert configuration for a client or global"""
    alert_type: AlertCategory
    enabled: bool = True
    warning_threshold: Optional[Decimal] = None
    critical_threshold: Optional[Decimal] = None
    notification_email: Optional[bool] = True
    notification_sms: Optional[bool] = False
    check_frequency_minutes: int = Field(default=60, ge=5, le=1440)


class AlertConfigCreate(AlertConfigBase):
    """Create alert configuration"""
    client_id: Optional[str] = None


class AlertConfigResponse(AlertConfigBase):
    """Alert configuration response"""
    config_id: str
    client_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
