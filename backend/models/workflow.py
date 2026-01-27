"""
Workflow Pydantic models for request/response validation
Implements Phase 10: Flexible Workflow Foundation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class WorkflowStatusEnum(str, Enum):
    """All possible workflow statuses"""
    RECEIVED = "RECEIVED"
    RELEASED = "RELEASED"
    DEMOTED = "DEMOTED"
    ACTIVE = "ACTIVE"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    SHIPPED = "SHIPPED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ClosureTriggerEnum(str, Enum):
    """When to automatically close an order"""
    AT_SHIPMENT = "at_shipment"           # Close when shipped
    AT_CLIENT_RECEIPT = "at_client_receipt"  # Close when client confirms receipt
    AT_COMPLETION = "at_completion"        # Close when production completes (skip shipping)
    MANUAL = "manual"                      # Never auto-close


class TriggerSourceEnum(str, Enum):
    """Source of a status transition"""
    MANUAL = "manual"           # User-initiated via UI
    AUTOMATIC = "automatic"     # System-triggered (e.g., auto-close)
    BULK = "bulk"               # Part of bulk operation
    API = "api"                 # Direct API call
    IMPORT = "import"           # Data import


# ===========================================
# Workflow Transition Models
# ===========================================

class WorkflowTransitionCreate(BaseModel):
    """Create a status transition request"""
    to_status: WorkflowStatusEnum = Field(..., description="Target status to transition to")
    notes: Optional[str] = Field(None, max_length=500, description="Reason or notes for this transition")
    trigger_source: TriggerSourceEnum = Field(default=TriggerSourceEnum.MANUAL)


class WorkflowTransitionResponse(BaseModel):
    """Response for a completed transition"""
    transition_id: int
    work_order_id: str
    client_id: str
    from_status: Optional[str] = None
    to_status: str
    transitioned_by: Optional[int] = None
    transitioned_at: datetime
    notes: Optional[str] = None
    trigger_source: Optional[str] = None
    elapsed_from_received_hours: Optional[int] = None
    elapsed_from_previous_hours: Optional[int] = None

    class Config:
        from_attributes = True


class WorkflowTransitionHistory(BaseModel):
    """Transition history for a work order"""
    work_order_id: str
    transitions: List[WorkflowTransitionResponse]
    total_transitions: int


# ===========================================
# Workflow Configuration Models
# ===========================================

class WorkflowConfigCreate(BaseModel):
    """Create/update workflow configuration for a client"""
    workflow_statuses: List[str] = Field(
        default=["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED"],
        description="Ordered list of statuses in the workflow"
    )
    workflow_transitions: Dict[str, List[str]] = Field(
        default={
            "RELEASED": ["RECEIVED"],
            "IN_PROGRESS": ["RELEASED"],
            "COMPLETED": ["IN_PROGRESS"],
            "SHIPPED": ["COMPLETED"],
            "CLOSED": ["SHIPPED", "COMPLETED"],
            "ON_HOLD": ["RECEIVED", "RELEASED", "IN_PROGRESS"],
            "DEMOTED": ["RELEASED"],
            "CANCELLED": ["RECEIVED", "RELEASED", "IN_PROGRESS", "ON_HOLD", "DEMOTED"],
            "REJECTED": ["IN_PROGRESS", "COMPLETED"]
        },
        description="Map of TO_STATUS to list of allowed FROM_STATUS values"
    )
    workflow_optional_statuses: List[str] = Field(
        default=["SHIPPED", "DEMOTED"],
        description="Statuses that can be skipped"
    )
    workflow_closure_trigger: ClosureTriggerEnum = Field(
        default=ClosureTriggerEnum.AT_SHIPMENT,
        description="When to automatically close orders"
    )


class WorkflowConfigResponse(BaseModel):
    """Workflow configuration response"""
    client_id: str
    workflow_statuses: List[str]
    workflow_transitions: Dict[str, List[str]]
    workflow_optional_statuses: List[str]
    workflow_closure_trigger: str
    workflow_version: int

    class Config:
        from_attributes = True


class WorkflowConfigUpdate(BaseModel):
    """Update workflow configuration (all fields optional)"""
    workflow_statuses: Optional[List[str]] = None
    workflow_transitions: Optional[Dict[str, List[str]]] = None
    workflow_optional_statuses: Optional[List[str]] = None
    workflow_closure_trigger: Optional[ClosureTriggerEnum] = None


# ===========================================
# Workflow Validation Models
# ===========================================

class TransitionValidationRequest(BaseModel):
    """Request to validate if a transition is allowed"""
    work_order_id: str
    from_status: str
    to_status: str


class TransitionValidationResponse(BaseModel):
    """Response for transition validation"""
    is_valid: bool
    from_status: str
    to_status: str
    reason: Optional[str] = None  # Explanation if invalid
    allowed_transitions: List[str] = []  # Valid next statuses from current


class AllowedTransitionsResponse(BaseModel):
    """List of allowed transitions from a status"""
    current_status: str
    allowed_next_statuses: List[str]
    client_id: str


# ===========================================
# Bulk Operations Models
# ===========================================

class BulkTransitionRequest(BaseModel):
    """Request to transition multiple work orders"""
    work_order_ids: List[str] = Field(..., min_length=1, max_length=100)
    to_status: WorkflowStatusEnum
    notes: Optional[str] = Field(None, max_length=500)


class BulkTransitionResult(BaseModel):
    """Result of a single work order in bulk transition"""
    work_order_id: str
    success: bool
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    error: Optional[str] = None


class BulkTransitionResponse(BaseModel):
    """Response for bulk transition operation"""
    total_requested: int
    successful: int
    failed: int
    results: List[BulkTransitionResult]


# ===========================================
# Workflow Templates
# ===========================================

class WorkflowTemplate(BaseModel):
    """Pre-built workflow template"""
    template_id: str
    name: str
    description: str
    workflow_statuses: List[str]
    workflow_transitions: Dict[str, List[str]]
    workflow_optional_statuses: List[str]
    workflow_closure_trigger: str


# Default templates
WORKFLOW_TEMPLATES = {
    "standard": WorkflowTemplate(
        template_id="standard",
        name="Standard Manufacturing",
        description="Full lifecycle: Received → Released → In Progress → Completed → Shipped → Closed",
        workflow_statuses=["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED"],
        workflow_transitions={
            "RELEASED": ["RECEIVED"],
            "IN_PROGRESS": ["RELEASED"],
            "COMPLETED": ["IN_PROGRESS"],
            "SHIPPED": ["COMPLETED"],
            "CLOSED": ["SHIPPED", "COMPLETED"],
            "ON_HOLD": ["RECEIVED", "RELEASED", "IN_PROGRESS"],
            "DEMOTED": ["RELEASED"],
            "CANCELLED": ["RECEIVED", "RELEASED", "IN_PROGRESS", "ON_HOLD", "DEMOTED"],
            "REJECTED": ["IN_PROGRESS", "COMPLETED"]
        },
        workflow_optional_statuses=["SHIPPED", "DEMOTED"],
        workflow_closure_trigger="at_shipment"
    ),
    "simple": WorkflowTemplate(
        template_id="simple",
        name="Simple Workflow",
        description="Minimal tracking: Received → In Progress → Completed → Closed",
        workflow_statuses=["RECEIVED", "IN_PROGRESS", "COMPLETED", "CLOSED"],
        workflow_transitions={
            "IN_PROGRESS": ["RECEIVED"],
            "COMPLETED": ["IN_PROGRESS"],
            "CLOSED": ["COMPLETED"],
            "ON_HOLD": ["RECEIVED", "IN_PROGRESS"],
            "CANCELLED": ["RECEIVED", "IN_PROGRESS", "ON_HOLD"]
        },
        workflow_optional_statuses=[],
        workflow_closure_trigger="at_completion"
    ),
    "express": WorkflowTemplate(
        template_id="express",
        name="Express Workflow",
        description="Minimal tracking for fast-turnaround: Received → Completed",
        workflow_statuses=["RECEIVED", "COMPLETED"],
        workflow_transitions={
            "COMPLETED": ["RECEIVED"],
            "CANCELLED": ["RECEIVED"]
        },
        workflow_optional_statuses=[],
        workflow_closure_trigger="at_completion"
    )
}
