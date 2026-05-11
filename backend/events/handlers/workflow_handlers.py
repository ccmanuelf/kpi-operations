"""
Workflow Event Handlers
Phase 3: Domain Events Infrastructure

Observability hooks for workflow state changes. The persistent audit trail
lives in the EVENT_STORE table populated by the event bus itself; these
handlers add human-readable INFO/DEBUG log lines for operational visibility.
"""

import logging
from backend.events.base import DomainEvent, EventHandler
from backend.events.domain_events import WorkOrderStatusChanged

logger = logging.getLogger(__name__)


class WorkflowAuditHandler(EventHandler):
    """Emits a human-readable audit log line for every work order status change."""

    def __init__(self) -> None:
        super().__init__(is_async=False, priority=10)

    async def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, WorkOrderStatusChanged):
            return

        logger.info(
            f"AUDIT: Work order {event.aggregate_id} "
            f"transitioned from {event.from_status} to {event.to_status} "
            f"by user {event.triggered_by} "
            f"(source: {event.trigger_source})"
        )


class WorkOrderAutoCloseHandler(EventHandler):
    """Detects closure-eligible state transitions for downstream automation."""

    CLOSURE_STATUSES = ("COMPLETED", "SHIPPED", "DELIVERED")

    def __init__(self) -> None:
        super().__init__(is_async=False, priority=50)

    async def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, WorkOrderStatusChanged):
            return

        if event.to_status in self.CLOSURE_STATUSES:
            logger.debug(f"Work order {event.aggregate_id} reached {event.to_status} - " f"eligible for auto-close")
