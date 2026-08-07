# Pivot Engine + API (Cycle 4 PR-A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the declarative pivot engine (`backend/pivot/`) and `/api/pivot/{dataset}` + `/csv` API over existing measures — Cycle 4 PR-A of the approved spec `docs/superpowers/specs/2026-08-06-pivot-summarization-layer-design.md`.

**Architecture:** A registry of dataset definitions (fact model, group-by allow-list, measures declared as Sum/Count components + Ratio/Share compositions) feeds a generic engine: one SQL aggregate per **(day, group)** (portable `func.date(...)` idiom already used by `summarize_labor_hours`), then a pure-Python rollup assigns days to week/month/quarter/year buckets (`date.weekday()`/month math — no dialect-specific SQL, which is where past MariaDB bugs hid) and computes every ratio from the **summed** components (ratio-of-sums structural). Two datasets whose semantics live in existing Python (labor's allocation math, delivery's date-inference chain) use per-dataset fetch hooks that return the same per-(day, group) component rows and reuse the existing calculation functions verbatim, so golden parity is by construction.

**Tech Stack:** FastAPI, SQLAlchemy 2.x typed ORM, pytest; no new dependencies, no migration, no new columns.

## Global Constraints

- Ratio-of-sums ONLY: every derived measure is computed from summed components; totals recompute the ratio over window sums, never sum/average row ratios (2026-08-06 ruling, tasks/lessons.md).
- Client scoping via `resolve_client_scope` → `scope.client_ids` (`None` = all clients); NEVER call `scope.as_single()` (backend/auth/jwt.py:311–360, #144 regression class).
- All wire values: Decimal→float coercion; bucket keys ISO `YYYY-MM-DD` strings; ratios `None` when denominator ≤ 0.
- Date filtering idiom: `func.date(Model.<date_col>) >= start_date` / `<= end_date` (matches `summarize_labor_hours`; portable across SQLite/MariaDB).
- ISO week, Monday start.
- One expected status code per test assertion — `assert response.status_code == 422`, never `in [...]`.
- New routes ⇒ regenerate `backend/tests/test_bootstrap/openapi_surface.json` (Task 6).
- Backend verification: `pytest tests/` from `backend/`; coverage gate ≥ 75 %.
- Work on branch `feat/pivot-summarization-layer` (spec already committed there).

## File Structure

- Create `backend/pivot/__init__.py` — empty package marker.
- Create `backend/pivot/buckets.py` — pure `bucket_start()` function (Task 1).
- Create `backend/pivot/registry.py` — measure/dataset dataclasses + `DATASETS` registry (Tasks 2, 4, 5).
- Create `backend/pivot/engine.py` — `run_pivot()` generic SQL path + rollup + ratio math (Task 3).
- Create `backend/pivot/hooks.py` — labor + delivery fetch hooks (Task 5).
- Create `backend/routes/pivot.py` — JSON + CSV endpoints (Task 6).
- Modify `backend/bootstrap/routers.py` — register the pivot router (Task 6).
- Modify `backend/tests/test_bootstrap/openapi_surface.json` — regenerated (Task 6).
- Tests: `backend/tests/test_pivot/` (`__init__.py`, `test_buckets.py`, `test_registry_guard.py`, `test_engine.py`, `test_hooks_golden.py`) and `backend/tests/test_routes/test_pivot_routes.py`.

---

### Task 1: Bucket helper

**Files:**
- Create: `backend/pivot/__init__.py` (empty), `backend/pivot/buckets.py`
- Test: `backend/tests/test_pivot/__init__.py` (empty), `backend/tests/test_pivot/test_buckets.py`

**Interfaces:**
- Produces: `bucket_start(d: date, bucket: str) -> date` and `VALID_BUCKETS: tuple[str, ...] = ("week", "month", "quarter", "year")`. Raises `ValueError` on unknown bucket. Consumed by engine (Task 3) and route validation (Task 6).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_pivot/test_buckets.py
"""Bucket assignment is pure Python (date.weekday()/month math) so week/month/
quarter/year grouping cannot diverge between SQLite and MariaDB — the dialect
split is where past prod bugs (julianday class) hid."""
from datetime import date

import pytest

from backend.pivot.buckets import VALID_BUCKETS, bucket_start


def test_valid_buckets_tuple():
    assert VALID_BUCKETS == ("week", "month", "quarter", "year")


def test_week_monday_maps_to_itself():
    assert bucket_start(date(2026, 8, 3), "week") == date(2026, 8, 3)  # a Monday


def test_week_sunday_maps_to_previous_monday():
    assert bucket_start(date(2026, 8, 9), "week") == date(2026, 8, 3)


def test_week_year_boundary():
    # 2026-01-01 is a Thursday; its ISO week starts Monday 2025-12-29.
    assert bucket_start(date(2026, 1, 1), "week") == date(2025, 12, 29)


def test_month_start():
    assert bucket_start(date(2026, 2, 28), "month") == date(2026, 2, 1)


def test_quarter_starts():
    assert bucket_start(date(2026, 1, 15), "quarter") == date(2026, 1, 1)
    assert bucket_start(date(2026, 3, 31), "quarter") == date(2026, 1, 1)
    assert bucket_start(date(2026, 4, 1), "quarter") == date(2026, 4, 1)
    assert bucket_start(date(2026, 12, 31), "quarter") == date(2026, 10, 1)


def test_year_start():
    assert bucket_start(date(2026, 7, 4), "year") == date(2026, 1, 1)


def test_unknown_bucket_raises():
    with pytest.raises(ValueError):
        bucket_start(date(2026, 1, 1), "day")
```

- [ ] **Step 2: Run tests to verify they fail**

Run from `backend/`: `pytest tests/test_pivot/test_buckets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.pivot'`

- [ ] **Step 3: Implement**

```python
# backend/pivot/buckets.py
"""Time-bucket assignment for the pivot engine (Cycle 4).

Pure Python on purpose: the engine's SQL aggregates per *day* (the portable
`func.date(...)` idiom) and this module rolls days up into buckets, so
week/quarter math never touches dialect-specific SQL.
"""
from datetime import date, timedelta

VALID_BUCKETS: tuple[str, ...] = ("week", "month", "quarter", "year")


def bucket_start(d: date, bucket: str) -> date:
    """Return the first day of the bucket containing d. ISO week, Monday start."""
    if bucket == "week":
        return d - timedelta(days=d.weekday())
    if bucket == "month":
        return d.replace(day=1)
    if bucket == "quarter":
        return date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)
    if bucket == "year":
        return date(d.year, 1, 1)
    raise ValueError(f"bucket must be one of {VALID_BUCKETS}, got {bucket!r}")
```

Also create empty `backend/pivot/__init__.py` and `backend/tests/test_pivot/__init__.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pivot/test_buckets.py -v` — Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pivot/ backend/tests/test_pivot/
git commit -m "feat(pivot): pure-Python bucket assignment (week/month/quarter/year, ISO Monday)"
```

---

### Task 2: Registry dataclasses + SQL-path datasets (production, downtime) + structural guard

**Files:**
- Create: `backend/pivot/registry.py`
- Test: `backend/tests/test_pivot/test_registry_guard.py`

**Interfaces:**
- Produces (consumed by engine Task 3, hooks Task 5, routes Task 6):
  - `@dataclass(frozen=True) Sum(expr)` — SQLAlchemy expression summed per (day, group).
  - `@dataclass(frozen=True) Count()` — row count per (day, group).
  - `@dataclass(frozen=True) Ratio(numerator: str, denominator: str, scale: float = 100.0)` — names of *declared component measures*.
  - `@dataclass(frozen=True) Share(of: str)` — component's share of the window total × 100.
  - `@dataclass(frozen=True) GroupBy(expr, joins: tuple = ())` — join tuples are `(Model, onclause)` applied as outer joins.
  - `@dataclass(frozen=True) Dataset(name, model, date_column, client_column, group_bys: dict[str, GroupBy], measures: dict[str, Sum | Count | Ratio | Share], joins: tuple = (), base_filters: tuple = (), fetch: Callable | None = None)`
  - `DATASETS: dict[str, Dataset]` with keys (after all tasks) `production, downtime, quality, holds, labor, delivery`; this task registers `production` and `downtime`.

- [ ] **Step 1: Write the failing structural-guard test**

```python
# backend/tests/test_pivot/test_registry_guard.py
"""Structural guard pinning the 2026-08-06 ratio-of-sums ruling: every derived
measure MUST be composed of declared Sum/Count components. An average-of-
averages is unrepresentable — this test makes that permanent for any dataset
anyone registers, present or future."""
from backend.pivot.registry import DATASETS, Count, Ratio, Share, Sum


def test_registry_has_sql_path_datasets():
    assert "production" in DATASETS
    assert "downtime" in DATASETS


def test_every_ratio_and_share_references_declared_sum_or_count_components():
    for name, ds in DATASETS.items():
        for mname, m in ds.measures.items():
            if isinstance(m, Ratio):
                for ref in (m.numerator, m.denominator):
                    assert ref in ds.measures, f"{name}.{mname} references undeclared {ref!r}"
                    assert isinstance(ds.measures[ref], (Sum, Count)), (
                        f"{name}.{mname} component {ref!r} must be Sum/Count, "
                        f"got {type(ds.measures[ref]).__name__} — ratios compose "
                        f"summed components only (ratio-of-sums ruling)"
                    )
            if isinstance(m, Share):
                assert m.of in ds.measures and isinstance(ds.measures[m.of], (Sum, Count))


def test_every_dataset_declares_scope_and_date_axis():
    for name, ds in DATASETS.items():
        assert ds.date_column is not None, name
        assert ds.client_column is not None, name
        assert "client" in ds.group_bys, name
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_pivot/test_registry_guard.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` on `backend.pivot.registry`

- [ ] **Step 3: Implement the registry with production + downtime**

```python
# backend/pivot/registry.py
"""Declarative dataset registry for the pivot engine (Cycle 4 spec §3–§4).

A dataset is either SQL-path (engine builds one GROUP BY (day, group) query
from Sum/Count exprs) or hook-path (fetch returns the same per-(day, group)
component rows from existing Python calculations). Ratio/Share measures name
their components; the engine computes them from SUMS — ratio-of-sums is
structural (see test_registry_guard.py).
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy import case, func

from backend.orm.client import Client
from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.product import Product
from backend.orm.production_entry import ProductionEntry
from backend.orm.production_line import ProductionLine


@dataclass(frozen=True)
class Sum:
    expr: Any


@dataclass(frozen=True)
class Count:
    pass


@dataclass(frozen=True)
class Ratio:
    numerator: str
    denominator: str
    scale: float = 100.0


@dataclass(frozen=True)
class Share:
    of: str


@dataclass(frozen=True)
class GroupBy:
    expr: Any
    joins: tuple = ()


@dataclass(frozen=True)
class Dataset:
    name: str
    model: Any
    date_column: Any
    client_column: Any
    group_bys: dict[str, GroupBy]
    measures: dict[str, Any]
    joins: tuple = ()
    base_filters: tuple = ()
    fetch: Optional[Callable] = None


# --- production -------------------------------------------------------------
# earned hours mirror backend/calculations/labor_hours.py::earned_hours:
# entry ideal_cycle_time, else product default; neither -> EXCLUDED (counted,
# never guessed). Product join is outer so entries without a product row still
# aggregate (they count as excluded).
_ict = func.coalesce(ProductionEntry.ideal_cycle_time, Product.ideal_cycle_time)

_PRODUCTION = Dataset(
    name="production",
    model=ProductionEntry,
    date_column=ProductionEntry.shift_date,
    client_column=ProductionEntry.client_id,
    joins=((Product, ProductionEntry.product_id == Product.product_id),),
    group_bys={
        "client": GroupBy(ProductionEntry.client_id),
        "line": GroupBy(
            ProductionLine.line_name,
            joins=((ProductionLine, ProductionEntry.line_id == ProductionLine.line_id),),
        ),
        "product": GroupBy(Product.product_name),
    },
    measures={
        "units": Sum(ProductionEntry.units_produced),
        "earned_hours": Sum(
            case((_ict.isnot(None), ProductionEntry.units_produced * _ict), else_=0)
        ),
        "excluded_entries": Sum(case((_ict.is_(None), 1), else_=0)),
        "run_hours": Sum(ProductionEntry.run_time_hours),
        "downtime_hours": Sum(func.coalesce(ProductionEntry.downtime_hours, 0)),
        "operators": Sum(func.coalesce(ProductionEntry.employees_present, 0)),
        "efficiency_pct": Ratio("earned_hours", "run_hours"),
    },
)

# --- downtime ---------------------------------------------------------------
_DOWNTIME = Dataset(
    name="downtime",
    model=DowntimeEntry,
    date_column=DowntimeEntry.shift_date,
    client_column=DowntimeEntry.client_id,
    group_bys={
        "client": GroupBy(DowntimeEntry.client_id),
        "category": GroupBy(func.coalesce(DowntimeEntry.root_cause_category, "uncategorized")),
        "reason": GroupBy(DowntimeEntry.downtime_reason),
        "line": GroupBy(
            ProductionLine.line_name,
            joins=((ProductionLine, DowntimeEntry.line_id == ProductionLine.line_id),),
        ),
    },
    measures={
        "downtime_hours": Sum(DowntimeEntry.downtime_duration_minutes / 60.0),
        "events": Count(),
        "share_of_window_pct": Share(of="downtime_hours"),
    },
)

DATASETS: dict[str, Dataset] = {
    "production": _PRODUCTION,
    "downtime": _DOWNTIME,
}
```

Note: the `Client` import is unused until a later task adds nothing needing it — if flake8 flags it, drop it (only import what these two datasets use).

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_pivot/test_registry_guard.py tests/test_pivot/test_buckets.py -v` — Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/pivot/registry.py backend/tests/test_pivot/test_registry_guard.py
git commit -m "feat(pivot): dataset registry + structural ratio-of-sums guard (production, downtime)"
```

---

### Task 3: Engine — generic SQL path, rollup, ratio math, coercion

**Files:**
- Create: `backend/pivot/engine.py`
- Test: `backend/tests/test_pivot/test_engine.py`

**Interfaces:**
- Consumes: `bucket_start`, `VALID_BUCKETS` (Task 1); `DATASETS`, dataclasses (Task 2).
- Produces (consumed by routes Task 6 and hook goldens Task 5):

```python
def run_pivot(
    db: Session,
    dataset_name: str,
    bucket: str,
    group_by: Optional[str],
    start_date: date,
    end_date: date,
    client_ids: Optional[Sequence[str]],
) -> dict
```

Return shape: `{"dataset": str, "bucket": str, "group_by": str | None, "rows": [{"bucket_start": "YYYY-MM-DD", "group_key": str | None, **measures_as_floats_or_None}], "totals": {**measures}}`. Rows sorted by (bucket_start, group_key). Raises `KeyError` for unknown dataset, `ValueError` for unknown bucket/group_by (routes translate to 422).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_pivot/test_engine.py
"""Engine behavior over the SQL-path datasets, on the standard SQLite test DB.

Seeds minimal ORM rows spanning a week boundary so bucket rollup, grouping,
ratio-of-sums, zero-denominator None, scoping, and coercion are all pinned.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest

from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.production_entry import ProductionEntry
from backend.pivot.engine import run_pivot


def _pe(db, entry_id, client, day, units, run_h, ict, present=5):
    db.add(
        ProductionEntry(
            production_entry_id=entry_id,
            client_id=client,
            product_id=1,
            shift_id=1,
            production_date=datetime(day.year, day.month, day.day, 6),
            shift_date=datetime(day.year, day.month, day.day, 6),
            units_produced=units,
            run_time_hours=Decimal(str(run_h)),
            employees_assigned=present,
            employees_present=present,
            ideal_cycle_time=Decimal(str(ict)) if ict is not None else None,
            entered_by="USR-ADMIN-001",
        )
    )


# NOTE for implementer: product_id=1 / shift_id=1 / entered_by must reference
# rows that exist in the template test DB (the demo-seeded SQLite template).
# Check with a quick query in the test if unsure and adjust to any existing
# product/shift/user PK — the assertion logic below is what matters.


def test_month_bucket_groups_and_ratio_of_sums(db_session):
    # Two entries same month, different ict presence, one excluded from earned
    _pe(db_session, "PVT-1", "PIVOT-CLI", date(2026, 3, 2), 100, 10, 0.05)
    _pe(db_session, "PVT-2", "PIVOT-CLI", date(2026, 3, 9), 200, 10, 0.10)
    db_session.commit()

    out = run_pivot(
        db_session, "production", "month", None,
        date(2026, 3, 1), date(2026, 3, 31), ["PIVOT-CLI"],
    )
    assert out["bucket"] == "month"
    [row] = out["rows"]
    assert row["bucket_start"] == "2026-03-01"
    assert row["units"] == 300
    assert row["run_hours"] == 20.0
    # earned = 100*0.05 + 200*0.10 = 25.0 ; efficiency = 25/20*100 (ratio of SUMS)
    assert row["earned_hours"] == 25.0
    assert row["efficiency_pct"] == pytest.approx(125.0)
    assert out["totals"]["efficiency_pct"] == pytest.approx(125.0)
    # JSON-safe: floats/ints/None/str only
    for v in row.values():
        assert v is None or isinstance(v, (int, float, str))


def test_week_bucket_splits_on_iso_monday(db_session):
    _pe(db_session, "PVT-3", "PIVOT-CLI", date(2026, 8, 2), 10, 1, 0.1)  # Sunday -> wk 7/27
    _pe(db_session, "PVT-4", "PIVOT-CLI", date(2026, 8, 3), 10, 1, 0.1)  # Monday -> wk 8/03
    db_session.commit()
    out = run_pivot(
        db_session, "production", "week", None,
        date(2026, 8, 1), date(2026, 8, 9), ["PIVOT-CLI"],
    )
    assert [r["bucket_start"] for r in out["rows"]] == ["2026-07-27", "2026-08-03"]


def test_zero_denominator_ratio_is_none(db_session):
    _pe(db_session, "PVT-5", "PIVOT-CLI", date(2026, 3, 2), 50, 0, None)
    db_session.commit()
    out = run_pivot(
        db_session, "production", "month", None,
        date(2026, 3, 1), date(2026, 3, 31), ["PIVOT-CLI"],
    )
    [row] = out["rows"]
    assert row["efficiency_pct"] is None
    assert row["excluded_entries"] == 1


def test_group_by_and_share(db_session):
    for i, (reason, cat, minutes) in enumerate(
        [("MECHANICAL_FAILURE", "machine", 90), ("MATERIAL_SHORTAGE", "materials", 30)]
    ):
        db_session.add(
            DowntimeEntry(
                downtime_entry_id=f"PVT-DT-{i}",
                client_id="PIVOT-CLI",
                shift_date=datetime(2026, 3, 2, 6),
                downtime_reason=reason,
                root_cause_category=cat,
                downtime_duration_minutes=minutes,
            )
        )
    db_session.commit()
    out = run_pivot(
        db_session, "downtime", "month", "category",
        date(2026, 3, 1), date(2026, 3, 31), ["PIVOT-CLI"],
    )
    by_key = {r["group_key"]: r for r in out["rows"]}
    assert by_key["machine"]["downtime_hours"] == 1.5
    assert by_key["machine"]["events"] == 1
    assert by_key["machine"]["share_of_window_pct"] == pytest.approx(75.0)
    assert by_key["materials"]["share_of_window_pct"] == pytest.approx(25.0)
    assert out["totals"]["downtime_hours"] == 2.0


def test_client_scope_filters(db_session):
    _pe(db_session, "PVT-6", "PIVOT-CLI", date(2026, 3, 2), 10, 1, 0.1)
    _pe(db_session, "PVT-7", "PIVOT-OTHER", date(2026, 3, 2), 999, 1, 0.1)
    db_session.commit()
    out = run_pivot(
        db_session, "production", "month", None,
        date(2026, 3, 1), date(2026, 3, 31), ["PIVOT-CLI"],
    )
    assert out["totals"]["units"] == 10


def test_unknown_group_by_raises_value_error(db_session):
    with pytest.raises(ValueError):
        run_pivot(
            db_session, "production", "month", "nope",
            date(2026, 3, 1), date(2026, 3, 31), None,
        )
```

Fixture note for the implementer: `db_session` is the function-scoped session from `backend/tests/conftest.py` (clone of the demo-seeded SQLite template). The seeded rows above use fresh client_ids so template data never pollutes assertions. If `ProductionEntry`/`DowntimeEntry` FK targets (`product_id=1`, `shift_id=1`, `entered_by="USR-ADMIN-001"`) don't exist in the template, query the template for any existing PKs and substitute — SQLite in tests may not enforce FKs, but keep the rows honest either way. Client-id rows: if a `CLIENT` FK is enforced, insert two `Client(client_id="PIVOT-CLI"/"PIVOT-OTHER", client_name=...)` rows first (check `backend/orm/client.py` for required fields).

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_pivot/test_engine.py -v` — Expected: FAIL (`backend.pivot.engine` missing)

- [ ] **Step 3: Implement the engine**

```python
# backend/pivot/engine.py
"""Generic pivot execution: one SQL aggregate per (day, group), Python bucket
rollup, ratio-of-sums composition, float coercion (Cycle 4 spec §3)."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.pivot.buckets import VALID_BUCKETS, bucket_start
from backend.pivot.registry import DATASETS, Count, Ratio, Share, Sum


def _as_date(value: Any) -> date:
    # func.date() returns date on MariaDB but str on SQLite
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def run_pivot(
    db: Session,
    dataset_name: str,
    bucket: str,
    group_by: Optional[str],
    start_date: date,
    end_date: date,
    client_ids: Optional[Sequence[str]],
) -> dict:
    ds = DATASETS[dataset_name]  # KeyError -> route 422
    if bucket not in VALID_BUCKETS:
        raise ValueError(f"bucket must be one of {VALID_BUCKETS}")
    if group_by is not None and group_by not in ds.group_bys:
        raise ValueError(f"group_by must be one of {sorted(ds.group_bys)}")

    components = {n: m for n, m in ds.measures.items() if isinstance(m, (Sum, Count))}

    if ds.fetch is not None:
        day_rows = ds.fetch(db, group_by, start_date, end_date, client_ids)
    else:
        day_rows = _sql_day_rows(db, ds, group_by, start_date, end_date, client_ids, components)

    # rollup: (bucket_start, group_key) -> {component: float}
    acc: dict[tuple, dict[str, float]] = defaultdict(lambda: {n: 0.0 for n in components})
    for day, grp, comps in day_rows:
        key = (bucket_start(day, bucket), grp)
        for n in components:
            acc[key][n] += _as_float(comps.get(n))

    window_totals = {n: sum(v[n] for v in acc.values()) for n in components}

    rows = []
    for (b_start, grp) in sorted(acc, key=lambda k: (k[0], str(k[1]))):
        comps = acc[(b_start, grp)]
        row: dict[str, Any] = {"bucket_start": b_start.isoformat(), "group_key": grp}
        row.update(comps)
        row.update(_derived(ds, comps, window_totals))
        rows.append(row)

    totals = dict(window_totals)
    totals.update(_derived(ds, window_totals, window_totals))

    return {
        "dataset": dataset_name,
        "bucket": bucket,
        "group_by": group_by,
        "rows": rows,
        "totals": totals,
    }


def _derived(ds, comps: dict[str, float], window_totals: dict[str, float]) -> dict:
    out: dict[str, Any] = {}
    for name, m in ds.measures.items():
        if isinstance(m, Ratio):
            den = comps.get(m.denominator, 0.0)
            num = comps.get(m.numerator, 0.0)
            out[name] = round(num / den * m.scale, 2) if den > 0 else None
        elif isinstance(m, Share):
            total = window_totals.get(m.of, 0.0)
            out[name] = round(comps.get(m.of, 0.0) / total * 100, 2) if total > 0 else None
    return out


def _sql_day_rows(db, ds, group_by, start_date, end_date, client_ids, components):
    day_expr = func.date(ds.date_column).label("pivot_day")
    cols = [day_expr]
    gb = ds.group_bys[group_by] if group_by else None
    if gb is not None:
        cols.append(gb.expr.label("pivot_grp"))
    names = list(components)
    for n in names:
        m = components[n]
        cols.append(func.count().label(n) if isinstance(m, Count) else func.sum(m.expr).label(n))

    q = db.query(*cols)
    for target, onclause in ds.joins + (gb.joins if gb else ()):
        q = q.outerjoin(target, onclause)
    q = q.filter(func.date(ds.date_column) >= start_date, func.date(ds.date_column) <= end_date)
    for f in ds.base_filters:
        q = q.filter(f)
    if client_ids is not None:
        q = q.filter(ds.client_column.in_(client_ids))
    q = q.group_by(day_expr, *( [gb.expr] if gb else [] ))

    for row in q.all():
        day = _as_date(row[0])
        grp = str(row[1]) if gb is not None and row[1] is not None else (None if gb is None else "unknown")
        comps = {n: row._mapping[n] for n in names}
        yield (day, grp, comps)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_pivot/ -v` — Expected: all PASS. Debug FK/fixture issues per the fixture note (adjust seeded PKs, not assertions).

- [ ] **Step 5: Commit**

```bash
git add backend/pivot/engine.py backend/tests/test_pivot/test_engine.py
git commit -m "feat(pivot): generic engine — day-grain SQL aggregate, Python bucket rollup, ratio-of-sums"
```

---

### Task 4: Quality + holds datasets (SQL path)

**Files:**
- Modify: `backend/pivot/registry.py` (add two datasets to `DATASETS`)
- Test: append to `backend/tests/test_pivot/test_engine.py`

**Interfaces:**
- Produces: `DATASETS["quality"]`, `DATASETS["holds"]` — same `Dataset` shape; consumed by routes (Task 6).

- [ ] **Step 1: Write failing tests (append to test_engine.py)**

```python
def test_quality_fpy_ratio_of_sums(db_session):
    from backend.orm.quality_entry import QualityEntry

    for i, (insp, passed, defects) in enumerate([(100, 90, 12), (50, 25, 30)]):
        db_session.add(
            QualityEntry(
                quality_entry_id=f"PVT-QE-{i}",
                client_id="PIVOT-CLI",
                work_order_id=None,
                shift_date=datetime(2026, 3, 2, 6),
                units_inspected=insp,
                units_passed=passed,
                units_defective=insp - passed,
                total_defects_count=defects,
            )
        )
    db_session.commit()
    out = run_pivot(
        db_session, "quality", "month", None,
        date(2026, 3, 1), date(2026, 3, 31), ["PIVOT-CLI"],
    )
    [row] = out["rows"]
    assert row["inspected"] == 150
    assert row["defects"] == 42
    # FPY ratio-of-sums: (90+25)/150*100 = 76.67 — NOT avg(90%, 50%) = 70
    assert row["fpy_pct"] == pytest.approx(76.67, abs=0.01)


def test_holds_measures(db_session):
    from backend.orm.hold_entry import HoldEntry

    for i, (cat, hours) in enumerate([("Material", 48), ("Material", 24), ("Quality", 12)]):
        db_session.add(
            HoldEntry(
                hold_entry_id=f"PVT-H-{i}",
                client_id="PIVOT-CLI",
                work_order_id="PVT-WO-HOLD",
                hold_status="ON_HOLD",
                hold_date=datetime(2026, 3, 2, 6),
                hold_reason_category=cat,
                hold_reason="MATERIAL_SHORTAGE",
                total_hold_duration_hours=Decimal(str(hours)),
            )
        )
    db_session.commit()
    out = run_pivot(
        db_session, "holds", "month", "reason_category",
        date(2026, 3, 1), date(2026, 3, 31), ["PIVOT-CLI"],
    )
    by_key = {r["group_key"]: r for r in out["rows"]}
    assert by_key["Material"]["holds"] == 2
    assert by_key["Material"]["hold_days"] == 3.0  # 72h / 24
    assert by_key["Material"]["avg_days_per_hold"] == pytest.approx(1.5)
```

Implementer notes: `QualityEntry.work_order_id` is nullable per the ORM (`backend/orm/quality_entry.py:38` shows the FK — verify nullability; if NOT NULL, create one `WorkOrder` fixture row and reference it). `HoldEntry.work_order_id` is NOT NULL — create a minimal `WorkOrder(work_order_id="PVT-WO-HOLD", client_id="PIVOT-CLI", style_model="PVT", planned_quantity=1, entered fields per ORM defaults)` first. `hold_reason` values are catalog strings — `"MATERIAL_SHORTAGE"` style; check `backend/orm/hold_reason_catalog.py` or an existing seeded row for a valid value and substitute if needed.

- [ ] **Step 2: Run to verify failure** — `pytest tests/test_pivot/test_engine.py -v` — new tests FAIL with `KeyError: 'quality'`

- [ ] **Step 3: Implement — add to registry.py**

```python
# additional imports at top of registry.py
from backend.orm.hold_entry import HoldEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.work_order import WorkOrder

# --- quality ----------------------------------------------------------------
_QUALITY = Dataset(
    name="quality",
    model=QualityEntry,
    date_column=QualityEntry.shift_date,
    client_column=QualityEntry.client_id,
    group_bys={
        "client": GroupBy(QualityEntry.client_id),
        "style": GroupBy(
            WorkOrder.style_model,
            joins=((WorkOrder, QualityEntry.work_order_id == WorkOrder.work_order_id),),
        ),
    },
    measures={
        "inspected": Sum(QualityEntry.units_inspected),
        "passed": Sum(QualityEntry.units_passed),
        "defective": Sum(QualityEntry.units_defective),
        "defects": Sum(QualityEntry.total_defects_count),
        "fpy_pct": Ratio("passed", "inspected"),
    },
)

# --- holds ------------------------------------------------------------------
_HOLDS = Dataset(
    name="holds",
    model=HoldEntry,
    date_column=HoldEntry.hold_date,
    client_column=HoldEntry.client_id,
    base_filters=(HoldEntry.hold_date.isnot(None),),
    group_bys={
        "client": GroupBy(HoldEntry.client_id),
        "reason_category": GroupBy(func.coalesce(HoldEntry.hold_reason_category, "uncategorized")),
        "reason": GroupBy(func.coalesce(HoldEntry.hold_reason, "uncategorized")),
    },
    measures={
        "holds": Count(),
        "hold_days": Sum(func.coalesce(HoldEntry.total_hold_duration_hours, 0) / 24.0),
        "avg_days_per_hold": Ratio("hold_days", "holds", scale=1.0),
    },
)

DATASETS["quality"] = _QUALITY
DATASETS["holds"] = _HOLDS
```

(Keep `DATASETS` construction style consistent — either extend the literal dict or assign after; pick one and match the file.)

- [ ] **Step 4: Run tests** — `pytest tests/test_pivot/ -v` — all PASS (guard test auto-covers the new datasets)

- [ ] **Step 5: Commit**

```bash
git add backend/pivot/registry.py backend/tests/test_pivot/test_engine.py
git commit -m "feat(pivot): quality + holds datasets (SQL path)"
```

---

### Task 5: Labor + delivery datasets (fetch hooks) with golden parity

**Files:**
- Create: `backend/pivot/hooks.py`
- Modify: `backend/pivot/registry.py` (register `labor`, `delivery`)
- Test: `backend/tests/test_pivot/test_hooks_golden.py`

**Interfaces:**
- Consumes: `summarize_labor_hours`, `earned_hours`, `billed_hours`, `available_for_efficiency_hours`, `effective_labor_class` from `backend/calculations/labor_hours.py`; `infer_planned_delivery_date` and the counting rules of `calculate_true_otd` from `backend/calculations/otd.py` (lines 286–380); `DelayClassificationEnum` from `backend/orm/delay_taxonomy.py`.
- Produces: fetch hooks with signature `fetch(db, group_by, start_date, end_date, client_ids) -> Iterable[tuple[date, str | None, dict[str, float]]]` (same triple shape `_sql_day_rows` yields), plus `DATASETS["labor"]` and `DATASETS["delivery"]`.

**Why hooks:** labor semantics (allocation category sets, effective-class fallback, unsplit transparency) and delivery semantics (COMPLETED-only, date-inference chain, justified-late) live in existing Python that is NOT SQL-expressible without duplication — reusing the functions verbatim makes the cross-source goldens pass by construction.

- [ ] **Step 1: Write the failing golden tests**

```python
# backend/tests/test_pivot/test_hooks_golden.py
"""Cross-source goldens (spec §8): for the same window/scope the pivot labor
dataset MUST equal summarize_labor_hours, and the pivot delivery dataset MUST
equal calculate_true_otd. These pin engine-vs-KPI consistency structurally —
run against the demo-seeded template DB, no synthetic rows needed."""
from datetime import date

import pytest

from backend.calculations.labor_hours import earned_hours, summarize_labor_hours
from backend.calculations.otd import calculate_true_otd
from backend.pivot.engine import run_pivot

WINDOW = (date(2025, 1, 1), date(2026, 12, 31))


def _demo_client(db_session):
    from backend.orm.client import Client

    client = db_session.query(Client).first()
    assert client is not None, "template DB must be demo-seeded"
    return client.client_id


def test_labor_totals_equal_summarize_labor_hours(db_session):
    cid = _demo_client(db_session)
    golden = summarize_labor_hours(db_session, [cid], *WINDOW)
    out = run_pivot(db_session, "labor", "year", None, *WINDOW, [cid])
    t = out["totals"]
    g = golden["totals"]
    for key in ("scheduled", "actual", "normal", "double", "triple",
                "unsplit_actual", "billed", "available_for_efficiency"):
        assert t[key] == pytest.approx(float(g[key])), key


def test_labor_by_class_equals_golden(db_session):
    cid = _demo_client(db_session)
    golden = summarize_labor_hours(db_session, [cid], *WINDOW)
    out = run_pivot(db_session, "labor", "year", "labor_class", *WINDOW, [cid])
    by_key = {r["group_key"]: r for r in out["rows"]}
    for cls in ("direct", "indirect"):
        if float(golden["by_labor_class"][cls]["actual"]) > 0:
            assert by_key[cls]["actual"] == pytest.approx(
                float(golden["by_labor_class"][cls]["actual"])
            )


def test_labor_efficiency_available_basis_matches_ratio_of_sums(db_session):
    cid = _demo_client(db_session)
    earned, _excluded = earned_hours(db_session, [cid], *WINDOW)
    golden = summarize_labor_hours(db_session, [cid], *WINDOW)
    out = run_pivot(db_session, "labor", "year", None, *WINDOW, [cid])
    avail = float(golden["totals"]["available_for_efficiency"])
    if avail > 0:
        assert out["totals"]["efficiency_available_basis"] == pytest.approx(
            round(float(earned) / avail * 100, 2)
        )


def test_delivery_totals_equal_calculate_true_otd(db_session):
    cid = _demo_client(db_session)
    golden = calculate_true_otd(db_session, cid, *WINDOW)
    out = run_pivot(db_session, "delivery", "year", None, *WINDOW, [cid])
    t = out["totals"]
    # Field names on calculate_true_otd's dict: read backend/calculations/otd.py
    # lines 370-520 to confirm exact keys (true_otd/net percentages + counts)
    # and adjust THESE lookups (never the pivot math) if the golden dict uses
    # different key names.
    assert t["delivered"] == golden["true_otd"]["total_orders"]
    assert t["on_time"] == golden["true_otd"]["on_time_count"]
    if t["delivered"] > 0:
        assert t["otd_gross_pct"] == pytest.approx(float(golden["true_otd"]["percentage"]), abs=0.01)
        assert t["otd_net_pct"] == pytest.approx(float(golden["true_otd"]["net_percentage"]), abs=0.01)
```

Implementer note: before finalizing the delivery assertions, read `backend/calculations/otd.py:370-520` for the exact return-dict keys of `calculate_true_otd` and align the golden lookups. The pivot side must mirror the *counting rules*, and the golden asserts they agree.

- [ ] **Step 2: Run to verify failure** — `pytest tests/test_pivot/test_hooks_golden.py -v` — FAIL with `KeyError: 'labor'`

- [ ] **Step 3: Implement hooks + register datasets**

```python
# backend/pivot/hooks.py
"""Fetch hooks for datasets whose semantics live in existing calculations.

Each hook yields (day, group_key, components) triples — the same shape the
generic SQL path produces — and REUSES the existing calculation functions so
the cross-source goldens hold by construction."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.calculations.labor_hours import (
    available_for_efficiency_hours,
    billed_hours,
    effective_labor_class,
)
from backend.calculations.otd import infer_planned_delivery_date
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.delay_taxonomy import DelayClassificationEnum
from backend.orm.employee import Employee
from backend.orm.production_entry import ProductionEntry
from backend.orm.work_order import WorkOrder, WorkOrderStatus


def fetch_labor(db, group_by, start_date, end_date, client_ids):
    """Per-(day, group) labor components, mirroring summarize_labor_hours
    entry-by-entry (same OT-split transparency, same allocation category sets,
    same effective-class fallback). Also folds in per-day earned hours from
    production entries (entry ict else product default; neither -> excluded)
    so efficiency_available_basis composes as a ratio of sums — earned is only
    attributed when group_by is None or 'client' (production rows carry no
    labor class)."""
    q = db.query(AttendanceEntry).filter(
        func.date(AttendanceEntry.shift_date) >= start_date,
        func.date(AttendanceEntry.shift_date) <= end_date,
    )
    if client_ids is not None:
        q = q.filter(AttendanceEntry.client_id.in_(client_ids))
    entries = q.all()

    class_by_employee = dict(
        db.query(Employee.employee_id, Employee.labor_class).all()
    )

    acc: dict[tuple, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for e in entries:
        day = e.shift_date.date()
        if group_by == "labor_class":
            cls = effective_labor_class(e.labor_class_override, class_by_employee.get(e.employee_id))
            grp = cls if cls in ("direct", "indirect") else "unclassified"
        elif group_by == "client":
            grp = e.client_id
        else:
            grp = None
        c = acc[(day, grp)]
        actual = float(e.actual_hours or 0)
        c["scheduled"] += float(e.scheduled_hours or 0)
        c["actual"] += actual
        if e.normal_hours is not None or e.double_hours is not None or e.triple_hours is not None:
            c["normal"] += float(e.normal_hours or 0)
            c["double"] += float(e.double_hours or 0)
            c["triple"] += float(e.triple_hours or 0)
        else:
            c["unsplit_actual"] += actual
        allocs = [(a.category, a.hours) for a in e.hour_allocations]
        c["billed"] += float(billed_hours(allocs))
        c["available_for_efficiency"] += float(
            available_for_efficiency_hours(Decimal(str(e.actual_hours or 0)), allocs)
        )

    if group_by in (None, "client"):
        pq = db.query(ProductionEntry).filter(
            func.date(ProductionEntry.shift_date) >= start_date,
            func.date(ProductionEntry.shift_date) <= end_date,
        )
        if client_ids is not None:
            pq = pq.filter(ProductionEntry.client_id.in_(client_ids))
        for pe in pq.all():
            ict = pe.ideal_cycle_time
            if ict is None and pe.product is not None:
                ict = pe.product.ideal_cycle_time
            day = pe.shift_date.date()
            grp = pe.client_id if group_by == "client" else None
            c = acc[(day, grp)]
            if ict is None:
                c["excluded_entries"] += 1
            else:
                c["earned_hours"] += float(Decimal(pe.units_produced) * ict)

    for (day, grp), comps in acc.items():
        yield (day, grp, dict(comps))


def fetch_delivery(db, group_by, start_date, end_date, client_ids):
    """Per-(day, group) delivery components mirroring calculate_true_otd's
    counting rules (backend/calculations/otd.py:286-380): COMPLETED orders
    with actual_delivery_date in window; planned date via the inference chain;
    orders with no inferable date are skipped (not in the denominator);
    justified-late per delay_classification."""
    from datetime import datetime

    q = db.query(WorkOrder).filter(
        WorkOrder.status == WorkOrderStatus.COMPLETED,
        WorkOrder.actual_delivery_date.isnot(None),
        WorkOrder.actual_delivery_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.actual_delivery_date <= datetime.combine(end_date, datetime.max.time()),
    )
    if client_ids is not None:
        q = q.filter(WorkOrder.client_id.in_(client_ids))

    acc: dict[tuple, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for wo in q.all():
        inferred = infer_planned_delivery_date(wo)
        if inferred.date is None or wo.actual_delivery_date is None:
            continue  # not inferable -> excluded from denominator (golden rule)
        day = wo.actual_delivery_date.date()
        if group_by == "client":
            grp = wo.client_id
        elif group_by == "style":
            grp = wo.style_model
        elif group_by == "delay_reason":
            grp = wo.justified_delay_reason or "none"
        else:
            grp = None
        c = acc[(day, grp)]
        c["delivered"] += 1
        on_time = wo.actual_delivery_date <= inferred.date
        justified_late = (not on_time) and (
            wo.delay_classification == DelayClassificationEnum.JUSTIFIED.value
        )
        if on_time:
            c["on_time"] += 1
        if justified_late:
            c["justified_late"] += 1
        if on_time or justified_late:
            c["net_on_time"] += 1

    for (day, grp), comps in acc.items():
        yield (day, grp, dict(comps))
```

Registry additions (registry.py) — hook datasets declare their components as documentation-only `Sum(None)` markers? **No** — declare them with `expr=None` NOT allowed by the guard's spirit. Instead add a `Component()` marker dataclass:

```python
@dataclass(frozen=True)
class Component:
    """A summed component produced by a fetch hook (no SQL expr)."""
```

Update the guard test (Task 2 file) so Ratio/Share components may be `Sum | Count | Component`, and the engine's `components` filter includes `Component` (it contributes a 0.0-initialized accumulator; hooks fill it). Then:

```python
from backend.pivot.hooks import fetch_delivery, fetch_labor

_LABOR = Dataset(
    name="labor",
    model=AttendanceEntry,
    date_column=AttendanceEntry.shift_date,
    client_column=AttendanceEntry.client_id,
    fetch=fetch_labor,
    group_bys={
        "client": GroupBy(AttendanceEntry.client_id),
        "labor_class": GroupBy(None),
    },
    measures={
        "scheduled": Component(), "actual": Component(), "normal": Component(),
        "double": Component(), "triple": Component(), "unsplit_actual": Component(),
        "billed": Component(), "available_for_efficiency": Component(),
        "earned_hours": Component(), "excluded_entries": Component(),
        "efficiency_available_basis": Ratio("earned_hours", "available_for_efficiency"),
    },
)

_DELIVERY = Dataset(
    name="delivery",
    model=WorkOrder,
    date_column=WorkOrder.actual_delivery_date,
    client_column=WorkOrder.client_id,
    fetch=fetch_delivery,
    group_bys={
        "client": GroupBy(WorkOrder.client_id),
        "style": GroupBy(WorkOrder.style_model),
        "delay_reason": GroupBy(WorkOrder.justified_delay_reason),
    },
    measures={
        "delivered": Component(), "on_time": Component(),
        "justified_late": Component(), "net_on_time": Component(),
        "otd_gross_pct": Ratio("on_time", "delivered"),
        "otd_net_pct": Ratio("net_on_time", "delivered"),
    },
)

DATASETS["labor"] = _LABOR
DATASETS["delivery"] = _DELIVERY
```

(`GroupBy(None)` for hook-only groupings is fine — hooks compute the group themselves; the guard's date/client assertions still hold. Adjust the guard test if it assumes `expr is not None`.)

Engine caveat: for hook datasets the labor `efficiency_available_basis` must be OMITTED (not 0/None-spammed) from rows/totals when `group_by == "labor_class"` (earned hours carry no class). Simplest rule in `_derived`: omit a Ratio when *neither component key was ever produced* by any row (track produced keys during rollup); `None` still appears when components were produced but the denominator is 0.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_pivot/ -v` — Expected: all PASS. The goldens run against demo-seeded template data — if `test_delivery_*` finds `delivered == 0` in the template, widen `WINDOW` or assert the golden and pivot agree on zero (both sides equal is still the invariant).

- [ ] **Step 5: Commit**

```bash
git add backend/pivot/ backend/tests/test_pivot/
git commit -m "feat(pivot): labor + delivery hook datasets with golden parity vs existing calculations"
```

---

### Task 6: Routes — JSON + CSV, registration, openapi regen

**Files:**
- Create: `backend/routes/pivot.py`
- Modify: `backend/bootstrap/routers.py`
- Modify: `backend/tests/test_bootstrap/openapi_surface.json` (regenerated)
- Test: `backend/tests/test_routes/test_pivot_routes.py`

**Interfaces:**
- Consumes: `run_pivot` (Task 3), `DATASETS`, `VALID_BUCKETS`; `get_current_user`, `resolve_client_scope`, `ClientScope` from `backend/auth/jwt.py`; `validate_date_range` from `backend/utils/date_range.py`.
- Produces: `GET /api/pivot/{dataset}` and `GET /api/pivot/{dataset}/csv`, router exported as `router`, tag `"Pivot Summaries"`.

- [ ] **Step 1: Write the failing route tests**

Mirror the TestClient + auth-header pattern of `backend/tests/test_routes/test_attendance_labor_capture.py` (Cycle 3's route tests — copy its client/auth fixtures/imports exactly).

```python
# backend/tests/test_routes/test_pivot_routes.py
"""Route tests for /api/pivot (Cycle 4 PR-A): shape, 422 allow-lists, scope
enforcement, CSV parity, JSON-number wire types."""


def test_pivot_labor_month_200_shape(client, admin_headers):
    r = client.get(
        "/api/pivot/labor",
        params={"bucket": "month", "start_date": "2025-01-01", "end_date": "2026-12-31"},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dataset"] == "labor"
    assert body["bucket"] == "month"
    assert set(body) >= {"dataset", "bucket", "group_by", "rows", "totals"}
    for row in body["rows"]:
        assert isinstance(row["bucket_start"], str)
        for k, v in row.items():
            if k not in ("bucket_start", "group_key"):
                assert v is None or isinstance(v, (int, float)), (k, type(v))


def test_unknown_dataset_422(client, admin_headers):
    r = client.get(
        "/api/pivot/nope",
        params={"bucket": "month", "start_date": "2026-01-01", "end_date": "2026-02-01"},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_unknown_bucket_422(client, admin_headers):
    r = client.get(
        "/api/pivot/production",
        params={"bucket": "fortnight", "start_date": "2026-01-01", "end_date": "2026-02-01"},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_unknown_group_by_422_names_allow_list(client, admin_headers):
    r = client.get(
        "/api/pivot/production",
        params={
            "bucket": "month", "group_by": "nope",
            "start_date": "2026-01-01", "end_date": "2026-02-01",
        },
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert "group_by" in r.text


def test_unauthenticated_401(client):
    r = client.get(
        "/api/pivot/production",
        params={"bucket": "month", "start_date": "2026-01-01", "end_date": "2026-02-01"},
    )
    assert r.status_code == 401


def test_scoped_user_cannot_read_other_client(client, operator_a_headers):
    # operator assigned to client A requesting client B explicitly -> 403
    # (resolve_client_scope's contract; reuse the two-client fixtures from
    # test_attendance_labor_capture.py / the uniform-scope test module)
    r = client.get(
        "/api/pivot/production",
        params={
            "bucket": "month", "client_id": "CLIENT-B",
            "start_date": "2026-01-01", "end_date": "2026-02-01",
        },
        headers=operator_a_headers,
    )
    assert r.status_code == 403


def test_csv_matches_json_rows(client, admin_headers):
    params = {"bucket": "year", "start_date": "2025-01-01", "end_date": "2026-12-31"}
    j = client.get("/api/pivot/downtime", params=params, headers=admin_headers).json()
    r = client.get("/api/pivot/downtime/csv", params=params, headers=admin_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = [ln for ln in r.text.strip().splitlines() if ln]
    assert len(lines) == len(j["rows"]) + 1  # header + rows
```

Implementer note: fixture names (`client`, `admin_headers`, `operator_a_headers`) must be replaced with whatever `test_attendance_labor_capture.py` actually uses — copy its exact fixture set; the 403 test's client ids come from those fixtures.

- [ ] **Step 2: Run to verify failure** — `pytest tests/test_routes/test_pivot_routes.py -v` — FAIL with 404s (route absent)

- [ ] **Step 3: Implement the routes + registration**

```python
# backend/routes/pivot.py
"""Pivot summary API (Cycle 4 PR-A, spec §5): pre-defined time buckets and
groupings over the dataset registry; CSV twin per the data-first position."""
import csv
import io
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.auth.jwt import ClientScope, get_current_user, resolve_client_scope
from backend.database import get_db
from backend.orm.user import User
from backend.pivot.buckets import VALID_BUCKETS
from backend.pivot.engine import run_pivot
from backend.pivot.registry import DATASETS
from backend.utils.date_range import validate_date_range

router = APIRouter(prefix="/api/pivot", tags=["Pivot Summaries"])


def _run(db, dataset, bucket, group_by, start_date, end_date, scope) -> dict:
    if dataset not in DATASETS:
        raise HTTPException(422, detail=f"dataset must be one of {sorted(DATASETS)}")
    if bucket not in VALID_BUCKETS:
        raise HTTPException(422, detail=f"bucket must be one of {list(VALID_BUCKETS)}")
    allowed = sorted(DATASETS[dataset].group_bys)
    if group_by is not None and group_by not in allowed:
        raise HTTPException(422, detail=f"group_by must be one of {allowed}")
    validate_date_range(start_date, end_date)
    return run_pivot(db, dataset, bucket, group_by, start_date, end_date, scope.client_ids)


@router.get("/{dataset}")
def get_pivot(
    dataset: str,
    bucket: str,
    start_date: date,
    end_date: date,
    group_by: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> Any:
    return _run(db, dataset, bucket, group_by, start_date, end_date, scope)


@router.get("/{dataset}/csv")
def get_pivot_csv(
    dataset: str,
    bucket: str,
    start_date: date,
    end_date: date,
    group_by: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> StreamingResponse:
    result = _run(db, dataset, bucket, group_by, start_date, end_date, scope)
    buf = io.StringIO()
    fieldnames = ["bucket_start", "group_key"] + [
        k for k in (result["rows"][0] if result["rows"] else result["totals"])
        if k not in ("bucket_start", "group_key")
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in result["rows"]:
        writer.writerow(row)
    buf.seek(0)
    filename = f"pivot_{dataset}_{bucket}_{start_date}_{end_date}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

Registration in `backend/bootstrap/routers.py` — next to the export router (line ~59/279 pattern):

```python
from backend.routes.pivot import router as pivot_router
# ... alongside app.include_router(export_router):
app.include_router(pivot_router)
```

Check `resolve_client_scope`'s actual dependency signature in `backend/auth/jwt.py:332` — if it reads `client_id` itself as a query param (the labor-hours route at `backend/routes/kpi/labor_hours.py:27-34` shows the working pattern), keep this route's `client_id` param identical to that file's.

- [ ] **Step 4: Run route tests** — `pytest tests/test_routes/test_pivot_routes.py -v` — all PASS

- [ ] **Step 5: Regenerate the OpenAPI surface golden and verify**

```bash
cd backend/..  # repo root
python -c "
from backend.tests.test_bootstrap.test_openapi_surface import SNAP, current_surface
import json
json.dump(current_surface(), open(SNAP, 'w'), indent=2)
print('regenerated', SNAP)
"
cd backend && pytest tests/test_bootstrap/test_openapi_surface.py -v
```
Expected: PASS. `git diff` on the JSON must show ONLY the two new `/api/pivot` routes (+ tag if tags changed) — anything else means an accidental surface change: stop and investigate.

- [ ] **Step 6: Check the permission-matrix / static auth guards**

```bash
cd backend && pytest tests/test_routes/test_permission_matrix.py tests/ -k "matrix or static_guard or authorization" -v
```
If a guard enumerates route surfaces and flags `/api/pivot/*`, add the new routes to its expectations following that test's documented pattern (authenticated read tier — same as `/api/kpi/labor-hours`).

- [ ] **Step 7: Commit**

```bash
git add backend/routes/pivot.py backend/bootstrap/routers.py backend/tests/test_bootstrap/openapi_surface.json backend/tests/test_routes/test_pivot_routes.py
git commit -m "feat(pivot): /api/pivot/{dataset} + /csv routes, scope-enforced, openapi surface regen"
```

---

### Task 7: Full verification + spec amendment

**Files:**
- Modify: `docs/superpowers/specs/2026-08-06-pivot-summarization-layer-design.md` (two amendments)
- No other code changes expected.

- [ ] **Step 1: Amend the spec to match the implemented mechanism** (doc-veracity rule)

In §3, replace the sentence describing SQL-side bucketing with: bucketing happens as a per-day SQL aggregate (`func.date`, the portable idiom) rolled up into buckets in pure Python (`backend/pivot/buckets.py`), eliminating dialect-specific date SQL entirely. In §4, note that (a) the labor and delivery datasets use fetch hooks reusing `summarize_labor_hours`-family and `calculate_true_otd`-family logic verbatim (goldens by construction), and (b) the Q5 WIP-aging triad is served to the PR-B view by the existing WIP-aging endpoints, not duplicated as a pivot measure.

- [ ] **Step 2: Run the full backend suite with coverage**

```bash
cd backend && pytest tests/
```
Expected: 0 failures, coverage ≥ 75 % (currently 81.88 % — new package is fully tested, so it must not drop). If any pre-existing test fails, STOP and investigate before proceeding — do not skip or weaken it.

- [ ] **Step 3: Run pre-commit on changed files**

```bash
pre-commit run --files $(git diff --name-only main...HEAD | tr '\n' ' ')
```
Expected: all hooks pass (fix any flake8/format findings).

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-08-06-pivot-summarization-layer-design.md
git commit -m "docs(spec): pivot Cycle 4 — record Python-rollup bucketing + hook-dataset amendments"
```

- [ ] **Step 5: Ship sequence (user-gated)**

Push branch; run `/cross-review`; open PR only after the user confirms (standing rule: user-confirmed merges). PR body lists: new package `backend/pivot/`, 2 routes, openapi regen, goldens, zero migrations.

---

## Self-Review (completed at write time)

- **Spec coverage:** §3 engine (Tasks 1–3), §4 datasets (Tasks 2, 4, 5 — `transitions` is PR-C by spec), §5 API + CSV + 422 + openapi (Task 6), §8 structural guard + goldens + bucketing edges + one-assert discipline (Tasks 1, 2, 5, 6), §9 PR-A boundary respected (no frontend, no derivations). §10-A live-verify happens post-merge per ship tradition, not in this plan.
- **Placeholder scan:** the two "check the actual key/fixture names" notes are deliberate read-the-file instructions with exact file:line pointers, not deferred design.
- **Type consistency:** `run_pivot` signature identical in Tasks 3/5/6; `Component` marker introduced in Task 5 explicitly amends the Task 2 guard; fetch-hook triple shape matches `_sql_day_rows` output.
