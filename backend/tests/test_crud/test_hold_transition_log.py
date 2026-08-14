"""Tests for record_hold_transition (backend/crud/hold/transition_log.py)."""

from datetime import datetime, timedelta

import pytest

from backend.crud.hold.transition_log import record_hold_transition
from backend.orm.hold_entry import HoldStatus
from backend.orm.hold_status_transition import HoldStatusTransition
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
