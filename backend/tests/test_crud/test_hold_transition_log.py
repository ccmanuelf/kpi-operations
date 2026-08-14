"""Tests for record_hold_transition (backend/crud/hold/transition_log.py)."""

from datetime import datetime, timedelta

import pytest

from backend.crud.hold import create_wip_hold, resume_hold
from backend.crud.hold.transition_log import record_hold_transition
from backend.orm.hold_entry import HoldStatus
from backend.orm.hold_status_transition import HoldStatusTransition
from backend.schemas.hold import WIPHoldCreate
from backend.tests.fixtures.factories import TestDataFactory


@pytest.fixture
def sample_client(db_session):
    client = TestDataFactory.create_client(
        db_session, client_id="HOLD-TXN-C1", client_name="Hold Transition Test Client"
    )
    db_session.commit()
    return client


@pytest.fixture
def sample_user(db_session, sample_client):
    user = TestDataFactory.create_user(
        db_session, username="hold_txn_user", role="admin", client_id=sample_client.client_id
    )
    db_session.commit()
    return user


@pytest.fixture
def sample_hold(db_session, sample_client, sample_user):
    work_order = TestDataFactory.create_work_order(db_session, client_id=sample_client.client_id)
    hold = TestDataFactory.create_hold_entry(
        db_session,
        work_order_id=work_order.work_order_id,
        client_id=sample_client.client_id,
        created_by=sample_user.user_id,
        hold_status=HoldStatus.PENDING_HOLD_APPROVAL,
    )
    db_session.commit()
    return hold


def test_records_transition_with_explicit_instant(db_session, sample_hold, sample_user):
    when = datetime(2026, 3, 1, 8, 30, 0)

    row = record_hold_transition(
        db_session,
        sample_hold,
        to_status="ON_HOLD",
        current_user=sample_user,
        from_status="PENDING_HOLD_APPROVAL",
        transitioned_at=when,
    )
    db_session.flush()

    assert row.transitioned_at == when
    assert row.from_status == "PENDING_HOLD_APPROVAL"
    assert row.to_status == "ON_HOLD"
    assert row.hold_entry_id == sample_hold.hold_entry_id
    assert row.client_id == sample_hold.client_id
    assert row.transitioned_by == sample_user.user_id


def test_from_status_defaults_to_holds_current_status(db_session, sample_hold, sample_user):
    sample_hold.hold_status = "ON_HOLD"

    row = record_hold_transition(db_session, sample_hold, to_status="RESUMED", current_user=sample_user)
    db_session.flush()

    assert row.from_status == "ON_HOLD"


def test_explicit_none_from_status_is_preserved(db_session, sample_hold, sample_user):
    """Explicit from_status=None (the hold-creation row) must not be silently
    overwritten by the hold's current status. This is only distinguishable
    from "not passed" because the implementation compares against the
    `_UNSET` sentinel by identity rather than treating `from_status` as
    falsy."""
    sample_hold.hold_status = "ON_HOLD"

    row = record_hold_transition(
        db_session, sample_hold, to_status="ON_HOLD", current_user=sample_user, from_status=None
    )
    db_session.flush()

    assert row.from_status is None


def test_defaults_transitioned_at_to_now_when_not_given(db_session, sample_hold, sample_user):
    before = datetime.utcnow() - timedelta(seconds=5)

    row = record_hold_transition(db_session, sample_hold, to_status="RESUMED", current_user=sample_user)
    db_session.flush()

    assert row.transitioned_at >= before


def test_rows_are_queryable_in_recorded_order(db_session, sample_hold, sample_user):
    day1 = datetime(2026, 3, 1, 8, 0, 0)
    day5 = datetime(2026, 3, 5, 8, 0, 0)
    record_hold_transition(db_session, sample_hold, to_status="ON_HOLD", current_user=sample_user, transitioned_at=day5)
    record_hold_transition(
        db_session,
        sample_hold,
        to_status="PENDING_HOLD_APPROVAL",
        current_user=sample_user,
        from_status=None,
        transitioned_at=day1,
    )
    db_session.flush()

    rows = (
        db_session.query(HoldStatusTransition)
        .filter(HoldStatusTransition.hold_entry_id == sample_hold.hold_entry_id)
        .order_by(HoldStatusTransition.transitioned_at)
        .all()
    )

    assert [r.to_status for r in rows] == ["PENDING_HOLD_APPROVAL", "ON_HOLD"]


def _hold_create_payload(client, work_order_id):
    return WIPHoldCreate(
        client_id=client.client_id,
        work_order_id=work_order_id,
        hold_reason_category="quality",
        hold_reason="QUALITY_ISSUE",
    )


def test_hold_creation_records_opening_row(db_session, sample_client, sample_user):
    """Every hold begins with a from_status=None row, so its history is complete."""
    work_order = TestDataFactory.create_work_order(db_session, client_id=sample_client.client_id)
    db_session.commit()

    hold = create_wip_hold(db_session, _hold_create_payload(sample_client, work_order.work_order_id), sample_user)
    db_session.flush()

    rows = db_session.query(HoldStatusTransition).filter(HoldStatusTransition.hold_entry_id == hold.hold_entry_id).all()

    assert len(rows) == 1
    assert rows[0].from_status is None
    assert rows[0].to_status == hold.hold_status


def test_resume_records_transition_to_resumed(db_session, sample_hold, sample_user):
    sample_hold.hold_status = "ON_HOLD"
    db_session.flush()

    resume_hold(db_session, sample_hold.hold_entry_id, sample_user.user_id, sample_user)
    db_session.flush()

    rows = (
        db_session.query(HoldStatusTransition)
        .filter(HoldStatusTransition.hold_entry_id == sample_hold.hold_entry_id)
        .order_by(HoldStatusTransition.transition_id)
        .all()
    )

    assert rows[-1].from_status == "ON_HOLD"
    assert rows[-1].to_status == "RESUMED"


def test_every_hold_status_write_site_is_instrumented():
    """Static guard: a hold_status assignment with no recorder call nearby is a
    hole in the history, and holes are invisible until a trend query is wrong.

    Scans for `hold_status =` assignments in production modules and requires
    `record_hold_transition` to appear in the same file.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2]
    assignment = re.compile(r"^\s*[\w.]*hold_status\s*=\s*(?!=)")
    offenders = []

    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("tests/", "orm/", "schemas/", "scripts/", "db/", "alembic/")):
            continue
        text = path.read_text()
        if any(assignment.match(line) for line in text.splitlines()):
            if "record_hold_transition" not in text:
                offenders.append(rel)

    assert offenders == []
