"""Tests for `active_as_of` reading real hold-status history (Cycle 4 PR-C1,
Task 4) instead of judging past dates by a hold's CURRENT status.

Fixtures build holds directly plus explicit `HoldStatusTransition` rows,
mirroring the pattern in backend/tests/test_crud/test_hold_transition_log.py
(file-local `sample_client` via `TestDataFactory`; `db_session` is the real
fixture from backend/tests/conftest.py -- `sample_client`/`sample_hold` are
not shared fixtures in this repo).
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from backend.calculations.wip_aging import active_as_of, hold_status_history_started_at
from backend.db.factories import TestDataFactory
from backend.orm.hold_entry import HoldEntry
from backend.orm.hold_status_transition import HoldStatusTransition


def _active_ids(db, as_of):
    return {h.hold_entry_id for h in db.query(HoldEntry).filter(active_as_of(as_of)).all()}


def _t(db, hold_id, client_id, from_status, to_status, when):
    db.add(
        HoldStatusTransition(
            hold_entry_id=hold_id,
            client_id=client_id,
            from_status=from_status,
            to_status=to_status,
            transitioned_at=when,
        )
    )


def _make_hold(db, client, hold_id, hold_date, current_status):
    """A HoldEntry that is never resumed, carrying the given CURRENT status.

    `current_status` is deliberately set to what the hold looks like TODAY --
    the tests turn on it differing from the status at the as-of date.

    `work_order_id` is NOT NULL on HOLD_ENTRY (backend/orm/hold_entry.py), so
    unlike the brief's placeholder this creates a real work order rather than
    passing None.
    """
    work_order = TestDataFactory.create_work_order(db, client_id=client.client_id, work_order_id=f"WO-{hold_id}")
    hold = HoldEntry(
        hold_entry_id=hold_id,
        client_id=client.client_id,
        work_order_id=work_order.work_order_id,
        hold_status=current_status,
        hold_date=hold_date,
        resume_date=None,
        hold_reason="test fixture",
    )
    db.add(hold)
    return hold


@pytest.fixture
def sample_client(db_session):
    client = TestDataFactory.create_client(db_session, client_id="HSH-C1", client_name="Hold History Test Client")
    db_session.commit()
    return client


@pytest.fixture
def hold_with_history(db_session, sample_client):
    a = _make_hold(db_session, sample_client, "H-PENDING-APPROVED", datetime(2026, 3, 1, 8, 0, 0), "ON_HOLD")
    b = _make_hold(db_session, sample_client, "H-HELD-CANCELLED", datetime(2026, 3, 1, 9, 0, 0), "CANCELLED")
    db_session.flush()

    _t(db_session, a.hold_entry_id, a.client_id, None, "PENDING_HOLD_APPROVAL", datetime(2026, 3, 1, 8, 0, 0))
    _t(db_session, a.hold_entry_id, a.client_id, "PENDING_HOLD_APPROVAL", "ON_HOLD", datetime(2026, 3, 5, 10, 0, 0))
    _t(db_session, b.hold_entry_id, b.client_id, None, "ON_HOLD", datetime(2026, 3, 1, 9, 0, 0))
    _t(db_session, b.hold_entry_id, b.client_id, "ON_HOLD", "CANCELLED", datetime(2026, 3, 8, 11, 0, 0))
    db_session.flush()

    return SimpleNamespace(pending_then_approved=a.hold_entry_id, held_then_cancelled=b.hold_entry_id)


@pytest.fixture
def hold_without_history(db_session, sample_client):
    hold = _make_hold(db_session, sample_client, "H-NO-HISTORY", datetime(2026, 3, 1, 8, 0, 0), "ON_HOLD")
    db_session.flush()
    return hold


@pytest.fixture
def same_second_hold(db_session, sample_client):
    hold = _make_hold(db_session, sample_client, "H-SAME-SECOND", datetime(2026, 3, 1, 8, 0, 0), "CANCELLED")
    db_session.flush()
    same = datetime(2026, 3, 4, 12, 0, 0)
    _t(db_session, hold.hold_entry_id, hold.client_id, None, "ON_HOLD", same)
    _t(db_session, hold.hold_entry_id, hold.client_id, "ON_HOLD", "CANCELLED", same)
    db_session.flush()
    return hold


def test_pending_then_approved_hold_is_absent_before_approval(db_session, hold_with_history):
    """Was only PENDING_HOLD_APPROVAL on day 3; approved on day 5.

    Current-status logic counts it at day 3 because it reads ON_HOLD today.
    """
    assert hold_with_history.pending_then_approved not in _active_ids(db_session, date(2026, 3, 3))
    assert hold_with_history.pending_then_approved in _active_ids(db_session, date(2026, 3, 6))


def test_held_then_cancelled_hold_is_present_before_cancellation(db_session, hold_with_history):
    """Was ON_HOLD on day 3; cancelled on day 8.

    Current-status logic drops it from day 3 because it reads CANCELLED today.
    """
    assert hold_with_history.held_then_cancelled in _active_ids(db_session, date(2026, 3, 3))
    assert hold_with_history.held_then_cancelled not in _active_ids(db_session, date(2026, 3, 9))


def test_hold_without_history_falls_back_to_current_status(db_session, hold_without_history):
    """No backfill: a pre-existing hold has no transitions, so behaviour is
    exactly what it was before this change -- present while unresumed."""
    assert hold_without_history.hold_entry_id in _active_ids(db_session, date(2026, 3, 3))
    assert hold_without_history.hold_entry_id in _active_ids(db_session, date(2026, 3, 9))


def test_same_second_transitions_resolve_by_insertion_order(db_session, same_second_hold):
    """MariaDB DATETIME has whole-second resolution, so two transitions can
    share a timestamp. The later-inserted row must win."""
    assert same_second_hold.hold_entry_id not in _active_ids(db_session, date(2026, 3, 5))


def test_history_boundary_reports_first_recorded_transition(db_session, hold_with_history):
    assert hold_status_history_started_at(db_session) == datetime(2026, 3, 1, 8, 0, 0)
