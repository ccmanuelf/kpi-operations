# main.py lifespan + app-assembly decomposition (C3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose `backend/main.py` (868 lines) into a `backend/bootstrap/` package of focused units (lifecycle, openapi, app_config, routers), leaving `main.py` a thin app-factory — behavior preserved exactly, with the best-effort startup `try/except` boilerplate consolidated.

**Architecture:** A golden-master OpenAPI route/tag snapshot is added FIRST so every relocation is provably surface-preserving. Then `tags_metadata`, router registration, middleware + exception handlers, and the lifespan move into `bootstrap/` modules (relocated verbatim, except the lifespan is decomposed into named startup/shutdown units behind a `run_best_effort` helper). `main.py` ends as imports + `FastAPI(...)` + `configure_middleware/register_exception_handlers/register_routers` calls + `root()`.

**Tech Stack:** FastAPI, SQLAlchemy, pytest (sqlite test DB via `test_client`).

**Spec:** `docs/superpowers/specs/2026-06-18-main-lifespan-decomposition-design.md`.

**Branch:** `refactor/main-lifespan-decomposition` (spec committed here @ `f9a7842`).

## Global Constraints

- **Behavior-preserving:** identical OpenAPI route set `(method, path)` + `tags`; middleware ADD-ORDER (correctness-critical, LIFO — preserve comments); each exception handler's type→status/body; `root()` response; lifespan startup/shutdown ORDER and each step's **fatal-vs-best-effort** classification; `DEMO_MODE` gating of `_auto_seed_demo_data`.
- **Fatal startup steps stay unwrapped** (`init_schema` = `create_all` + the `<45`-table warning; `create_capacity_tables`) — a failure must still abort startup. **Best-effort steps** (event infra, schedulers, demo-seed, dependency-seed, all shutdown steps) warn-and-continue via `run_best_effort`.
- **Per-module logger:** each `bootstrap/*` module and `main.py` defines `logger = logging.getLogger(__name__)` (do NOT share one `_logger`); the lifespan's `_logger.*` calls become `logger.*` in `lifecycle.py`, the handlers' in `app_config.py`.
- **Tests:** `pytest tests/` from `backend/` (no PYTHONPATH). Coverage ≥75% (holds/rises). One expected value per assert — no `assert x in [...]`.
- **Verbatim relocation:** moved blocks keep exact order/args; only import locations change. The whole suite spins up the app on every run (via `test_client`) — it is the implicit safety net; keep it green at every task.
- Commit per task. black/flake8/detect-secrets pre-commit may reformat/abort the first commit — re-add + re-commit. CI's 4 required checks must stay green.

### Reference (current main.py layout)
- imports + middleware classes + `logger`(157) + scheduler globals (`report_scheduler` 164–168, `dual_view_scheduler` 174–178) + `_auto_seed_demo_data()` (188–~265): lines 1–267
- `lifespan` (268–371) — startup 274–343, `yield` 345, shutdown 351–370
- `tags_metadata` (374–515, 35 tags)
- `app = FastAPI(...)` (517–523)
- middleware: `SecurityHeadersMiddleware`, `configure_rate_limiting(app)`, `AuditLogMiddleware`, `APIVersionMiddleware`, `CORSMiddleware` (525–548)
- 5 exception handlers (556–600): `DomainValidationError`→400, `ResourceNotFoundError`→404, `DomainException`→400, `SQLAlchemyError`→503, `Exception`→500
- `root()` (608–616)
- 59 `app.include_router(...)` (619–868)

---

## Task 1: OpenAPI surface golden-master snapshot (guards every relocation)

**Files:**
- Create: `backend/tests/test_bootstrap/__init__.py` (empty), `backend/tests/test_bootstrap/openapi_surface.json` (generated), `backend/tests/test_bootstrap/test_openapi_surface.py`

- [ ] **Step 1: Write the surface helper + test.**
```python
# backend/tests/test_bootstrap/test_openapi_surface.py
import json
import os
from backend.main import app

SNAP = os.path.join(os.path.dirname(__file__), "openapi_surface.json")


def current_surface() -> dict:
    routes = sorted(
        [m, r.path]
        for r in app.routes
        for m in (getattr(r, "methods", None) or [])
    )
    tags = [t["name"] for t in app.openapi().get("tags", [])]
    return {"routes": routes, "tags": tags}


def test_openapi_tag_set_unchanged():
    expected = json.load(open(SNAP))
    assert current_surface()["tags"] == expected["tags"]


def test_openapi_route_set_unchanged():
    expected = json.load(open(SNAP))
    assert current_surface()["routes"] == expected["routes"]
```

- [ ] **Step 2: Generate the golden snapshot from CURRENT code.** Run from `backend/`:
```bash
mkdir -p tests/test_bootstrap && touch tests/test_bootstrap/__init__.py
python -c "import json, tests.test_bootstrap.test_openapi_surface as t; json.dump(t.current_surface(), open('tests/test_bootstrap/openapi_surface.json','w'), indent=2)"
```
This captures the current route/tag surface as the golden master (the JSON stores `routes` as `[method, path]` lists + `tags` as names).

- [ ] **Step 3: Run — must PASS on current code.** `pytest tests/test_bootstrap/test_openapi_surface.py -v` → 2 PASS. This snapshot now guards every relocation in Tasks 2–5: any lost/added route or tag fails it.

- [ ] **Step 4: Commit.**
```bash
git add backend/tests/test_bootstrap/
git commit -m "test(bootstrap): golden-master OpenAPI route/tag snapshot (C3 Task 1)"
```

---

## Task 2: Extract `bootstrap/openapi.py` (tags_metadata)

**Files:**
- Create: `backend/bootstrap/__init__.py` (empty), `backend/bootstrap/openapi.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Move `tags_metadata`.** Create `backend/bootstrap/openapi.py`:
```python
"""OpenAPI tag metadata for the FastAPI app."""

tags_metadata = [
    # ... move the entire list from main.py lines 374-515 VERBATIM ...
]
```
Cut the `tags_metadata = [ ... ]` block (lines 374–515) out of `main.py`.

- [ ] **Step 2: Wire main.py.** Add `from backend.bootstrap.openapi import tags_metadata` to `main.py`'s imports; `app = FastAPI(..., openapi_tags=tags_metadata, ...)` already references `tags_metadata`, now from the import.

- [ ] **Step 3: Verify surface unchanged.** From `backend/`: `pytest tests/test_bootstrap/test_openapi_surface.py -v` → 2 PASS (tags identical).

- [ ] **Step 4: Commit.**
```bash
git add backend/bootstrap/__init__.py backend/bootstrap/openapi.py backend/main.py
git commit -m "refactor(bootstrap): extract OpenAPI tags_metadata (C3 Task 2)"
```

---

## Task 3: Extract `bootstrap/routers.py` (register_routers)

**Files:**
- Create: `backend/bootstrap/routers.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create `register_routers(app)`.** Move the 59 `app.include_router(...)` calls (lines 619–868) AND the router-object imports they use (the `from backend.endpoints... import ..._router` / `from backend.routes... import ..._router` lines in main.py's import block) into `backend/bootstrap/routers.py`:
```python
"""Registers every API router on the FastAPI app, in order."""
from fastapi import FastAPI

# ... move all the `..._router` imports here ...


def register_routers(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(auth_router)
    # ... all 59 includes, in the SAME ORDER, verbatim (keep section comments) ...
```

- [ ] **Step 2: Wire main.py.** Replace the 59 inline includes in `main.py` with `from backend.bootstrap.routers import register_routers` (import) and a single `register_routers(app)` call placed where the includes were. Remove the now-unused router imports from `main.py`.

- [ ] **Step 3: Verify surface unchanged.** From `backend/`: `pytest tests/test_bootstrap/test_openapi_surface.py -v` → 2 PASS (route set identical — proves no router lost/reordered into a different path). Then `pytest tests/ -q` (full) to confirm nothing else broke from moving imports.

- [ ] **Step 4: Commit.**
```bash
git add backend/bootstrap/routers.py backend/main.py
git commit -m "refactor(bootstrap): extract register_routers (C3 Task 3)"
```

---

## Task 4: Extract `bootstrap/app_config.py` (middleware + exception handlers)

**Files:**
- Create: `backend/bootstrap/app_config.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Create `configure_middleware(app)` + `register_exception_handlers(app)`.**
```python
"""Middleware wiring and global exception handlers."""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
# ... move imports used by the middleware/handlers: SecurityHeadersMiddleware,
#     AuditLogMiddleware, APIVersionMiddleware, configure_rate_limiting, settings,
#     DomainValidationError, ResourceNotFoundError, DomainException ...

logger = logging.getLogger(__name__)


def configure_middleware(app: FastAPI) -> None:
    # Move lines 525-548 VERBATIM, SAME ORDER (LIFO-critical — keep the comments):
    app.add_middleware(SecurityHeadersMiddleware)
    configure_rate_limiting(app)
    app.add_middleware(AuditLogMiddleware)
    app.add_middleware(APIVersionMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    )


def register_exception_handlers(app: FastAPI) -> None:
    # Convert each @app.exception_handler(T) (lines 556-600) into a function +
    # app.add_exception_handler(T, handler). Same status codes/bodies VERBATIM.
    async def domain_validation_error_handler(request: Request, exc: DomainValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message, "code": exc.code})

    async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.message, "code": exc.code})

    async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message, "code": exc.code})

    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database error: %s", exc)
        return JSONResponse(status_code=503, content={"detail": "Database service temporarily unavailable"})

    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.add_exception_handler(DomainValidationError, domain_validation_error_handler)
    app.add_exception_handler(ResourceNotFoundError, resource_not_found_handler)
    app.add_exception_handler(DomainException, domain_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
```

- [ ] **Step 2: Wire main.py.** Replace the inline middleware block (525–548) and the 5 `@app.exception_handler` defs (551–600) with `from backend.bootstrap.app_config import configure_middleware, register_exception_handlers` and calls `configure_middleware(app)` / `register_exception_handlers(app)` (place them after `app = FastAPI(...)`, BEFORE `register_routers(app)` — same relative position as the originals). Remove now-unused imports from `main.py`.

- [ ] **Step 3: Verify.** From `backend/`: `pytest tests/test_bootstrap/test_openapi_surface.py -v` → 2 PASS; then `pytest tests/ -q` (full) → green (existing middleware/CORS/error-handler tests prove behavior unchanged).

- [ ] **Step 4: Commit.**
```bash
git add backend/bootstrap/app_config.py backend/main.py
git commit -m "refactor(bootstrap): extract middleware + exception handlers (C3 Task 4)"
```

---

## Task 5: Extract + decompose `bootstrap/lifecycle.py` (the core target)

**Files:**
- Create: `backend/bootstrap/lifecycle.py`, `backend/tests/test_bootstrap/test_lifecycle.py`
- Modify: `backend/main.py`

**Interfaces — Produces:** `lifespan` (async context manager), `run_best_effort(name, fn)`, and the named units below.

- [ ] **Step 1: Create `bootstrap/lifecycle.py`.** Move from `main.py` (verbatim): the scheduler globals + guarded-import init (`report_scheduler` 164–168, `dual_view_scheduler` 174–178) and `_auto_seed_demo_data()` (188–~265, with its imports). Then write the decomposed lifespan:
```python
"""Application lifecycle: startup/shutdown units + the FastAPI lifespan."""
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Optional

from fastapi import FastAPI

from backend.database import engine, Base
from backend.events import register_all_handlers, get_event_bus
from backend.orm.event_store import create_event_persistence_handler

logger = logging.getLogger(__name__)

# ... moved: report_scheduler / dual_view_scheduler globals + guarded imports,
#     and the _auto_seed_demo_data() function (verbatim) ...


def run_best_effort(name: str, fn: Callable[[], None]) -> None:
    """Run a best-effort startup/shutdown step; log and swallow any exception."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001 - best-effort by design
        logger.warning("%s failed: %s", name, e)


def init_schema() -> None:
    """FATAL: create all tables (idempotent) + warn if the registry looks incomplete."""
    Base.metadata.create_all(bind=engine)
    actual = len(Base.metadata.tables)
    if actual < 45:
        logger.warning(
            "Schema registry may be incomplete: expected >=45 tables, got %d. "
            "Check that all ORM models are imported in backend/orm/__init__.py.",
            actual,
        )


def init_event_infrastructure() -> None:
    """Register domain-event handlers + wire persistence."""
    from backend.database import SessionLocal

    register_all_handlers()
    event_bus = get_event_bus()
    event_bus.set_persistence_handler(create_event_persistence_handler(SessionLocal))
    logger.info("Domain events infrastructure initialized")


def start_schedulers() -> None:
    """Start the report + dual-view schedulers (each None-guarded AND isolated:
    one scheduler's start failure must not skip the other — matches the original's
    two separate try/excepts)."""
    run_best_effort("report scheduler start", lambda: report_scheduler.start() if report_scheduler else None)
    run_best_effort("dual-view scheduler start", lambda: dual_view_scheduler.start() if dual_view_scheduler else None)


def stop_schedulers() -> None:
    """Stop the dual-view then report schedulers (each None-guarded AND isolated)."""
    run_best_effort("dual-view scheduler stop", lambda: dual_view_scheduler.stop() if dual_view_scheduler else None)
    run_best_effort("report scheduler stop", lambda: report_scheduler.stop() if report_scheduler else None)


def seed_metric_dependencies_step() -> None:
    """Idempotently seed the metric→assumption dependency map."""
    from backend.database import SessionLocal
    from backend.services.calculations.assumption_catalog import seed_metric_dependencies

    dep_db = SessionLocal()
    try:
        inserted = seed_metric_dependencies(dep_db)
        if inserted:
            logger.info("Seeded %d metric->assumption dependency rows", inserted)
    finally:
        dep_db.close()


def dispose_engine() -> None:
    """Dispose the DB engine connection pool."""
    engine.dispose()
    logger.info("Database engine disposed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup then shutdown, preserving order + failure semantics."""
    # STARTUP — fatal steps unwrapped; best-effort steps via run_best_effort
    init_schema()  # fatal
    from backend.db.migrations.capacity_planning_tables import create_capacity_tables
    create_capacity_tables()  # fatal
    run_best_effort("event infrastructure init", init_event_infrastructure)
    start_schedulers()  # per-scheduler isolation lives inside (see its definition)
    run_best_effort("demo data seed", _auto_seed_demo_data)
    run_best_effort("metric dependency seed", seed_metric_dependencies_step)

    yield

    # SHUTDOWN — all best-effort
    stop_schedulers()
    run_best_effort("engine dispose", dispose_engine)
```
Order is unchanged from the original: schema → capacity → event → report-start → dual-start → demo seed → dep seed → yield → dual-stop → report-stop → dispose. The fatal steps (`init_schema`, `create_capacity_tables`) stay unwrapped; every other step is best-effort (per-scheduler isolated inside `start_schedulers`/`stop_schedulers`).

- [ ] **Step 2: Wire main.py.** Replace the moved blocks (logger@157 stays in main.py as its own `logger`; scheduler globals + `_auto_seed_demo_data` + the whole `lifespan` are now in lifecycle.py) with `from backend.bootstrap.lifecycle import lifespan`. `app = FastAPI(..., lifespan=lifespan)` references the import. Remove the now-unused imports (`asynccontextmanager`, scheduler imports, event imports, etc.) from `main.py`.

- [ ] **Step 3: Write lifecycle unit tests.**
```python
# backend/tests/test_bootstrap/test_lifecycle.py
import logging
import pytest
from backend.bootstrap import lifecycle


def test_run_best_effort_swallows_and_warns(caplog):
    def boom():
        raise RuntimeError("nope")
    with caplog.at_level(logging.WARNING):
        lifecycle.run_best_effort("step x", boom)  # must NOT raise
    assert any("step x failed" in r.message for r in caplog.records)


def test_run_best_effort_runs_fn():
    calls = []
    lifecycle.run_best_effort("ok", lambda: calls.append(1))
    assert calls == [1]


def test_init_schema_is_fatal_on_error(monkeypatch):
    def boom(bind):
        raise RuntimeError("db down")
    monkeypatch.setattr(lifecycle.Base.metadata, "create_all", boom)
    with pytest.raises(RuntimeError):
        lifecycle.init_schema()


def test_start_schedulers_noop_when_none(monkeypatch):
    monkeypatch.setattr(lifecycle, "report_scheduler", None)
    monkeypatch.setattr(lifecycle, "dual_view_scheduler", None)
    lifecycle.start_schedulers()  # must not raise
    lifecycle.stop_schedulers()
```

- [ ] **Step 4: Run.** From `backend/`: `pytest tests/test_bootstrap/ -v` → all PASS; then `pytest tests/ -q` (full) → green (every `test_client` startup exercises the new lifespan; the snapshot proves the surface).

- [ ] **Step 5: Commit.**
```bash
git add backend/bootstrap/lifecycle.py backend/tests/test_bootstrap/test_lifecycle.py backend/main.py
git commit -m "refactor(bootstrap): decompose lifespan into testable units (C3 Task 5)"
```

---

## Task 6: Thin `main.py` final pass + full verification + PR

**Files:**
- Modify: `backend/main.py` (cleanup)

- [ ] **Step 1: Final main.py shape.** Confirm `main.py` is now: module docstring, imports, `logger = logging.getLogger(__name__)`, `app = FastAPI(title="Manufacturing KPI Platform API", description=..., version="1.0.0", openapi_tags=tags_metadata, lifespan=lifespan)`, `configure_middleware(app)`, `register_exception_handlers(app)`, `register_routers(app)`, and the `root()` endpoint (608–616, unchanged). Remove any leftover now-unused imports (run `flake8 backend/main.py` → clean). Target ~120 lines.

- [ ] **Step 2: Full gates.** From `backend/`:
```
pytest tests/
```
Expected: all green; coverage ≥75% (rose — new bootstrap unit tests). No `assert ... in [...]` introduced.

- [ ] **Step 3: Smoke + line count.** `wc -l backend/main.py` (≈120, down from 868) and `python -c "import backend.main"` imports clean. Confirm the snapshot test still passes (`pytest tests/test_bootstrap/test_openapi_surface.py -v`).

- [ ] **Step 4: Push + PR.**
```bash
git push -u origin refactor/main-lifespan-decomposition
gh pr create --base main --head refactor/main-lifespan-decomposition \
  --title "refactor(main): decompose lifespan + app-assembly into bootstrap/ (C3)" \
  --body "C3. Splits backend/main.py (868->~120 lines) into a bootstrap/ package: lifecycle.py (lifespan decomposed into named startup/shutdown units behind run_best_effort, preserving order + fatal-vs-best-effort semantics), openapi.py (tags_metadata), app_config.py (configure_middleware + register_exception_handlers), routers.py (register_routers, 59 includes verbatim). A golden-master OpenAPI route/tag snapshot test proves the surface is unchanged; new unit tests cover the lifecycle units. Spec/plan under docs/superpowers/."
```
Expected: 4 required checks green; report for merge approval (do not auto-merge). After merge: sync local main 0/0, confirm post-merge main CI, verify local == GitHub == Render.

---

## Self-review notes (author)

- **Spec coverage:** bootstrap package + thin app-factory (Tasks 2–6) · lifespan decomposition w/ fatal-vs-best-effort + run_best_effort (Task 5) · tags/middleware/handlers/routers verbatim relocation (Tasks 2–4) · OpenAPI-surface snapshot + lifecycle unit tests (Tasks 1, 5) · behavior-preservation via green suite + snapshot (every task) · verify + PR (Task 6). All spec sections map to a task.
- **No placeholders:** Task 1 (snapshot) + Task 5 (lifecycle decomposition + unit tests) carry full code; Tasks 2–4 are verbatim relocations bounded by exact line ranges + module skeletons (the moved code is existing, cited by line).
- **Type/name consistency:** `lifespan`, `run_best_effort(name, fn)`, `init_schema`/`init_event_infrastructure`/`start_schedulers`/`stop_schedulers`/`seed_metric_dependencies_step`/`dispose_engine`, `configure_middleware(app)`/`register_exception_handlers(app)`/`register_routers(app)`, `tags_metadata` — used consistently across tasks and `main.py` wiring.
- **Risk:** the per-scheduler failure-isolation subtlety is called out explicitly (Task 5 Step 2) so the decomposition matches the original's separate try/excepts, not a coarser single wrapper. The snapshot golden master + full-suite-spins-up-app make any surface or startup regression loud.
```
