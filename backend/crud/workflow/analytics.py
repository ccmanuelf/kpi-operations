"""
CRUD operations for Workflow Analytics
Implements Phase 10: Flexible Workflow Foundation - Analytics & Reporting
"""
from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.schemas.workflow import WorkflowTransitionLog
from backend.schemas.work_order import WorkOrder
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access


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
