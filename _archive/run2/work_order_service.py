"""
Work Order Service
Service layer for Work Order operations.
Coordinates CRUD operations with workflow transitions and status validation.

Phase 2: Service Layer Enforcement
"""

from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from fastapi import Depends

from backend.schemas.work_order import WorkOrder
from backend.schemas.user import User

# Note: Using lazy imports in methods to avoid circular import with crud.workflow
from backend.database import get_db


class WorkOrderService:
    """
    Service layer for Work Order operations.

    Wraps work order CRUD with business logic:
    - Workflow state machine transitions
    - Status validation before updates
    - QC approval workflows
    - Progress tracking
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_work_order(self, work_order_id: str, user: User) -> Optional[WorkOrder]:
        """
        Get a work order by ID.

        Args:
            work_order_id: Work order ID
            user: Authenticated user

        Returns:
            Work order or None
        """
        from backend.crud.work_order import get_work_order

        return get_work_order(self.db, work_order_id, user)

    def list_work_orders(
        self, user: User, client_id: Optional[str] = None, status: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[WorkOrder]:
        """
        List work orders with filtering.

        Args:
            user: Authenticated user
            client_id: Filter by client
            status: Filter by status
            skip: Records to skip
            limit: Maximum records

        Returns:
            List of work orders
        """
        from backend.crud.work_order import get_work_orders

        return get_work_orders(self.db, user, skip=skip, limit=limit, client_id=client_id, status=status)

    def transition_status(self, work_order_id: str, to_status: str, user: User, notes: Optional[str] = None) -> Dict:
        """
        Transition a work order to a new status.

        Validates the transition against the workflow state machine.

        Args:
            work_order_id: Work order ID
            to_status: Target status
            user: Authenticated user
            notes: Optional transition notes

        Returns:
            Dictionary with work order and transition log
        """
        from backend.crud.workflow import transition_work_order

        return transition_work_order(self.db, work_order_id, to_status, user, notes)

    def validate_transition(self, work_order_id: str, to_status: str, user: User) -> Dict:
        """
        Validate if a transition is allowed (without executing).

        Args:
            work_order_id: Work order ID
            to_status: Target status
            user: Authenticated user

        Returns:
            Validation result with reason
        """
        from backend.crud.workflow import validate_transition

        return validate_transition(self.db, work_order_id, to_status, user)

    def get_allowed_transitions(self, work_order_id: str, user: User) -> Dict:
        """
        Get allowed next statuses for a work order.

        Args:
            work_order_id: Work order ID
            user: Authenticated user

        Returns:
            Current status and allowed transitions
        """
        from backend.crud.workflow import get_allowed_transitions_for_work_order

        return get_allowed_transitions_for_work_order(self.db, work_order_id, user)

    def bulk_transition(
        self, work_order_ids: List[str], to_status: str, client_id: str, user: User, notes: Optional[str] = None
    ) -> Dict:
        """
        Perform bulk status transition.

        Args:
            work_order_ids: List of work order IDs
            to_status: Target status
            client_id: Client ID
            user: Authenticated user
            notes: Optional notes

        Returns:
            Bulk operation results
        """
        from backend.crud.workflow import bulk_transition_work_orders

        return bulk_transition_work_orders(self.db, work_order_ids, to_status, client_id, user, notes)

    def get_transition_history(self, work_order_id: str, user: User) -> List:
        """
        Get transition history for a work order.

        Args:
            work_order_id: Work order ID
            user: Authenticated user

        Returns:
            List of transition log entries
        """
        from backend.crud.workflow import get_work_order_transitions

        return get_work_order_transitions(self.db, work_order_id, user)


def get_work_order_service(db: Session = Depends(get_db)) -> WorkOrderService:
    """
    FastAPI dependency to get WorkOrderService instance.
    """
    return WorkOrderService(db)
