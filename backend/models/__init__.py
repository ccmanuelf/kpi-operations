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
from .work_order import (
    WorkOrderCreate,
    WorkOrderUpdate,
    WorkOrderResponse,
    WorkOrderWithMetrics,
    WorkOrderStatusEnum,
)
from .workflow import (
    WorkflowStatusEnum,
    ClosureTriggerEnum,
    TriggerSourceEnum,
    WorkflowTransitionCreate,
    WorkflowTransitionResponse,
    WorkflowTransitionHistory,
    WorkflowConfigCreate,
    WorkflowConfigResponse,
    WorkflowConfigUpdate,
    TransitionValidationRequest,
    TransitionValidationResponse,
    AllowedTransitionsResponse,
    BulkTransitionRequest,
    BulkTransitionResponse,
    WorkflowTemplate,
    WORKFLOW_TEMPLATES,
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
    # Work Order models (Phase 10)
    "WorkOrderCreate",
    "WorkOrderUpdate",
    "WorkOrderResponse",
    "WorkOrderWithMetrics",
    "WorkOrderStatusEnum",
    # Workflow models (Phase 10)
    "WorkflowStatusEnum",
    "ClosureTriggerEnum",
    "TriggerSourceEnum",
    "WorkflowTransitionCreate",
    "WorkflowTransitionResponse",
    "WorkflowTransitionHistory",
    "WorkflowConfigCreate",
    "WorkflowConfigResponse",
    "WorkflowConfigUpdate",
    "TransitionValidationRequest",
    "TransitionValidationResponse",
    "AllowedTransitionsResponse",
    "BulkTransitionRequest",
    "BulkTransitionResponse",
    "WorkflowTemplate",
    "WORKFLOW_TEMPLATES",
]
