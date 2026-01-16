"""
Pydantic models for request/response validation
"""
from .user import UserCreate, UserLogin, UserResponse, Token
from .production import (
    ProductionEntryCreate,
    ProductionEntryUpdate,
    ProductionEntryResponse,
    ProductionEntryWithKPIs,
    CSVUploadResponse,
    KPICalculationResponse
)
from .preferences import (
    DashboardWidgetConfig,
    DashboardPreferences,
    DashboardPreferencesUpdate,
    PreferenceResponse,
    WidgetDefaultResponse,
    RoleDefaultsResponse,
    ResetPreferencesRequest,
    ResetPreferencesResponse
)

__all__ = [
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "Token",
    "ProductionEntryCreate",
    "ProductionEntryUpdate",
    "ProductionEntryResponse",
    "ProductionEntryWithKPIs",
    "CSVUploadResponse",
    "KPICalculationResponse",
    # Preferences models
    "DashboardWidgetConfig",
    "DashboardPreferences",
    "DashboardPreferencesUpdate",
    "PreferenceResponse",
    "WidgetDefaultResponse",
    "RoleDefaultsResponse",
    "ResetPreferencesRequest",
    "ResetPreferencesResponse",
]
