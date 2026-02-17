"""
Workflow State Machine Service
Implements Phase 10: Flexible Workflow Foundation

Provides:
- State machine validation
- Transition rules enforcement
- Client-specific workflow configuration
- Elapsed time calculations
"""

from typing import List, Optional, Dict, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException
import json

from backend.schemas.work_order import WorkOrder, WorkOrderStatus
from backend.schemas.client_config import ClientConfig
from backend.schemas.workflow import WorkflowTransitionLog
from backend.schemas.user import User
from backend.models.workflow import WorkflowStatusEnum, ClosureTriggerEnum, TriggerSourceEnum, WORKFLOW_TEMPLATES


# Default workflow transitions (used when no client config exists)
DEFAULT_WORKFLOW_TRANSITIONS: Dict[str, List[str]] = {
    "RELEASED": ["RECEIVED"],
    "IN_PROGRESS": ["RELEASED"],
    "COMPLETED": ["IN_PROGRESS"],
    "SHIPPED": ["COMPLETED"],
    "CLOSED": ["SHIPPED", "COMPLETED"],
    "ON_HOLD": ["RECEIVED", "RELEASED", "IN_PROGRESS"],
    "DEMOTED": ["RELEASED"],
    "CANCELLED": ["RECEIVED", "RELEASED", "IN_PROGRESS", "ON_HOLD", "DEMOTED"],
    "REJECTED": ["IN_PROGRESS", "COMPLETED"],
}

# Statuses that can transition from any state (emergency transitions)
UNIVERSAL_FROM_STATUSES = ["CANCELLED"]

# Statuses that can be transitioned to from any active state
UNIVERSAL_TO_STATUSES = ["ON_HOLD", "CANCELLED"]


class WorkflowStateMachine:
    """
    State machine for work order workflow transitions.
    Supports client-specific configuration and validation.
    """

    def __init__(self, db: Session, client_id: str):
        """
        Initialize state machine for a specific client.

        Args:
            db: Database session
            client_id: Client ID for configuration lookup
        """
        self.db = db
        self.client_id = client_id
        self._config: Optional[ClientConfig] = None
        self._transitions: Dict[str, List[str]] = {}
        self._statuses: List[str] = []
        self._optional_statuses: List[str] = []
        self._closure_trigger: str = "at_shipment"
        self._load_config()

    def _load_config(self) -> None:
        """Load workflow configuration from client config or use defaults."""
        self._config = self.db.query(ClientConfig).filter(ClientConfig.client_id == self.client_id).first()

        if self._config:
            # Parse JSON configuration
            try:
                self._statuses = json.loads(self._config.workflow_statuses or "[]")
                self._transitions = json.loads(self._config.workflow_transitions or "{}")
                self._optional_statuses = json.loads(self._config.workflow_optional_statuses or "[]")
                self._closure_trigger = self._config.workflow_closure_trigger or "at_shipment"
            except (json.JSONDecodeError, TypeError):
                # Fall back to defaults if JSON parsing fails
                self._use_defaults()
        else:
            self._use_defaults()

    def _use_defaults(self) -> None:
        """Apply default workflow configuration."""
        self._statuses = ["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED"]
        self._transitions = DEFAULT_WORKFLOW_TRANSITIONS.copy()
        self._optional_statuses = ["SHIPPED", "DEMOTED"]
        self._closure_trigger = "at_shipment"

    def get_allowed_transitions(self, from_status: str) -> List[str]:
        """
        Get list of statuses that can be transitioned to from the given status.

        Args:
            from_status: Current status

        Returns:
            List of valid target statuses
        """
        allowed = []

        for to_status, from_statuses in self._transitions.items():
            if from_status in from_statuses:
                allowed.append(to_status)

        # Add universal transitions
        for universal in UNIVERSAL_TO_STATUSES:
            if universal not in allowed and from_status not in ["CLOSED", "CANCELLED", "REJECTED"]:
                allowed.append(universal)

        return sorted(allowed)

    def is_transition_valid(self, from_status: Optional[str], to_status: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if a transition is allowed.

        Args:
            from_status: Current status (None for new work orders)
            to_status: Target status

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Initial creation - only RECEIVED is valid
        if from_status is None:
            if to_status == "RECEIVED":
                return True, None
            return False, f"New work orders must start with RECEIVED status, not {to_status}"

        # Same status - no transition needed
        if from_status == to_status:
            return True, None

        # Terminal statuses - cannot transition from
        if from_status in ["CLOSED", "CANCELLED", "REJECTED"]:
            return False, f"Cannot transition from terminal status {from_status}"

        # Check if to_status allows from_status
        allowed_from = self._transitions.get(to_status, [])

        if from_status in allowed_from:
            return True, None

        # Check universal transitions
        if to_status in UNIVERSAL_TO_STATUSES and from_status not in ["CLOSED", "CANCELLED", "REJECTED"]:
            return True, None

        # Special case: Resume from ON_HOLD to previous_status
        if from_status == "ON_HOLD":
            # ON_HOLD can resume to the original state it came from
            # This should be handled by checking work_order.previous_status
            pass

        return (
            False,
            f"Transition from {from_status} to {to_status} is not allowed. Allowed targets: {self.get_allowed_transitions(from_status)}",
        )

    def validate_transition(self, work_order: WorkOrder, to_status: str) -> Tuple[bool, Optional[str]]:
        """
        Validate transition for a specific work order.

        Args:
            work_order: Work order instance
            to_status: Target status

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        from_status = work_order.status

        # Basic transition validation
        is_valid, reason = self.is_transition_valid(from_status, to_status)
        if not is_valid:
            return False, reason

        # Special case: Resume from ON_HOLD
        if from_status == "ON_HOLD" and to_status not in ["CANCELLED"]:
            # When resuming from ON_HOLD, we should go back to previous_status
            if work_order.previous_status and to_status != work_order.previous_status:
                return False, f"ON_HOLD work orders should resume to {work_order.previous_status}, not {to_status}"

        # COMPLETED requires actual_quantity
        if to_status == "COMPLETED":
            if work_order.actual_quantity is None or work_order.actual_quantity == 0:
                return False, "Cannot mark as COMPLETED: actual_quantity must be greater than 0"

        # SHIPPED requires QC approval (if configured)
        if to_status == "SHIPPED":
            if not work_order.qc_approved:
                return False, "Cannot mark as SHIPPED: QC approval required"

        return True, None

    def get_closure_trigger(self) -> str:
        """Get the configured closure trigger for this client."""
        return self._closure_trigger

    def should_auto_close(self, work_order: WorkOrder, new_status: str) -> bool:
        """
        Determine if work order should be automatically closed.

        Args:
            work_order: Work order instance
            new_status: New status being set

        Returns:
            True if work order should be auto-closed
        """
        trigger = self.get_closure_trigger()

        if trigger == "at_shipment" and new_status == "SHIPPED":
            return True
        elif trigger == "at_completion" and new_status == "COMPLETED":
            return True
        # at_client_receipt and manual require explicit closure

        return False


def get_workflow_config(db: Session, client_id: str) -> Dict:
    """
    Get workflow configuration for a client.

    Args:
        db: Database session
        client_id: Client ID

    Returns:
        Dictionary with workflow configuration
    """
    sm = WorkflowStateMachine(db, client_id)
    return {
        "client_id": client_id,
        "workflow_statuses": sm._statuses,
        "workflow_transitions": sm._transitions,
        "workflow_optional_statuses": sm._optional_statuses,
        "workflow_closure_trigger": sm._closure_trigger,
        "workflow_version": sm._config.workflow_version if sm._config else 1,
    }


def validate_transition(db: Session, work_order: WorkOrder, to_status: str) -> Tuple[bool, Optional[str], List[str]]:
    """
    Validate a status transition for a work order.

    Args:
        db: Database session
        work_order: Work order instance
        to_status: Target status

    Returns:
        Tuple of (is_valid, reason_if_invalid, allowed_transitions)
    """
    sm = WorkflowStateMachine(db, work_order.client_id)
    is_valid, reason = sm.validate_transition(work_order, to_status)
    allowed = sm.get_allowed_transitions(work_order.status)

    return is_valid, reason, allowed


def get_allowed_transitions(db: Session, client_id: str, current_status: str) -> List[str]:
    """
    Get allowed transitions from a status.

    Args:
        db: Database session
        client_id: Client ID
        current_status: Current status

    Returns:
        List of allowed target statuses
    """
    sm = WorkflowStateMachine(db, client_id)
    return sm.get_allowed_transitions(current_status)


def calculate_elapsed_hours(from_datetime: Optional[datetime], to_datetime: Optional[datetime]) -> Optional[int]:
    """
    Calculate elapsed hours between two datetimes.

    Args:
        from_datetime: Start datetime
        to_datetime: End datetime

    Returns:
        Elapsed hours as integer, or None if dates are missing
    """
    if from_datetime is None or to_datetime is None:
        return None

    # Normalize naive datetimes (from SQLite) to UTC for safe comparison
    if from_datetime.tzinfo is None and to_datetime.tzinfo is not None:
        from_datetime = from_datetime.replace(tzinfo=timezone.utc)
    elif from_datetime.tzinfo is not None and to_datetime.tzinfo is None:
        to_datetime = to_datetime.replace(tzinfo=timezone.utc)

    delta = to_datetime - from_datetime
    return int(delta.total_seconds() / 3600)


def execute_transition(
    db: Session,
    work_order: WorkOrder,
    to_status: str,
    user_id: Optional[int] = None,
    notes: Optional[str] = None,
    trigger_source: str = "manual",
) -> Tuple[WorkOrder, WorkflowTransitionLog]:
    """
    Execute a validated status transition.

    Args:
        db: Database session
        work_order: Work order to transition
        to_status: Target status
        user_id: User performing the transition
        notes: Transition notes
        trigger_source: Source of transition

    Returns:
        Tuple of (updated_work_order, transition_log)

    Raises:
        HTTPException 400: If transition is not valid
    """
    sm = WorkflowStateMachine(db, work_order.client_id)

    # Validate transition
    is_valid, reason = sm.validate_transition(work_order, to_status)
    if not is_valid:
        raise HTTPException(status_code=400, detail=reason)

    from_status = work_order.status
    now = datetime.now(tz=timezone.utc)

    # Calculate elapsed times
    elapsed_from_received = calculate_elapsed_hours(work_order.received_date, now)
    elapsed_from_previous = None

    # Get last transition for elapsed_from_previous calculation
    last_transition = (
        db.query(WorkflowTransitionLog)
        .filter(WorkflowTransitionLog.work_order_id == work_order.work_order_id)
        .order_by(WorkflowTransitionLog.transitioned_at.desc())
        .first()
    )

    if last_transition:
        elapsed_from_previous = calculate_elapsed_hours(last_transition.transitioned_at, now)

    # Handle ON_HOLD - save previous status
    if to_status == "ON_HOLD":
        work_order.previous_status = from_status

    # Update work order status
    work_order.status = to_status

    # Update relevant date fields
    if to_status == "RELEASED":
        work_order.dispatch_date = now
    elif to_status == "SHIPPED":
        work_order.shipped_date = now
    elif to_status in ["CLOSED", "COMPLETED"]:
        if to_status == "CLOSED":
            work_order.closure_date = now
            work_order.closed_by = user_id

    # Check for auto-close
    if sm.should_auto_close(work_order, to_status):
        # Perform auto-close after this transition
        work_order.closure_date = now
        work_order.closed_by = user_id
        # Status remains as SHIPPED or COMPLETED, but closure_date is set

    # Create transition log
    transition_log = WorkflowTransitionLog(
        work_order_id=work_order.work_order_id,
        client_id=work_order.client_id,
        from_status=from_status,
        to_status=to_status,
        transitioned_by=user_id,
        transitioned_at=now,
        notes=notes,
        trigger_source=trigger_source,
        elapsed_from_received_hours=elapsed_from_received,
        elapsed_from_previous_hours=elapsed_from_previous,
    )

    db.add(transition_log)
    db.commit()
    db.refresh(work_order)
    db.refresh(transition_log)

    return work_order, transition_log


def get_transition_history(db: Session, work_order_id: str, client_id: str) -> List[WorkflowTransitionLog]:
    """
    Get transition history for a work order.

    Args:
        db: Database session
        work_order_id: Work order ID
        client_id: Client ID (for security filtering)

    Returns:
        List of transition log entries
    """
    return (
        db.query(WorkflowTransitionLog)
        .filter(
            and_(WorkflowTransitionLog.work_order_id == work_order_id, WorkflowTransitionLog.client_id == client_id)
        )
        .order_by(WorkflowTransitionLog.transitioned_at.asc())
        .all()
    )


def bulk_transition(
    db: Session,
    work_order_ids: List[str],
    to_status: str,
    client_id: str,
    user_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict:
    """
    Perform bulk status transition on multiple work orders.

    Args:
        db: Database session
        work_order_ids: List of work order IDs
        to_status: Target status
        client_id: Client ID
        user_id: User performing the transition
        notes: Transition notes

    Returns:
        Dictionary with results: {successful: [], failed: []}
    """
    results = {"total_requested": len(work_order_ids), "successful": 0, "failed": 0, "results": []}

    for wo_id in work_order_ids:
        try:
            work_order = (
                db.query(WorkOrder)
                .filter(and_(WorkOrder.work_order_id == wo_id, WorkOrder.client_id == client_id))
                .first()
            )

            if not work_order:
                results["results"].append({"work_order_id": wo_id, "success": False, "error": "Work order not found"})
                results["failed"] += 1
                continue

            work_order, _ = execute_transition(db, work_order, to_status, user_id, notes, "bulk")

            results["results"].append(
                {
                    "work_order_id": wo_id,
                    "success": True,
                    "from_status": work_order.previous_status or work_order.status,
                    "to_status": to_status,
                }
            )
            results["successful"] += 1

        except HTTPException as e:
            results["results"].append({"work_order_id": wo_id, "success": False, "error": e.detail})
            results["failed"] += 1
        except Exception as e:
            results["results"].append({"work_order_id": wo_id, "success": False, "error": str(e)})
            results["failed"] += 1

    return results


def apply_workflow_template(db: Session, client_id: str, template_id: str) -> Dict:
    """
    Apply a workflow template to a client's configuration.

    Args:
        db: Database session
        client_id: Client ID
        template_id: Template ID

    Returns:
        Dictionary with updated configuration

    Raises:
        HTTPException 404: If template not found
    """
    if template_id not in WORKFLOW_TEMPLATES:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow template '{template_id}' not found. Available: {list(WORKFLOW_TEMPLATES.keys())}",
        )

    template = WORKFLOW_TEMPLATES[template_id]

    # Get or create client config
    config = db.query(ClientConfig).filter(ClientConfig.client_id == client_id).first()

    if not config:
        config = ClientConfig(client_id=client_id)
        db.add(config)

    # Apply template
    config.workflow_statuses = json.dumps(template.workflow_statuses)
    config.workflow_transitions = json.dumps(template.workflow_transitions)
    config.workflow_optional_statuses = json.dumps(template.workflow_optional_statuses)
    config.workflow_closure_trigger = template.workflow_closure_trigger
    config.workflow_version = (config.workflow_version or 0) + 1

    db.commit()
    db.refresh(config)

    return get_workflow_config(db, client_id)
