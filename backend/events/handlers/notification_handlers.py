"""
Notification Event Handlers
Phase 3: Domain Events Infrastructure

Handles notification-related events:
- Hold creation notifications
- KPI threshold alerts
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
    """
    Handler for hold-related notifications.

    Sends notifications when holds are created or require approval.
    Runs asynchronously to avoid blocking request.
    """

    def __init__(self):
        super().__init__(is_async=True, priority=100)

    async def handle(self, event: DomainEvent) -> None:
        """Send hold notification."""
        if isinstance(event, HoldCreated):
            await self._handle_hold_created(event)
        elif isinstance(event, HoldApprovalRequired):
            await self._handle_approval_required(event)

    async def _handle_hold_created(self, event: HoldCreated) -> None:
        """Handle new hold creation."""
        logger.info(
            f"NOTIFICATION: New hold created for work order {event.work_order_id} "
            f"(reason: {event.hold_reason_category}) - {event.quantity_on_hold} units"
        )
        # TODO: Send email/SMS notification to supervisors
        # TODO: Create in-app notification

    async def _handle_approval_required(self, event: HoldApprovalRequired) -> None:
        """Handle hold approval request."""
        logger.info(
            f"NOTIFICATION: Hold approval required for work order {event.work_order_id} "
            f"(requested by user {event.requested_by})"
        )
        # TODO: Send urgent notification to supervisors
        # TODO: Create approval workflow task


class KPIAlertHandler(EventHandler):
    """
    Handler for KPI threshold alerts.

    Sends alerts when KPIs exceed thresholds.
    Runs asynchronously to avoid blocking request.
    """

    def __init__(self):
        super().__init__(is_async=True, priority=100)

    async def handle(self, event: DomainEvent) -> None:
        """Send KPI threshold alert."""
        if not isinstance(event, KPIThresholdViolated):
            return

        logger.warning(
            f"KPI ALERT: {event.metric_name} violated {event.threshold_type} threshold "
            f"(current: {event.current_value}, threshold: {event.threshold_value}) "
            f"for client {event.client_id}"
        )
        # TODO: Send alert notification based on alert configuration
        # TODO: Create alert record for dashboard
