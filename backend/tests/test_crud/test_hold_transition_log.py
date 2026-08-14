"""Tests for record_hold_transition (backend/crud/hold/transition_log.py)."""

from datetime import date, datetime, timedelta

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
    # Concrete expected status, not `== hold.hold_status` -- that tautology
    # passes even if create_wip_hold and the recorder silently diverged,
    # since both sides would read the same (possibly wrong) value.
    assert rows[0].to_status == HoldStatus.ON_HOLD


def test_backdated_hold_opening_transition_is_stamped_at_hold_date(db_session, sample_client, sample_user):
    """A CSV import routinely supplies a past hold_date. The opening
    transition must record history AS OF that date, not the moment the
    import ran -- otherwise every as-of date before the import falls into
    active_as_of's no-history COALESCE fallback and the whole point of this
    branch fails for the primary bulk-ingestion path."""
    work_order = TestDataFactory.create_work_order(db_session, client_id=sample_client.client_id)
    db_session.commit()

    backdated = date(2020, 1, 15)
    payload = WIPHoldCreate(
        client_id=sample_client.client_id,
        work_order_id=work_order.work_order_id,
        hold_reason_category="quality",
        hold_reason="QUALITY_ISSUE",
        hold_date=backdated,
    )

    hold = create_wip_hold(db_session, payload, sample_user)
    db_session.flush()

    rows = db_session.query(HoldStatusTransition).filter(HoldStatusTransition.hold_entry_id == hold.hold_entry_id).all()

    assert len(rows) == 1
    assert rows[0].transitioned_at == datetime.combine(backdated, datetime.min.time())


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


def test_approve_hold_records_transition_to_on_hold(db_session, sample_hold, sample_user):
    """approve_hold (backend/routes/holds.py) must record the PENDING_HOLD_APPROVAL
    -> ON_HOLD transition it performs, not some other pair."""
    from backend.routes.holds import approve_hold

    assert sample_hold.hold_status == HoldStatus.PENDING_HOLD_APPROVAL

    approve_hold(sample_hold.hold_entry_id, db=db_session, current_user=sample_user)

    rows = (
        db_session.query(HoldStatusTransition)
        .filter(HoldStatusTransition.hold_entry_id == sample_hold.hold_entry_id)
        .order_by(HoldStatusTransition.transition_id)
        .all()
    )

    assert rows[-1].from_status == HoldStatus.PENDING_HOLD_APPROVAL
    assert rows[-1].to_status == HoldStatus.ON_HOLD


def test_request_resume_records_transition_to_pending_resume_approval(db_session, sample_hold, sample_user):
    """request_resume (backend/routes/holds.py) must record the ON_HOLD ->
    PENDING_RESUME_APPROVAL transition it performs. A mutant that instead
    records `to_status=RELEASED` stays undetected by the static write-site
    guard (which only checks a recorder call exists nearby, not what it
    records) while silently dropping the hold from every WIP-aging
    aggregate/top-N/trend/chronic list, since RELEASED is in
    NON_WIP_HOLD_STATUSES."""
    from backend.routes.holds import request_resume

    sample_hold.hold_status = HoldStatus.ON_HOLD
    db_session.flush()

    request_resume(sample_hold.hold_entry_id, db=db_session, current_user=sample_user)

    rows = (
        db_session.query(HoldStatusTransition)
        .filter(HoldStatusTransition.hold_entry_id == sample_hold.hold_entry_id)
        .order_by(HoldStatusTransition.transition_id)
        .all()
    )

    assert rows[-1].from_status == HoldStatus.ON_HOLD
    assert rows[-1].to_status == HoldStatus.PENDING_RESUME_APPROVAL


def test_approve_resume_records_transition_to_resumed(db_session, sample_hold, sample_user):
    """approve_resume (backend/routes/holds.py) must record the
    PENDING_RESUME_APPROVAL -> RESUMED transition it performs."""
    from backend.routes.holds import approve_resume

    sample_hold.hold_status = HoldStatus.PENDING_RESUME_APPROVAL
    db_session.flush()

    approve_resume(sample_hold.hold_entry_id, db=db_session, current_user=sample_user)

    rows = (
        db_session.query(HoldStatusTransition)
        .filter(HoldStatusTransition.hold_entry_id == sample_hold.hold_entry_id)
        .order_by(HoldStatusTransition.transition_id)
        .all()
    )

    assert rows[-1].from_status == HoldStatus.PENDING_RESUME_APPROVAL
    assert rows[-1].to_status == HoldStatus.RESUMED


def test_release_hold_records_transition_to_resumed(db_session, sample_hold, sample_user):
    """release_hold (backend/crud/hold/duration.py) must record the ON_HOLD
    -> RESUMED transition it performs."""
    from backend.crud.hold.duration import release_hold

    sample_hold.hold_status = HoldStatus.ON_HOLD
    db_session.flush()

    release_hold(db_session, sample_hold.hold_entry_id, sample_user)

    rows = (
        db_session.query(HoldStatusTransition)
        .filter(HoldStatusTransition.hold_entry_id == sample_hold.hold_entry_id)
        .order_by(HoldStatusTransition.transition_id)
        .all()
    )

    assert rows[-1].from_status == HoldStatus.ON_HOLD
    assert rows[-1].to_status == HoldStatus.RESUMED


def test_every_hold_status_write_site_is_instrumented():
    """Static guard: a hold_status write with no recorder call nearby is a
    hole in the history, and holes are invisible until a trend query is wrong.

    Four write forms exist or are guarded against in this codebase and all
    four must be caught:
      - attribute assignment:   db_hold.hold_status = ...
      - dict/bracket-key assignment: hold_data["hold_status"] = ...   (crud/hold/core.py)
      - setattr-style:          setattr(db_hold, "hold_status", ...)
      - bulk-update forms:      .update({HoldEntry.hold_status: X}) /
                                 update(HoldEntry).values(hold_status=X)
                                 (no writer uses this shape today; this guard
                                 is the branch's stated defence against a
                                 future one, and a bulk path is exactly the
                                 shape a future writer takes -- it bypasses
                                 setattr entirely, so the three per-line
                                 patterns above cannot see it)

    Presence-in-file is not enough (that was the bug in the first version of
    this guard): it can't tell a real recorder call for site A from silence
    at site B in the same file. So this checks PROXIMITY per site — each
    matching write line must have a `record_hold_transition(` call within
    WINDOW lines of it, in the same file.

    WINDOW = 30. The largest legitimate gap among the seven real sites is
    crud/hold/core.py's create_wip_hold: Task 2's contract requires the
    recorder to run AFTER the flush that assigns hold_entry_id/client_id,
    so its one recorder call sits ~22 lines below the status write it
    describes (and covers both if/else branches, which sit even closer to
    it). Every other site calls the recorder immediately before the
    assignment (0-1 line gap). 30 lines comfortably covers the widest real
    gap while staying far short of a typical file's length, so a stray
    unrecorded write elsewhere in the same file still gets caught.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2]
    WINDOW = 30

    # Anchored at line-start (after leading whitespace) so this only matches
    # writes, not reads like `x = db_hold.hold_status`.
    attribute_write = re.compile(r"^\s*[\w.]*hold_status\s*=\s*(?!=)")
    # Requires the assignment `=` to follow the closing bracket, so a read
    # like `x = hold_data["hold_status"]` does not match.
    bracket_write = re.compile(r"""\[\s*['"]hold_status['"]\s*\]\s*=\s*(?!=)""")
    setattr_write = re.compile(r"""setattr\(\s*[\w.]+\s*,\s*['"]hold_status['"]\s*,""")
    # `.update({HoldEntry.hold_status: X})` (Query.update dict form) and
    # `update(HoldEntry).values(hold_status=X)` (Core update().values() form).
    # Scanned over the whole file text rather than per-line, since the
    # dict/kwargs argument routinely wraps onto its own line(s) in this
    # codebase's formatting.
    bulk_write = re.compile(r"\.(?:update|values)\([^)]{0,200}?hold_status", re.DOTALL)

    offenders = []

    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("tests/", "orm/", "schemas/", "scripts/", "db/", "alembic/")):
            continue
        text = path.read_text()
        lines = text.splitlines()
        recorder_lines = [i for i, line in enumerate(lines) if "record_hold_transition(" in line]

        for i, line in enumerate(lines):
            is_write = attribute_write.match(line) or bracket_write.search(line) or setattr_write.search(line)
            if not is_write:
                continue
            if not any(abs(i - r) <= WINDOW for r in recorder_lines):
                offenders.append(f"{rel}:{i + 1}")

        for match in bulk_write.finditer(text):
            line_no = text.count("\n", 0, match.start())
            if not any(abs(line_no - r) <= WINDOW for r in recorder_lines):
                offenders.append(f"{rel}:{line_no + 1}")

    assert offenders == []
