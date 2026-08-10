"""The WIP-aging endpoints must return 200 (they build date-diff SQL via the
portable date_diff_days expression). On SQLite this also proves no behavior
regression; the MariaDB execution proof lives in test_mariadb_portability.py.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.factories import TestDataFactory
from backend.main import app
from backend.orm.hold_entry import HoldEntry, HoldStatus


def test_wip_aging_top_returns_200(test_client, admin_auth_headers):
    resp = test_client.get("/api/kpi/wip-aging/top", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_wip_aging_trend_returns_200(test_client, admin_auth_headers):
    resp = test_client.get(
        "/api/kpi/wip-aging/trend?start_date=2026-06-01&end_date=2026-06-03",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# As-of snapshot semantics (owner ruling 2026-08-07)
#
# Windowed WIP-aging means an as-of snapshot, not "holds opened in the
# window". Live-VM evidence: a trailing-30-day window returned all-zeros
# while 4 chronic holds sat at 60-70 days -- windowing an AGING metric
# excluded precisely the worst holds. GET /api/kpi/wip-aging and
# GET /api/kpi/wip-aging/top now scope on `hold_date <= end_of_day(as_of)`
# AND (`resume_date IS NULL` OR `resume_date > end_of_day(as_of)`), where
# `as_of = end_date` (default today); `start_date` no longer scopes the
# query. All three WIP-aging endpoints (including /wip-aging/trend) share
# that boundary via routes/holds.py `_snapshot_cutoff` -- see its docstring
# for why both sides are end-of-day.
# ---------------------------------------------------------------------------


@pytest.fixture
def _bind(transactional_db):
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


def _as(user):
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _make_hold(
    db, *, client_id, work_order_id, hold_entry_id, hold_date, hold_status=HoldStatus.ON_HOLD, resume_date=None
):
    hold = HoldEntry(
        hold_entry_id=hold_entry_id,
        client_id=client_id,
        work_order_id=work_order_id,
        hold_date=hold_date,
        resume_date=resume_date,
        hold_status=hold_status,
        hold_reason_category="QUALITY",
    )
    db.add(hold)
    db.flush()
    return hold


def test_chronic_hold_counted_under_trailing_30_day_window(_bind, admin_user):
    """A hold opened 60 days ago, still ON_HOLD, must be counted -- and land
    in the >30-day bucket -- even under a trailing-30-day window. This is
    the exact live-VM bug: opened-in-window filtering excluded chronic
    holds because they were opened long before the window started."""
    db = _bind
    client = TestDataFactory.create_client(db)
    wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
    hold_open_date = datetime.now(tz=timezone.utc) - timedelta(days=60)
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo.work_order_id,
        hold_entry_id="HOLD-CHRONIC-1",
        hold_date=hold_open_date,
    )

    today = date.today()
    window_start = today - timedelta(days=30)

    c = _as(admin_user)
    try:
        resp = c.get(
            "/api/kpi/wip-aging",
            params={
                "client_id": client.client_id,
                "start_date": window_start.isoformat(),
                "end_date": today.isoformat(),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_held_quantity"] == 1
        assert body["aging_over_30_days"] == 1
        assert body["average_aging_days"] == pytest.approx(60, abs=1)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_historical_snapshot_excludes_hold_resumed_before_window_end(_bind, admin_user):
    """Window ending in the past: a hold opened before `end_date` and
    resumed AFTER it is still counted (age as-of `end_date`); a hold
    resumed BEFORE `end_date` is excluded."""
    db = _bind
    client = TestDataFactory.create_client(db)
    wo_a = TestDataFactory.create_work_order(db, client_id=client.client_id, work_order_id="WO-SNAP-A")
    wo_b = TestDataFactory.create_work_order(db, client_id=client.client_id, work_order_id="WO-SNAP-B")

    end_date = date(2026, 6, 15)
    hold_open = datetime(2026, 5, 1, tzinfo=timezone.utc)

    # Resumed AFTER end_date -- still active as-of the snapshot -> in scope.
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo_a.work_order_id,
        hold_entry_id="HOLD-SNAP-A",
        hold_date=hold_open,
        hold_status=HoldStatus.RESUMED,
        resume_date=datetime(2026, 6, 20, tzinfo=timezone.utc),
    )
    # Resumed BEFORE end_date -- no longer active as-of the snapshot -> excluded.
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo_b.work_order_id,
        hold_entry_id="HOLD-SNAP-B",
        hold_date=hold_open,
        hold_status=HoldStatus.RESUMED,
        resume_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    c = _as(admin_user)
    try:
        resp = c.get(
            "/api/kpi/wip-aging",
            params={"client_id": client.client_id, "end_date": end_date.isoformat()},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_held_quantity"] == 1
        expected_age = (end_date - hold_open.date()).days
        assert body["average_aging_days"] == pytest.approx(expected_age, abs=0.1)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_past_window_ages_are_reproducible_not_today_leaking(_bind, admin_user):
    """Repeated calls for the same past `end_date` must return identical
    ages -- no date.today() leakage into a historical snapshot."""
    db = _bind
    client = TestDataFactory.create_client(db)
    wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
    end_date = date(2026, 3, 1)
    hold_open = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo.work_order_id,
        hold_entry_id="HOLD-REPRO-1",
        hold_date=hold_open,
    )

    c = _as(admin_user)
    try:
        params = {"client_id": client.client_id, "end_date": end_date.isoformat()}
        first = c.get("/api/kpi/wip-aging", params=params).json()
        second = c.get("/api/kpi/wip-aging", params=params).json()
        # calculation_timestamp is a real wall-clock stamp (intentionally
        # differs per call); everything else is the reproducible snapshot.
        first.pop("calculation_timestamp")
        second.pop("calculation_timestamp")
        assert first == second
        expected_age = (end_date - hold_open.date()).days
        assert first["average_aging_days"] == pytest.approx(expected_age, abs=0.1)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_hold_resumed_during_snapshot_day_is_not_active(_bind, admin_user):
    """The snapshot boundary is END of day: a hold resumed at any hour of
    `end_date` has already resumed at the snapshot instant, so it is not
    active WIP. Guards the asymmetry described in `_snapshot_cutoff` --
    binding a bare date put this boundary at midnight, which counted a
    resumed hold as still on hold for the whole of its resume day."""
    db = _bind
    client = TestDataFactory.create_client(db)
    wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
    end_date = date(2026, 6, 15)
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo.work_order_id,
        hold_entry_id="HOLD-SAMEDAY-RESUME",
        hold_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        hold_status=HoldStatus.RESUMED,
        resume_date=datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc),
    )

    c = _as(admin_user)
    try:
        resp = c.get(
            "/api/kpi/wip-aging",
            params={"client_id": client.client_id, "end_date": end_date.isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json()["total_held_quantity"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_top_excludes_hold_resumed_during_snapshot_day(_bind, admin_user):
    """/wip-aging/top applies the same end-of-day resume boundary."""
    db = _bind
    client = TestDataFactory.create_client(db)
    wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
    end_date = date(2026, 6, 15)
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo.work_order_id,
        hold_entry_id="HOLD-SAMEDAY-TOP",
        hold_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        hold_status=HoldStatus.RESUMED,
        resume_date=datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc),
    )

    c = _as(admin_user)
    try:
        resp = c.get(
            "/api/kpi/wip-aging/top",
            params={"client_id": client.client_id, "end_date": end_date.isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_hold_opened_during_snapshot_day_is_active_at_age_zero(_bind, admin_user):
    """Mirror of the resume boundary: `hold_date` is also compared against
    END of day, so a hold opened at any hour of `end_date` is active with
    age 0 rather than being missed until the following day."""
    db = _bind
    client = TestDataFactory.create_client(db)
    wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
    end_date = date(2026, 6, 15)
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo.work_order_id,
        hold_entry_id="HOLD-SAMEDAY-OPEN",
        hold_date=datetime(2026, 6, 15, 9, 30, tzinfo=timezone.utc),
    )

    c = _as(admin_user)
    try:
        resp = c.get(
            "/api/kpi/wip-aging",
            params={"client_id": client.client_id, "end_date": end_date.isoformat()},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_held_quantity"] == 1
        assert body["average_aging_days"] == pytest.approx(0, abs=0.1)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.parametrize("terminal_status", [HoldStatus.CANCELLED, HoldStatus.RELEASED, HoldStatus.SCRAPPED])
def test_terminal_status_hold_is_not_active_wip(_bind, admin_user, terminal_status):
    """A hold in a terminal status left WIP without ever stamping
    `resume_date`, so a resume_date-only predicate would age it forever.
    CANCELLED/RELEASED/SCRAPPED must not count as active WIP."""
    db = _bind
    client = TestDataFactory.create_client(db)
    wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo.work_order_id,
        hold_entry_id=f"HOLD-TERMINAL-{terminal_status}",
        hold_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        hold_status=terminal_status,
        resume_date=None,
    )

    c = _as(admin_user)
    try:
        resp = c.get(
            "/api/kpi/wip-aging",
            params={"client_id": client.client_id, "end_date": date(2026, 6, 15).isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json()["total_held_quantity"] == 0
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_pending_resume_approval_still_counts_as_active_wip(_bind, admin_user):
    """The counterpart to the terminal-status exclusion: work awaiting
    resume approval has NOT resumed, so it is still WIP on hold."""
    db = _bind
    client = TestDataFactory.create_client(db)
    wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo.work_order_id,
        hold_entry_id="HOLD-PENDING-RESUME",
        hold_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        hold_status=HoldStatus.PENDING_RESUME_APPROVAL,
        resume_date=None,
    )

    c = _as(admin_user)
    try:
        resp = c.get(
            "/api/kpi/wip-aging",
            params={"client_id": client.client_id, "end_date": date(2026, 6, 15).isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json()["total_held_quantity"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_boundary_uses_no_fractional_seconds(_bind, admin_user):
    """The cutoff is an exclusive next-midnight, not an inclusive
    23:59:59.999999 -- MariaDB DATETIME columns carry no fractional seconds,
    so a microsecond-bearing bound risks dialect-dependent rounding at
    exactly this boundary. Pins both edges: a hold opened at the last second
    of `as_of` is active, one opened at the first second of the next day is
    not."""
    db = _bind
    client = TestDataFactory.create_client(db)
    as_of = date(2026, 6, 15)
    wo_in = TestDataFactory.create_work_order(db, client_id=client.client_id, work_order_id="WO-EDGE-IN")
    wo_out = TestDataFactory.create_work_order(db, client_id=client.client_id, work_order_id="WO-EDGE-OUT")
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo_in.work_order_id,
        hold_entry_id="HOLD-EDGE-IN",
        hold_date=datetime(2026, 6, 15, 23, 59, 59, tzinfo=timezone.utc),
    )
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo_out.work_order_id,
        hold_entry_id="HOLD-EDGE-OUT",
        hold_date=datetime(2026, 6, 16, 0, 0, 0, tzinfo=timezone.utc),
    )

    c = _as(admin_user)
    try:
        resp = c.get(
            "/api/kpi/wip-aging",
            params={"client_id": client.client_id, "end_date": as_of.isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json()["total_held_quantity"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_explicit_as_of_date_outranks_end_date(_bind, admin_user):
    """`as_of_date` names the snapshot instant explicitly; `end_date` only
    implies one (it arrives from the shared dashboard date range). When a
    caller supplies both, the explicit parameter must win -- otherwise
    passing `as_of_date` silently does nothing."""
    db = _bind
    client = TestDataFactory.create_client(db)
    wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo.work_order_id,
        hold_entry_id="HOLD-PRECEDENCE",
        hold_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )

    c = _as(admin_user)
    try:
        resp = c.get(
            "/api/kpi/wip-aging",
            params={
                "client_id": client.client_id,
                "as_of_date": date(2026, 5, 11).isoformat(),
                "end_date": date(2026, 6, 15).isoformat(),
            },
        )
        assert resp.status_code == 200
        # Age from as_of_date (10 days), not from end_date (45 days).
        assert resp.json()["average_aging_days"] == pytest.approx(10, abs=0.1)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_top_returns_oldest_holds_when_limit_truncates(_bind, admin_user):
    """The top-N is applied in SQL (ORDER BY hold_date ASC LIMIT n) rather
    than by sorting every candidate in Python. Ordering by hold_date is
    equivalent to ordering by age descending because `as_of` is fixed for
    the query -- this pins that equivalence, so a truncated result is still
    the OLDEST holds, not an arbitrary n."""
    db = _bind
    client = TestDataFactory.create_client(db)
    as_of = date(2026, 6, 15)
    # Ages 40, 30, 20, 10 days as of `as_of`.
    for age_days in (40, 30, 20, 10):
        wo = TestDataFactory.create_work_order(db, client_id=client.client_id, work_order_id=f"WO-LIMIT-{age_days}")
        _make_hold(
            db,
            client_id=client.client_id,
            work_order_id=wo.work_order_id,
            hold_entry_id=f"HOLD-LIMIT-{age_days}",
            hold_date=datetime.combine(as_of - timedelta(days=age_days), datetime.min.time(), tzinfo=timezone.utc),
        )

    c = _as(admin_user)
    try:
        resp = c.get(
            "/api/kpi/wip-aging/top",
            params={"client_id": client.client_id, "end_date": as_of.isoformat(), "limit": 2},
        )
        assert resp.status_code == 200
        assert [item["age"] for item in resp.json()] == [40, 30]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_trend_point_equals_snapshot_for_the_same_date(_bind, admin_user):
    """STRUCTURAL GUARD: /wip-aging/trend must share the snapshot boundary,
    so the trend point for date D equals the average GET /wip-aging reports
    with `end_date=D`. These drifted before `_snapshot_cutoff` centralized
    the predicate (trend put the resume boundary at midnight). The fixture
    deliberately spans all three cases the boundary decides: still open,
    resumed during D, resumed after D."""
    db = _bind
    client = TestDataFactory.create_client(db)
    snapshot_day = date(2026, 6, 15)
    fixtures = [
        # (suffix, hold_date, resume_date) -- open, resumed-during-D, resumed-after-D
        ("OPEN", datetime(2026, 5, 1, tzinfo=timezone.utc), None),
        ("MID", datetime(2026, 5, 10, tzinfo=timezone.utc), datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)),
        ("LATE", datetime(2026, 5, 20, tzinfo=timezone.utc), datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc)),
    ]
    for suffix, hold_date, resume_date in fixtures:
        wo = TestDataFactory.create_work_order(db, client_id=client.client_id, work_order_id=f"WO-TREND-{suffix}")
        _make_hold(
            db,
            client_id=client.client_id,
            work_order_id=wo.work_order_id,
            hold_entry_id=f"HOLD-TREND-{suffix}",
            hold_date=hold_date,
            hold_status=HoldStatus.ON_HOLD if resume_date is None else HoldStatus.RESUMED,
            resume_date=resume_date,
        )

    c = _as(admin_user)
    try:
        snapshot = c.get(
            "/api/kpi/wip-aging",
            params={"client_id": client.client_id, "end_date": snapshot_day.isoformat()},
        )
        trend = c.get(
            "/api/kpi/wip-aging/trend",
            params={
                "client_id": client.client_id,
                "start_date": snapshot_day.isoformat(),
                "end_date": snapshot_day.isoformat(),
            },
        )
        assert snapshot.status_code == 200
        assert trend.status_code == 200
        trend_points = trend.json()
        assert len(trend_points) == 1
        assert trend_points[0]["value"] == pytest.approx(snapshot.json()["average_aging_days"], abs=0.1)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_top_endpoint_scoping_consistent_with_wip_aging(_bind, admin_user):
    """GET /wip-aging/top must apply the same as-of scoping as GET
    /wip-aging -- a chronic hold outside a trailing-30-day window is
    counted in both, with matching age."""
    db = _bind
    client = TestDataFactory.create_client(db)
    wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
    hold_open_date = datetime.now(tz=timezone.utc) - timedelta(days=60)
    _make_hold(
        db,
        client_id=client.client_id,
        work_order_id=wo.work_order_id,
        hold_entry_id="HOLD-TOP-CONSISTENCY-1",
        hold_date=hold_open_date,
    )

    today = date.today()
    window_start = today - timedelta(days=30)
    params = {
        "client_id": client.client_id,
        "start_date": window_start.isoformat(),
        "end_date": today.isoformat(),
    }

    c = _as(admin_user)
    try:
        aging_resp = c.get("/api/kpi/wip-aging", params=params)
        top_resp = c.get("/api/kpi/wip-aging/top", params=params)
        assert aging_resp.status_code == 200
        assert top_resp.status_code == 200
        aging_body = aging_resp.json()
        top_body = top_resp.json()
        assert aging_body["total_held_quantity"] == len(top_body) == 1
        assert top_body[0]["age"] == pytest.approx(60, abs=1)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
