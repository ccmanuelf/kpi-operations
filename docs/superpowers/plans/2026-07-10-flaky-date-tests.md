# Deterministic Clock Freeze for Date-Boundary Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the UTC-midnight flaky-test race in three backend test files by freezing `date.today()` to a fixed value deterministically, dependency-free, test-only.

**Architecture:** A shared helper `backend/tests/_time.py` exposes `FROZEN_TODAY` and `freeze_today(monkeypatch, *module_names)`, which monkeypatches the `date` symbol in named production modules to a `_FrozenDate` subclass whose `.today()` returns `FROZEN_TODAY`. Each of the three test files pins `TODAY = FROZEN_TODAY`, adds an autouse fixture freezing the production modules it exercises, and converts call-time `== date.today()` assertions to `== TODAY`.

**Tech Stack:** pytest, `pytest.MonkeyPatch`, `datetime.date` (stdlib) — no new dependency.

**Spec:** `docs/superpowers/specs/2026-07-10-flaky-date-tests-design.md`.

## Global Constraints

- No new dependency (freezegun/time-machine rejected). Test-only changes; **no production code edits**.
- `FROZEN_TODAY = date(2026, 6, 15)` (mid-month, avoids month/year-boundary arithmetic surprises).
- After the change, NO module-level `TODAY = date.today()` and NO assertion comparing against a live `date.today()`/`datetime.now()` may remain in the three files — all resolve to `FROZEN_TODAY`/`TODAY`.
- `backend/tests/__init__.py` exists, so `from backend.tests._time import ...` resolves.
- Permissive assertions forbidden (keep exact `==`; no `in [...]`).
- Backend tests run from `backend/`: `pytest tests/…`, coverage ≥ 75% (unchanged — test-only).
- Conventional commits. Files under 500 lines.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/tests/_time.py` | Create | `FROZEN_TODAY` + `_FrozenDate` + `freeze_today(monkeypatch, *modules)` |
| `backend/tests/test_db/test_time_helper.py` | Create | Unit-proves `freeze_today` pins a real module's `date.today()` |
| `backend/tests/test_crud/test_employee_line_assignment_crud.py` | Modify (L7-8, L32; add fixture) | Fixed TODAY + freeze the CRUD module |
| `backend/tests/test_routes/test_employee_line_assignment_routes.py` | Modify (L8, L26, L543; add fixture) | Fixed TODAY + freeze the CRUD module + convert the end_date assert |
| `backend/tests/test_services/test_capacity_services.py` | Modify (L16, L75, L468, L857; add fixture) | Fixed TODAY + freeze mrp/scheduling + convert two asserts |

---

### Task 1: The freeze helper + its unit test

**Files:**
- Create: `backend/tests/_time.py`
- Test: `backend/tests/test_db/test_time_helper.py`

**Interfaces:**
- Produces: `FROZEN_TODAY: date` (== `date(2026, 6, 15)`); `freeze_today(monkeypatch: pytest.MonkeyPatch, *module_names: str) -> date` — patches `date` to `_FrozenDate` in each named module so its `date.today()` returns `FROZEN_TODAY`; returns `FROZEN_TODAY`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_db/test_time_helper.py`:

```python
"""The freeze_today test helper must deterministically pin date.today() in a
named production module to FROZEN_TODAY (dependency-free clock freeze)."""

from datetime import date

from backend.tests._time import FROZEN_TODAY, freeze_today


def test_frozen_today_is_the_fixed_date():
    assert FROZEN_TODAY == date(2026, 6, 15)


def test_freeze_today_pins_a_module_date_today(monkeypatch):
    import backend.crud.employee_line_assignment as mod

    # Real today (whatever it is) must differ from the frozen date most days;
    # after freezing, the module's date.today() returns exactly FROZEN_TODAY.
    returned = freeze_today(monkeypatch, "backend.crud.employee_line_assignment")
    assert returned == FROZEN_TODAY
    assert mod.date.today() == FROZEN_TODAY


def test_frozen_date_still_constructs_and_compares(monkeypatch):
    import backend.crud.employee_line_assignment as mod

    freeze_today(monkeypatch, "backend.crud.employee_line_assignment")
    # date(...) construction and isinstance still behave (subclass of date).
    explicit = mod.date(2026, 1, 1)
    assert explicit == date(2026, 1, 1)
    assert isinstance(mod.date.today(), date)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && pytest tests/test_db/test_time_helper.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'backend.tests._time'`.

- [ ] **Step 3: Write the helper**

Create `backend/tests/_time.py`:

```python
"""Deterministic clock freeze for date-boundary tests (dependency-free).

Some tests capture the current date at import time and compare it against
production code that computes `date.today()` at call time; across UTC midnight
those disagree and the test flakes. `freeze_today` patches the `date` symbol in
named production modules to a subclass whose `today()` returns a fixed date, so
both sides see the same day. Test-only; `monkeypatch` reverts after each test.
"""

import importlib
from datetime import date

import pytest

FROZEN_TODAY = date(2026, 6, 15)  # mid-month: no month/year-boundary arithmetic surprises


class _FrozenDate(date):
    """A date whose today() is pinned. Subclassing date keeps construction,
    arithmetic, ordering, and isinstance() working; only today() is overridden."""

    @classmethod
    def today(cls) -> date:
        return FROZEN_TODAY


def freeze_today(monkeypatch: "pytest.MonkeyPatch", *module_names: str) -> date:
    """Patch `date` to `_FrozenDate` in each named production module so its
    `date.today()` returns FROZEN_TODAY. Returns FROZEN_TODAY for convenience.

    Each module must reference `date` as a module global (i.e. `from datetime
    import date`), which the target modules do.
    """
    for name in module_names:
        module = importlib.import_module(name)
        monkeypatch.setattr(module, "date", _FrozenDate)
    return FROZEN_TODAY
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd backend && pytest tests/test_db/test_time_helper.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/_time.py backend/tests/test_db/test_time_helper.py
git commit -m "test(time): dependency-free freeze_today helper for date-boundary determinism"
```

---

### Task 2: Wire the three flaky test files to the freeze

**Files:**
- Modify: `backend/tests/test_crud/test_employee_line_assignment_crud.py`
- Modify: `backend/tests/test_routes/test_employee_line_assignment_routes.py`
- Modify: `backend/tests/test_services/test_capacity_services.py`

**Interfaces:**
- Consumes: `FROZEN_TODAY`, `freeze_today` from `backend.tests._time` (Task 1).

- [ ] **Step 1: Wire `test_crud/test_employee_line_assignment_crud.py`**

After the existing import block (the `from datetime import date, timedelta` is line 7), add the helper import:

```python
from backend.tests._time import FROZEN_TODAY, freeze_today
```

Replace line 32 `TODAY = date.today()` with:

```python
TODAY = FROZEN_TODAY
```

(Lines 33-34 `YESTERDAY`/`TOMORROW` derive from `TODAY` — leave them; they now derive from `FROZEN_TODAY`.)

Immediately after the `TODAY`/`YESTERDAY`/`TOMORROW` constants (after line 34), add the autouse fixture:

```python
@pytest.fixture(autouse=True)
def _freeze_clock(monkeypatch):
    """Pin date.today() in the CRUD under test so end_date/effective-date defaults
    are deterministic across the UTC-midnight boundary."""
    freeze_today(monkeypatch, "backend.crud.employee_line_assignment")
```

- [ ] **Step 2: Run that file**

Run: `cd backend && pytest tests/test_crud/test_employee_line_assignment_crud.py -q`
Expected: all pass (including `test_end_sets_today`, `test_future_end_date_is_active`).

- [ ] **Step 3: Wire `test_routes/test_employee_line_assignment_routes.py`**

After line 8 (`from datetime import date`), add:

```python
from backend.tests._time import FROZEN_TODAY, freeze_today
```

Replace line 26 `TODAY = date.today().isoformat()` with:

```python
TODAY = FROZEN_TODAY.isoformat()
```

After that constant, add the autouse fixture (routes delegate to the CRUD, whose `date.today()` sets `end_date`):

```python
@pytest.fixture(autouse=True)
def _freeze_clock(monkeypatch):
    """Pin date.today() in the CRUD the routes delegate to, so end_date defaults
    are deterministic across the UTC-midnight boundary."""
    freeze_today(monkeypatch, "backend.crud.employee_line_assignment")
```

Change the assertion at line 543 from:

```python
        assert data["end_date"] == date.today().isoformat()
```

to:

```python
        assert data["end_date"] == TODAY
```

- [ ] **Step 4: Run that file**

Run: `cd backend && pytest tests/test_routes/test_employee_line_assignment_routes.py -q`
Expected: all pass.

- [ ] **Step 5: Wire `test_services/test_capacity_services.py`**

After line 16 (`from datetime import date, timedelta`), add:

```python
from backend.tests._time import FROZEN_TODAY, freeze_today
```

Replace line 75 `TODAY = date.today()` with:

```python
TODAY = FROZEN_TODAY
```

(Lines 76-77 `PERIOD_START`/`PERIOD_END` derive from `TODAY` — leave them.)

After the `PERIOD_START`/`PERIOD_END` constants, add the autouse fixture freezing the two modules whose `date.today()` feeds asserted values (`mrp_service` → `run_date`, `scheduling_service` → `committed_at`):

```python
@pytest.fixture(autouse=True)
def _freeze_clock(monkeypatch):
    """Pin date.today() in the capacity services whose call-time date feeds
    asserted values (run_date, committed_at), for midnight-boundary determinism."""
    freeze_today(
        monkeypatch,
        "backend.services.capacity.mrp_service",
        "backend.services.capacity.scheduling_service",
    )
```

Change the assertion at line 468 from `assert result.run_date == date.today()` to:

```python
        assert result.run_date == TODAY
```

Change the assertion at line 857 from `assert committed.committed_at == date.today()` to:

```python
        assert committed.committed_at == TODAY
```

- [ ] **Step 6: Run that file**

Run: `cd backend && pytest tests/test_services/test_capacity_services.py -q`
Expected: all pass. If any test still fails because a stored value read a live clock from a capacity module NOT in the freeze list, add that module name to the `_freeze_clock` list here and re-run (completeness — see Step 7).

- [ ] **Step 7: Completeness grep — no live-clock assert remains in the three files**

Run:
```bash
cd backend && grep -nE "date\.today\(\)|datetime\.now\(|datetime\.utcnow\(" \
  tests/test_crud/test_employee_line_assignment_crud.py \
  tests/test_routes/test_employee_line_assignment_routes.py \
  tests/test_services/test_capacity_services.py
```
Expected: **no matches** (every occurrence replaced by `FROZEN_TODAY`/`TODAY`). If a match remains, it is either a leftover assert to convert to `TODAY`, or a module whose clock must be added to that file's `freeze_today(...)` — resolve before proceeding.

- [ ] **Step 8: Run the full backend suite (coverage gate + no regressions)**

Run: `cd backend && pytest tests/ -q`
Expected: all pass, coverage ≥ 75%.

- [ ] **Step 9: Commit**

```bash
git add backend/tests/test_crud/test_employee_line_assignment_crud.py backend/tests/test_routes/test_employee_line_assignment_routes.py backend/tests/test_services/test_capacity_services.py
git commit -m "test: freeze the clock in date-boundary tests (fixes UTC-midnight flake)"
```

---

## Verification (whole-PR definition of done)

1. `cd backend && pytest tests/` — all pass, coverage ≥ 75%.
2. The completeness grep (Task 2 Step 7) returns no matches — no live-clock read remains in the three files.
3. `git diff main...HEAD --stat` shows ONLY the two new files + the three test files (no production code changed).
4. Final whole-branch review + `/code-review` + `/cross-review`; all 7 CI checks green; merge on user confirmation.
5. No deploy needed (test-only; no runtime behavior change).
