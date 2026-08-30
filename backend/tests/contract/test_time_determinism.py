"""The golden-master capture must be clock invariant.

Two hazards of the same shape, one dimension apart: a route that branches on
the time of DAY, and a route that defaults a date RANGE off the current DAY.
Both make the recorded shape a function of when the suite ran rather than of
what was seeded, and both are proved here the same way -- capture the route at
two clock readings that straddle the boundary, assert the two DIFFER without
the pin and are IDENTICAL with it.

--- 1. Time of day: `GET /api/shifts/active`.

`GET /api/shifts/active` (backend/routes/reference.py::get_active_shift) branches
on `datetime.now(tz=timezone.utc).time()`: whether a seeded shift is active, and
therefore whether the route returns a shift dict or a 404, depends on the real
wall-clock hour the suite happens to run at. Reproduced live: at 18:17 UTC the
unpinned capture returns a shift dict; the committed golden entry is
`["<status:404>"]`, captured during a window with no shift active. That is a
genuinely flaky gate, not a hypothetical one -- the golden-master capture fails
roughly half of every day without `capture.ShiftActivePin`.

This module proves the fix is real determinism, not a lucky golden-file
regeneration: it captures the same route at two real "wall-clock" moments that
straddle the shift boundary (one inside a seeded shift, one in the dead zone
between shifts) and asserts the two DIFFER without the pin (the flake, made
concrete) and are IDENTICAL with it (the fix).

Swept for other routes reading the clock the same way (`grep -rn
"datetime.now" routes/ | grep "\\.time()"`): only one other hit,
`routes/production.py:80` inside `create_entry` (POST /api/production).
It is NOT in the golden master's 164-route surface at all (that route
already has a real `response_model=ProductionEntryResponse`, so `is_loose`
never selects it, and `golden/api_shapes.json` has no entry for
`POST /api/production`) -- the capture harness would need a real body to
even reach that branch, which `capture_all` deliberately never fabricates.
Out of scope for this fix; noted rather than silently skipped.

--- 2. Day of year: `GET /api/jobs/kpi/rty-summary`.

It defaults its window to `date.today() - 30 days .. date.today()`
(routes/jobs.py) and `calculate_job_rty_summary` returns a different KEY SET
depending on whether any completed job lands inside it -- `response_model_
exclude_unset=True` makes total_good_units, jobs_meeting_target and
interpretation absent, not null, when none does. The harness seeds a universe
ending at `conftest.SEED_AS_OF`, so the populated branch is recorded only
while the real clock is still within 30 days of that date. Capturing it
unpinned pins a shape with an expiry date: nothing in the repo changes and
`test_no_route_lost_a_field` starts failing around SEED_AS_OF + 30 days.
`capture.SeededToday` pins `today()` to SEED_AS_OF itself.

MEASURED, and disclosed rather than implied: this route is NOT the only one.
Patching `date.today()` forward across every `backend.routes.*` module and
re-capturing the whole plan moves 24 of the golden master's entries -- the
eight `/api/kpi/*/trend` routes among them, which go from `["[].date",
"[].value"]` to `[]`. They carry the identical expiry and are NOT pinned
here: this module's `SeededToday` is wired to `backend.routes.jobs` alone,
which is the one route the S3 work regenerated. Pinning the other 23 is a
change to 23 golden entries' provenance and belongs in its own pass -- but
nobody should read the green run below as evidence they are safe.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Iterator, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.migrate import upgrade_to_head
from backend.main import app
from backend.seed.cli import ALLOWLIST as ALLOWLIST_CLIENTS
from backend.seed.cli import seed
from backend.tests.contract.capture import SeededToday, ShiftActivePin, capture_all
from backend.tests.contract.conftest import SEED_AS_OF
from backend.tests.test_routes.test_smoke_paramless_get import _mock_admin

#: smoke seeds 2 shifts/client, 8 hours each, at hour 6 and hour 18 UTC for
#: every client (see ShiftActivePin's docstring for the derivation) -- so
#: 10:00 UTC sits inside the 06:00-14:00 shift (a real shift is active for
#: every client), and 16:00 UTC sits in the 14:00-18:00 dead zone (no shift
#: is active for any client). These two straddle exactly the boundary the
#: real-world flake was reproduced against (18:08-18:17 UTC, inside the
#: OTHER shift window, 18:00-02:00) -- a different pair of hours, same
#: underlying bug, chosen so this test does not depend on which half of the
#: day it happens to run in.
_MOMENT_INSIDE_A_SHIFT = datetime(2026, 8, 25, 10, 0, tzinfo=timezone.utc)
_MOMENT_IN_THE_GAP = datetime(2026, 8, 25, 16, 0, tzinfo=timezone.utc)

_ROUTE = "GET /api/shifts/active"
_ROUTE_RTY = "GET /api/jobs/kpi/rty-summary"

#: Two readings of `date.today()` that straddle the SEED's own horizon the
#: way the two moments above straddle a shift boundary. SEED_AS_OF is the
#: last day the seeded universe has data for, so the route's trailing-30-day
#: window still covers the seeded completions there; 100 days later it has
#: moved entirely past them. 100, not 31, so the pair keeps straddling even
#: if the profile's activity window is widened.
_TODAY_AT_THE_SEED_HORIZON = SEED_AS_OF
_TODAY_LONG_AFTER_THE_SEED = SEED_AS_OF + timedelta(days=100)


@pytest.fixture(scope="module")
def _client() -> Iterator[TestClient]:
    """Same disposable-DB pattern as `conftest.py`'s `harness` fixture, scoped
    to just this module since only one route is exercised here. Deliberately
    NOT that fixture: this module needs to swap the clock per test, and
    `harness` is module-scoped with the pin already applied."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        url = f"sqlite:///{tmp}/time_determinism.db"
        upgrade_to_head(url)
        engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=NullPool)
        seed(
            engine,
            client_ids=tuple(sorted(ALLOWLIST_CLIENTS)),
            profile_name="smoke",
            seed_value=1234,
            as_of=SEED_AS_OF,
            reset=False,
        )
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        def _override_get_db():
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = _mock_admin
        try:
            yield TestClient(app, raise_server_exceptions=False)
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)
            engine.dispose()


def _capture_shift_active(client: TestClient) -> List[str]:
    shape: List[str] = capture_all(client, [("GET", "/api/shifts/active", {})])[_ROUTE]
    return shape


def test_unpinned_capture_genuinely_differs_across_the_two_moments(monkeypatch, _client: TestClient) -> None:
    """Baseline: proves the two chosen moments really do straddle the flake --
    i.e. this is what the golden-master capture looked like before
    ShiftActivePin existed, and what it reverts to if the pin is ever removed
    from `conftest.py`'s `harness` fixture.
    If this assertion ever starts passing (shapes equal), the two moments no
    longer straddle a real boundary and need re-picking -- it is not testing
    the fix, it is testing that the fix is *necessary*.
    """

    class _RawClock(datetime):
        _instant: datetime

        @classmethod
        def now(cls, tz=None):
            return cls._instant

    monkeypatch.setattr(
        "backend.routes.reference.datetime", type("_A", (_RawClock,), {"_instant": _MOMENT_INSIDE_A_SHIFT})
    )
    shape_inside = _capture_shift_active(_client)

    monkeypatch.setattr("backend.routes.reference.datetime", type("_B", (_RawClock,), {"_instant": _MOMENT_IN_THE_GAP}))
    shape_gap = _capture_shift_active(_client)

    assert shape_inside != shape_gap
    assert shape_inside == ["end_time", "is_active", "shift_id", "shift_name", "start_time"]
    assert shape_gap == ["<status:404>"]


def test_pinned_capture_is_identical_across_the_two_moments(monkeypatch, _client: TestClient) -> None:
    """The required assertion: same route, same two real moments as above,
    but through ShiftActivePin (the actual class wired into `conftest.py`'s
    `harness` fixture) -- output must be
    identical regardless of which of the two real moments `_real_now` reports.
    """
    monkeypatch.setattr("backend.routes.reference.datetime", ShiftActivePin)

    monkeypatch.setattr(ShiftActivePin, "_real_now", lambda tz=None: _MOMENT_INSIDE_A_SHIFT)
    shape_a = _capture_shift_active(_client)

    monkeypatch.setattr(ShiftActivePin, "_real_now", lambda tz=None: _MOMENT_IN_THE_GAP)
    shape_b = _capture_shift_active(_client)

    assert shape_a == shape_b == ["<status:404>"]


class _RawToday(date):
    """The UNPINNED behaviour, made testable: `date.today()` answering with a
    fixed real-world day, exactly as the real clock would on that day. The
    `date` half of `_RawClock` above, and used the same way -- subclassed per
    test with `_day` filled in."""

    _day: date

    @classmethod
    def today(cls) -> "_RawToday":
        # Rebuilt as `cls`, not returned as the plain `_day`, so the override's
        # return type is honest -- same reason `tests/_time.py::_FrozenDate`
        # does it. Value-equal either way.
        return cls(cls._day.year, cls._day.month, cls._day.day)


def _capture_rty_summary(client: TestClient) -> List[str]:
    shape: List[str] = capture_all(client, [("GET", "/api/jobs/kpi/rty-summary", {})])[_ROUTE_RTY]
    return shape


def test_unpinned_rty_summary_expires_once_its_window_clears_the_seed(monkeypatch, _client: TestClient) -> None:
    """Baseline, and the reason `SeededToday` exists: proves the two chosen
    days really do straddle a branch boundary, so the committed golden entry
    for this route has an expiry date without the pin.

    The three keys that disappear are not cosmetic -- they are the entire
    evidence the golden master holds that total_good_units, jobs_meeting_target
    and interpretation exist on this response at all.

    If this assertion ever starts passing (shapes equal), the two days no
    longer straddle a real boundary and need re-picking: it is not testing the
    fix, it is testing that the fix is *necessary*.
    """
    monkeypatch.setattr(
        "backend.routes.jobs.date", type("_AtHorizon", (_RawToday,), {"_day": _TODAY_AT_THE_SEED_HORIZON})
    )
    at_horizon = _capture_rty_summary(_client)

    monkeypatch.setattr(
        "backend.routes.jobs.date", type("_LongAfter", (_RawToday,), {"_day": _TODAY_LONG_AFTER_THE_SEED})
    )
    long_after = _capture_rty_summary(_client)

    assert at_horizon != long_after
    assert {"total_good_units", "jobs_meeting_target", "interpretation"} <= set(at_horizon)
    assert set(at_horizon) - set(long_after) == {
        "total_good_units",
        "jobs_meeting_target",
        "interpretation",
        "top_scrap_operations[].operation",
        "top_scrap_operations[].units_scrapped",
    }


def test_pinned_rty_summary_records_the_branch_the_seed_supports(monkeypatch, _client: TestClient) -> None:
    """The required assertion: same route, through `SeededToday` (the actual
    class wired into `conftest.py`'s `harness` fixture).

    There is no pair of moments to straddle here, because that is the fix --
    `SeededToday` reads no clock at all, so nothing about the calendar can
    reach the capture. What must be shown instead is that what it records is
    the branch the SEED supports: identical to the unpinned capture taken AT
    the seed horizon, which the test above shows the unpinned one drifting
    away from within 30 days.
    """
    monkeypatch.setattr(SeededToday, "AS_OF", SEED_AS_OF)
    monkeypatch.setattr("backend.routes.jobs.date", SeededToday)
    pinned = _capture_rty_summary(_client)

    monkeypatch.setattr(
        "backend.routes.jobs.date", type("_AtHorizon", (_RawToday,), {"_day": _TODAY_AT_THE_SEED_HORIZON})
    )

    assert SeededToday.today() == SEED_AS_OF
    assert pinned == _capture_rty_summary(_client)
    assert {"total_good_units", "jobs_meeting_target", "interpretation"} <= set(pinned)


def test_an_unset_pin_refuses_to_fall_back_to_the_real_clock(monkeypatch) -> None:
    """The failure mode a silent default would hide. `SeededToday` installed
    without its `AS_OF` set must fail loudly, not quietly answer with the real
    clock -- which would reinstate the drift while every test above still
    passed."""
    monkeypatch.setattr(SeededToday, "AS_OF", None)

    with pytest.raises(AssertionError, match="AS_OF is unset"):
        SeededToday.today()


def test_the_whole_capture_would_drift_a_year_out_without_the_pin(harness, monkeypatch) -> None:
    """The generalisation of the two single-route proofs above: not one route,
    the WHOLE plan.

    Those answer "is the pin real for rty-summary". They cannot answer "is any
    OTHER entry still carrying an expiry", and the answer used to be yes for 23
    of them -- the eight `/api/kpi/*/trend` routes among them, which go from
    `["[].date", "[].value"]` to `[]` once the window clears the seed.

    Shaped like the ShiftActivePin pair: this half proves the hazard is REAL by
    removing the pin and advancing the clock a year, asserting the capture
    genuinely moves. If it ever starts passing with an empty diff, the pin has
    stopped being necessary -- or the routes stopped reading the clock -- and
    that is the thing to re-examine, not this test to delete.

    A year, not a day: the windows default to 7, 30 and 90 days, so a shift
    small enough to sit inside the widest of them would prove nothing.
    """
    from backend.tests.contract.capture import capture_all
    from backend.tests.contract.conftest import CLOCK_READING_ROUTE_MODULES, SEED_AS_OF

    pinned = capture_all(harness.client, harness.plan.requests, urls=harness.plan.urls)

    far_future = SEED_AS_OF + timedelta(days=365)

    class _UnpinnedFarFuture(date):
        @classmethod
        def today(cls) -> date:  # type: ignore[override]
            # A plain date, for the reason SeededToday returns one: sqlite3
            # cannot bind a date subclass, and pydantic cannot build a field
            # from one.
            return date(far_future.year, far_future.month, far_future.day)

    for module in CLOCK_READING_ROUTE_MODULES:
        monkeypatch.setattr(f"{module}.date", _UnpinnedFarFuture)

    unpinned = capture_all(harness.client, harness.plan.requests, urls=harness.plan.urls)

    drifted = {route for route in pinned if pinned[route] != unpinned[route]}
    assert drifted, (
        "advancing the clock a year moved nothing -- either the routes stopped "
        "reading it or the plan captured nothing, and this proves neither"
    )
    assert len(pinned) > 100, "the plan captured almost nothing; this would prove nothing"


def test_the_pinned_capture_is_the_one_on_disk(harness) -> None:
    """And the other half: what the pin produces is what the golden holds.

    Together with the test above -- the clock moves the answer, the pin holds
    it -- this is what makes a wall-clock-sensitive entry a property of the
    seed. Neither half is worth anything alone: the first without this proves
    only that something changed, and this without the first passes happily on a
    suite where no route reads the clock at all.
    """
    import json

    from backend.tests.contract.capture import capture_all
    from backend.tests.contract.conftest import GOLDEN

    golden = json.loads(GOLDEN.read_text())
    pinned = capture_all(harness.client, harness.plan.requests, urls=harness.plan.urls)

    mismatched = {r: (golden[r], pinned[r]) for r in pinned if r in golden and golden[r] != pinned[r]}
    assert mismatched == {}


def test_every_clock_reading_route_module_is_pinned() -> None:
    """The coverage half, and the one the drift test cannot provide.

    `test_the_whole_capture_would_drift_a_year_out_without_the_pin` patches the
    same list `conftest` pins, so a module DROPPED from that list is patched in
    neither capture, answers the real clock in both, and the diff stays empty.
    Removing `backend.routes.kpi.trends` from the tuple is invisible to it --
    verified, which is why this exists.

    So the list is checked against the source instead: every route module that
    calls `date.today()` must be pinned, or be the one documented exclusion.
    A new route defaulting a window off the clock fails here, by name, on the
    commit that adds it rather than on the date its golden entry expires.
    """
    from pathlib import Path

    from backend.tests.contract.conftest import CLOCK_READING_ROUTE_MODULES

    #: The one module that CANNOT be pinned: it is the only clock-reading route
    #: module using `from __future__ import annotations`, so its `Optional[date]`
    #: parameters are strings resolved against module globals at request time,
    #: and swapping `date` makes FastAPI try to build a pydantic field from a
    #: date subclass. Its routes keep their expiry; that is a known cost, not an
    #: oversight, and it is recorded here rather than left to be rediscovered.
    UNPINNABLE = {"backend.routes.simulation_calibration"}

    routes_dir = Path(__file__).resolve().parents[2] / "routes"
    reads_clock = set()
    for path in routes_dir.rglob("*.py"):
        if "date.today()" in path.read_text():
            relative = path.relative_to(routes_dir.parent.parent)
            reads_clock.add(str(relative)[:-3].replace("/", "."))

    assert reads_clock, "found no clock-reading route module; this test would prove nothing"

    unpinned = reads_clock - set(CLOCK_READING_ROUTE_MODULES) - UNPINNABLE
    assert unpinned == set(), (
        f"these route modules default a window off date.today() but are not pinned, so their "
        f"golden entries expire silently: {sorted(unpinned)}"
    )

    # Two-sided: a module listed but no longer reading the clock is a stale
    # declaration, and stale declarations are how a list stops describing
    # anything.
    stale = set(CLOCK_READING_ROUTE_MODULES) - reads_clock
    assert stale == set(), f"pinned but no longer reads the clock: {sorted(stale)}"
