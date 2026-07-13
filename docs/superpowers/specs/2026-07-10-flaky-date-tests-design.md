# Deterministic Clock Freeze for Date-Boundary Tests — Design

**Date:** 2026-07-10
**Status:** Design approved (user, 2026-07-10) — pending implementation plan
**Trigger:** PR #134 CI failed `backend-tests` at 23:58 UTC: `test_end_sets_today` asserted `end_date == TODAY` but got `date(2026,7,11) == date(2026,7,10)`. Unrelated to that PR — a pre-existing flaky test that fails in the minutes straddling UTC midnight. Fixing per the no-tech-debt directive.

## Root cause

Three test files capture the current date **at module import time** and compare it against production code that computes the date **at call time**:

- `TODAY = date.today()` (module level) — `test_crud/test_employee_line_assignment_crud.py:32`, `test_services/test_capacity_services.py:75`, `test_routes/test_employee_line_assignment_routes.py:26` (the last `.isoformat()`).
- Production computes `date.today()` when the code runs: `backend/crud/employee_line_assignment.py:32,352`; `backend/services/capacity/mrp_service.py:99` (`run_date`); `backend/services/capacity/scheduling_service.py:277` (`committed_at`).

When the test module is imported at 23:58 UTC (`TODAY`=day N) and a test runs after midnight (production computes day N+1), the equality fails. A second, narrower form compares a stored value to a **freshly-recomputed** `date.today()` in the assertion itself (`test_capacity_services.py:468` `run_date`, `:857` `committed_at`; `test_routes:543` `end_date`) — raceable only at the exact midnight tick, but still non-deterministic.

`freezegun` is **not** installed, and adding it would route through the hash-pinned `requirements.lock` process (C4) — out of proportion for a test-hygiene fix.

## Design (Approach A — deterministic freeze, dependency-free, test-only)

Freeze `date.today()` to a fixed value inside these tests by monkeypatching the `date` symbol in each **production module the test exercises**, and pin each file's `TODAY` to that same fixed value. No production code changes; no new dependency; assertions stay exact `==`.

### Component 1 — shared helper `backend/tests/_time.py` (new)

```python
from datetime import date

FROZEN_TODAY = date(2026, 6, 15)  # arbitrary fixed, mid-month (no month/year-boundary surprises)


class _FrozenDate(date):
    @classmethod
    def today(cls):
        return FROZEN_TODAY


def freeze_today(monkeypatch, *module_names: str) -> date:
    """Patch `date` to _FrozenDate in each named production module so its
    `date.today()` returns FROZEN_TODAY deterministically. Returns FROZEN_TODAY."""
    import importlib
    for name in module_names:
        mod = importlib.import_module(name)
        monkeypatch.setattr(mod, "date", _FrozenDate)
    return FROZEN_TODAY
```

`_FrozenDate` subclasses `date`, so `date(y, m, d)` construction, `timedelta` arithmetic, `isinstance(x, date)`, and ordering all keep working; only `.today()` is pinned. `monkeypatch` auto-reverts after each test.

### Component 2 — per-file autouse fixtures + fixed `TODAY`

Each file replaces its live `TODAY = date.today()` with `TODAY = FROZEN_TODAY` (imported from `_time`), adds an `autouse` fixture that freezes the production modules it exercises, and switches call-time `== date.today()` assertions to `== TODAY`:

- **`test_crud/test_employee_line_assignment_crud.py`** — freeze `backend.crud.employee_line_assignment`. `TODAY = FROZEN_TODAY`. (No `== date.today()` asserts beyond `TODAY`.)
- **`test_routes/test_employee_line_assignment_routes.py`** — freeze `backend.crud.employee_line_assignment` (routes delegate to the CRUD). `TODAY = FROZEN_TODAY.isoformat()`. Change the assert at line 543 from `== date.today().isoformat()` to `== TODAY`.
- **`test_services/test_capacity_services.py`** — freeze `backend.services.capacity.mrp_service` and `backend.services.capacity.scheduling_service` (the modules whose `date.today()` feeds asserted values). `TODAY = FROZEN_TODAY`. Change line 468 `run_date == date.today()` and line 857 `committed_at == date.today()` to `== TODAY`.

The autouse fixture pattern (each file):

```python
import pytest
from backend.tests._time import FROZEN_TODAY, freeze_today

TODAY = FROZEN_TODAY  # (or FROZEN_TODAY.isoformat() in the routes file)

@pytest.fixture(autouse=True)
def _freeze_clock(monkeypatch):
    freeze_today(monkeypatch, "backend.crud.employee_line_assignment")  # per-file module list
```

### Completeness — verify the module list is exhaustive

For each file, after wiring, grep the production modules the test imports/calls for `date.today()`/`datetime.now()` whose result feeds an **asserted** value, and confirm every such module is in that file's `freeze_today(...)` list. The three modules named above cover today's asserts; the implementer confirms no asserted value still reads a live clock (search each test for `date.today()`/`datetime.now()` after the change — only `FROZEN_TODAY`/`TODAY` should remain).

## Testing

- The existing tests in all three files pass under the freeze (values now compare against the frozen date on both sides). No new test logic; the fix is the determinism itself.
- **Determinism proof:** the freeze makes `date.today()` return `FROZEN_TODAY` (2026-06-15) irrespective of the wall clock, so the previously-failing `test_end_sets_today` / `test_future_end_date_is_active` (and the capacity/route asserts) can no longer straddle midnight. A reviewer can confirm by reading that no asserted value derives from a live clock after the change.
- Full backend suite green from `backend/` (`pytest tests/`), coverage ≥ 75% (unchanged — test-only edits).

## Definition of done

- No module-level `TODAY = date.today()` and no `== date.today()`/`datetime.now()` assertion against a live clock remains in the three files; all resolve to `FROZEN_TODAY`/`TODAY`.
- `backend/tests/_time.py` provides the single shared freeze helper.
- Full backend suite green; all 7 CI checks green; `/code-review` + `/cross-review`; merge on user confirmation. (No deploy needed — test-only, no runtime behavior change.)

## Out of scope

- Adding `freezegun`/`time-machine` (rejected — dependency + lock-process churn).
- Changing production date handling (the production `date.today()` calls are correct; only the tests were non-deterministic).
- Auditing other test files for unrelated flakiness — this fix targets the three files with the module-level-date anti-pattern found in the sweep. If the implementer's completeness grep surfaces the identical anti-pattern in another file, it joins this fix (self-audit); otherwise no speculative expansion.
