"""
CRUD operations for Workflow
Implements Phase 10: Flexible Workflow Foundation

Provides:
- Transition log CRUD
- Workflow configuration management
- Bulk operations
"""
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from fastapi import HTTPException
import json

from backend.schemas.workflow import WorkflowTransitionLog
from backend.schemas.work_order import WorkOrder
from backend.schemas.client_config import ClientConfig
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.services.workflow_service import (
    WorkflowStateMachine,
    execute_transition,
    get_transition_history,
    bulk_transition as service_bulk_transition,
    apply_workflow_template as service_apply_template,
    get_workflow_config
)


# ============================================
# Transition Log CRUD
# ============================================

def create_transition_log(
    db: Session,
    work_order_id: str,
    client_id: str,
    from_status: Optional[str],
    to_status: str,
    user_id: Optional[int] = None,
    notes: Optional[str] = None,
    trigger_source: str = "manual",
    elapsed_from_received_hours: Optional[int] = None,
    elapsed_from_previous_hours: Optional[int] = None
) -> WorkflowTransitionLog:
    """
    Create a transition log entry.

    Args:
        db: Database session
        work_order_id: Work order ID
        client_id: Client ID
        from_status: Previous status
        to_status: New status
        user_id: User who performed transition
        notes: Optional notes
        trigger_source: Source of transition
        elapsed_from_received_hours: Hours since received
        elapsed_from_previous_hours: Hours since previous transition

    Returns:
        Created transition log entry
    """
    log_entry = WorkflowTransitionLog(
        work_order_id=work_order_id,
        client_id=client_id,
        from_status=from_status,
        to_status=to_status,
        transitioned_by=user_id,
        transitioned_at=datetime.utcnow(),
        notes=notes,
        trigger_source=trigger_source,
        elapsed_from_received_hours=elapsed_from_received_hours,
        elapsed_from_previous_hours=elapsed_from_previous_hours
    )

    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    return log_entry


def get_transition_log_by_id(
    db: Session,
    transition_id: int,
    current_user: User
) -> Optional[WorkflowTransitionLog]:
    """
    Get transition log entry by ID.
    SECURITY: Verifies user access to the client.

    Args:
        db: Database session
        transition_id: Transition log ID
        current_user: Authenticated user

    Returns:
        Transition log entry or None
    """
    log_entry = db.query(WorkflowTransitionLog).filter(
        WorkflowTransitionLog.transition_id == transition_id
    ).first()

    if log_entry:
        verify_client_access(current_user, log_entry.client_id)

    return log_entry


def get_work_order_transitions(
    db: Session,
    work_order_id: str,
    current_user: User
) -> List[WorkflowTransitionLog]:
    """
    Get all transitions for a work order.
    SECURITY: Verifies user access to the work order's client.

    Args:
        db: Database session
        work_order_id: Work order ID
        current_user: Authenticated user

    Returns:
        List of transition log entries
    """
    # Get work order to verify access
    work_order = db.query(WorkOrder).filter(
        WorkOrder.work_order_id == work_order_id
    ).first()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    verify_client_access(current_user, work_order.client_id)

    return get_transition_history(db, work_order_id, work_order.client_id)


def get_client_transitions(
    db: Session,
    client_id: str,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    trigger_source: Optional[str] = None
) -> List[WorkflowTransitionLog]:
    """
    Get transitions for a client with optional filtering.
    SECURITY: Verifies user access to the client.

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user
        skip: Records to skip
        limit: Maximum records
        from_status: Filter by from_status
        to_status: Filter by to_status
        trigger_source: Filter by trigger source

    Returns:
        List of transition log entries
    """
    verify_client_access(current_user, client_id)

    query = db.query(WorkflowTransitionLog).filter(
        WorkflowTransitionLog.client_id == client_id
    )

    if from_status:
        query = query.filter(WorkflowTransitionLog.from_status == from_status)
    if to_status:
        query = query.filter(WorkflowTransitionLog.to_status == to_status)
    if trigger_source:
        query = query.filter(WorkflowTransitionLog.trigger_source == trigger_source)

    return query.order_by(
        WorkflowTransitionLog.transitioned_at.desc()
    ).offset(skip).limit(limit).all()


# ============================================
# Workflow Configuration CRUD
# ============================================

def get_workflow_configuration(
    db: Session,
    client_id: str,
    current_user: User
) -> Dict:
    """
    Get workflow configuration for a client.
    SECURITY: Verifies user access to the client.

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user

    Returns:
        Dictionary with workflow configuration
    """
    verify_client_access(current_user, client_id)
    return get_workflow_config(db, client_id)


def update_workflow_configuration(
    db: Session,
    client_id: str,
    config_update: Dict,
    current_user: User
) -> Dict:
    """
    Update workflow configuration for a client.
    SECURITY: Only admins can update workflow configuration.

    Args:
        db: Database session
        client_id: Client ID
        config_update: Configuration updates
        current_user: Authenticated user

    Returns:
        Updated workflow configuration

    Raises:
        HTTPException 403: If user is not admin
    """
    verify_client_access(current_user, client_id)

    # Only admins can modify workflow configuration
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=403,
            detail="Only admins can update workflow configuration"
        )

    # Get or create client config
    config = db.query(ClientConfig).filter(
        ClientConfig.client_id == client_id
    ).first()

    if not config:
        config = ClientConfig(client_id=client_id)
        db.add(config)

    # Update workflow fields
    if 'workflow_statuses' in config_update:
        config.workflow_statuses = json.dumps(config_update['workflow_statuses'])

    if 'workflow_transitions' in config_update:
        config.workflow_transitions = json.dumps(config_update['workflow_transitions'])

    if 'workflow_optional_statuses' in config_update:
        config.workflow_optional_statuses = json.dumps(config_update['workflow_optional_statuses'])

    if 'workflow_closure_trigger' in config_update:
        config.workflow_closure_trigger = config_update['workflow_closure_trigger']

    # Increment version
    config.workflow_version = (config.workflow_version or 0) + 1

    db.commit()
    db.refresh(config)

    return get_workflow_config(db, client_id)


def apply_workflow_template(
    db: Session,
    client_id: str,
    template_id: str,
    current_user: User
) -> Dict:
    """
    Apply a workflow template to a client.
    SECURITY: Only admins can apply workflow templates.

    Args:
        db: Database session
        client_id: Client ID
        template_id: Template ID
        current_user: Authenticated user

    Returns:
        Updated workflow configuration

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 404: If template not found
    """
    verify_client_access(current_user, client_id)

    if current_user.role != 'admin':
        raise HTTPException(
            status_code=403,
            detail="Only admins can apply workflow templates"
        )

    return service_apply_template(db, client_id, template_id)


# ============================================
# Transition Operations
# ============================================

def transition_work_order(
    db: Session,
    work_order_id: str,
    to_status: str,
    current_user: User,
    notes: Optional[str] = None
) -> Dict:
    """
    Transition a work order to a new status.
    SECURITY: Verifies user access to the work order's client.

    Args:
        db: Database session
        work_order_id: Work order ID
        to_status: Target status
        current_user: Authenticated user
        notes: Optional notes

    Returns:
        Dictionary with work order and transition log

    Raises:
        HTTPException 400: If transition is invalid
        HTTPException 404: If work order not found
    """
    work_order = db.query(WorkOrder).filter(
        WorkOrder.work_order_id == work_order_id
    ).first()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    verify_client_access(current_user, work_order.client_id)

    # Execute transition
    updated_wo, transition = execute_transition(
        db=db,
        work_order=work_order,
        to_status=to_status,
        user_id=current_user.user_id,
        notes=notes,
        trigger_source="manual"
    )

    return {
        "work_order": updated_wo,
        "transition": transition,
        "success": True
    }


def validate_transition(
    db: Session,
    work_order_id: str,
    to_status: str,
    current_user: User
) -> Dict:
    """
    Validate if a transition is allowed without executing it.
    SECURITY: Verifies user access to the work order's client.

    Args:
        db: Database session
        work_order_id: Work order ID
        to_status: Target status
        current_user: Authenticated user

    Returns:
        Dictionary with validation result
    """
    work_order = db.query(WorkOrder).filter(
        WorkOrder.work_order_id == work_order_id
    ).first()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    verify_client_access(current_user, work_order.client_id)

    sm = WorkflowStateMachine(db, work_order.client_id)
    is_valid, reason = sm.validate_transition(work_order, to_status)
    allowed = sm.get_allowed_transitions(work_order.status)

    return {
        "is_valid": is_valid,
        "from_status": work_order.status,
        "to_status": to_status,
        "reason": reason,
        "allowed_transitions": allowed
    }


def get_allowed_transitions_for_work_order(
    db: Session,
    work_order_id: str,
    current_user: User
) -> Dict:
    """
    Get allowed transitions for a work order.
    SECURITY: Verifies user access to the work order's client.

    Args:
        db: Database session
        work_order_id: Work order ID
        current_user: Authenticated user

    Returns:
        Dictionary with current status and allowed transitions
    """
    work_order = db.query(WorkOrder).filter(
        WorkOrder.work_order_id == work_order_id
    ).first()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    verify_client_access(current_user, work_order.client_id)

    sm = WorkflowStateMachine(db, work_order.client_id)
    allowed = sm.get_allowed_transitions(work_order.status)

    return {
        "work_order_id": work_order_id,
        "current_status": work_order.status,
        "allowed_next_statuses": allowed,
        "client_id": work_order.client_id
    }


def bulk_transition_work_orders(
    db: Session,
    work_order_ids: List[str],
    to_status: str,
    client_id: str,
    current_user: User,
    notes: Optional[str] = None
) -> Dict:
    """
    Perform bulk status transition.
    SECURITY: Verifies user access to the client.

    Args:
        db: Database session
        work_order_ids: List of work order IDs
        to_status: Target status
        client_id: Client ID
        current_user: Authenticated user
        notes: Optional notes

    Returns:
        Dictionary with bulk operation results
    """
    verify_client_access(current_user, client_id)

    return service_bulk_transition(
        db=db,
        work_order_ids=work_order_ids,
        to_status=to_status,
        client_id=client_id,
        user_id=current_user.user_id,
        notes=notes
    )


# ============================================
# Analytics & Reporting
# ============================================

def get_transition_statistics(
    db: Session,
    client_id: str,
    current_user: User
) -> Dict:
    """
    Get transition statistics for a client.
    SECURITY: Verifies user access to the client.

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user

    Returns:
        Dictionary with transition statistics
    """
    verify_client_access(current_user, client_id)

    # Total transitions
    total = db.query(func.count(WorkflowTransitionLog.transition_id)).filter(
        WorkflowTransitionLog.client_id == client_id
    ).scalar()

    # Transitions by type
    by_transition = db.query(
        WorkflowTransitionLog.from_status,
        WorkflowTransitionLog.to_status,
        func.count(WorkflowTransitionLog.transition_id).label('count'),
        func.avg(WorkflowTransitionLog.elapsed_from_previous_hours).label('avg_hours')
    ).filter(
        WorkflowTransitionLog.client_id == client_id
    ).group_by(
        WorkflowTransitionLog.from_status,
        WorkflowTransitionLog.to_status
    ).all()

    # Transitions by source
    by_source = db.query(
        WorkflowTransitionLog.trigger_source,
        func.count(WorkflowTransitionLog.transition_id).label('count')
    ).filter(
        WorkflowTransitionLog.client_id == client_id
    ).group_by(
        WorkflowTransitionLog.trigger_source
    ).all()

    return {
        "client_id": client_id,
        "total_transitions": total,
        "by_transition": [
            {
                "from_status": t.from_status,
                "to_status": t.to_status,
                "count": t.count,
                "avg_elapsed_hours": round(t.avg_hours, 2) if t.avg_hours else None
            }
            for t in by_transition
        ],
        "by_source": [
            {"trigger_source": s.trigger_source, "count": s.count}
            for s in by_source
        ]
    }


def get_status_distribution(
    db: Session,
    client_id: str,
    current_user: User
) -> Dict:
    """
    Get current status distribution for work orders.
    SECURITY: Verifies user access to the client.

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user

    Returns:
        Dictionary with status distribution
    """
    verify_client_access(current_user, client_id)

    total = db.query(func.count(WorkOrder.work_order_id)).filter(
        WorkOrder.client_id == client_id
    ).scalar()

    by_status = db.query(
        WorkOrder.status,
        func.count(WorkOrder.work_order_id).label('count')
    ).filter(
        WorkOrder.client_id == client_id
    ).group_by(
        WorkOrder.status
    ).all()

    return {
        "client_id": client_id,
        "total_work_orders": total,
        "by_status": [
            {
                "status": s.status,
                "count": s.count,
                "percentage": round((s.count / total * 100), 2) if total > 0 else 0
            }
            for s in by_status
        ]
    }
