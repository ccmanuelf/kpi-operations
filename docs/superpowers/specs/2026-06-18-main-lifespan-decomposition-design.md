# C3 — main.py lifespan + app-assembly decomposition — Design

**Status:** Approved (brainstorm 2026-06-18). PR4 robustness slate, Run-7 audit Architecture-Medium (`main.py` lifespan decomposition). Last active slate item before C4/C5 (deferred to MariaDB go-live).

## Goal

Decompose `backend/main.py` (868 lines) — whose monolithic `lifespan` and inline app-assembly do too much — into a small `backend/bootstrap/` package of focused, individually-testable units, leaving `main.py` a thin **app-factory** (~120 lines). Behavior is preserved exactly (startup order + per-step failure semantics, middleware order, exception-handler behavior, the route/tag surface); the only intentional change is a robustness/consistency cleanup of the repeated best-effort `try/except` boilerplate.

## Background

`main.py` currently crams every app-assembly concern into one file:
- **`lifespan`** (lines 268–371): ~8 startup steps + 3 shutdown steps, each with ad-hoc `try/except`. Failure semantics **vary by design**: schema/`create_all` + capacity-tables are unwrapped (fatal — the app must not start without its schema); event-infra, schedulers, and the two seeds are best-effort (`try/except Exception → _logger.warning`, warn-and-continue).
- **`tags_metadata`** (374–515): ~140 lines of OpenAPI tag descriptions.
- **`app = FastAPI(...)`** (517) + **5 middleware** (525–548) whose add-order is correctness-critical (LIFO: CORS added last → runs outermost; documented inline).
- **5 global exception handlers** (551–600: `DomainValidationError`→400, `ResourceNotFoundError`→404, `DomainException`→400, `SQLAlchemyError`→503, `Exception`→500).
- **`root()`** health endpoint (608).
- **59 `app.include_router(...)`** calls (619–868), all bare includes, grouped by section comments.

## Scope (comprehensive — user choice 2026-06-18)

Decompose the lifespan AND the surrounding app-assembly (tags, middleware, exception handlers, router registration) into `backend/bootstrap/`. In scope: pure relocation + the best-effort-helper cleanup. Non-goals below.

## Architecture

New package `backend/bootstrap/` (groups "how the app is assembled"; avoids colliding with the existing `backend/middleware/` package of middleware *classes*):

- **`bootstrap/lifecycle.py`** — the decomposed startup/shutdown units + the `lifespan` async context manager + a `run_best_effort(name, fn)` helper.
- **`bootstrap/openapi.py`** — `tags_metadata: list[dict]`.
- **`bootstrap/app_config.py`** — `configure_middleware(app)` (the 5 middleware, same order + comments) and `register_exception_handlers(app)` (the 5 handlers, registered via `app.add_exception_handler(ExcType, handler)`).
- **`bootstrap/routers.py`** — `register_routers(app)` (all 59 `include_router` calls, verbatim order/args; imports the router objects).
- **`main.py`** → imports; `app = FastAPI(title=..., description=..., version="1.0.0", openapi_tags=tags_metadata, lifespan=lifespan)`; `configure_middleware(app)`; `register_exception_handlers(app)`; `register_routers(app)`; the `root()` endpoint stays (tiny). ~868 → ~120 lines.

Each `bootstrap` module has one clear responsibility and a small surface (`lifespan`, `tags_metadata`, `configure_middleware`/`register_exception_handlers`, `register_routers`), understandable and testable in isolation.

## Lifespan decomposition (the core target)

`lifespan` becomes a thin orchestrator calling named units in the **exact current order**, preserving each step's failure semantics:

**Startup (in order):**
1. `init_schema()` — `Base.metadata.create_all(bind=engine)` + the `<45`-table registry warning. **Fatal** (unwrapped).
2. `create_capacity_tables()` — existing call. **Fatal** (unwrapped, as today).
3. `init_event_infrastructure()` — register handlers + set persistence handler. **Best-effort.**
4. `start_schedulers()` — start report + dual-view schedulers (each `None`-guarded). **Best-effort** per scheduler.
5. `seed_demo_data()` — `_auto_seed_demo_data()` (no-op unless `DEMO_MODE`). **Best-effort.**
6. `seed_metric_dependencies()` — idempotent dependency-map seed. **Best-effort.**

**Shutdown (in order):** `stop_schedulers()` (dual-view then report), `dispose_engine()`. **Best-effort** (as today).

**Robustness cleanup:** `run_best_effort(name: str, fn: Callable[[], None]) -> None` wraps `try: fn() except Exception as e: _logger.warning("...%s failed: %s", name, e)` — applied ONLY to the steps that are best-effort today, replacing the repeated inline `try/except`. The fatal steps (`init_schema`, `create_capacity_tables`) stay unwrapped so a failure still aborts startup exactly as now. No step's fatal-vs-best-effort classification changes.

## Other extractions (pure relocation — verbatim, no behavior change)

- **`tags_metadata`** → `bootstrap/openapi.py` (data move).
- **Middleware** → `configure_middleware(app)`: the 5 `add_middleware`/`configure_rate_limiting` calls in the **same order** (order is correctness-critical — preserve the LIFO comments).
- **Exception handlers** → `register_exception_handlers(app)`: each `@app.exception_handler(T)` becomes a module-level handler function + `app.add_exception_handler(T, handler)`; same status codes/bodies.
- **Router registration** → `register_routers(app)`: the 59 `include_router` calls in the **same order** (imports of the router objects move with it).

## Behavior-preservation contract

Identical after refactor: the OpenAPI route set (every path + method) and `tags`; middleware add-order (hence runtime order); each exception handler's type→status/body mapping; the `root()` response; the lifespan's startup/shutdown **order** and each step's **fatal-vs-best-effort** behavior; `DEMO_MODE` gating. Intentionally changed: best-effort `try/except` boilerplate consolidated behind `run_best_effort` (same observable outcome — warn-and-continue).

## Testing & verification

- **New unit tests** (`tests/test_bootstrap/`): lifecycle units — `start_schedulers`/`stop_schedulers` no-op when a scheduler is `None`; `run_best_effort` catches an exception and logs a warning (does NOT propagate); a fatal unit propagates; the orchestrator invokes steps in the documented order (e.g. via monkeypatched units + a call-order recorder). `register_routers(app)` registers the expected number of routes; `register_exception_handlers(app)` installs the 5 handlers.
- **OpenAPI-surface snapshot check:** a test asserting the set of `(path, method)` from `app.routes` and the `openapi()["tags"]` names match an expected snapshot — proves the route/tag surface is unchanged by the relocation.
- **Implicit safety net:** the whole backend suite constructs the app (via `test_client`) on every run, exercising the real lifespan + middleware + handlers + routers — a regression breaks many tests.
- Full `pytest tests/` green; coverage ≥75% (holds/rises — new unit tests); permissive-assertion rule respected; smoke `/health/live`; CI 4 required checks; post-merge main CI + Render (local == GitHub == Render).

## Non-goals

- No change to what any startup step DOES (schema creation, seeding, scheduler behavior, event infra) — only where the code lives + the best-effort wrapper.
- No change to middleware/exception-handler/router LOGIC or any endpoint.
- No change to the schema-evolution mechanism (`create_all` vs Alembic) — that is C5, deferred.
- C4 (lockfile) / C5 stay deferred to MariaDB go-live.

## Delivery

One PR, sequenced commits: create each `bootstrap` module (relocation) keeping the suite green, decompose the lifespan with `run_best_effort`, add the unit + OpenAPI-snapshot tests, then thin `main.py`. Own brainstorm→spec→plan→execute→PR→merge-on-green cycle.
