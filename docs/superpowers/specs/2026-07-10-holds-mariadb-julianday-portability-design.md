# holds.py MariaDB Portability — julianday() → portable date-diff — Design

**Date:** 2026-07-10
**Status:** Design approved (user, 2026-07-10) — pending implementation plan
**Trigger:** First live production deploy (VM `192.168.2.234`, MariaDB) — browser verification hit HTTP 500s from the WIP-aging/holds endpoints:
`(pymysql.err.OperationalError) (1305, 'FUNCTION kpi_platform.julianday does not exist')`.

## Problem

`backend/routes/holds.py` composes date arithmetic with `func.julianday(...)` at three call sites:

- **L442** `get_top_aging_items` — SELECT column: `func.julianday("now") - func.julianday(HoldEntry.hold_date)`
- **L454** `get_top_aging_items` — `ORDER BY (func.julianday("now") - func.julianday(HoldEntry.hold_date)).desc()`
- **L494** `get_wip_aging_trend` — `func.avg(func.julianday(current_date) - func.julianday(HoldEntry.hold_date))`

`julianday()` is a **SQLite-only** function; MariaDB has no such function, so all three queries raise `OperationalError (1305)`. Live impact on the VM: the **WIP Aging KPI**, the **hold/aging list table**, and the **WIP-aging trend chart** all error. The rest of the dashboard renders (other KPIs use portable SQL).

**Why every test missed it:** the entire backend suite (5017 tests) runs on SQLite, where `julianday` works. A SQLite-only green suite structurally cannot catch a SQLite-only function — this is the "validate against the running app" lesson. PR-1 (#128) fixed MariaDB portability for columns/FKs but did not sweep dialect-specific SQL *functions* in route handlers; `holds.py` was outside its set.

**Also SQLite-specific:** the literal string `"now"` passed to `func.julianday("now")` is SQLite's date modifier, not a portable "current timestamp".

## Sweep result (scope confirmation)

A backend-wide grep for dialect-risky SQL functions (excluding tests, `.venv`, `backend/db/dialects/`) found:

- `func.julianday(...)` — **SQLite-only** — 3 sites, all in `holds.py`. **This is the bug.**
- `func.date(...)` — ~40 sites across `my_shift.py`, `kpi/trends.py`, `kpi/dashboard.py`, `kpi/efficiency.py`, `attendance.py`, `crud/defect_detail.py`, `calculations/efficiency.py`. **Portable** — `DATE()` exists in both SQLite and MariaDB; consistent with those dashboards rendering fine live. **Out of scope; do not touch.**

No `strftime`, `unixepoch`, or other SQLite-only functions in production code. **The fix is confined to `holds.py` plus a new shared helper.**

## Existing abstraction & why it doesn't drop in

`backend/db/dialects/{base,sqlite,mariadb,mysql}.py` already model dialect differences, including `get_date_diff_sql(date1, date2, unit)` (SQLite → `julianday` subtraction; MariaDB → `TIMESTAMPDIFF`). But it returns a **raw SQL string**, for string-built SQL. `holds.py` builds queries with the **SQLAlchemy ORM** (`func.…` composed into `.query()/.filter()/.order_by()`). A raw string can't compose into an ORM `ColumnElement` cleanly. So the fix introduces an **ORM-level** portable expression rather than reusing the string helper.

## Approach (chosen: A — custom compiled expression)

A new `ColumnElement` `date_diff_days(end, start)` in a small module `backend/db/sql_functions.py`, using SQLAlchemy's `@compiles` to emit per-dialect SQL. It returns the difference **in fractional days** to preserve SQLite's current behavior exactly.

- **SQLite** → `julianday(end) - julianday(start)` (fractional days, unchanged from today).
- **MySQL / MariaDB** → `TIMESTAMPDIFF(SECOND, start, end) / 86400.0` (fractional-day **parity**, not integer `TIMESTAMPDIFF(DAY)`).
- **Default compiler** (any other dialect) → same `TIMESTAMPDIFF(SECOND, …) / 86400.0` form.

Rejected alternatives: **B** inline `db.bind.dialect.name` branching in `holds.py` (scatters portability logic, easy to forget next time); **C** compute aging in Python (turns the SQL `ORDER BY … LIMIT` top-N into fetch-all-and-sort and multiplies the trend's per-day queries — most invasive).

### Component: `backend/db/sql_functions.py`

```python
class date_diff_days(expression.FunctionElement):
    """Portable difference between two datetime expressions, in fractional days.
    end - start. Compiles to julianday subtraction on SQLite and
    TIMESTAMPDIFF(SECOND, start, end)/86400.0 on MySQL/MariaDB."""
    name = "date_diff_days"
    inherit_cache = True
    type = Float()
```

- `@compiles(date_diff_days, "sqlite")` → `julianday(<end>) - julianday(<start>)`
- `@compiles(date_diff_days, "mysql")` (covers MariaDB — SQLAlchemy reports both as dialect `mysql`) → `TIMESTAMPDIFF(SECOND, <start>, <end>) / 86400.0`
- `@compiles(date_diff_days)` (default) → same TIMESTAMPDIFF form
- Argument order in the element is `(end, start)`; compilers read `element.clauses` positionally.

### Changes in `backend/routes/holds.py`

Replace the SQLite-only `"now"` literal with the portable `func.now()` (SQLAlchemy emits `CURRENT_TIMESTAMP`), and the julianday subtraction with `date_diff_days`:

- L442 / L454: `date_diff_days(func.now(), HoldEntry.hold_date)` (SELECT column and `.desc()` ORDER BY).
- L494: `func.avg(date_diff_days(current_date, HoldEntry.hold_date))` — `current_date` is the loop's Python `date`, bound as a parameter.

Numeric handling downstream is unchanged: `int(r[3])` (top items) and `round(avg_age, 1)` (trend) both accept the fractional result.

## Testing

The regression must be caught on **real MariaDB**, since SQLite cannot reproduce it.

1. **Unit test of the helper on both dialects** — `backend/tests/test_db/test_sql_functions.py`: assert `date_diff_days` compiles to the expected SQL string under a SQLite dialect and under a MySQL dialect (compile-only, no DB), pinning both branches.
2. **MariaDB endpoint coverage** — extend the existing real-MariaDB path (`backend/tests/test_mariadb_portability.py`, run by the `mariadb-portability` CI job): exercise the three holds queries (or the endpoints) against MariaDB with seeded `HOLD_ENTRY` rows and assert they return without `OperationalError` and produce sane aging values. This is the test that would have caught the bug.
3. **SQLite behavior unchanged** — existing `holds` tests continue to pass on SQLite (fractional-day parity means values don't move).
4. **Regression guard** — a cheap static test (e.g. `backend/tests/test_db/test_no_sqlite_only_funcs.py`) asserting no `func.julianday(` / `\.julianday(` appears under `backend/routes/`, so the SQLite-only function can't creep back into a handler. Scoped to `julianday` (the confirmed-nonportable one); `func.date()` is explicitly allowed.

## Definition of done

- The three `holds.py` endpoints return 200 with correct aging values on MariaDB (verified live on the VM after deploy) and unchanged behavior on SQLite.
- Helper unit test pins both dialect branches; `mariadb-portability` job exercises the holds queries on real MariaDB; regression guard rejects new `julianday` in `routes/`.
- Full suite green, coverage ≥ 75%; all 7 required CI checks green; `/code-review` + `/cross-review`; merge on user confirmation.
- Post-merge: deploy to the VM (`git pull` + rebuild + `up -d`) and re-verify the WIP-aging panels in the browser.

## Out of scope

- The ~40 portable `func.date()` call sites (they work on MariaDB).
- Converting the string-based `get_date_diff_sql` dialect helper or migrating other raw-SQL code paths.
- Any broader audit of non-date SQL portability (separate effort if ever needed).
