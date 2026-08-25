"""The seeded database, the authenticated client, and the capture, once.

Shared by `test_golden_master.py` (does every route still send the fields it
sent?) and `test_capture_integrity.py` (is the capture itself trustworthy?).
Both need the same expensive fixture, and splitting them apart was forced by
the 500-line limit, not by a change of design -- read this file first.

Two findings from building the capture, both load-bearing enough to fail the
whole exercise silently if missed:

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
   would return. Not this harness's bug to fix, but it must survive it to
   capture anything at all.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Dict, Iterator, List

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
from backend.tests.contract.capture import ShiftActivePin, capture_all, capture_isolated
from backend.tests.contract.param_resolution import CapturePlan, Resolver, blocked_shape, bogus_url_for, plan_capture
from backend.tests.test_routes.test_smoke_paramless_get import _mock_admin

GOLDEN = Path(__file__).parent / "golden" / "api_shapes.json"


@dataclass
class _Harness:
    client: TestClient
    plan: CapturePlan
    engine: Engine
    #: Copies the post-seed snapshot back over the working database.
    restore: Callable[[], None]


@pytest.fixture(scope="module")
def harness(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Harness]:
    """A seeded throwaway database, an authenticated client, and a fully
    resolved capture plan -- never the VM, never a real client. See the module
    docstring for why auth is overridden and why `raise_server_exceptions=False`
    is required.

    The snapshot taken right after seeding is what makes it safe to request
    mutating path-param routes with REAL ids, and it is worth being precise
    about which hazard it closes, because the wrong reason is what gets a
    correct mechanism deleted later.

    It is NOT mutation-versus-read. `plan_capture` already defers every
    mutating path-param route into `plan.isolated`, which runs after the whole
    read pass, so no GET can see a DELETE's damage regardless of the snapshot.
    What the snapshot closes is MUTATION-versus-MUTATION: within the isolated
    phase, `DELETE /api/clients/{client_id}` resolves to a seeded client and
    every later mutation touching that client would otherwise record what the
    earlier one left behind.

    Today no golden entry would move if the restore vanished -- the collisions
    that exist are masked by the `soft_delete()` bug that makes seven DELETEs
    404 for any id. That makes the mechanism silently inert, which is why
    `test_the_isolated_phase_restores_between_mutations` drives it directly
    rather than relying on the golden file to notice.

    Restoring the file at all is possible only because this is SQLite in
    `journal_mode=delete` with `NullPool`: no connection is open between
    requests, so the database is exactly one file to copy. The boundary is that
    file -- in-process state (the cache) is not restored; see `capture_isolated`.

    Runs from `backend/` as cwd. `POST /api/predictions/demo/seed` has a lazy
    import missing its `backend.` prefix (see the module docstring), so it
    resolves to `<status:500>` only when the interpreter's directory is
    `backend/`; a full recapture driven from the repo root records a different
    entry for that route.
    """
    db_path = tmp_path_factory.mktemp("golden") / "golden.db"
    snapshot = db_path.with_suffix(".pristine.db")
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
    engine.dispose()
    shutil.copyfile(db_path, snapshot)

    def _restore() -> None:
        engine.dispose()
        shutil.copyfile(snapshot, db_path)

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
        # Plan against the routes the GOLDEN MASTER names, not the
        # currently-loose ones. This is the difference between the net working
        # and the net deleting itself route by route as the refactor proceeds.
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
        plan = plan_capture(sorted(json.loads(GOLDEN.read_text())), Resolver(engine))
        yield _Harness(client=client, plan=plan, engine=engine, restore=_restore)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        time_pin.undo()
        engine.dispose()


@pytest.fixture(scope="module")
def captured_shapes(harness: _Harness) -> Dict[str, List[str]]:
    """Every golden route's shape: one pass for the read-only routes, then one
    restored-snapshot request per mutating path-param route, then the declared
    placeholders for routes no id can reach."""
    shapes = capture_all(harness.client, harness.plan.requests, urls=harness.plan.urls)
    shapes.update(capture_isolated(harness.client, harness.plan.isolated, harness.plan.urls, harness.restore))
    shapes.update({route: blocked_shape(exc.key) for route, exc in harness.plan.blocked.items()})
    return shapes


@pytest.fixture(scope="module")
def bogus_id_shapes(harness: _Harness, captured_shapes: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Every path-param route, re-requested with an id that cannot exist.

    Depends on `captured_shapes` so the real capture is already finished:
    these probes mutate (`DELETE /api/clients/NO-SUCH-ID` is harmless, but
    `POST .../approve-qc` with a real id is not, and the fixture restores
    around all of them anyway) and must not run first.
    """
    resolver = Resolver(harness.engine)
    shapes: Dict[str, List[str]] = {}
    for route, url in sorted(harness.plan.urls.items()):
        method, path = route.split(" ", 1)
        if "{" not in path:
            continue
        harness.restore()
        shapes.update(capture_all(harness.client, [(method, path, {})], urls={route: bogus_url_for(path, resolver)}))
    harness.restore()
    return shapes
