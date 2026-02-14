"""
Event Handlers Package
Phase 3: Domain Events Infrastructure

Contains event handlers for different domains:
- workflow_handlers: Workflow state change handlers
- notification_handlers: Notification and alert handlers
- analytics_handlers: Analytics and metrics handlers
"""

from typing import List

from backend.events.base import EventHandler
from backend.events.bus import get_event_bus


def register_all_handlers() -> None:
    """
    Register all event handlers with the event bus.

    Call this at application startup to enable event handling.
    """
    bus = get_event_bus()

    # Import and register handlers
    from backend.events.handlers.workflow_handlers import (
        WorkflowAuditHandler,
        WorkOrderAutoCloseHandler,
    )
    from backend.events.handlers.notification_handlers import (
        HoldNotificationHandler,
        KPIAlertHandler,
    )
    from backend.events.handlers.analytics_handlers import (
        ProductionMetricsHandler,
        QualityMetricsHandler,
    )

    # Workflow handlers
    bus.subscribe("work_order.status_changed", WorkflowAuditHandler(), priority=10)
    bus.subscribe("work_order.status_changed", WorkOrderAutoCloseHandler(), priority=50)

    # Notification handlers (async)
    bus.subscribe("hold.created", HoldNotificationHandler(), priority=100, is_async=True)
    bus.subscribe("hold.approval_required", HoldNotificationHandler(), priority=100, is_async=True)
    bus.subscribe("kpi.threshold_violated", KPIAlertHandler(), priority=100, is_async=True)

    # Analytics handlers
    bus.subscribe("production.entry_created", ProductionMetricsHandler(), priority=50)
    bus.subscribe("production.entry_updated", ProductionMetricsHandler(), priority=50)
    bus.subscribe("quality.inspection_recorded", QualityMetricsHandler(), priority=50)
    bus.subscribe("quality.defect_reported", QualityMetricsHandler(), priority=50)


__all__ = [
    "register_all_handlers",
]
