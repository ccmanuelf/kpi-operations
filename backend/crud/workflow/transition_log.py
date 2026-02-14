"""
CRUD operations for Workflow Transition Log
Implements Phase 10: Flexible Workflow Foundation - Transition logging
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.schemas.workflow import WorkflowTransitionLog
from backend.schemas.work_order import WorkOrder
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.services.workflow_service import get_transition_history


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
    elapsed_from_previous_hours: Optional[int] = None,
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
        elapsed_from_previous_hours=elapsed_from_previous_hours,
    )

    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    return log_entry


def get_transition_log_by_id(db: Session, transition_id: int, current_user: User) -> Optional[WorkflowTransitionLog]:
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
    log_entry = db.query(WorkflowTransitionLog).filter(WorkflowTransitionLog.transition_id == transition_id).first()

    if log_entry:
        verify_client_access(current_user, log_entry.client_id)

    return log_entry


def get_work_order_transitions(db: Session, work_order_id: str, current_user: User) -> List[WorkflowTransitionLog]:
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
    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

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
    trigger_source: Optional[str] = None,
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

    query = db.query(WorkflowTransitionLog).filter(WorkflowTransitionLog.client_id == client_id)

    if from_status:
        query = query.filter(WorkflowTransitionLog.from_status == from_status)
    if to_status:
        query = query.filter(WorkflowTransitionLog.to_status == to_status)
    if trigger_source:
        query = query.filter(WorkflowTransitionLog.trigger_source == trigger_source)

    return query.order_by(WorkflowTransitionLog.transitioned_at.desc()).offset(skip).limit(limit).all()
