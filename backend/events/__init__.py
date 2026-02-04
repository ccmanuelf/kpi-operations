"""
Domain Events Package
Phase 3: Domain Events Infrastructure

Provides event-driven architecture for the KPI Operations platform:
- Domain events for state change capture
- Event bus for publish/subscribe
- Collect/flush pattern for transactional consistency
- Session hooks for automatic event handling

Usage:
    from backend.events import event_bus, WorkOrderStatusChanged

    # In a service method:
    event = WorkOrderStatusChanged(
        aggregate_id=work_order.work_order_id,
        from_status=old_status,
        to_status=new_status,
        triggered_by=user.user_id,
        client_id=work_order.client_id
    )
    event_bus.collect(event)
    # Event will be flushed after db.commit()
"""

# Base classes
from backend.events.base import DomainEvent, EventHandler

# Event bus
from backend.events.bus import EventBus, get_event_bus, event_bus

# Domain events
from backend.events.domain_events import (
    # Work Order events
    WorkOrderStatusChanged,
    WorkOrderCreated,
    WorkOrderClosed,
    # Production events
    ProductionEntryCreated,
    ProductionEntryUpdated,
    # Quality events
    QualityInspectionRecorded,
    QualityDefectReported,
    # Hold events
    HoldCreated,
    HoldResumed,
    HoldApprovalRequired,
    # KPI events
    KPIThresholdViolated,
    KPITargetAchieved,
    # Employee events
    EmployeeAssignedToFloatingPool,
    EmployeeAssignedToClient,
    # Capacity Planning events
    OrderScheduled,
    ComponentShortageDetected,
    CapacityOverloadDetected,
    ScheduleCommitted,
    KPIVarianceAlert,
    BOMExploded,
    CapacityScenarioCreated,
    CapacityScenarioCompared,
)

# Session hooks
from backend.events.session_hooks import (
    setup_session_hooks,
    setup_scoped_session_hooks,
    EventCollectorMixin,
)

# Handler registration
from backend.events.handlers import register_all_handlers


__all__ = [
    # Base
    "DomainEvent",
    "EventHandler",
    # Bus
    "EventBus",
    "get_event_bus",
    "event_bus",
    # Work Order events
    "WorkOrderStatusChanged",
    "WorkOrderCreated",
    "WorkOrderClosed",
    # Production events
    "ProductionEntryCreated",
    "ProductionEntryUpdated",
    # Quality events
    "QualityInspectionRecorded",
    "QualityDefectReported",
    # Hold events
    "HoldCreated",
    "HoldResumed",
    "HoldApprovalRequired",
    # KPI events
    "KPIThresholdViolated",
    "KPITargetAchieved",
    # Employee events
    "EmployeeAssignedToFloatingPool",
    "EmployeeAssignedToClient",
    # Capacity Planning events
    "OrderScheduled",
    "ComponentShortageDetected",
    "CapacityOverloadDetected",
    "ScheduleCommitted",
    "KPIVarianceAlert",
    "BOMExploded",
    "CapacityScenarioCreated",
    "CapacityScenarioCompared",
    # Session hooks
    "setup_session_hooks",
    "setup_scoped_session_hooks",
    "EventCollectorMixin",
    # Handler registration
    "register_all_handlers",
]
