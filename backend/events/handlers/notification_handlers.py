"""
Notification Event Handlers
Phase 3: Domain Events Infrastructure

Observability hooks for notification-eligible events. These handlers log
the events at INFO level so they appear in operational logs and can be
exported to external notification systems by log-shipping pipelines. The
project does not currently integrate an in-process email/SMS provider; if
one is added, replace the log statements with provider calls.
"""

import logging
from backend.events.base import DomainEvent, EventHandler
from backend.events.domain_events import (
    HoldCreated,
    HoldApprovalRequired,
    KPIThresholdViolated,
)

logger = logging.getLogger(__name__)


class HoldNotificationHandler(EventHandler):
    """Logs hold-creation and approval-required events for downstream alerting."""

    def __init__(self) -> None:
        super().__init__(is_async=True, priority=100)

    async def handle(self, event: DomainEvent) -> None:
        if isinstance(event, HoldCreated):
            await self._handle_hold_created(event)
        elif isinstance(event, HoldApprovalRequired):
            await self._handle_approval_required(event)

    async def _handle_hold_created(self, event: HoldCreated) -> None:
        logger.info(
            f"NOTIFICATION: New hold created for work order {event.work_order_id} "
            f"(reason: {event.hold_reason_category}) - {event.quantity_on_hold} units"
        )

    async def _handle_approval_required(self, event: HoldApprovalRequired) -> None:
        logger.info(
            f"NOTIFICATION: Hold approval required for work order {event.work_order_id} "
            f"(requested by user {event.requested_by})"
        )


class KPIAlertHandler(EventHandler):
    """Logs KPI threshold violations at WARNING level for downstream alerting."""

    def __init__(self) -> None:
        super().__init__(is_async=True, priority=100)

    async def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, KPIThresholdViolated):
            return

        logger.warning(
            f"KPI ALERT: {event.metric_name} violated {event.threshold_type} threshold "
            f"(current: {event.current_value}, threshold: {event.threshold_value}) "
            f"for client {event.client_id}"
        )
