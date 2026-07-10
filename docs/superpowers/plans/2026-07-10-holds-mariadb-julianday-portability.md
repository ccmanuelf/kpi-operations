# holds.py MariaDB Portability (julianday → date_diff_days) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the SQLite-only `func.julianday(...)` date arithmetic in `backend/routes/holds.py` with a portable ORM expression so the WIP-aging/holds endpoints work on MariaDB (they currently 500 in production), with SQLite behavior unchanged.

**Architecture:** Introduce a custom SQLAlchemy `FunctionElement` `date_diff_days(end, start)` compiled per-dialect (SQLite → `julianday` subtraction; MySQL/MariaDB → `TIMESTAMPDIFF(SECOND, start, end)/86400.0`, fractional-day parity). Rewire the three `holds.py` call sites to it and replace the SQLite-only `"now"` literal with portable `func.now()`. Cover both dialect branches with a compile-only unit test, prove execution on real MariaDB in the existing `mariadb-portability` CI job, and add a regression guard forbidding new `julianday` in `routes/`.

**Tech Stack:** Python 3.11, SQLAlchemy 2 (`sqlalchemy.ext.compiler.compiles`, `FunctionElement`), pytest, MariaDB 11.4 (via pymysql — SQLAlchemy dialect name `mysql`).

**Spec:** `docs/superpowers/specs/2026-07-10-holds-mariadb-julianday-portability-design.md`.

## Global Constraints

- SQLAlchemy reports MariaDB (pymysql driver) as dialect **`mysql`** — the `@compiles(..., "mysql")` branch covers MariaDB; there is no separate `mariadb` compile target.
- **Fractional-day parity:** MariaDB branch uses `TIMESTAMPDIFF(SECOND, start, end) / 86400.0`, NOT integer `TIMESTAMPDIFF(DAY, …)` — SQLite's `julianday` subtraction yields fractional days and downstream `round(avg, 1)` depends on it.
- Argument order is `date_diff_days(end, start)` meaning `end - start`.
- **Only `julianday` is non-portable.** `func.date(...)` (used ~40 places) is portable (`DATE()` exists in both dialects) — do NOT touch it.
- Backend tests run from `backend/`: `pytest tests/…`. Coverage gate ≥ 75% (`backend/.coveragerc`; note `backend/scripts/` is excluded but `backend/db/` and `backend/routes/` are counted).
- MariaDB integration tests are gated by `@requires_mariadb` (skip unless `DATABASE_URL` is MariaDB); they run only in the `mariadb-portability` CI job. Never make them run unconditionally.
- Permissive assertions forbidden: each test asserts ONE expected value (no `assert x in [...]`).
- Conventional commits. Files under 500 lines.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/db/sql_functions.py` | Create | Portable `date_diff_days` FunctionElement + per-dialect compilers |
| `backend/tests/test_db/test_sql_functions.py` | Create | Compile-only unit test pinning both dialect branches |
| `backend/routes/holds.py` | Modify (L442, L454, L494 + import) | Use `date_diff_days` + `func.now()` instead of `func.julianday` |
| `backend/tests/test_routes/test_holds_aging_portability.py` | Create | SQLite endpoint test: `/wip-aging/top` + `/wip-aging/trend` return 200 |
| `backend/tests/test_db/test_no_sqlite_only_funcs.py` | Create (Task 2) | Regression guard: no `julianday` under `backend/routes/` (green once holds.py is fixed) |
| `backend/tests/test_mariadb_portability.py` | Modify (append) | Real-MariaDB execution of `date_diff_days` + holds query shape |

---

### Task 1: Portable `date_diff_days` expression + unit test + regression guard

**Files:**
- Create: `backend/db/sql_functions.py`
- Test: `backend/tests/test_db/test_sql_functions.py`

**Interfaces:**
- Produces: `date_diff_days(end, start)` — a SQLAlchemy `ColumnElement` (subclass of `FunctionElement`, `.type` is `Float`) usable anywhere a column expression is valid (`.query(...)`, `.filter(...)`, `.order_by(...)`, `func.avg(...)`). Compiles to `julianday(end) - julianday(start)` on SQLite and `TIMESTAMPDIFF(SECOND, start, end) / 86400.0` on mysql/mariadb and the default dialect.

- [ ] **Step 1: Write the failing unit test**

Create `backend/tests/test_db/test_sql_functions.py`:

```python
"""Both dialect branches of the portable date_diff_days expression (PR: holds MariaDB fix).

Compile-only: no database needed. Renders the expression under the SQLite and
MySQL (== MariaDB) dialects and asserts each emits the correct function form.
"""

from sqlalchemy import Float, column, func, select
from sqlalchemy.dialects import mysql, sqlite

from backend.db.sql_functions import date_diff_days


def _compiled(dialect):
    expr = date_diff_days(func.now(), column("hold_date"))
    return str(select(expr).compile(dialect=dialect, compile_kwargs={"literal_binds": False}))


def test_sqlite_uses_julianday_subtraction():
    sql = _compiled(sqlite.dialect())
    assert "julianday" in sql


def test_mysql_uses_fractional_timestampdiff_seconds():
    sql = _compiled(mysql.dialect())
    assert "TIMESTAMPDIFF(SECOND" in sql
    assert "86400.0" in sql


def test_mysql_does_not_use_integer_day_diff():
    sql = _compiled(mysql.dialect())
    assert "TIMESTAMPDIFF(DAY" not in sql


def test_result_type_is_float():
    expr = date_diff_days(func.now(), column("hold_date"))
    assert isinstance(expr.type, Float)


def test_argument_order_end_minus_start_sqlite():
    # end is func.now(), start is the column: julianday(now) appears before julianday(hold_date)
    sql = _compiled(sqlite.dialect())
    now_idx = sql.index("julianday(CURRENT_TIMESTAMP")
    col_idx = sql.index("julianday(hold_date")
    assert now_idx < col_idx
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_db/test_sql_functions.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'backend.db.sql_functions'`

- [ ] **Step 3: Write the implementation**

Create `backend/db/sql_functions.py`:

```python
"""Portable SQL expressions for cross-dialect date arithmetic (SQLite ↔ MariaDB).

`func.julianday()` is SQLite-only and 500s on MariaDB (errno 1305). This module
provides an ORM-level, dialect-compiled replacement so route handlers can build
date-difference expressions without hardcoding a dialect-specific function.

SQLAlchemy reports MariaDB (pymysql) as dialect "mysql", so the "mysql" compiler
covers MariaDB; the default compiler mirrors it for any other backend.
"""

from sqlalchemy import Float
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement


class date_diff_days(FunctionElement):  # noqa: N801 — SQLAlchemy expression convention is lowercase
    """Difference between two datetime expressions, in FRACTIONAL days (end - start).

    Usage: date_diff_days(end_expr, start_expr). Compose it anywhere a column
    expression is valid (SELECT, WHERE, ORDER BY, func.avg(...)).
    """

    name = "date_diff_days"
    type = Float()
    inherit_cache = True


@compiles(date_diff_days, "sqlite")
def _date_diff_days_sqlite(element, compiler, **kw):
    end, start = list(element.clauses)
    return f"julianday({compiler.process(end, **kw)}) - julianday({compiler.process(start, **kw)})"


@compiles(date_diff_days, "mysql")
def _date_diff_days_mysql(element, compiler, **kw):
    # MariaDB is reported as "mysql". TIMESTAMPDIFF(unit, a, b) = b - a, so pass
    # (start, end) to get end - start. SECOND / 86400.0 preserves SQLite's
    # fractional-day result (integer TIMESTAMPDIFF(DAY) would truncate).
    end, start = list(element.clauses)
    return f"TIMESTAMPDIFF(SECOND, {compiler.process(start, **kw)}, {compiler.process(end, **kw)}) / 86400.0"


@compiles(date_diff_days)
def _date_diff_days_default(element, compiler, **kw):
    end, start = list(element.clauses)
    return f"TIMESTAMPDIFF(SECOND, {compiler.process(start, **kw)}, {compiler.process(end, **kw)}) / 86400.0"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && pytest tests/test_db/test_sql_functions.py -v`
Expected: 5 passed

- [ ] **Step 5: Run the focused module to confirm a clean tree**

Run: `cd backend && pytest tests/test_db/ -q`
Expected: all pass (the new file plus the existing `test_dialects.py` / `test_providers.py`).

- [ ] **Step 6: Commit**

```bash
git add backend/db/sql_functions.py backend/tests/test_db/test_sql_functions.py
git commit -m "feat(db): portable date_diff_days expression (SQLite julianday / MariaDB TIMESTAMPDIFF)"
```

(The regression guard forbidding `julianday` in `routes/` is added in Task 2, where `holds.py` is fixed in the same commit — so it is never committed red.)

---

### Task 2: Rewire `holds.py` to the portable expression

**Files:**
- Modify: `backend/routes/holds.py` (import + lines 442, 454, 494)
- Test: `backend/tests/test_routes/test_holds_aging_portability.py`
- Test: `backend/tests/test_db/test_no_sqlite_only_funcs.py` (regression guard, green because holds.py is fixed in this same task)

**Interfaces:**
- Consumes: `date_diff_days(end, start)` from `backend.db.sql_functions` (Task 1).

- [ ] **Step 1: Write the failing SQLite endpoint test**

Create `backend/tests/test_routes/test_holds_aging_portability.py`:

```python
"""The WIP-aging endpoints must return 200 (they build date-diff SQL via the
portable date_diff_days expression). On SQLite this also proves no behavior
regression; the MariaDB execution proof lives in test_mariadb_portability.py.
"""


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
```

- [ ] **Step 2: Run it to confirm it passes on SQLite BEFORE the change (baseline)**

Run: `cd backend && pytest tests/test_routes/test_holds_aging_portability.py -v`
Expected: 2 passed (the endpoints already work on SQLite; this test locks that in so Task 2's edit can't regress it).

- [ ] **Step 3: Add the import to `holds.py`**

In `backend/routes/holds.py`, find the existing import block near the top (after the `from sqlalchemy…` imports) and add:

```python
from backend.db.sql_functions import date_diff_days
```

- [ ] **Step 4: Replace the three `func.julianday` call sites**

In `backend/routes/holds.py`:

Line ~442 (SELECT column in `get_top_aging_items`) — replace:
```python
            func.julianday("now") - func.julianday(HoldEntry.hold_date),
```
with:
```python
            date_diff_days(func.now(), HoldEntry.hold_date),
```

Line ~454 (ORDER BY in `get_top_aging_items`) — replace:
```python
    results = query.order_by((func.julianday("now") - func.julianday(HoldEntry.hold_date)).desc()).limit(limit).all()
```
with:
```python
    results = query.order_by(date_diff_days(func.now(), HoldEntry.hold_date).desc()).limit(limit).all()
```

Line ~494 (AVG in `get_wip_aging_trend`) — replace:
```python
        query = db.query(func.avg(func.julianday(current_date) - func.julianday(HoldEntry.hold_date))).filter(
```
with:
```python
        query = db.query(func.avg(date_diff_days(current_date, HoldEntry.hold_date))).filter(
```

(Leave every other line — the `.filter(...)`, client scoping, `int(r[3])`, `round(avg_age, 1)` — unchanged. `func` is already imported in holds.py.)

- [ ] **Step 5: Write the regression-guard test**

Create `backend/tests/test_db/test_no_sqlite_only_funcs.py`:

```python
"""Guard: the SQLite-only `julianday` function must never reappear in route handlers.

It compiles on the SQLite test suite but 500s on MariaDB (errno 1305), so a
green suite cannot catch its reintroduction — this static check does.
Use backend.db.sql_functions.date_diff_days instead. `func.date()` is portable
(DATE() exists in both dialects) and is intentionally NOT restricted.
"""

import pathlib


def test_routes_do_not_use_sqlite_only_julianday():
    routes_dir = pathlib.Path(__file__).resolve().parents[2] / "routes"
    offenders = []
    for py in routes_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "julianday" in text:
            offenders.append(str(py.relative_to(routes_dir.parents[1])))
    assert offenders == []
```

- [ ] **Step 6: Run the endpoint test + the regression guard + the existing WIP-aging tests**

Run: `cd backend && pytest tests/test_routes/test_holds_aging_portability.py tests/test_db/test_no_sqlite_only_funcs.py tests/test_calculations/test_wip_aging.py tests/test_calculations/test_wip_aging_comprehensive.py -v`
Expected: all pass — endpoints still 200 on SQLite, the guard is GREEN (no `julianday` left in `routes/`), and the existing WIP-aging calculation tests are unchanged (fractional-day parity means values don't move).

- [ ] **Step 7: Commit**

```bash
git add backend/routes/holds.py backend/tests/test_routes/test_holds_aging_portability.py backend/tests/test_db/test_no_sqlite_only_funcs.py
git commit -m "fix(holds): portable date_diff_days instead of SQLite-only julianday (MariaDB 500 fix)"
```

---

### Task 3: Real-MariaDB execution coverage

**Files:**
- Modify: `backend/tests/test_mariadb_portability.py` (append tests using the existing `mariadb_schema` fixture + `@requires_mariadb`)

**Interfaces:**
- Consumes: `date_diff_days` (Task 1); the fixed `holds.py` query shape (Task 2); existing `mariadb_schema` fixture, `requires_mariadb` marker, `SessionLocal`, `engine` from the test module.

- [ ] **Step 1: Write the MariaDB execution tests**

Append to `backend/tests/test_mariadb_portability.py` (end of file):

```python
# ---------------------------------------------------------------------------
# holds.py MariaDB portability: date_diff_days must EXECUTE on real MariaDB.
# Before the fix, holds.py used func.julianday(), which 500s on MariaDB with
# (1305, 'FUNCTION kpi_platform.julianday does not exist'). SQLite cannot
# reproduce that, so these run only in the mariadb-portability CI job.
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta  # noqa: E402

from sqlalchemy import func, literal, select  # noqa: E402

from backend.db.sql_functions import date_diff_days  # noqa: E402


@requires_mariadb
def test_date_diff_days_executes_on_mariadb(mariadb_schema):
    """date_diff_days must run on MariaDB and return the fractional day delta."""
    start = datetime(2026, 6, 1, 0, 0, 0)
    end = datetime(2026, 6, 11, 0, 0, 0)  # exactly 10 days later
    session = SessionLocal()
    try:
        value = session.execute(select(date_diff_days(literal(end), literal(start)))).scalar()
    finally:
        session.close()
    assert value is not None
    assert abs(float(value) - 10.0) < 0.001


@requires_mariadb
def test_wip_aging_top_query_shape_executes_on_mariadb(mariadb_schema):
    """The get_top_aging_items query shape (SELECT + ORDER BY date_diff_days)
    must execute on MariaDB without OperationalError, even against an empty
    HOLD_ENTRY table (proves the function resolves; 1305 is raised at parse/exec
    time regardless of row count)."""
    from backend.orm.hold_entry import HoldEntry, HoldStatus
    from backend.orm.work_order import WorkOrder

    session = SessionLocal()
    try:
        rows = (
            session.query(
                HoldEntry.work_order_id,
                WorkOrder.style_model,
                HoldEntry.hold_date,
                date_diff_days(func.now(), HoldEntry.hold_date),
            )
            .outerjoin(WorkOrder, HoldEntry.work_order_id == WorkOrder.work_order_id)
            .filter(HoldEntry.hold_status == HoldStatus.ON_HOLD)
            .order_by(date_diff_days(func.now(), HoldEntry.hold_date).desc())
            .limit(10)
            .all()
        )
    finally:
        session.close()
    assert rows == []


@requires_mariadb
def test_wip_aging_trend_avg_executes_on_mariadb(mariadb_schema):
    """The get_wip_aging_trend AVG(date_diff_days(...)) shape must execute on
    MariaDB. Empty table → AVG is NULL → scalar() is None, no OperationalError."""
    from backend.orm.hold_entry import HoldEntry

    current_date = datetime(2026, 6, 11).date()
    session = SessionLocal()
    try:
        result = session.query(
            func.avg(date_diff_days(current_date, HoldEntry.hold_date))
        ).filter(HoldEntry.hold_date <= current_date).scalar()
    finally:
        session.close()
    assert result is None
```

- [ ] **Step 2: Run the MariaDB tests locally (expected: skipped on SQLite)**

Run: `cd backend && pytest tests/test_mariadb_portability.py -v -k "date_diff or aging_top_query or trend_avg"`
Expected: 3 skipped (reason: "requires the app engine to be MariaDB") — local/default suite is SQLite. This proves the `@requires_mariadb` gate works; the tests actually execute in the `mariadb-portability` CI job.

- [ ] **Step 3: Verify the compile-only + guard + endpoint tests all still pass together**

Run: `cd backend && pytest tests/test_db/ tests/test_routes/test_holds_aging_portability.py -v`
Expected: all pass, 0 failed (includes the new `test_sql_functions.py` (5) + `test_no_sqlite_only_funcs.py` (1) + the two endpoint tests, alongside the pre-existing `test_dialects.py`/`test_providers.py`).

- [ ] **Step 4: Run the full backend suite (coverage gate)**

Run: `cd backend && pytest tests/ -q`
Expected: all pass, coverage ≥ 75%.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_mariadb_portability.py
git commit -m "test(mariadb): execute date_diff_days + holds aging query shapes on real MariaDB"
```

---

## Verification (whole-PR definition of done)

1. `cd backend && pytest tests/` — all pass, coverage ≥ 75%.
2. `grep -rn julianday backend/routes` — no matches (guard enforces this).
3. No change to any `func.date(...)` call site; only `holds.py` and the new files changed (`git diff main...HEAD --stat`).
4. Final whole-branch review + `/code-review` + `/cross-review`; push; all 7 CI checks green (the `mariadb-portability` job now executes the 3 new MariaDB tests against real MariaDB — they must pass, not skip, there); merge on user confirmation.
5. Post-merge: deploy to the VM (`git -C /opt/kpi-operations/app pull --ff-only` → `docker compose -f docker-compose.prod.yml build` → uid re-chown check → `up -d`) and re-verify in the browser that the WIP-aging KPI, hold/aging list, and trend render without 500s.
