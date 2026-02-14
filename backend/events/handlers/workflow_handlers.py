"""
Workflow Event Handlers
Phase 3: Domain Events Infrastructure

Handles workflow-related events:
- Audit logging for status changes
- Auto-close detection
"""

import logging
from backend.events.base import DomainEvent, EventHandler
from backend.events.domain_events import WorkOrderStatusChanged


logger = logging.getLogger(__name__)


class WorkflowAuditHandler(EventHandler):
    """
    Handler for workflow audit logging.

    Records workflow transitions to audit log for compliance.
    """

    def __init__(self):
        super().__init__(is_async=False, priority=10)

    async def handle(self, event: DomainEvent) -> None:
        """Log workflow transition to audit trail."""
        if not isinstance(event, WorkOrderStatusChanged):
            return

        logger.info(
            f"AUDIT: Work order {event.aggregate_id} "
            f"transitioned from {event.from_status} to {event.to_status} "
            f"by user {event.triggered_by} "
            f"(source: {event.trigger_source})"
        )

        # TODO: Persist to audit log table if needed beyond EVENT_STORE


class WorkOrderAutoCloseHandler(EventHandler):
    """
    Handler to detect auto-close conditions.

    Checks if work order should be automatically closed
    based on status transitions and business rules.
    """

    def __init__(self):
        super().__init__(is_async=False, priority=50)

    async def handle(self, event: DomainEvent) -> None:
        """Check for auto-close conditions."""
        if not isinstance(event, WorkOrderStatusChanged):
            return

        # Check if transitioning to a closure-eligible status
        closure_statuses = ["COMPLETED", "SHIPPED", "DELIVERED"]

        if event.to_status in closure_statuses:
            logger.debug(f"Work order {event.aggregate_id} reached {event.to_status} - " f"eligible for auto-close")
            # Actual auto-close logic would be triggered here
            # based on client configuration (workflow_closure_trigger)
