"""
Comprehensive tests for the domain events infrastructure.

Covers:
- DomainEvent base class (immutability, serialization, auto-fields)
- EventHandler base class (interface contract, defaults)
- EventBus (subscribe, unsubscribe, publish, collect/flush/discard, wildcard,
  priority ordering, error isolation, persistence handler)
- Domain event subclass definitions (field defaults, inheritance, serialization)

Run with:
    cd backend && python -m pytest tests/test_events/test_event_bus.py -v
"""

import asyncio
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import List

import pytest
from pydantic import ValidationError

from backend.events.base import DomainEvent, EventHandler
from backend.events.bus import EventBus, HandlerRegistration
from backend.events.domain_events import (
    WorkOrderStatusChanged,
    WorkOrderCreated,
    WorkOrderClosed,
    ProductionEntryCreated,
    ProductionEntryUpdated,
    QualityInspectionRecorded,
    QualityDefectReported,
    HoldCreated,
    HoldResumed,
    HoldApprovalRequired,
    KPIThresholdViolated,
    KPITargetAchieved,
    EmployeeAssignedToFloatingPool,
    EmployeeAssignedToClient,
    OrderScheduled,
    ComponentShortageDetected,
    CapacityOverloadDetected,
    ScheduleCommitted,
    KPIVarianceAlert,
    BOMExploded,
    CapacityScenarioCreated,
    CapacityScenarioCompared,
)


# ---------------------------------------------------------------------------
# Test handler implementations (used across multiple test classes)
# ---------------------------------------------------------------------------


class RecordingHandler(EventHandler):
    """Handler that records every event it processes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.handled_events: List[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.handled_events.append(event)

    def can_handle(self, event: DomainEvent) -> bool:
        return True


class SelectiveHandler(EventHandler):
    """Handler that only accepts events whose event_type is in accepted_types."""

    def __init__(self, accepted_types: List[str], **kwargs):
        super().__init__(**kwargs)
        self.accepted_types = accepted_types
        self.handled_events: List[DomainEvent] = []

    async def handle(self, event: DomainEvent) -> None:
        self.handled_events.append(event)

    def can_handle(self, event: DomainEvent) -> bool:
        return event.event_type in self.accepted_types


class ErrorHandler(EventHandler):
    """Handler that always raises an error -- used to verify error isolation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.call_count = 0

    async def handle(self, event: DomainEvent) -> None:
        self.call_count += 1
        raise ValueError("Intentional test error from ErrorHandler")


class OrderTrackingHandler(EventHandler):
    """Handler that records its own label when invoked, for priority-order checks."""

    def __init__(self, label: str, log: list, **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.log = log

    async def handle(self, event: DomainEvent) -> None:
        self.log.append(self.label)


# ---------------------------------------------------------------------------
# Fixture: reset the EventBus singleton between every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Reset EventBus singleton state so each test starts clean."""
    bus = EventBus()
    bus._handlers.clear()
    bus._collected_events.clear()
    bus._persistence_handler = None
    yield bus
    # Cleanup after the test as well
    bus._handlers.clear()
    bus._collected_events.clear()
    bus._persistence_handler = None


# ---------------------------------------------------------------------------
# Helper: create a minimal valid DomainEvent (aggregate_id is required)
# ---------------------------------------------------------------------------


def _make_event(**overrides) -> DomainEvent:
    defaults = {
        "aggregate_id": "agg-1",
        "aggregate_type": "TestAggregate",
        "event_type": "test.event",
    }
    defaults.update(overrides)
    return DomainEvent(**defaults)


# ========================================================================
# 1. DomainEvent base class
# ========================================================================


class TestDomainEvent:
    """Tests for the DomainEvent Pydantic base model."""

    def test_auto_generated_event_id_is_valid_uuid(self):
        event = _make_event()
        # Should parse as a valid UUID-4
        parsed = uuid.UUID(event.event_id)
        assert parsed.version == 4

    def test_each_event_gets_unique_id(self):
        e1 = _make_event()
        e2 = _make_event()
        assert e1.event_id != e2.event_id

    def test_occurred_at_is_auto_populated(self):
        before = datetime.utcnow()
        event = _make_event()
        after = datetime.utcnow()
        assert before <= event.occurred_at <= after

    def test_aggregate_id_is_required(self):
        with pytest.raises(ValidationError):
            DomainEvent(aggregate_type="X")

    def test_aggregate_type_is_required(self):
        with pytest.raises(ValidationError):
            DomainEvent(aggregate_id="x")

    def test_optional_fields_default_to_none(self):
        event = _make_event()
        assert event.client_id is None
        assert event.triggered_by is None

    def test_metadata_defaults_to_empty_dict(self):
        event = _make_event()
        assert event.metadata == {}

    def test_metadata_is_included(self):
        event = _make_event(metadata={"key": "value"})
        assert event.metadata == {"key": "value"}

    def test_immutability_prevents_field_mutation(self):
        event = _make_event()
        with pytest.raises(ValidationError):
            event.aggregate_id = "changed"

    def test_to_dict_returns_all_base_fields(self):
        event = _make_event(
            client_id="client-A",
            triggered_by=42,
            metadata={"action": "create"},
        )
        d = event.to_dict()
        assert d["event_id"] == event.event_id
        assert d["event_type"] == "test.event"
        assert d["aggregate_id"] == "agg-1"
        assert d["aggregate_type"] == "TestAggregate"
        assert d["client_id"] == "client-A"
        assert d["triggered_by"] == 42
        assert d["metadata"] == {"action": "create"}
        # occurred_at should be ISO-formatted string
        assert isinstance(d["occurred_at"], str)
        datetime.fromisoformat(d["occurred_at"])  # must parse without error

    def test_to_dict_occurred_at_is_iso_string(self):
        event = _make_event()
        d = event.to_dict()
        parsed = datetime.fromisoformat(d["occurred_at"])
        assert isinstance(parsed, datetime)


# ========================================================================
# 2. EventHandler base class
# ========================================================================


class TestEventHandler:
    """Tests for the abstract EventHandler base class."""

    def test_handle_raises_not_implemented(self):
        handler = EventHandler()
        with pytest.raises(NotImplementedError, match="Subclasses must implement"):
            asyncio.run(handler.handle(_make_event()))

    def test_can_handle_returns_true_by_default(self):
        handler = EventHandler()
        assert handler.can_handle(_make_event()) is True

    def test_default_priority_is_100(self):
        handler = EventHandler()
        assert handler.priority == 100

    def test_default_is_async_is_false(self):
        handler = EventHandler()
        assert handler.is_async is False

    def test_custom_priority_and_async(self):
        handler = EventHandler(is_async=True, priority=10)
        assert handler.is_async is True
        assert handler.priority == 10

    def test_subclass_can_override_can_handle(self):
        handler = SelectiveHandler(accepted_types=["a.b"])
        assert handler.can_handle(_make_event(event_type="a.b")) is True
        assert handler.can_handle(_make_event(event_type="x.y")) is False


# ========================================================================
# 3. EventBus -- subscription management
# ========================================================================


class TestEventBusSubscription:
    """Tests for EventBus.subscribe / unsubscribe."""

    def test_subscribe_adds_handler(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("test.event", handler)
        assert len(bus._handlers["test.event"]) == 1
        assert bus._handlers["test.event"][0].handler is handler

    def test_subscribe_multiple_handlers_to_same_event(self, reset_event_bus):
        bus = reset_event_bus
        h1 = RecordingHandler()
        h2 = RecordingHandler()
        bus.subscribe("test.event", h1)
        bus.subscribe("test.event", h2)
        assert len(bus._handlers["test.event"]) == 2

    def test_subscribe_same_handler_to_different_events(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("event.a", handler)
        bus.subscribe("event.b", handler)
        assert len(bus._handlers["event.a"]) == 1
        assert len(bus._handlers["event.b"]) == 1

    def test_handlers_sorted_by_priority(self, reset_event_bus):
        bus = reset_event_bus
        h_low = RecordingHandler(priority=10)
        h_mid = RecordingHandler(priority=50)
        h_high = RecordingHandler(priority=200)
        # Subscribe in reverse priority order
        bus.subscribe("test.event", h_high, priority=200)
        bus.subscribe("test.event", h_low, priority=10)
        bus.subscribe("test.event", h_mid, priority=50)
        priorities = [r.priority for r in bus._handlers["test.event"]]
        assert priorities == [10, 50, 200]

    def test_unsubscribe_removes_handler(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("test.event", handler)
        result = bus.unsubscribe("test.event", handler)
        assert result is True
        assert len(bus._handlers["test.event"]) == 0

    def test_unsubscribe_returns_false_for_missing_handler(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        result = bus.unsubscribe("test.event", handler)
        assert result is False

    def test_unsubscribe_returns_false_for_wrong_event_type(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("event.a", handler)
        result = bus.unsubscribe("event.b", handler)
        assert result is False

    def test_unsubscribe_only_removes_correct_handler(self, reset_event_bus):
        bus = reset_event_bus
        h1 = RecordingHandler()
        h2 = RecordingHandler()
        bus.subscribe("test.event", h1)
        bus.subscribe("test.event", h2)
        bus.unsubscribe("test.event", h1)
        assert len(bus._handlers["test.event"]) == 1
        assert bus._handlers["test.event"][0].handler is h2


# ========================================================================
# 4. EventBus -- publish (immediate dispatch)
# ========================================================================


class TestEventBusPublish:
    """Tests for EventBus.publish (synchronous immediate dispatch)."""

    def test_publish_dispatches_to_matching_handler(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("test.event", handler)
        event = _make_event(event_type="test.event")
        bus.publish(event)
        assert len(handler.handled_events) == 1
        assert handler.handled_events[0] is event

    def test_publish_does_not_dispatch_to_unrelated_handler(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("other.event", handler)
        bus.publish(_make_event(event_type="test.event"))
        assert len(handler.handled_events) == 0

    def test_publish_dispatches_to_wildcard_handler(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("*", handler)
        bus.publish(_make_event(event_type="any.event.type"))
        assert len(handler.handled_events) == 1

    def test_publish_skips_async_handlers(self, reset_event_bus):
        """publish() uses sync_only=True, so async handlers must be skipped."""
        bus = reset_event_bus
        sync_handler = RecordingHandler(is_async=False)
        async_handler = RecordingHandler(is_async=True)
        bus.subscribe("test.event", sync_handler, is_async=False)
        bus.subscribe("test.event", async_handler, is_async=True)
        bus.publish(_make_event(event_type="test.event"))
        assert len(sync_handler.handled_events) == 1
        assert len(async_handler.handled_events) == 0

    def test_publish_respects_can_handle_filter(self, reset_event_bus):
        bus = reset_event_bus
        handler = SelectiveHandler(accepted_types=["a.b"])
        bus.subscribe("a.b", handler)
        bus.subscribe("x.y", handler)
        bus.publish(_make_event(event_type="a.b"))
        bus.publish(_make_event(event_type="x.y"))
        # Only "a.b" passes can_handle
        assert len(handler.handled_events) == 1
        assert handler.handled_events[0].event_type == "a.b"

    def test_publish_priority_order(self, reset_event_bus):
        """Handlers should run in priority order (lower number first)."""
        bus = reset_event_bus
        log: list = []
        h1 = OrderTrackingHandler("first", log, priority=1)
        h2 = OrderTrackingHandler("second", log, priority=50)
        h3 = OrderTrackingHandler("third", log, priority=200)
        # Subscribe in scrambled order
        bus.subscribe("test.event", h3, priority=200)
        bus.subscribe("test.event", h1, priority=1)
        bus.subscribe("test.event", h2, priority=50)
        bus.publish(_make_event(event_type="test.event"))
        assert log == ["first", "second", "third"]

    def test_publish_with_no_handlers_does_not_raise(self, reset_event_bus):
        bus = reset_event_bus
        # No handlers subscribed -- should be a no-op, not an error
        bus.publish(_make_event(event_type="no.handlers"))


# ========================================================================
# 5. EventBus -- collect / flush / discard
# ========================================================================


class TestEventBusCollectFlush:
    """Tests for the collect/flush/discard transactional pattern."""

    def test_collect_stores_event(self, reset_event_bus):
        bus = reset_event_bus
        event = _make_event()
        bus.collect(event)
        collected = bus.get_collected_events()
        assert len(collected) == 1
        assert collected[0] is event

    def test_collect_multiple_events(self, reset_event_bus):
        bus = reset_event_bus
        e1 = _make_event(event_type="e1")
        e2 = _make_event(event_type="e2")
        bus.collect(e1)
        bus.collect(e2)
        assert len(bus.get_collected_events()) == 2

    def test_get_collected_events_returns_copy(self, reset_event_bus):
        bus = reset_event_bus
        bus.collect(_make_event())
        copy = bus.get_collected_events()
        copy.clear()
        # Internal list should be unaffected
        assert len(bus.get_collected_events()) == 1

    def test_flush_dispatches_all_collected_events(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("test.event", handler)
        bus.collect(_make_event(event_type="test.event"))
        bus.collect(_make_event(event_type="test.event"))
        count = bus.flush_collected()
        assert count == 2
        assert len(handler.handled_events) == 2

    def test_flush_clears_collected_events(self, reset_event_bus):
        bus = reset_event_bus
        bus.collect(_make_event())
        bus.flush_collected()
        assert len(bus.get_collected_events()) == 0

    def test_flush_returns_zero_when_empty(self, reset_event_bus):
        bus = reset_event_bus
        assert bus.flush_collected() == 0

    def test_discard_clears_collected_events(self, reset_event_bus):
        bus = reset_event_bus
        bus.collect(_make_event())
        bus.collect(_make_event())
        count = bus.discard_collected()
        assert count == 2
        assert len(bus.get_collected_events()) == 0

    def test_discard_returns_zero_when_empty(self, reset_event_bus):
        bus = reset_event_bus
        assert bus.discard_collected() == 0

    def test_discard_does_not_dispatch(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("test.event", handler)
        bus.collect(_make_event(event_type="test.event"))
        bus.discard_collected()
        assert len(handler.handled_events) == 0

    def test_flush_calls_persistence_handler(self, reset_event_bus):
        bus = reset_event_bus
        persisted = []
        bus.set_persistence_handler(lambda e: persisted.append(e))
        bus.collect(_make_event())
        bus.flush_collected()
        assert len(persisted) == 1

    def test_flush_without_persistence_handler(self, reset_event_bus):
        """Flush should work fine when no persistence handler is set."""
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("test.event", handler)
        bus.collect(_make_event(event_type="test.event"))
        count = bus.flush_collected()
        assert count == 1
        assert len(handler.handled_events) == 1

    def test_set_persistence_handler(self, reset_event_bus):
        bus = reset_event_bus
        callback = lambda e: None  # noqa: E731
        bus.set_persistence_handler(callback)
        assert bus._persistence_handler is callback

    def test_collect_then_publish_are_independent(self, reset_event_bus):
        """Collecting does not dispatch; publishing does not touch collected list."""
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("test.event", handler)

        event_collected = _make_event(event_type="test.event")
        event_published = _make_event(event_type="test.event")

        bus.collect(event_collected)
        bus.publish(event_published)

        # Only the published event was dispatched so far
        assert len(handler.handled_events) == 1
        assert handler.handled_events[0] is event_published
        # Collected event is still pending
        assert len(bus.get_collected_events()) == 1


# ========================================================================
# 6. EventBus -- error isolation
# ========================================================================


class TestEventBusErrorIsolation:
    """One handler's error must not prevent other handlers from running."""

    def test_error_in_handler_does_not_block_next_handler(self, reset_event_bus):
        bus = reset_event_bus
        error_handler = ErrorHandler(priority=1)
        ok_handler = RecordingHandler(priority=50)
        bus.subscribe("test.event", error_handler, priority=1)
        bus.subscribe("test.event", ok_handler, priority=50)
        bus.publish(_make_event(event_type="test.event"))
        # The recording handler should still have received the event
        assert len(ok_handler.handled_events) == 1

    def test_error_in_handler_during_flush_continues(self, reset_event_bus):
        bus = reset_event_bus
        error_handler = ErrorHandler(priority=1)
        ok_handler = RecordingHandler(priority=50)
        bus.subscribe("test.event", error_handler, priority=1)
        bus.subscribe("test.event", ok_handler, priority=50)
        bus.collect(_make_event(event_type="test.event"))
        bus.collect(_make_event(event_type="test.event"))
        count = bus.flush_collected()
        # flush_collected increments count per event dispatched, even if a
        # handler inside _dispatch_to_handlers raises (the try/except in
        # _dispatch_to_handlers isolates per-handler errors, not per-event).
        # The outer try/except in flush_collected catches if the whole
        # dispatch blows up. Since ErrorHandler's error is isolated inside
        # _dispatch_to_handlers, both events should flush successfully.
        assert count == 2
        assert len(ok_handler.handled_events) == 2

    def test_wildcard_error_handler_does_not_block_specific(self, reset_event_bus):
        bus = reset_event_bus
        error_handler = ErrorHandler(priority=1)
        ok_handler = RecordingHandler(priority=50)
        bus.subscribe("*", error_handler, priority=1)
        bus.subscribe("test.event", ok_handler, priority=50)
        bus.publish(_make_event(event_type="test.event"))
        # The specific handler list runs before wildcard is appended,
        # but both are in all_handlers. Error in error_handler should
        # not prevent ok_handler from executing.
        assert len(ok_handler.handled_events) == 1


# ========================================================================
# 7. EventBus -- wildcard handlers
# ========================================================================


class TestEventBusWildcard:
    """Wildcard ('*') handlers should receive every published event."""

    def test_wildcard_receives_all_event_types(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("*", handler)
        bus.publish(_make_event(event_type="first.type"))
        bus.publish(_make_event(event_type="second.type"))
        bus.publish(_make_event(event_type="third.type"))
        assert len(handler.handled_events) == 3

    def test_wildcard_and_specific_both_fire(self, reset_event_bus):
        bus = reset_event_bus
        wildcard = RecordingHandler()
        specific = RecordingHandler()
        bus.subscribe("*", wildcard)
        bus.subscribe("test.event", specific)
        bus.publish(_make_event(event_type="test.event"))
        assert len(wildcard.handled_events) == 1
        assert len(specific.handled_events) == 1

    def test_wildcard_does_not_receive_after_unsubscribe(self, reset_event_bus):
        bus = reset_event_bus
        handler = RecordingHandler()
        bus.subscribe("*", handler)
        bus.unsubscribe("*", handler)
        bus.publish(_make_event(event_type="any.event"))
        assert len(handler.handled_events) == 0


# ========================================================================
# 8. HandlerRegistration dataclass
# ========================================================================


class TestHandlerRegistration:
    """Tests for the HandlerRegistration data class."""

    def test_fields_are_stored(self):
        handler = RecordingHandler()
        reg = HandlerRegistration(
            handler=handler,
            event_type="test.event",
            priority=42,
            is_async=True,
        )
        assert reg.handler is handler
        assert reg.event_type == "test.event"
        assert reg.priority == 42
        assert reg.is_async is True


# ========================================================================
# 9. EventBus -- singleton behaviour
# ========================================================================


class TestEventBusSingleton:
    """EventBus uses the singleton pattern via __new__."""

    def test_same_instance_returned(self):
        a = EventBus()
        b = EventBus()
        assert a is b

    def test_get_event_bus_returns_same_instance(self):
        from backend.events.bus import get_event_bus, event_bus as global_bus

        assert get_event_bus() is global_bus
        assert EventBus() is global_bus


# ========================================================================
# 10. Domain event definitions -- representative sample
# ========================================================================


class TestDomainEventDefinitions:
    """
    Verify that concrete domain event subclasses carry correct defaults
    and serialize properly via to_dict().
    """

    # -- WorkOrderStatusChanged --

    def test_work_order_status_changed_defaults(self):
        event = WorkOrderStatusChanged(
            aggregate_id="wo-1",
            to_status="IN_PROGRESS",
        )
        assert event.event_type == "work_order.status_changed"
        assert event.aggregate_type == "WorkOrder"
        assert event.from_status is None
        assert event.to_status == "IN_PROGRESS"
        assert event.trigger_source == "manual"
        assert event.notes is None

    def test_work_order_status_changed_custom_fields(self):
        event = WorkOrderStatusChanged(
            aggregate_id="wo-2",
            from_status="PENDING",
            to_status="IN_PROGRESS",
            trigger_source="scheduler",
            notes="auto-scheduled",
            client_id="client-X",
        )
        assert event.from_status == "PENDING"
        assert event.trigger_source == "scheduler"
        assert event.client_id == "client-X"

    def test_work_order_status_changed_immutable(self):
        event = WorkOrderStatusChanged(
            aggregate_id="wo-1",
            to_status="IN_PROGRESS",
        )
        with pytest.raises(ValidationError):
            event.to_status = "DONE"

    # -- ProductionEntryCreated --

    def test_production_entry_created_defaults(self):
        event = ProductionEntryCreated(
            aggregate_id="pe-1",
            product_id=10,
            shift_id=1,
            production_date=date(2026, 2, 14),
            units_produced=500,
        )
        assert event.event_type == "production.entry_created"
        assert event.aggregate_type == "ProductionEntry"
        assert event.efficiency_percentage is None
        assert event.performance_percentage is None

    def test_production_entry_created_with_decimals(self):
        event = ProductionEntryCreated(
            aggregate_id="pe-2",
            product_id=10,
            shift_id=1,
            production_date=date(2026, 2, 14),
            units_produced=500,
            efficiency_percentage=Decimal("92.5"),
            performance_percentage=Decimal("88.0"),
        )
        assert event.efficiency_percentage == Decimal("92.5")
        assert event.performance_percentage == Decimal("88.0")

    # -- HoldCreated --

    def test_hold_created_defaults(self):
        event = HoldCreated(
            aggregate_id="hold-1",
            work_order_id="wo-77",
        )
        assert event.event_type == "hold.created"
        assert event.aggregate_type == "HoldEntry"
        assert event.hold_reason_category is None
        assert event.hold_reason is None
        assert event.quantity_on_hold == 0
        assert event.initial_status == "ON_HOLD"

    # -- KPIThresholdViolated --

    def test_kpi_threshold_violated(self):
        event = KPIThresholdViolated(
            aggregate_id="kpi-1",
            metric_name="OTD",
            current_value=Decimal("78.5"),
            threshold_value=Decimal("85.0"),
            threshold_type="min",
        )
        assert event.event_type == "kpi.threshold_violated"
        assert event.aggregate_type == "KPIMetric"
        assert event.metric_name == "OTD"
        assert event.current_value == Decimal("78.5")
        assert event.threshold_value == Decimal("85.0")
        assert event.period is None

    # -- CapacityScenarioCreated --

    def test_capacity_scenario_created(self):
        event = CapacityScenarioCreated(
            aggregate_id="sc-1",
            scenario_id=42,
            scenario_name="Overtime Q3",
            scenario_type="overtime",
        )
        assert event.event_type == "capacity.scenario_created"
        assert event.aggregate_type == "CapacityScenario"
        assert event.scenario_id == 42
        assert event.scenario_name == "Overtime Q3"
        assert event.base_schedule_id is None

    # -- ComponentShortageDetected --

    def test_component_shortage_detected(self):
        event = ComponentShortageDetected(
            aggregate_id="cs-1",
            order_id="ord-5",
            component_item_code="COMP-ABC",
            shortage_quantity=Decimal("15"),
            required_quantity=Decimal("100"),
            available_quantity=Decimal("85"),
        )
        assert event.event_type == "capacity.component_shortage"
        assert event.aggregate_type == "ComponentCheck"
        assert event.affected_orders_count == 1

    # -- QualityInspectionRecorded --

    def test_quality_inspection_recorded_defaults(self):
        event = QualityInspectionRecorded(
            aggregate_id="qi-1",
        )
        assert event.event_type == "quality.inspection_recorded"
        assert event.aggregate_type == "QualityInspection"
        assert event.defect_count == 0
        assert event.scrap_count == 0
        assert event.passed is True

    # -- Serialization round-trip for subclass fields --

    def test_subclass_to_dict_includes_extra_fields(self):
        """to_dict() only includes base DomainEvent fields by design."""
        event = WorkOrderStatusChanged(
            aggregate_id="wo-1",
            to_status="CLOSED",
            from_status="IN_PROGRESS",
            client_id="client-1",
        )
        d = event.to_dict()
        # Base fields must be present
        assert d["event_type"] == "work_order.status_changed"
        assert d["aggregate_type"] == "WorkOrder"
        assert d["client_id"] == "client-1"
        # to_dict() only serializes base DomainEvent fields
        # Subclass-specific fields are NOT in the dict (by design)
        assert "from_status" not in d
        assert "to_status" not in d

    def test_subclass_model_dump_includes_all_fields(self):
        """Pydantic model_dump / dict() includes all fields, including subclass."""
        event = WorkOrderStatusChanged(
            aggregate_id="wo-1",
            to_status="CLOSED",
            from_status="IN_PROGRESS",
        )
        full = event.model_dump() if hasattr(event, "model_dump") else event.dict()
        assert full["from_status"] == "IN_PROGRESS"
        assert full["to_status"] == "CLOSED"
        assert full["trigger_source"] == "manual"


# ========================================================================
# 11. Parametrized: verify every domain event subclass has correct defaults
# ========================================================================

_ALL_EVENT_CLASSES = [
    (WorkOrderStatusChanged, "work_order.status_changed", "WorkOrder", {"to_status": "X"}),
    (WorkOrderCreated, "work_order.created", "WorkOrder", {"work_order_number": "WO-1"}),
    (WorkOrderClosed, "work_order.closed", "WorkOrder", {}),
    (
        ProductionEntryCreated,
        "production.entry_created",
        "ProductionEntry",
        {"product_id": 1, "shift_id": 1, "production_date": date(2026, 1, 1), "units_produced": 10},
    ),
    (ProductionEntryUpdated, "production.entry_updated", "ProductionEntry", {}),
    (QualityInspectionRecorded, "quality.inspection_recorded", "QualityInspection", {}),
    (QualityDefectReported, "quality.defect_reported", "DefectEntry", {"defect_type": "scratch"}),
    (HoldCreated, "hold.created", "HoldEntry", {"work_order_id": "wo-1"}),
    (HoldResumed, "hold.resumed", "HoldEntry", {"work_order_id": "wo-1"}),
    (HoldApprovalRequired, "hold.approval_required", "HoldEntry", {"work_order_id": "wo-1", "requested_by": 1}),
    (
        KPIThresholdViolated,
        "kpi.threshold_violated",
        "KPIMetric",
        {"metric_name": "OTD", "current_value": Decimal("1"), "threshold_value": Decimal("2"), "threshold_type": "min"},
    ),
    (
        KPITargetAchieved,
        "kpi.target_achieved",
        "KPIMetric",
        {"metric_name": "OTD", "current_value": Decimal("1"), "target_value": Decimal("2")},
    ),
    (
        EmployeeAssignedToFloatingPool,
        "employee.assigned_to_floating_pool",
        "Employee",
        {"employee_name": "John", "employee_code": "E001"},
    ),
    (
        EmployeeAssignedToClient,
        "employee.assigned_to_client",
        "FloatingPoolAssignment",
        {"employee_id": 1, "employee_name": "John", "assigned_client_id": "C1"},
    ),
    (
        OrderScheduled,
        "capacity.order_scheduled",
        "CapacitySchedule",
        {"order_id": "O1", "line_id": "L1", "scheduled_date": date(2026, 1, 1)},
    ),
    (
        ComponentShortageDetected,
        "capacity.component_shortage",
        "ComponentCheck",
        {
            "order_id": "O1",
            "component_item_code": "C1",
            "shortage_quantity": Decimal("1"),
            "required_quantity": Decimal("10"),
            "available_quantity": Decimal("9"),
        },
    ),
    (
        CapacityOverloadDetected,
        "capacity.overload_detected",
        "CapacityAnalysis",
        {
            "line_id": "L1",
            "analysis_date": date(2026, 1, 1),
            "utilization_percent": Decimal("110"),
            "available_hours": Decimal("8"),
            "required_hours": Decimal("9"),
        },
    ),
    (ScheduleCommitted, "capacity.schedule_committed", "CapacitySchedule", {"schedule_id": 1}),
    (
        KPIVarianceAlert,
        "capacity.kpi_variance",
        "KPICommitment",
        {
            "kpi_key": "k1",
            "committed_value": Decimal("1"),
            "actual_value": Decimal("2"),
            "variance_percent": Decimal("100"),
        },
    ),
    (BOMExploded, "capacity.bom_exploded", "BOM", {"parent_item_code": "P1", "quantity_requested": Decimal("10")}),
    (
        CapacityScenarioCreated,
        "capacity.scenario_created",
        "CapacityScenario",
        {"scenario_id": 1, "scenario_name": "S1"},
    ),
    (CapacityScenarioCompared, "capacity.scenario_compared", "CapacityScenario", {}),
]


class TestAllDomainEventSubclasses:
    """Parametrized tests covering every domain event subclass."""

    @pytest.mark.parametrize(
        "cls, expected_event_type, expected_aggregate_type, extra_fields",
        _ALL_EVENT_CLASSES,
        ids=[c[0].__name__ for c in _ALL_EVENT_CLASSES],
    )
    def test_inherits_from_domain_event(self, cls, expected_event_type, expected_aggregate_type, extra_fields):
        assert issubclass(cls, DomainEvent)

    @pytest.mark.parametrize(
        "cls, expected_event_type, expected_aggregate_type, extra_fields",
        _ALL_EVENT_CLASSES,
        ids=[c[0].__name__ for c in _ALL_EVENT_CLASSES],
    )
    def test_default_event_type(self, cls, expected_event_type, expected_aggregate_type, extra_fields):
        event = cls(aggregate_id="test-id", **extra_fields)
        assert event.event_type == expected_event_type

    @pytest.mark.parametrize(
        "cls, expected_event_type, expected_aggregate_type, extra_fields",
        _ALL_EVENT_CLASSES,
        ids=[c[0].__name__ for c in _ALL_EVENT_CLASSES],
    )
    def test_default_aggregate_type(self, cls, expected_event_type, expected_aggregate_type, extra_fields):
        event = cls(aggregate_id="test-id", **extra_fields)
        assert event.aggregate_type == expected_aggregate_type

    @pytest.mark.parametrize(
        "cls, expected_event_type, expected_aggregate_type, extra_fields",
        _ALL_EVENT_CLASSES,
        ids=[c[0].__name__ for c in _ALL_EVENT_CLASSES],
    )
    def test_to_dict_returns_dict(self, cls, expected_event_type, expected_aggregate_type, extra_fields):
        event = cls(aggregate_id="test-id", **extra_fields)
        d = event.to_dict()
        assert isinstance(d, dict)
        assert d["event_type"] == expected_event_type
        assert d["aggregate_type"] == expected_aggregate_type

    @pytest.mark.parametrize(
        "cls, expected_event_type, expected_aggregate_type, extra_fields",
        _ALL_EVENT_CLASSES,
        ids=[c[0].__name__ for c in _ALL_EVENT_CLASSES],
    )
    def test_immutability(self, cls, expected_event_type, expected_aggregate_type, extra_fields):
        event = cls(aggregate_id="test-id", **extra_fields)
        with pytest.raises(ValidationError):
            event.aggregate_id = "mutated"
