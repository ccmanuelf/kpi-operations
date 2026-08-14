import dataclasses
from datetime import datetime

import pytest

from backend.seed.events import (
    EVENT_TYPES,
    Event,
    HoldOpened,
    ShiftWorked,
    WorkOrderReceived,
)


def _evt(**kw):
    base = dict(at=datetime(2026, 3, 1, 6, 0, 0), seq=1, client_id="DEMO-PIECE")
    base.update(kw)
    return base


def test_events_are_frozen():
    e = WorkOrderReceived(**_evt(), work_order_id="WO-1", product_id="P-1", planned_quantity=100)
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.seq = 2


def test_order_key_is_at_then_seq():
    a = WorkOrderReceived(**_evt(seq=1), work_order_id="WO-1", product_id="P-1", planned_quantity=1)
    b = WorkOrderReceived(**_evt(seq=2), work_order_id="WO-2", product_id="P-1", planned_quantity=1)

    assert a.order_key < b.order_key


def test_microsecond_bearing_timestamp_is_rejected():
    """MariaDB DATETIME rounds fractional seconds, which would move an event
    across a day boundary. The model refuses them rather than letting the
    materializer discover it."""
    with pytest.raises(ValueError) as exc:
        HoldOpened(
            at=datetime(2026, 3, 1, 23, 59, 59, 500000),
            seq=1,
            client_id="DEMO-PIECE",
            hold_entry_id="H-1",
            work_order_id="WO-1",
            reason_category="QUALITY",
        )

    assert "microsecond" in str(exc.value)


def test_date_instead_of_datetime_is_rejected():
    """PR-C1's recorder calls .replace(microsecond=0) and raises on a bare
    date; the seeder is the caller that can reach that path (spec section 12)."""
    from datetime import date

    with pytest.raises(TypeError):
        ShiftWorked(
            at=date(2026, 3, 1),
            seq=1,
            client_id="DEMO-PIECE",
            line_id="L-1",
            shift_id="S-1",
            units_produced=10,
            units_defective=0,
            downtime_minutes=0,
            attendance_headcount=8,
        )


def test_every_event_type_subclasses_event_and_is_registered():
    for t in EVENT_TYPES:
        assert issubclass(t, Event)
    assert len(EVENT_TYPES) == len(set(EVENT_TYPES))
