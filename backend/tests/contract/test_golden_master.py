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
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Dict, Iterator, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, func, select, table
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.db.migrate import upgrade_to_head
from backend.main import app
from backend.seed.cli import ALLOWLIST as ALLOWLIST_CLIENTS
from backend.seed.cli import seed
from backend.tests.contract.capture import ShiftActivePin, capture_all, capture_isolated
from backend.tests.contract.frontend_usage import KNOWN_BLIND
from backend.tests.contract.param_resolution import (
    REGISTRY,
    CapturePlan,
    Resolver,
    blocked_shape,
    plan_capture,
)
from backend.tests.test_routes.test_smoke_paramless_get import _mock_admin

GOLDEN = Path(__file__).parent / "golden" / "api_shapes.json"

#: Re-measured 2026-08-25 after Task 8b gave path-param routes REAL ids: 41
#: of 164 loose routes record a status rather than a shape, down from 78. The
#: 37 that moved are all path-param routes that used to be requested with
#: literal braces in the URL -- see param_resolution's module docstring. No
#: route moved the other way.
#:
#: What is left is genuine and none of it is an id problem: mutations missing
#: a request body or a required query param (Task 15), and 7 DELETEs whose
#: crud layer calls `soft_delete()` on a model with no `is_active` column,
#: which returns False and surfaces as a 404 even for a correct id. A harness
#: regression (auth or db wiring silently breaking) still shows up here as
#: "most routes are erroring" rather than passing invisibly.
MAX_STATUS_ONLY_ROUTES = 41

#: The 15 routes no id can reach, because their backing table has zero seeded
#: rows. Pinned EXACTLY, not as a ceiling: a route dropping out of this set
#: means the seeder started writing its table and the route is now capturable
#: (promote its spec out of Kind.BLOCKED), while a route joining it means the
#: opposite -- something that used to be reachable no longer is. Both are
#: findings, and neither should pass silently. Reasons live in
#: `param_resolution.REGISTRY[key].reason`.
BLOCKED_ROUTES = frozenset(
    {
        "DELETE /api/break-times/{break_id}",
        "DELETE /api/coverage/{coverage_id}",
        "DELETE /api/equipment/{equipment_id}",
        "DELETE /api/filters/{filter_id}",
        "DELETE /api/floating-pool/{pool_id}",
        "DELETE /api/jobs/{job_id}",
        "DELETE /api/part-opportunities/{part_number}",
        "DELETE /api/v2/simulation/scenarios/{scenario_id}",
        "GET /api/jobs/{job_id}/dpmo",
        "GET /api/jobs/{job_id}/efficiency",
        "GET /api/jobs/{job_id}/kpi-summary",
        "GET /api/jobs/{job_id}/performance",
        "GET /api/jobs/{job_id}/ppm",
        "GET /api/jobs/{job_id}/yield",
        "GET /api/qr/job/{job_id}/image",
    }
)


def _is_status_only(shape: List[str]) -> bool:
    return len(shape) == 1 and shape[0].startswith("<status:")


def _is_placeholder(shape: List[str]) -> bool:
    """True for any entry that carries no field information at all --
    `<status:404>`, `<blocked:job_id>`, `<non-json>`. Distinct from
    `_is_status_only` because a route moving from a real shape to ANY of
    these is a regression, whatever flavour of nothing it landed on."""
    return len(shape) == 1 and shape[0].startswith("<")


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
    shapes.update({route: blocked_shape(key) for route, key in harness.plan.blocked.items()})
    return shapes


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


def test_no_captured_url_contains_an_unresolved_path_param(harness: _Harness) -> None:
    """The defect this task repairs, pinned at the plan level.

    Every path-param route used to be requested as
    `/api/workflow/statistics/%7Bclient_id%7D/status-distribution` and its
    answer recorded as if a real client had been asked. `capture_all` now
    raises on a braced URL, but that guard only fires for routes the plan
    actually issues; this one covers the plan itself, so a resolver that
    starts returning the template unchanged fails with the route named rather
    than with a shape diff 60 entries wide.
    """
    braced = {route: url for route, url in harness.plan.urls.items() if "{" in url or "}" in url}

    assert braced == {}


def test_blocked_routes_are_exactly_the_declared_manifest(harness: _Harness) -> None:
    """No surprises in either direction.

    An UNLISTED blocked route means the capture silently stopped reaching
    something it used to reach. A listed route that is no longer blocked means
    the seeder started writing its table and the spec must be promoted out of
    `Kind.BLOCKED` -- without this half, seed coverage improves and the harness
    keeps skipping routes it could now capture. That is the failure mode
    section 5.5 of the resolution map calls "rotting into folklore".
    """
    assert frozenset(harness.plan.blocked) == BLOCKED_ROUTES


def test_every_blocked_spec_still_has_zero_rows(harness: _Harness) -> None:
    """The staleness half of the gate, asserted against the seeded database
    rather than against a comment. Each blocked spec claims its table is
    empty; the moment Task 8d seeds `JOB`, `EQUIPMENT`, `BREAK_TIME` or any
    other of them, this goes red and forces the promotion.
    """
    # `if spec.table` narrows away the Optional; that a BLOCKED spec always
    # HAS a table is gated separately by
    # test_param_resolution.test_row_backed_specs_name_the_table_they_read,
    # so a None here cannot silently shrink this set unnoticed.
    specs = [REGISTRY[key] for key in set(harness.plan.blocked.values())]
    blocked_tables = sorted({spec.table for spec in specs if spec.table})
    # `select(func.count()).select_from(table(name))` rather than an f-string
    # SQL literal: the name comes from our own REGISTRY, but interpolating it
    # is a B608 finding that would have to be silenced with a bandit
    # suppression comment, and SQLAlchemy quotes the identifier correctly for
    # either dialect anyway.
    with harness.engine.connect() as conn:
        counts = {name: conn.execute(select(func.count()).select_from(table(name))).scalar() for name in blocked_tables}

    assert counts == {
        "BREAK_TIME": 0,
        "EQUIPMENT": 0,
        "FLOATING_POOL": 0,
        "JOB": 0,
        "PART_OPPORTUNITIES": 0,
        "SAVED_FILTER": 0,
        "SIMULATION_SCENARIO": 0,
        "shift_coverage": 0,
    }


def test_no_route_regressed_from_a_real_shape_to_a_placeholder(captured_shapes: Dict[str, List[str]]) -> None:
    """Direction matters, and `test_no_route_lost_a_field` cannot say which
    way a route moved -- it reports "changed shape" for an improvement and a
    regression alike.

    A route whose golden entry is a real shape and whose capture is a
    `<status:...>`, `<blocked:...>` or `<non-json>` placeholder has lost every
    field it had. That direction is never acceptable churn: it means id
    resolution, auth or the seed got WORSE, and it must fail rather than be
    recaptured over.
    """
    golden = json.loads(GOLDEN.read_text())
    regressed = {
        route: captured_shapes.get(route, ["<status:MISSING>"])
        for route, keys in golden.items()
        if not _is_placeholder(keys) and _is_placeholder(captured_shapes.get(route, ["<status:MISSING>"]))
    }

    assert regressed == {}


def test_a_known_wrong_shape_entry_gained_its_nested_object(captured_shapes: Dict[str, List[str]]) -> None:
    """Anti-vacuity control for THIS task.

    Eight golden entries recorded a 200 shape for an entity whose id was the
    literal string `{client_id}`; those are worse than the 54 statuses,
    because they look like real answers. This is the sharpest of them: asked
    with real braces it recorded three keys, and `by_status` was one of them
    -- a bare name with nothing under it. Asked with a real client it carries
    an entire nested object. A response model built from the old entry would
    have dropped `status`, `count` and `percentage` from every response.

    Pinned exactly, so a regression to brace-requesting fails here with the
    reason visible instead of as one line in a wide diff.
    """
    assert captured_shapes.get("GET /api/workflow/statistics/{client_id}/status-distribution") == [
        "by_status[].count",
        "by_status[].percentage",
        "by_status[].status",
        "client_id",
        "total_work_orders",
    ]


def _request(route: str) -> tuple:
    method, path = route.split(" ", 1)
    return (method, path, {})


def test_the_isolated_phase_restores_between_mutations(harness: _Harness, captured_shapes) -> None:
    """The snapshot restore is the largest new mechanism in this harness, and
    the golden file cannot see it.

    Disabling it leaves all 164 entries byte-identical, because the only
    collisions available today are masked by the `soft_delete()` bug that makes
    seven DELETEs 404 for any id -- and most of the DELETEs that DO succeed are
    soft deletes, so repeating them still answers 204. A mechanism whose
    absence looks exactly like its presence is gated by nothing, so this drives
    `capture_isolated` directly against the two genuinely non-idempotent routes
    in the plan, once with the real restore and once with a no-op.

    `DELETE /api/kpi-thresholds/{client_id}/{kpi_key}` HARD-deletes its row:
    200 `{message}` first, 404 forever after. `capture_all` keys by route
    template, so running it twice records the SECOND answer -- which is the
    real shape if and only if the database was restored in between.

    `POST /api/work-orders/{work_order_id}/approve-qc` is the sharper of the
    two, because it does not fail loudly: approving an already-approved work
    order answers 200 and silently DROPS the `message` key. That is a golden
    entry quietly losing a field to a neighbouring route -- precisely the class
    of accident this whole task exists to remove, reproduced one layer down.

    Boundary, stated rather than discovered later: this gates the `restore()`
    call inside `capture_isolated`, which is the only one in the capture path.
    It cannot catch a fixture rewired to pass a no-op in place of
    `harness.restore`; that would need the module-scoped capture to be re-run.
    """
    thresholds = "DELETE /api/kpi-thresholds/{client_id}/{kpi_key}"
    approve_qc = "POST /api/work-orders/{work_order_id}/approve-qc"
    urls = harness.plan.urls
    approved = ["message", "qc_approved", "qc_approved_by", "qc_approved_date", "status", "work_order_id"]

    try:
        harness.restore()
        twice_restored = capture_isolated(
            harness.client, [_request(thresholds)] * 2, urls, harness.restore
        ) | capture_isolated(harness.client, [_request(approve_qc)] * 2, urls, harness.restore)

        harness.restore()
        twice_unrestored = capture_isolated(
            harness.client, [_request(thresholds)] * 2, urls, lambda: None
        ) | capture_isolated(harness.client, [_request(approve_qc)] * 2, urls, lambda: None)
    finally:
        harness.restore()

    assert twice_restored == {thresholds: ["message"], approve_qc: approved}
    # The control: without the restore both routes record something else, so
    # the assertion above is not passing because these routes are inert.
    assert twice_unrestored == {thresholds: ["<status:404>"], approve_qc: approved[1:]}
