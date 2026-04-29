"""
Workflow CRUD Service
Thin service layer wrapping Workflow CRUD operations.
Routes should import from this module instead of backend.crud.workflow directly.

Note: This wraps the CRUD layer functions. The core workflow state machine
logic lives in backend.services.workflow_service (WorkflowStateMachine).
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.workflow import (
    get_work_order_transitions,
    get_client_transitions,
    get_workflow_configuration,
    update_workflow_configuration,
    apply_workflow_template,
    transition_work_order,
    validate_transition,
    get_allowed_transitions_for_work_order,
    bulk_transition_work_orders,
    get_transition_statistics,
    get_status_distribution,
)


def get_transitions_for_work_order(db: Session, work_order_id: str, current_user: User) -> Any:
    """Get transition history for a work order."""
    return get_work_order_transitions(db, work_order_id, current_user)


def get_transitions_for_client(
    db: Session,
    client_id: str,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    trigger_source: Optional[str] = None,
) -> Any:
    """Get transition history for a client."""
    return get_client_transitions(
        db,
        client_id,
        current_user,
        skip=skip,
        limit=limit,
        from_status=from_status,
        to_status=to_status,
        trigger_source=trigger_source,
    )


def get_config(db: Session, client_id: str, current_user: User) -> Dict:
    """Get workflow configuration for a client."""
    return get_workflow_configuration(db, client_id, current_user)


def update_config(db: Session, client_id: str, config_update: dict, current_user: User) -> Dict:
    """Update workflow configuration for a client."""
    return update_workflow_configuration(db, client_id, config_update, current_user)


def apply_template(db: Session, client_id: str, template_id: str, current_user: User) -> Dict:
    """Apply a workflow template to a client."""
    return apply_workflow_template(db, client_id, template_id, current_user)


def execute_transition(
    db: Session, work_order_id: str, to_status: str, current_user: User, notes: Optional[str] = None
) -> Dict:
    """Execute a work order status transition."""
    return transition_work_order(db, work_order_id, to_status, current_user, notes)


def check_transition_valid(db: Session, work_order_id: str, to_status: str, current_user: User) -> Dict:
    """Check if a transition is valid."""
    return validate_transition(db, work_order_id, to_status, current_user)


def get_allowed_transitions(db: Session, work_order_id: str, current_user: User) -> Dict:
    """Get allowed transitions for a work order."""
    return get_allowed_transitions_for_work_order(db, work_order_id, current_user)


def bulk_transition(
    db: Session,
    work_order_ids: List[str],
    to_status: str,
    client_id: str,
    current_user: User,
    notes: Optional[str] = None,
) -> Dict:
    """Bulk transition work orders."""
    return bulk_transition_work_orders(db, work_order_ids, to_status, client_id, current_user, notes)


def get_statistics(db: Session, client_id: str, current_user: User) -> Dict:
    """Get transition statistics for a client."""
    return get_transition_statistics(db, client_id, current_user)


def get_distribution(db: Session, client_id: str, current_user: User) -> Dict:
    """Get status distribution for a client."""
    return get_status_distribution(db, client_id, current_user)
