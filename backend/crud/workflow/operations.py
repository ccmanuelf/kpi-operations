"""
CRUD operations for Workflow Transitions
Implements Phase 10: Flexible Workflow Foundation - Transition operations
"""

from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.schemas.work_order import WorkOrder
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.services.workflow_service import (
    WorkflowStateMachine,
    execute_transition,
    bulk_transition as service_bulk_transition,
)


def transition_work_order(
    db: Session, work_order_id: str, to_status: str, current_user: User, notes: Optional[str] = None
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
    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

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
        trigger_source="manual",
    )

    return {"work_order": updated_wo, "transition": transition, "success": True}


def validate_transition(db: Session, work_order_id: str, to_status: str, current_user: User) -> Dict:
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
    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

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
        "allowed_transitions": allowed,
    }


def get_allowed_transitions_for_work_order(db: Session, work_order_id: str, current_user: User) -> Dict:
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
    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    verify_client_access(current_user, work_order.client_id)

    sm = WorkflowStateMachine(db, work_order.client_id)
    allowed = sm.get_allowed_transitions(work_order.status)

    return {
        "work_order_id": work_order_id,
        "current_status": work_order.status,
        "allowed_next_statuses": allowed,
        "client_id": work_order.client_id,
    }


def bulk_transition_work_orders(
    db: Session,
    work_order_ids: List[str],
    to_status: str,
    client_id: str,
    current_user: User,
    notes: Optional[str] = None,
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
        notes=notes,
    )
