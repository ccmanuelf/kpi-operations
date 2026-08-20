import dataclasses
from datetime import datetime

import pytest

from backend.seed.events import (
    EVENT_TYPES,
    PLATFORM_CLIENT_ID,
    AttendanceRecorded,
    DefectsFound,
    DowntimeLogged,
    Event,
    HoldOpened,
    ProductionRecorded,
    QualityInspected,
    UserCreated,
    WorkOrderReceived,
)


def _evt(**kw):
    base = dict(at=datetime(2026, 3, 1, 6, 0, 0), seq=1, client_id="DEMO-PIECE")
    base.update(kw)
    return base


def test_events_are_frozen():
    e = WorkOrderReceived(
        **_evt(),
        work_order_id="WO-1",
        product_id="P-1",
        planned_quantity=100,
        style_model="STYLE-1",
        origin="AD_HOC",
        required_date=datetime(2026, 3, 5, 0, 0, 0),
        priority=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.seq = 2


def test_order_key_is_at_then_seq():
    a = WorkOrderReceived(
        **_evt(seq=1),
        work_order_id="WO-1",
        product_id="P-1",
        planned_quantity=1,
        style_model="STYLE-1",
        origin="AD_HOC",
        required_date=datetime(2026, 3, 5, 0, 0, 0),
        priority=None,
    )
    b = WorkOrderReceived(
        **_evt(seq=2),
        work_order_id="WO-2",
        product_id="P-1",
        planned_quantity=1,
        style_model="STYLE-1",
        origin="AD_HOC",
        required_date=datetime(2026, 3, 5, 0, 0, 0),
        priority=None,
    )

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
    date; the seeder is the caller that can reach that path (spec section 12).
    ShiftWorked is gone (split into per-table events) so this now exercises
    a widened event instead."""
    from datetime import date

    with pytest.raises(TypeError):
        AttendanceRecorded(
            at=date(2026, 3, 1),
            seq=1,
            client_id="DEMO-PIECE",
            employee_id="E-1",
            line_id="L-1",
            shift_id="S-1",
            shift_date=datetime(2026, 3, 1, 6, 0, 0),
            scheduled_hours=8.0,
            hours_worked=8.0,
            is_absent=False,
        )


def test_every_event_type_subclasses_event_and_is_registered():
    for t in EVENT_TYPES:
        assert issubclass(t, Event)
    assert len(EVENT_TYPES) == len(set(EVENT_TYPES))


def _base(**kw):
    b = dict(at=datetime(2026, 3, 2, 6, 30, 0), seq=1, client_id="DEMO-PIECE")
    b.update(kw)
    return b


def test_shift_worked_no_longer_exists():
    """One shift writes rows in five tables and N per-employee attendance rows.
    A single ShiftWorked forces the materializer to invent the ones it does not
    describe, which is generation in the write layer."""
    import backend.seed.events as events_mod

    assert not hasattr(events_mod, "ShiftWorked")


def test_attendance_is_per_employee():
    e = AttendanceRecorded(
        **_base(),
        employee_id="DEMO-PIECE-EMP-001",
        line_id="DEMO-PIECE-LINE-01",
        shift_id="DEMO-PIECE-SHIFT-01",
        shift_date=datetime(2026, 3, 2, 6, 0, 0),
        scheduled_hours=8.0,
        hours_worked=8.0,
        is_absent=False,
    )

    assert e.employee_id == "DEMO-PIECE-EMP-001"
    assert e.is_absent is False


def test_every_datetime_field_is_validated_not_just_at():
    """`at` was the only guarded field while it was the only datetime one. The
    widened events carry shift_date and required_date, and MariaDB rounds a
    fractional second on ANY of them across a day boundary."""
    with pytest.raises(ValueError) as exc:
        AttendanceRecorded(
            **_base(),
            employee_id="E1",
            line_id="L1",
            shift_id="S1",
            shift_date=datetime(2026, 3, 2, 23, 59, 59, 500000),
            scheduled_hours=8.0,
            hours_worked=8.0,
            is_absent=False,
        )

    assert "shift_date" in str(exc.value)


def test_downtime_carries_a_root_cause():
    """Spec section 6 wants DEMO-HOURLY to read as equipment reliability and the
    Q4 correlation block needs scheduling-category downtime. Without a root cause
    on the event, both render as undifferentiated totals."""
    e = DowntimeLogged(
        **_base(),
        line_id="DEMO-HOURLY-LINE-01",
        shift_id="DEMO-HOURLY-SHIFT-01",
        shift_date=datetime(2026, 3, 2, 6, 0, 0),
        downtime_reason="MAINTENANCE",
        root_cause_category="machine",
        downtime_minutes=45,
    )

    assert e.root_cause_category == "machine"


def test_defects_reference_a_catalog_code_not_a_display_name():
    e = DefectsFound(**_base(), quality_entry_id="QE-1", defect_code="STITCH", defect_count=3)

    assert e.defect_code == "STITCH"


def test_quality_names_the_work_order_it_inspected():
    e = QualityInspected(
        **_base(),
        quality_entry_id="QE-1",
        work_order_id="DEMO-PIECE-WO-0001",
        shift_date=datetime(2026, 3, 2, 6, 0, 0),
        units_inspected=200,
        units_passed=195,
        units_defective=5,
        total_defects_count=7,
    )

    assert e.work_order_id == "DEMO-PIECE-WO-0001"


def test_production_carries_the_columns_the_table_requires():
    e = ProductionRecorded(
        **_base(),
        production_entry_id="PE-1",
        line_id="L1",
        shift_id="S1",
        product_id="P1",
        work_order_id="DEMO-PIECE-WO-0001",
        shift_date=datetime(2026, 3, 2, 6, 0, 0),
        units_produced=200,
        run_time_hours=7.5,
        scrap_count=2,
        employees_assigned=4,
        entered_by="demo_supervisor",
    )

    assert e.run_time_hours == 7.5
    assert e.entered_by == "demo_supervisor"


def test_platform_users_carry_the_sentinel_client():
    """admin and poweruser belong to no tenant. The sentinel keeps client_id a
    required str on every event; the materializer must never write it to a
    client_id column (guarded in test_seed_gates.py)."""
    e = UserCreated(
        **_base(client_id=PLATFORM_CLIENT_ID),
        user_id="USR-ADMIN",
        username="demo_admin",
        role="admin",
        email="demo_admin@example.invalid",
        full_name="Demo Admin",
        password="DemoSeed#2026",  # pragma: allowlist secret
    )

    assert e.client_id == PLATFORM_CLIENT_ID


def test_event_types_is_exhaustive():
    """EVENT_TYPES drives the coverage and purity guards, and it is what the
    materializer dispatches on: a subclass defined in this module but left out
    of the tuple would be generated and silently never written, so the
    registered set must EQUAL the defined set rather than merely be internally
    consistent.

    Walks vars(module) rather than Event.__subclasses__(), which is why the
    __subclasses__ variant of this test was dropped instead of this one:
    __subclasses__() returns only DIRECT subclasses, so an event that ever
    specialises another event would vanish from the "defined" side and the
    equality would pass while the registry was wrong."""
    import backend.seed.events as events_mod
    from backend.seed.events import Event

    declared = {
        obj
        for obj in vars(events_mod).values()
        if isinstance(obj, type) and issubclass(obj, Event) and obj is not Event
    }

    assert declared == set(EVENT_TYPES)
