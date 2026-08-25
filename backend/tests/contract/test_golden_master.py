"""Golden master shapes for all 164 loose response routes (Task 5).

This is what the response-model refactor diffs every subsequent route
conversion against, and -- per the Task 4 handoff -- the SOLE safety net for
the eight `/api/kpi/*/trend` routes: `frontend_usage.KNOWN_BLIND` documents
that the frontend field-usage extractor cannot see them (structural, not a
regex gap -- see that module), and no e2e spec mentions `trend` or `chart`,
so a chart silently losing its data renders empty and every other gate stays
green.

Two findings surfaced while building this fixture, both load-bearing enough
to fail the whole exercise silently if missed:

1. A bare `TestClient` with no auth override records `<status:401>` for all
   164 routes. Re-running that against itself reports "zero differences" --
   the phase-0 exit criterion would read as SUCCESS on a capture that
   protects nothing. `get_current_user` is overridden with `_mock_admin`,
   reused verbatim from `test_smoke_paramless_get` rather than rewritten
   thinner: it is a `SimpleNamespace`, not a `MagicMock`, because attribute
   access on a mock auto-creates objects that fail Pydantic string
   validation wherever a route serializes the user.

2. `TestClient(app, raise_server_exceptions=False)`, not the bare default:
   `POST /api/predictions/demo/seed` has a pre-existing bug -- an inline
   lazy import (`from generators.sample_data_phase5 import ...`) missing the
   `backend.` package prefix that every other import site in this codebase
   uses. It only resolves when the interpreter's own directory is
   `backend/` (true for `cd backend && python -m pytest`, false for a
   script run from elsewhere), so a default TestClient turns it into a
   crashed fixture instead of the `<status:500>` a real ASGI deployment
   would return. Not this task's bug to fix -- it predates the refactor and
   sits outside the response-model surface -- but the fixture must survive
   it to capture anything at all.

`MAX_STATUS_ONLY_ROUTES` and the known-good route below are the anti-vacuity
control: finding 1 shows the zero-diff exit criterion is satisfiable by a
worthless capture, so the golden master needs its own sanity check that
fails if a capture degenerates back to that shape.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Dict, Iterator, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.migrate import upgrade_to_head
from backend.main import app
from backend.seed.cli import ALLOWLIST as ALLOWLIST_CLIENTS
from backend.seed.cli import seed
from backend.tests.contract.capture import ShiftActivePin, capture_all
from backend.tests.contract.frontend_usage import KNOWN_BLIND
from backend.tests.test_routes.test_smoke_paramless_get import _mock_admin

GOLDEN = Path(__file__).parent / "golden" / "api_shapes.json"

#: Measured 2026-08-25 against a fresh `smoke` seed (see captured_shapes):
#: 78 of 164 loose routes recorded a status rather than a shape -- all 26
#: DELETEs (need a real id this harness deliberately never fabricates, see
#: capture_all's docstring), most POST/PUT (need a real id or body), and 31
#: GETs needing a path or required query param. 78/164 is a minority
#: (47.6%), i.e. most routes ARE resolving to real shapes, so this is the
#: measured ceiling, not an invented round number: a harness regression
#: (auth or db wiring silently breaking) shows up as "most routes are
#: erroring" rather than passing invisibly.
MAX_STATUS_ONLY_ROUTES = 78


def _is_status_only(shape: List[str]) -> bool:
    return len(shape) == 1 and shape[0].startswith("<status:")


@pytest.fixture(scope="module")
def captured_shapes(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Dict[str, List[str]]]:
    """Capture every loose route's shape against a disposable, throwaway
    database built fresh for this module -- never the VM, never a real
    client. See the module docstring for why auth is overridden and why
    `raise_server_exceptions=False` is required.
    """
    db_path = tmp_path_factory.mktemp("golden") / "golden.db"
    url = f"sqlite:///{db_path}"
    upgrade_to_head(url)

    engine: Engine = create_engine(url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    seed(
        engine,
        client_ids=tuple(sorted(ALLOWLIST_CLIENTS)),
        profile_name="smoke",
        seed_value=1234,
        as_of=date(2026, 8, 25),
        reset=False,
    )

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _mock_admin
    # `pytest.MonkeyPatch()` used directly, not the `monkeypatch` fixture --
    # this fixture is module-scoped and `monkeypatch` is function-scoped, so
    # pytest refuses to inject it here (ScopeMismatch). Undone in `finally`.
    #
    # GET /api/shifts/active branches on `datetime.now(tz=timezone.utc).time()`
    # (backend/routes/reference.py::get_active_shift): whether a seeded shift
    # is active depends on the WALL-CLOCK HOUR the suite happens to run at,
    # so an unpinned capture is genuinely flaky (a shift dict roughly half the
    # day, `<status:404>` the other half) rather than merely theoretically so
    # -- reproduced live against this exact fixture. Pinning only this one
    # route's `datetime.now` (see ShiftActivePin) makes the capture
    # deterministic without touching how any other route reads the clock.
    time_pin = pytest.MonkeyPatch()
    time_pin.setattr("backend.routes.reference.datetime", ShiftActivePin)
    try:
        client = TestClient(app, raise_server_exceptions=False)
        # Capture the routes the GOLDEN MASTER names, not the currently-loose
        # ones. This is the difference between the net working and the net
        # deleting itself route by route as the refactor proceeds.
        #
        # `loose_routes(app)` shrinks with every conversion, so a converted route
        # would stop being captured, read as None, and fail the comparison -- a
        # FALSE REGRESSION for a correct change. The tempting remedy is to prune
        # that route's golden entry, which is exactly backwards: the golden entry
        # is the proof the new response model did not drop a field, so pruning it
        # discards the protection at the moment it is finally being used.
        #
        # Driving from golden's keys means a converted route stays captured and
        # stays compared, which is the entire point of taking the shape first.
        golden_routes: List[tuple] = [
            (route.split(" ", 1)[0], route.split(" ", 1)[1], {}) for route in sorted(json.loads(GOLDEN.read_text()))
        ]
        yield capture_all(client, golden_routes)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        time_pin.undo()
        engine.dispose()


def test_no_route_lost_a_field(captured_shapes: Dict[str, List[str]]) -> None:
    """Compares KEY SETS, never value types. Changing a type is the point of
    this refactor -- "4" becoming 4 is success -- so a type-comparing golden
    master would fail on every intended change and be switched off within a
    day.
    """
    golden = json.loads(GOLDEN.read_text())

    for route, keys in golden.items():
        assert captured_shapes.get(route) == keys, f"{route} changed shape"


def test_a_known_good_trend_route_resolves_real_fields(captured_shapes: Dict[str, List[str]]) -> None:
    """Anti-vacuity control, half A.

    A zero-diff pass is also what a completely worthless capture -- 164
    identical `<status:401>` entries, see the module docstring's finding 1 --
    would report. Pinning one route to the shape it must resolve to when
    auth genuinely works means a regression back to that failure mode fails
    HERE instead of reading as success.
    """
    assert captured_shapes.get("GET /api/kpi/efficiency/trend") == ["[].date", "[].value"]


def test_status_only_routes_stay_under_the_measured_ceiling(captured_shapes: Dict[str, List[str]]) -> None:
    """Anti-vacuity control, half B.

    Half A alone would not catch a partial regression -- e.g. auth breaking
    for every route except the one pinned above. Counting how many of the
    164 recorded a status instead of a shape, and pinning that count, catches
    a harness that stops reaching routes it used to reach, whatever the
    cause (auth, db wiring, routing).
    """
    status_only = [route for route, shape in captured_shapes.items() if _is_status_only(shape)]
    assert len(status_only) <= MAX_STATUS_ONLY_ROUTES


def test_no_known_blind_trend_route_recorded_only_a_status(captured_shapes: Dict[str, List[str]]) -> None:
    """The eight `/api/kpi/*/trend` routes are where this golden master
    matters most: `frontend_usage.KNOWN_BLIND` documents that the frontend
    extractor cannot see them, and no e2e spec mentions `trend` or `chart`.
    A `<status:...>` entry for any of them would mean the one net watching
    this cluster isn't actually reaching it.
    """
    for endpoint in sorted(KNOWN_BLIND):
        route = f"GET {endpoint}"
        # A missing entry (route dropped out of loose_routes(app) entirely --
        # e.g. it already picked up a real response_model) is exactly as
        # untrustworthy as a status-only one, so it is treated the same way
        # rather than raising an opaque KeyError.
        shape = captured_shapes.get(route, ["<status:MISSING>"])
        assert not _is_status_only(shape), f"{route} recorded {shape}"
