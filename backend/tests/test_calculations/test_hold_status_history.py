"""Tests for `active_as_of` reading real hold-status history (Cycle 4 PR-C1,
Task 4) instead of judging past dates by a hold's CURRENT status.

Fixtures build holds directly plus explicit `HoldStatusTransition` rows,
mirroring the pattern in backend/tests/test_crud/test_hold_transition_log.py
(file-local `sample_client` via `TestDataFactory`; `db_session` is the real
fixture from backend/tests/conftest.py -- `sample_client`/`sample_hold` are
not shared fixtures in this repo).
"""

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.auth.jwt import get_current_user
from backend.calculations.wip_aging import active_as_of, hold_status_history_started_at
from backend.crud.hold.transition_log import record_hold_transition
from backend.database import get_db
from backend.db.factories import TestDataFactory
from backend.main import app
from backend.orm.hold_entry import HoldEntry, HoldStatus
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
    # current_status is deliberately ON_HOLD -- the OPPOSITE of the correct
    # as-of answer (CANCELLED, per the transition chain below). If either the
    # tie-break (transition_id DESC) or the correlation itself is broken, the
    # subquery can resolve to NULL or to the wrong row, and COALESCE would
    # then fall back to (or land on) ON_HOLD -- which is active WIP -- making
    # the "not in _active_ids" assertion fail. A CANCELLED current_status
    # would have masked both bugs, since CANCELLED is what a broken NULL
    # fallback lands on too.
    hold = _make_hold(db_session, sample_client, "H-SAME-SECOND", datetime(2026, 3, 1, 8, 0, 0), "ON_HOLD")
    db_session.flush()
    same = datetime(2026, 3, 4, 12, 0, 0)
    _t(db_session, hold.hold_entry_id, hold.client_id, None, "ON_HOLD", same)
    _t(db_session, hold.hold_entry_id, hold.client_id, "ON_HOLD", "CANCELLED", same)
    db_session.flush()
    return hold


@pytest.fixture
def hold_with_only_future_history(db_session, sample_client):
    """Two holds whose hold_date precedes the cutoff, but whose ONLY recorded
    transition post-dates it -- the documented BOUNDARY case: the correlated
    subquery finds no row before the cutoff (returns NULL), so COALESCE
    falls back to the hold's current `hold_status`.

    Two current statuses, not one: a hold whose current status is CANCELLED
    is excluded whether or not COALESCE runs (NULL NOT IN (...) is also
    excluded), so it alone cannot prove the fallback fired -- only that the
    *documented* outcome holds. `on_hold_id`'s current status is ACTIVE WIP,
    so it only stays present because COALESCE reached for it; dropping the
    fallback flips it to absent (proved in the task-4 fix report).
    """
    cancelled = _make_hold(
        db_session, sample_client, "H-FUTURE-HISTORY-CANCELLED", datetime(2026, 2, 1, 8, 0, 0), "CANCELLED"
    )
    on_hold = _make_hold(db_session, sample_client, "H-FUTURE-HISTORY-ONHOLD", datetime(2026, 2, 1, 8, 0, 0), "ON_HOLD")
    db_session.flush()
    _t(db_session, cancelled.hold_entry_id, cancelled.client_id, None, "CANCELLED", datetime(2026, 3, 8, 9, 0, 0))
    _t(db_session, on_hold.hold_entry_id, on_hold.client_id, None, "ON_HOLD", datetime(2026, 3, 8, 9, 0, 0))
    db_session.flush()
    return SimpleNamespace(cancelled_id=cancelled.hold_entry_id, on_hold_id=on_hold.hold_entry_id)


def test_pending_then_approved_hold_is_absent_before_approval(db_session, hold_with_history):
    """Was only PENDING_HOLD_APPROVAL through day 4; approved at 10:00 on
    day 5 -- so day 5 is the only date that discriminates the status-arm
    boundary. A regression that bound the subquery to the START of the as-of
    day (e.g. `transitioned_at <= as_of` instead of `< cutoff`) would miss
    the day-5 transition and read the hold as still-pending, which day 3 and
    day 6 alone cannot catch.

    Current-status logic counts it at day 3/4 because it reads ON_HOLD today.
    """
    assert hold_with_history.pending_then_approved not in _active_ids(db_session, date(2026, 3, 3))
    assert hold_with_history.pending_then_approved not in _active_ids(db_session, date(2026, 3, 4))
    assert hold_with_history.pending_then_approved in _active_ids(db_session, date(2026, 3, 5))
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


def test_no_transition_before_cutoff_falls_back_to_current_status(db_session, hold_with_only_future_history):
    """The BOUNDARY case the docstring documents: both holds HAVE recorded
    transitions, but none of them predate the as-of cutoff, so tier 1's
    correlated subquery returns NULL. This is different from
    `hold_without_history_falls_back_to_current_status`, which has no
    transition rows at all; here rows exist but are filtered out by date,
    exercising the actual NULL-subquery path rather than an
    absent-correlation path.

    Two assertions, not one: `cancelled_id` alone would pass even if the
    fallback were removed entirely (NULL NOT IN (...) is also excluded), so
    `on_hold_id` -- present only because the fallback reached its ACTIVE
    current status -- is what proves the fallback actually ran.

    Cycle 4 PR-C1b: this is now also the genuine tier-2-NULL -> tier-3
    fall-through proof, not just a tier-1-NULL one. Both holds' ONLY
    transition is their creation row (`None -> <status>`), recorded at
    2026-03-08 -- more than a MONTH after `hold_date` (2026-02-01) -- so at
    `as_of=2026-02-15` (cutoff 2026-02-16) that creation row satisfies tier
    2's `transitioned_at >= cutoff` and is the earliest (only) candidate;
    its `from_status` is NULL by construction, so tier 2 also yields NULL
    and tier 3 -- current `hold_status` -- is what actually decides both
    assertions here.

    A hold whose creation row is stamped AT `hold_date` (the case PR-C1
    guarantees for holds created going forward) can NEVER reach tier 3,
    which is why a dedicated "creation-row" fixture for that shape would be
    unable to test anything past tier 1: for any `as_of >= hold_date`,
    `cutoff > hold_date`, so that very row already satisfies tier 1's
    `transitioned_at < cutoff` and resolves the status via its `to_status`
    before tier 2 is ever evaluated; for `as_of < hold_date` the date arm
    (`hold_date < cutoff`) excludes the hold regardless of status. Tier 2
    and tier 3 are reachable only when the FIRST transition lands strictly
    after `hold_date`, as it does here.
    """
    assert hold_with_only_future_history.cancelled_id not in _active_ids(db_session, date(2026, 2, 15))
    assert hold_with_only_future_history.on_hold_id in _active_ids(db_session, date(2026, 2, 15))


def test_same_second_transitions_resolve_by_insertion_order(db_session, same_second_hold):
    """MariaDB DATETIME has whole-second resolution, so two transitions can
    share a timestamp. The later-inserted row must win."""
    assert same_second_hold.hold_entry_id not in _active_ids(db_session, date(2026, 3, 5))


def test_history_boundary_reports_first_recorded_transition(db_session, hold_with_history):
    assert hold_status_history_started_at(db_session) == datetime(2026, 3, 1, 8, 0, 0)


# =============================================================================
# Task 5: as-of-now invariance, trend-endpoint regression, query-plan guard
# =============================================================================

# Golden master captured at c138616 (branch tip immediately before Task 4's
# rewrite -- see .superpowers/sdd/2026-08-13-hold-status-history/golden-master.md),
# against the UNMODIFIED `active_as_of` (current-status logic, no transition
# table involved). `as_of` is pinned to the date it was captured at rather
# than re-derived from `date.today()`, so this assertion doesn't depend on
# which day the suite happens to run (golden-master.md's own recommendation).
GOLDEN_MASTER_AS_OF = date(2026, 8, 14)
GOLDEN_ACTIVE_IDS_TODAY = {"GM-ONHOLD", "GM-PENDRES"}


@pytest.fixture
def seeded_holds(db_session):
    """7 holds, one per `HoldStatus` value, reproducing the fixture used to
    capture the golden master (golden-master.md) at c138616. 3 carry no
    transition history at all (current status is the only signal the OLD
    predicate ever had); the other 4 each carry a transition chain --
    `None -> ON_HOLD` at `hold_date`, then `ON_HOLD -> <target>` on
    2026-01-05 -- that ENDS at the hold's current `hold_status`, so the
    rewritten predicate's history read must agree with the old current-status
    read for `as_of = GOLDEN_MASTER_AS_OF` on every one of these holds. That
    agreement is precisely the "today's dashboards are unmoved" property
    Task 5 exists to prove.
    """
    client = TestDataFactory.create_client(db_session, client_id="GM-CLIENT")
    hold_date = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)

    def _wo(suffix):
        return TestDataFactory.create_work_order(
            db_session, client_id=client.client_id, work_order_id=f"GM-WO-{suffix}"
        )

    holds = []

    # No-history holds (3): current status is the only signal available.
    for suffix, status in (
        ("PENDING", HoldStatus.PENDING_HOLD_APPROVAL),
        ("ONHOLD", HoldStatus.ON_HOLD),
        ("PENDRES", HoldStatus.PENDING_RESUME_APPROVAL),
    ):
        wo = _wo(suffix)
        hold = HoldEntry(
            hold_entry_id=f"GM-{suffix}",
            client_id=client.client_id,
            work_order_id=wo.work_order_id,
            hold_status=status,
            hold_date=hold_date,
            resume_date=None,
            hold_reason="golden master fixture",
        )
        db_session.add(hold)
        holds.append(hold)

    db_session.flush()

    # History-bearing holds (4): each carries a transition chain that ENDS at
    # its current status.
    def _hold_with_history(suffix, current_status, resume_date=None):
        wo = _wo(suffix)
        hold = HoldEntry(
            hold_entry_id=f"GM-{suffix}",
            client_id=client.client_id,
            work_order_id=wo.work_order_id,
            hold_status=current_status,
            hold_date=hold_date,
            resume_date=resume_date,
            hold_reason="golden master fixture",
        )
        db_session.add(hold)
        db_session.flush()
        record_hold_transition(
            db_session, hold, to_status=HoldStatus.ON_HOLD, from_status=None, transitioned_at=hold_date
        )
        if current_status != HoldStatus.ON_HOLD:
            record_hold_transition(
                db_session,
                hold,
                to_status=current_status,
                from_status=HoldStatus.ON_HOLD,
                transitioned_at=datetime(2026, 1, 5, 9, 0, 0, tzinfo=timezone.utc),
            )
        db_session.flush()
        return hold

    resumed = _hold_with_history(
        "RESUMED", HoldStatus.RESUMED, resume_date=datetime(2026, 1, 5, 9, 0, 0, tzinfo=timezone.utc)
    )
    cancelled = _hold_with_history("CANCELLED", HoldStatus.CANCELLED)
    released = _hold_with_history("RELEASED", HoldStatus.RELEASED)
    scrapped = _hold_with_history("SCRAPPED", HoldStatus.SCRAPPED)

    holds.extend([resumed, cancelled, released, scrapped])
    db_session.commit()
    return holds


def test_as_of_today_is_unchanged_by_the_history_rewrite(db_session, seeded_holds):
    """The fix targets historical as-of dates. Today's dashboards must not move.

    Golden values captured against active_as_of at c138616, before the status
    arm was rewritten (golden-master.md).
    """
    active = _active_ids(db_session, GOLDEN_MASTER_AS_OF)

    assert active == GOLDEN_ACTIVE_IDS_TODAY


# --- Trend-endpoint regression -----------------------------------------


@pytest.fixture
def endpoint_db(transactional_db):
    """Bind get_db to the isolated in-memory session for TestClient requests.

    D3/#130 pattern (see backend/tests/test_kpi/test_trend_endpoints_ppm_throughput.py):
    `transactional_db` is bound to `get_db` so writes land in the
    function-scoped in-memory SQLite the TestClient reads from. A separate
    fixture name from `db_session` (rather than overriding it) so the
    conftest `db_session` used by every other test in this file keeps its
    own semantics.
    """
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def endpoint_client(endpoint_db):
    """TestClient authenticated as an admin, bound to endpoint_db."""
    admin = TestDataFactory.create_user(endpoint_db, username="trend_admin", role="admin")
    endpoint_db.commit()
    app.dependency_overrides[get_current_user] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_trend_reflects_history_not_current_status(endpoint_client, endpoint_db):
    """GET /api/kpi/wip-aging/trend is the one caller that walks past dates.

    Real response shape (backend/routes/holds.py:514 get_wip_aging_trend):
    a bare list of `{"date": iso, "value": avg_age_in_days}` points -- NOT
    the `{"trend": [...], "active_holds": ...}` shape the brief guessed.

    H-TREND-HIST was only PENDING_HOLD_APPROVAL (excluded --
    NON_WIP_HOLD_STATUSES, nothing has stopped yet) through 2026-03-04, and
    was approved into ON_HOLD at 2026-03-05 10:00. Before this change the
    trend read today's ON_HOLD status for every point on the line, so it
    counted the hold as active on 2026-03-03 too and reported a nonzero
    average age; the rewrite correctly reports no active WIP that day (the
    average of an empty set is 0), then a genuine 5-day average once the
    hold is actually on hold.
    """
    client = TestDataFactory.create_client(endpoint_db, client_id="TREND-HIST")
    work_order = TestDataFactory.create_work_order(
        endpoint_db, client_id=client.client_id, work_order_id="WO-TREND-HIST"
    )
    hold = HoldEntry(
        hold_entry_id="H-TREND-HIST",
        client_id=client.client_id,
        work_order_id=work_order.work_order_id,
        hold_status=HoldStatus.ON_HOLD,
        hold_date=datetime(2026, 3, 1, 8, 0, 0),
        resume_date=None,
        hold_reason="trend regression fixture",
    )
    endpoint_db.add(hold)
    endpoint_db.flush()
    record_hold_transition(
        endpoint_db,
        hold,
        to_status=HoldStatus.PENDING_HOLD_APPROVAL,
        from_status=None,
        transitioned_at=datetime(2026, 3, 1, 8, 0, 0),
    )
    record_hold_transition(
        endpoint_db,
        hold,
        to_status=HoldStatus.ON_HOLD,
        from_status=HoldStatus.PENDING_HOLD_APPROVAL,
        transitioned_at=datetime(2026, 3, 5, 10, 0, 0),
    )
    endpoint_db.commit()

    response = endpoint_client.get(
        "/api/kpi/wip-aging/trend",
        params={"start_date": "2026-03-02", "end_date": "2026-03-07", "client_id": "TREND-HIST"},
    )

    assert response.status_code == 200

    points = {p["date"]: p["value"] for p in response.json()}

    assert points["2026-03-03"] == 0
    assert points["2026-03-06"] == 5.0


# --- Query-plan guard -----------------------------------------------------


def test_top_n_query_still_uses_an_index(db_session, seeded_holds):
    """active_as_of's docstring promises callers keep index-assisted
    ORDER BY ... LIMIT. A correlated subquery must not cost them that.

    The plan is taken from a query built WITH the predicate -- explaining a
    hand-written SQL string instead would pass no matter what active_as_of
    does, which is no test at all.
    """
    query = (
        db_session.query(HoldEntry.hold_entry_id)
        .filter(active_as_of(date(2026, 3, 10)))
        .order_by(HoldEntry.hold_date)
        .limit(5)
    )
    compiled = query.statement.compile(db_session.bind, compile_kwargs={"literal_binds": True})
    plan = db_session.execute(text(f"EXPLAIN QUERY PLAN {compiled}")).fetchall()

    assert not any("SCAN HOLD_ENTRY" in str(row) for row in plan)


# =============================================================================
# Cycle 4 PR-C1b Task 1: three-tier resolution (earliest from_status fallback)
# =============================================================================


@pytest.fixture
def hold_with_only_later_history(db_session, sample_client):
    """Two holds, each with history that begins AFTER the as-of date.

    Their earliest transition's `from_status` proves what they were before it,
    and it disagrees with their current status in both directions -- so tier 2
    and tier 3 cannot produce the same answer.
    """
    # Was ON_HOLD through March; cancelled in August.
    a = _make_hold(db_session, sample_client, "H-LATER-CANCELLED", datetime(2026, 2, 1, 8, 0, 0), "CANCELLED")
    # Was CANCELLED through March; re-opened in August.
    b = _make_hold(db_session, sample_client, "H-LATER-REOPENED", datetime(2026, 2, 1, 9, 0, 0), "ON_HOLD")
    db_session.flush()

    _t(db_session, a.hold_entry_id, a.client_id, "ON_HOLD", "CANCELLED", datetime(2026, 8, 8, 10, 0, 0))
    _t(db_session, b.hold_entry_id, b.client_id, "CANCELLED", "ON_HOLD", datetime(2026, 8, 8, 11, 0, 0))
    db_session.flush()

    return SimpleNamespace(later_cancelled=a.hold_entry_id, later_reopened=b.hold_entry_id)


def test_earliest_from_status_wins_over_current_status(db_session, hold_with_only_later_history):
    """Tier 2: no transition before the cutoff, but the earliest one records
    what the hold WAS. Current status is the wrong answer in both directions."""
    active = _active_ids(db_session, date(2026, 3, 3))

    # Was ON_HOLD in March even though it reads CANCELLED today.
    assert hold_with_only_later_history.later_cancelled in active
    # Was CANCELLED in March even though it reads ON_HOLD today.
    assert hold_with_only_later_history.later_reopened not in active


def test_after_that_transition_tier_one_takes_over(db_session, hold_with_only_later_history):
    """Past the August transition, tier 1 governs again and the answers flip."""
    active = _active_ids(db_session, date(2026, 8, 9))

    assert hold_with_only_later_history.later_cancelled not in active
    assert hold_with_only_later_history.later_reopened in active


def test_earliest_of_two_later_transitions_beats_the_later_one(db_session, sample_client):
    """Finding 1(a): every other tier-2 fixture in this file has exactly ONE
    transition at or after the cutoff, so "earliest" is indistinguishable
    from "latest" or "any" of them -- flipping tier 2's `.asc()` to `.desc()`
    would leave those green. This hold has TWO, with opposing meanings:
    ON_HOLD->CANCELLED on 8/8, then CANCELLED->ON_HOLD on 8/10. The earliest
    (correct, ASC) one's `from_status` is ON_HOLD -- active. The latest
    (wrong, DESC) one's `from_status` is CANCELLED -- absent. Distinct
    outcomes, so this discriminates the ordering direction.
    """
    hold = _make_hold(db_session, sample_client, "H-TWO-LATER", datetime(2026, 2, 1, 8, 0, 0), "ON_HOLD")
    db_session.flush()
    _t(db_session, hold.hold_entry_id, hold.client_id, "ON_HOLD", "CANCELLED", datetime(2026, 8, 8, 10, 0, 0))
    _t(db_session, hold.hold_entry_id, hold.client_id, "CANCELLED", "ON_HOLD", datetime(2026, 8, 10, 10, 0, 0))
    db_session.flush()

    assert hold.hold_entry_id in _active_ids(db_session, date(2026, 3, 3))


def test_earliest_of_same_second_later_transitions_breaks_tie_by_insertion_order(db_session, sample_client):
    """Finding 1(b): mirrors `same_second_hold` (which pins tier 1's
    transition_id DESC tie-break) but for tier 2's transition_id ASC
    tie-break. Two transitions share ONE instant, both at or after the
    cutoff, with opposing `from_status`: the first-inserted (lower
    transition_id) has from_status=ON_HOLD, the second-inserted (higher
    transition_id) has from_status=CANCELLED. Correct tie-break
    (transitioned_at ASC, transition_id ASC) picks the first-inserted row --
    active. Deleting the transition_id tie-break clause risks the wrong row
    (or a dialect-dependent one) winning instead.
    """
    hold = _make_hold(db_session, sample_client, "H-TIE-LATER", datetime(2026, 2, 1, 8, 0, 0), "CANCELLED")
    db_session.flush()
    same = datetime(2026, 8, 10, 10, 0, 0)
    _t(db_session, hold.hold_entry_id, hold.client_id, "ON_HOLD", "CANCELLED", same)
    _t(db_session, hold.hold_entry_id, hold.client_id, "CANCELLED", "ON_HOLD", same)
    db_session.flush()

    assert hold.hold_entry_id in _active_ids(db_session, date(2026, 3, 3))


def test_tier_two_matches_a_transition_exactly_at_the_cutoff_instant(db_session, sample_client):
    """Finding 3: tier 2's bound is `transitioned_at >= cutoff` (inclusive).
    No other fixture has a transition at exactly the cutoff instant, so a
    silent `> cutoff` regression (missed by both tiers, falling through to
    tier 3) would leave every other test green. `as_of=2026-03-03` has
    cutoff `2026-03-04 00:00:00` -- exactly this hold's sole transition.
    `from_status` there is ON_HOLD (tier 2, correct); current `hold_status`
    is CANCELLED (tier 3, wrong), so the two tiers disagree and the
    assertion pins which one actually decided.
    """
    hold = _make_hold(db_session, sample_client, "H-AT-CUTOFF", datetime(2026, 2, 1, 8, 0, 0), "CANCELLED")
    db_session.flush()
    _t(db_session, hold.hold_entry_id, hold.client_id, "ON_HOLD", "CANCELLED", datetime(2026, 3, 4, 0, 0, 0))
    db_session.flush()

    assert hold.hold_entry_id in _active_ids(db_session, date(2026, 3, 3))
