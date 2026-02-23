"""
User Preferences Pydantic models
Dashboard customization and widget configuration
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class DashboardWidgetConfig(BaseModel):
    """
    Individual widget configuration within a dashboard

    Attributes:
        widget_key: Unique identifier for the widget type
        widget_name: Display name for the widget
        widget_order: Position in the dashboard layout (0-indexed)
        is_visible: Whether the widget is displayed
        custom_config: Widget-specific settings (chart type, filters, etc.)
    """

    widget_key: str = Field(..., min_length=1, max_length=50, description="Unique identifier for the widget type")
    widget_name: str = Field(..., min_length=1, max_length=100, description="Display name shown in the dashboard header")
    widget_order: int = Field(default=0, ge=0, le=100, description="Position in the dashboard layout, 0-indexed")
    is_visible: bool = Field(default=True, description="Whether this widget is displayed on the dashboard")
    custom_config: Optional[Dict[str, Any]] = Field(default=None, description="Widget-specific settings such as chart type, filters, and display options")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "widget_key": "production_summary",
                "widget_name": "Production Summary",
                "widget_order": 0,
                "is_visible": True,
                "custom_config": {"chart_type": "bar", "time_range": "7d", "show_trend": True},
            }
        }


class DashboardPreferences(BaseModel):
    """
    Complete dashboard preferences for a user

    Attributes:
        layout: Dashboard layout type (grid, list, compact)
        widgets: List of widget configurations
        theme: Color theme preference
        auto_refresh: Auto-refresh interval in seconds (0 = disabled)
        default_time_range: Default time range for data displays
    """

    layout: str = Field(default="grid", pattern="^(grid|list|compact)$", description="Dashboard layout type: grid, list, or compact")
    widgets: List[DashboardWidgetConfig] = Field(default_factory=list, description="Ordered list of widget configurations for the dashboard")
    theme: str = Field(default="light", pattern="^(light|dark|system)$", description="Color theme preference: light, dark, or system")
    auto_refresh: int = Field(default=0, ge=0, le=3600, description="Auto-refresh interval in seconds; 0 disables auto-refresh")
    default_time_range: str = Field(default="7d", pattern="^(1d|7d|30d|90d)$", description="Default time range for KPI data displays: 1d, 7d, 30d, or 90d")

    @field_validator("widgets")
    @classmethod
    def validate_widgets(cls, v: List[DashboardWidgetConfig]) -> List[DashboardWidgetConfig]:
        """Ensure no duplicate widget keys"""
        widget_keys = [w.widget_key for w in v]
        if len(widget_keys) != len(set(widget_keys)):
            raise ValueError("Duplicate widget keys are not allowed")
        return v

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "layout": "grid",
                "widgets": [
                    {
                        "widget_key": "production_summary",
                        "widget_name": "Production Summary",
                        "widget_order": 0,
                        "is_visible": True,
                    },
                    {
                        "widget_key": "quality_metrics",
                        "widget_name": "Quality Metrics",
                        "widget_order": 1,
                        "is_visible": True,
                    },
                ],
                "theme": "light",
                "auto_refresh": 300,
                "default_time_range": "7d",
            }
        }


class DashboardPreferencesUpdate(BaseModel):
    """
    Partial update model for dashboard preferences
    All fields are optional for PATCH-style updates
    """

    layout: Optional[str] = Field(default=None, pattern="^(grid|list|compact)$", description="Updated dashboard layout type")
    widgets: Optional[List[DashboardWidgetConfig]] = Field(default=None, description="Updated list of widget configurations")
    theme: Optional[str] = Field(default=None, pattern="^(light|dark|system)$", description="Updated color theme preference")
    auto_refresh: Optional[int] = Field(default=None, ge=0, le=3600, description="Updated auto-refresh interval in seconds")
    default_time_range: Optional[str] = Field(default=None, pattern="^(1d|7d|30d|90d)$", description="Updated default time range for KPI displays")

    @field_validator("widgets")
    @classmethod
    def validate_widgets(cls, v: Optional[List[DashboardWidgetConfig]]) -> Optional[List[DashboardWidgetConfig]]:
        """Ensure no duplicate widget keys if widgets provided"""
        if v is None:
            return v
        widget_keys = [w.widget_key for w in v]
        if len(widget_keys) != len(set(widget_keys)):
            raise ValueError("Duplicate widget keys are not allowed")
        return v

    class Config:
        from_attributes = True


class PreferenceResponse(BaseModel):
    """
    Full preference response with metadata

    Attributes:
        preference_id: Database ID
        user_id: Owner user ID
        preference_type: Type of preference (dashboard, theme, etc.)
        preferences: The actual preference data
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    preference_id: int = Field(..., description="Unique database identifier for this preference record")
    user_id: str = Field(..., description="User ID of the preference owner")
    preference_type: str = Field(..., description="Category of preference: dashboard, theme, or notifications")
    preferences: DashboardPreferences = Field(..., description="The full dashboard preference configuration")
    created_at: datetime = Field(..., description="Timestamp when the preference was first created")
    updated_at: datetime = Field(..., description="Timestamp of the last preference modification")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "preference_id": 1,
                "user_id": "user-001",
                "preference_type": "dashboard",
                "preferences": {
                    "layout": "grid",
                    "widgets": [],
                    "theme": "light",
                    "auto_refresh": 300,
                    "default_time_range": "7d",
                },
                "created_at": "2024-01-15T10:30:00",
                "updated_at": "2024-01-15T10:30:00",
            }
        }


class WidgetDefaultResponse(BaseModel):
    """
    Response model for default widget configurations
    """

    config_id: int = Field(..., description="Unique identifier for this default widget configuration")
    role: str = Field(..., description="User role this default applies to: admin, supervisor, operator, or viewer")
    widget_key: str = Field(..., description="Unique identifier for the widget type")
    widget_name: str = Field(..., description="Display name shown in the dashboard header")
    widget_order: int = Field(..., description="Default position in the dashboard layout")
    is_visible: bool = Field(..., description="Whether this widget is visible by default for the role")
    default_config: Optional[Dict[str, Any]] = Field(None, description="Default widget-specific settings for this role")

    @field_validator("default_config", mode="before")
    @classmethod
    def parse_default_config(cls, v):
        """Parse JSON string to dict if needed"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    class Config:
        from_attributes = True


class RoleDefaultsResponse(BaseModel):
    """
    Response containing all default widgets for a role
    """

    role: str = Field(..., description="User role these defaults apply to")
    widgets: List[WidgetDefaultResponse] = Field(..., description="List of default widget configurations for the role")
    total_widgets: int = Field(..., description="Total number of default widgets configured for this role")

    class Config:
        from_attributes = True


class ResetPreferencesRequest(BaseModel):
    """
    Request model for resetting preferences to role defaults
    """

    role: Optional[str] = Field(default=None, description="Role to reset to (uses current user role if not specified)")

    class Config:
        json_schema_extra = {"example": {"role": "operator"}}


class ResetPreferencesResponse(BaseModel):
    """
    Response after resetting preferences
    """

    success: bool = Field(..., description="Whether the preference reset completed successfully")
    message: str = Field(..., description="Human-readable result message")
    reset_to_role: str = Field(..., description="The role whose defaults were applied")
    widgets_applied: int = Field(..., description="Number of default widgets applied from the role template")
    preferences: DashboardPreferences = Field(..., description="The resulting dashboard preferences after reset")

    class Config:
        from_attributes = True
