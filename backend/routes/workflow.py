"""
Workflow API Routes
Implements Phase 10: Flexible Workflow Foundation

Provides endpoints for:
- Status transitions
- Transition history
- Workflow configuration
- Bulk operations
- Elapsed time analytics
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Any, List, Optional, Dict
from datetime import datetime

from backend.database import get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User
from backend.dependencies import PaginationParams
from backend.schemas.workflow import (
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
from backend.services.workflow_crud_service import (
    get_transitions_for_work_order as get_work_order_transitions,
    get_transitions_for_client as get_client_transitions,
    get_config as get_workflow_configuration,
    update_config as update_workflow_configuration,
    apply_template as apply_workflow_template,
    execute_transition as transition_work_order,
    check_transition_valid as validate_transition,
    get_allowed_transitions as get_allowed_transitions_for_work_order,
    bulk_transition as bulk_transition_work_orders,
    get_statistics as get_transition_statistics,
    get_distribution as get_status_distribution,
)
from backend.calculations.elapsed_time import (
    calculate_work_order_elapsed_times,
    calculate_client_average_times,
    get_transition_elapsed_times,
    calculate_stage_duration_summary,
)
from backend.orm.work_order import WorkOrder
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/workflow", tags=["Workflow"])


# ============================================
# Status Transitions
# ============================================


@router.post("/work-orders/{work_order_id}/transition", response_model=Dict)
def transition_work_order_status(
    work_order_id: str,
    transition: WorkflowTransitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Transition a work order to a new status.

    Validates the transition against the client's workflow configuration.
    Logs the transition in the audit trail.

    SECURITY: Requires authentication and client access.
    """
    result = transition_work_order(
        db=db,
        work_order_id=work_order_id,
        to_status=transition.to_status.value,
        current_user=current_user,
        notes=transition.notes,
    )
    db.commit()
    return result


@router.post("/work-orders/{work_order_id}/validate", response_model=Dict)
def validate_work_order_transition(
    work_order_id: str,
    to_status: str = Query(..., description="Target status to validate"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Validate if a transition is allowed without executing it.

    Returns whether the transition is valid and the reason if not.

    SECURITY: Requires authentication and client access.
    """
    return validate_transition(db=db, work_order_id=work_order_id, to_status=to_status, current_user=current_user)


@router.get("/work-orders/{work_order_id}/allowed-transitions", response_model=Dict)
def get_work_order_allowed_transitions(
    work_order_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get list of allowed status transitions for a work order.

    Returns the current status and all valid next statuses.

    SECURITY: Requires authentication and client access.
    """
    return get_allowed_transitions_for_work_order(db=db, work_order_id=work_order_id, current_user=current_user)


@router.get("/work-orders/{work_order_id}/history", response_model=List[WorkflowTransitionResponse])
def get_work_order_transition_history(
    work_order_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get complete transition history for a work order.

    Returns all status changes in chronological order.

    SECURITY: Requires authentication and client access.
    """
    return get_work_order_transitions(db=db, work_order_id=work_order_id, current_user=current_user)


# ============================================
# Bulk Operations
# ============================================


@router.post("/bulk-transition", response_model=Dict)
def bulk_transition_work_orders_endpoint(
    request: BulkTransitionRequest,
    client_id: str = Query(..., description="Client ID for the work orders"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> Dict[str, Any]:
    """
    Transition multiple work orders to a new status.

    All work orders must belong to the specified client.
    Returns results for each work order (success or failure).

    SECURITY: Requires supervisor role.
    """
    result = bulk_transition_work_orders(
        db=db,
        work_order_ids=request.work_order_ids,
        to_status=request.to_status.value,
        client_id=client_id,
        current_user=current_user,
        notes=request.notes,
    )
    db.commit()
    return result


# ============================================
# Workflow Configuration
# ============================================


@router.get("/config/{client_id}", response_model=Dict)
def get_client_workflow_config(
    client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get workflow configuration for a client.

    Returns the client's workflow statuses, transitions, and settings.

    SECURITY: Requires authentication and client access.
    """
    return get_workflow_configuration(db=db, client_id=client_id, current_user=current_user)


@router.put("/config/{client_id}", response_model=Dict)
def update_client_workflow_config(
    client_id: str,
    config: WorkflowConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> Dict[str, Any]:
    """
    Update workflow configuration for a client.

    SECURITY: Requires admin role.
    """
    config_dict = config.model_dump(exclude_none=True)
    result = update_workflow_configuration(
        db=db, client_id=client_id, config_update=config_dict, current_user=current_user
    )
    db.commit()
    return result


@router.post("/config/{client_id}/apply-template", response_model=Dict)
def apply_workflow_template_endpoint(
    client_id: str,
    template_id: str = Query(..., description="Template ID to apply"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> Dict[str, Any]:
    """
    Apply a workflow template to a client.

    Available templates: standard, simple, express

    SECURITY: Requires admin role.
    """
    result = apply_workflow_template(db=db, client_id=client_id, template_id=template_id, current_user=current_user)
    db.commit()
    return result


@router.get("/templates", response_model=Dict)
def list_workflow_templates(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    List available workflow templates.

    Returns all pre-defined workflow configurations.
    """
    templates = []
    for template_id, template in WORKFLOW_TEMPLATES.items():
        templates.append(
            {
                "template_id": template.template_id,
                "name": template.name,
                "description": template.description,
                "workflow_statuses": template.workflow_statuses,
                "workflow_closure_trigger": template.workflow_closure_trigger,
            }
        )

    return {"templates": templates, "count": len(templates)}


# ============================================
# Elapsed Time Analytics
# ============================================


@router.get("/work-orders/{work_order_id}/elapsed-time", response_model=Dict)
def get_work_order_elapsed_time(
    work_order_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get elapsed time metrics for a work order.

    Returns lifecycle times, stage durations, and overdue status.

    SECURITY: Requires authentication and client access.
    """
    from backend.middleware.client_auth import verify_client_access

    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    verify_client_access(current_user, work_order.client_id)

    return calculate_work_order_elapsed_times(work_order)


@router.get("/work-orders/{work_order_id}/transition-times", response_model=List[Dict])
def get_work_order_transition_times(
    work_order_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """
    Get elapsed times between each transition for a work order.

    Returns detailed timing for each status change.

    SECURITY: Requires authentication and client access.
    """
    from backend.middleware.client_auth import verify_client_access

    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    verify_client_access(current_user, work_order.client_id)

    return get_transition_elapsed_times(db=db, work_order_id=work_order_id, client_id=work_order.client_id)


@router.get("/analytics/{client_id}/average-times", response_model=Dict)
def get_client_average_elapsed_times(
    client_id: str,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get average elapsed times for a client's work orders.

    Returns aggregate metrics for lifecycle, lead time, and processing.

    SECURITY: Requires authentication and client access.
    """
    from backend.middleware.client_auth import verify_client_access

    verify_client_access(current_user, client_id)

    return calculate_client_average_times(
        db=db, client_id=client_id, status=status_filter, start_date=start_date, end_date=end_date
    )


@router.get("/analytics/{client_id}/stage-durations", response_model=Dict)
def get_client_stage_durations(
    client_id: str,
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get average duration for each workflow stage.

    Returns timing statistics for each type of transition.

    SECURITY: Requires authentication and client access.
    """
    from backend.middleware.client_auth import verify_client_access

    verify_client_access(current_user, client_id)

    return calculate_stage_duration_summary(db=db, client_id=client_id, start_date=start_date, end_date=end_date)


# ============================================
# Statistics & Reporting
# ============================================


@router.get("/statistics/{client_id}/transitions", response_model=Dict)
def get_client_transition_statistics(
    client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get transition statistics for a client.

    Returns counts and averages for all transition types.

    SECURITY: Requires authentication and client access.
    """
    return get_transition_statistics(db=db, client_id=client_id, current_user=current_user)


@router.get("/statistics/{client_id}/status-distribution", response_model=Dict)
def get_client_status_distribution(
    client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get current status distribution for work orders.

    Returns count and percentage of work orders in each status.

    SECURITY: Requires authentication and client access.
    """
    return get_status_distribution(db=db, client_id=client_id, current_user=current_user)


@router.get("/transitions/{client_id}", response_model=List[WorkflowTransitionResponse])
def get_client_all_transitions(
    client_id: str,
    pagination: PaginationParams = Depends(),
    from_status: Optional[str] = Query(None, description="Filter by from_status"),
    to_status: Optional[str] = Query(None, description="Filter by to_status"),
    trigger_source: Optional[str] = Query(None, description="Filter by trigger source"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get all transitions for a client with filtering.

    Returns paginated list of all status changes.

    SECURITY: Requires authentication and client access.
    """
    return get_client_transitions(
        db=db,
        client_id=client_id,
        current_user=current_user,
        skip=pagination.skip,
        limit=pagination.limit,
        from_status=from_status,
        to_status=to_status,
        trigger_source=trigger_source,
    )
