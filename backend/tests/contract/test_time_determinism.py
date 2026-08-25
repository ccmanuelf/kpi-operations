"""The golden-master capture must be time-of-day invariant.

`GET /api/shifts/active` (backend/routes/reference.py::get_active_shift) branches
on `datetime.now(tz=timezone.utc).time()`: whether a seeded shift is active, and
therefore whether the route returns a shift dict or a 404, depends on the real
wall-clock hour the suite happens to run at. Reproduced live: at 18:17 UTC the
unpinned capture returns a shift dict; the committed golden entry is
`["<status:404>"]`, captured during a window with no shift active. That is a
genuinely flaky gate, not a hypothetical one -- `test_golden_master.py` fails
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
"""

from datetime import date, datetime, timezone
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
from backend.tests.contract.capture import ShiftActivePin, capture_all
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


@pytest.fixture(scope="module")
def _client() -> Iterator[TestClient]:
    """Same disposable-DB pattern as test_golden_master.py's captured_shapes,
    scoped to just this module since only one route is exercised here."""
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
            as_of=date(2026, 8, 25),
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
    i.e. this is what `test_golden_master.py` looked like before ShiftActivePin
    existed, and what it reverts to if the pin is ever removed from its fixture.
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
    but through ShiftActivePin (the actual class wired into
    test_golden_master.py's captured_shapes fixture) -- output must be
    identical regardless of which of the two real moments `_real_now` reports.
    """
    monkeypatch.setattr("backend.routes.reference.datetime", ShiftActivePin)

    monkeypatch.setattr(ShiftActivePin, "_real_now", lambda tz=None: _MOMENT_INSIDE_A_SHIFT)
    shape_a = _capture_shift_active(_client)

    monkeypatch.setattr(ShiftActivePin, "_real_now", lambda tz=None: _MOMENT_IN_THE_GAP)
    shape_b = _capture_shift_active(_client)

    assert shape_a == shape_b == ["<status:404>"]
