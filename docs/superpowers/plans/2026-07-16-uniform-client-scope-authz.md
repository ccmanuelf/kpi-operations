# Uniform Client-Scope Authorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 28 copies of a trust-the-caller client-scoping block with one shared authorization dependency, so a scoped user requesting an unauthorized `client_id` gets 403 while admin/poweruser (all clients) and multi-client leaders keep their access.

**Architecture:** A `ClientScope` value object + `resolve_client_scope` FastAPI dependency in `backend/auth/jwt.py`, delegating to the vetted `middleware/client_auth.py` primitives. Every vulnerable endpoint swaps its inline block for `scope: ClientScope = Depends(resolve_client_scope)` and applies `scope.filter(col)` (SQL filter) or `scope.as_single()` (scalar service arg).

**Tech Stack:** FastAPI, SQLAlchemy (SQLite + MariaDB portable), pytest, Playwright/browser agent for the e2e smoke test.

## Global Constraints

- **The migration recipe (apply verbatim at every site):**
  1. Delete the 3-line inline block:
     ```python
     effective_client_id = client_id
     if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
         effective_client_id = current_user.client_id_assigned
     ```
  2. Add `scope: ClientScope = Depends(resolve_client_scope)` to the endpoint signature. **Keep** the existing `client_id: Optional[str]` param and `current_user` param as-is (FastAPI de-dupes the shared `client_id` query param; `current_user` documents auth).
  3. SQL filter: `if effective_client_id: X = X.filter(Col == effective_client_id)` → `X = X.filter(scope.filter(Col))` (unconditional; `scope.filter` returns `true()` for all-clients).
  4. Scalar service arg: `service(..., effective_client_id, ...)` → `service(..., scope.as_single(), ...)`.
  5. Response echo: `"client_id": effective_client_id` → `"client_id": client_id`.
- **Do not** change the `client_auth.py` primitives, the role model, JWT contents, or any service function signature (services keep `Optional[str]`).
- **OpenAPI unchanged:** the `client_id` query param stays on every endpoint, so `test_openapi_surface.py` (route paths + tags) must stay green **without** regenerating the snapshot. If it fails, a signature change dropped/renamed a route — revert that, don't regenerate.
- **403 comes from `ClientAccessError`** (a 403 `HTTPException` subclass in `client_auth.py`); the multi-client-leader-on-a-scalar-endpoint case is a **400** from `ClientScope.as_single`.
- Portability: `sqlalchemy.true()` and `.in_(tuple)` render on SQLite + MariaDB.
- Backend coverage gate ≥75% stays green; every existing tenant-isolation test stays green.
- Test role fixtures (in `backend/tests/conftest.py`): `admin_user` (client_id_assigned=None), `operator_user_client_a` ("CLIENT-A"), `operator_user_client_b` ("CLIENT-B"), `leader_user_multi_client` ("CLIENT-A,CLIENT-B").

---

### Task 1: Core unit — ClientScope + resolve_client_scope + unit tests

**Files:**
- Modify: `backend/auth/jwt.py` (add imports + `ClientScope` + `resolve_client_scope`)
- Test: `backend/tests/test_security/test_client_scope.py` (create)

**Interfaces:**
- Produces:
  - `class ClientScope` — `client_ids: Optional[tuple[str, ...]]` (None = all); `.filter(column)` → SQLAlchemy clause; `.as_single() -> Optional[str]` (raises 400 if >1).
  - `def resolve_client_scope(client_id=Query(None), current_user=Depends(get_current_user), db=Depends(get_db)) -> ClientScope`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_security/test_client_scope.py
import pytest
from fastapi import HTTPException
from sqlalchemy import Column, String
from backend.auth.jwt import ClientScope, resolve_client_scope
from backend.middleware.client_auth import ClientAccessError

_col = Column("client_id", String)


def test_scope_filter_all_is_true_clause():
    # None client_ids -> a clause that filters nothing (renders as a truthy constant)
    clause = ClientScope(None).filter(_col)
    assert "true" in str(clause).lower() or "1 = 1" in str(clause)


def test_scope_filter_uses_in_for_concrete_clients():
    assert "IN" in str(ClientScope(("CLIENT-A", "CLIENT-B")).filter(_col)).upper()


def test_as_single_none_one_and_many():
    assert ClientScope(None).as_single() is None
    assert ClientScope(("CLIENT-A",)).as_single() == "CLIENT-A"
    with pytest.raises(HTTPException) as e:
        ClientScope(("CLIENT-A", "CLIENT-B")).as_single()
    assert e.value.status_code == 400


def test_resolve_admin_all_and_narrow(admin_user):
    assert resolve_client_scope(client_id=None, current_user=admin_user, db=None).client_ids is None
    assert resolve_client_scope(client_id="CLIENT-X", current_user=admin_user, db=None).client_ids == ("CLIENT-X",)


def test_resolve_operator_own_ok(operator_user_client_a):
    assert resolve_client_scope(client_id="CLIENT-A", current_user=operator_user_client_a, db=None).client_ids == ("CLIENT-A",)
    # omitted -> their own single client
    assert resolve_client_scope(client_id=None, current_user=operator_user_client_a, db=None).client_ids == ("CLIENT-A",)


def test_resolve_operator_other_client_forbidden(operator_user_client_a):
    with pytest.raises(ClientAccessError) as e:
        resolve_client_scope(client_id="CLIENT-B", current_user=operator_user_client_a, db=None)
    assert e.value.status_code == 403


def test_resolve_leader_multi(leader_user_multi_client):
    # one of theirs -> that one
    assert resolve_client_scope(client_id="CLIENT-B", current_user=leader_user_multi_client, db=None).client_ids == ("CLIENT-B",)
    # not theirs -> 403
    with pytest.raises(ClientAccessError):
        resolve_client_scope(client_id="CLIENT-C", current_user=leader_user_multi_client, db=None)
    # omitted -> full authorized set
    assert set(resolve_client_scope(client_id=None, current_user=leader_user_multi_client, db=None).client_ids) == {"CLIENT-A", "CLIENT-B"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_security/test_client_scope.py -v`
Expected: FAIL — `ImportError: cannot import name 'ClientScope'`.

- [ ] **Step 3: Write minimal implementation**

Add to the imports at the top of `backend/auth/jwt.py`:
- change `from fastapi import Depends, HTTPException, Request, status` → add `Query`: `from fastapi import Depends, HTTPException, Query, Request, status`
- add `from dataclasses import dataclass`
- add `from sqlalchemy import true`
- add `from backend.middleware.client_auth import get_user_client_filter, ClientAccessError`

Append (e.g. after the existing `get_current_*` guards):

```python
@dataclass(frozen=True)
class ClientScope:
    """Resolved, authorized set of clients for a request. client_ids is None
    => all clients (admin/poweruser); otherwise the exact authorized tuple."""

    client_ids: Optional[tuple[str, ...]]

    def filter(self, column: Any) -> Any:
        """SQLAlchemy clause scoping `column` to this scope (true() = no filter)."""
        if self.client_ids is None:
            return true()
        return column.in_(self.client_ids)

    def as_single(self) -> Optional[str]:
        """Scalar client_id for legacy scalar-consuming services."""
        if self.client_ids is None:
            return None
        if len(self.client_ids) == 1:
            return self.client_ids[0]
        raise HTTPException(status_code=400, detail="Multiple clients in scope; specify a client_id")


def resolve_client_scope(
    client_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClientScope:
    """Central client-scope authorization for read endpoints. Admin/poweruser
    see all clients (or narrow to one); scoped users are confined to their
    assigned client(s); an unauthorized client_id -> 403."""
    allowed = get_user_client_filter(current_user, db)  # None=all; list=scoped; raises 403 if scoped & unassigned
    if client_id is not None:
        if allowed is not None and client_id not in allowed:
            raise ClientAccessError(detail=f"Not authorized for client {client_id}")
        return ClientScope((client_id,))
    return ClientScope(None if allowed is None else tuple(allowed))
```

(`Any` is already imported in jwt.py via `from typing import Any, Dict, Optional, cast`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_security/test_client_scope.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/auth/jwt.py backend/tests/test_security/test_client_scope.py
git commit -m "feat(authz): ClientScope + resolve_client_scope dependency"
```

---

### Task 2: Migrate KPI trends + efficiency + otd (12 sites)

**Files:**
- Modify: `backend/routes/kpi/trends.py` (9 endpoints: blocks at lines 47, 93, 159, 217, 261, 323, 404, 445, 501; filter lines listed below), `backend/routes/kpi/efficiency.py` (block 173, filter 186), `backend/routes/kpi/otd.py` (blocks 47 & 209, filters 60 & 235, echo 92)
- Test: `backend/tests/test_kpi/test_client_scope_enforced.py` (create)

**Interfaces:**
- Consumes: `ClientScope`, `resolve_client_scope` (Task 1). Import: `from backend.auth.jwt import ClientScope, resolve_client_scope`.

Apply the Global-Constraints recipe to each endpoint. Exact per-site filter columns:
- `trends.py`: all filters are `scope.filter(ProductionEntry.client_id)` except line 231 → `scope.filter(QualityEntry.client_id)`; lines 288 & 368 → `scope.filter(DowntimeEntry.client_id)`; line 353 → `scope.filter(QualityEntry.client_id)`; line 420 → `scope.filter(WorkOrder.client_id)`; line 460 → `scope.filter(AttendanceEntry.client_id)`. (The three multi-query endpoints at 261/323 each have 2–3 filter lines — convert every one.)
- `efficiency.py:186` → `scope.filter(ProductionEntry.client_id)`.
- `otd.py:60` & `otd.py:235` → `scope.filter(WorkOrder.client_id)`; the `otd.py:92` response echo `"client_id": effective_client_id` → `"client_id": client_id`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_kpi/test_client_scope_enforced.py
import pytest
from fastapi.testclient import TestClient
from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.main import app


@pytest.fixture
def _bind(transactional_db):
    app.dependency_overrides[get_db] = lambda: transactional_db
    yield transactional_db
    app.dependency_overrides.pop(get_db, None)


def _as(user):
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_operator_cannot_read_other_clients_trend(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/efficiency/trend", params={"client_id": "CLIENT-B"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_can_read_own_trend(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/efficiency/trend", params={"client_id": "CLIENT-A"})
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_admin_can_narrow_to_any_client(_bind, admin_user):
    c = _as(admin_user)
    try:
        r = c.get("/api/kpi/efficiency/trend", params={"client_id": "CLIENT-B"})
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py -v`
Expected: FAIL — the operator-other-client test gets 200 (current buggy behavior), not 403.

- [ ] **Step 3: Apply the recipe to trends.py, efficiency.py, otd.py**

Migrate all 12 sites per the recipe + the column map above.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py tests/test_kpi/ -v`
Expected: PASS (new scope tests + existing trend tests unchanged)

- [ ] **Step 5: Commit**

```bash
git add backend/routes/kpi/trends.py backend/routes/kpi/efficiency.py backend/routes/kpi/otd.py backend/tests/test_kpi/test_client_scope_enforced.py
git commit -m "fix(authz): enforce client scope on KPI trends/efficiency/otd"
```

---

### Task 3: Migrate KPI cause (scalar) + dashboard (7 sub-queries)

**Files:**
- Modify: `backend/routes/kpi/cause.py` (block 43, scalar call 61), `backend/routes/kpi/dashboard.py` (block 66, echo 76, sub-query filters 96/114/159/176/226/256/292/323)
- Test: extend `backend/tests/test_kpi/test_client_scope_enforced.py`

**Interfaces:**
- Consumes: `ClientScope`, `resolve_client_scope` (Task 1).

Recipe specifics:
- `cause.py`: delete block; add `scope`; line 61 `driver(db, effective_client_id, date)` → `driver(db, scope.as_single(), date)`.
- `dashboard.py`: delete block; add `scope`; echo line 76 `"client_id": effective_client_id` → `"client_id": client_id`. Each sub-query filter `if effective_client_id: Q = Q.filter(Col == effective_client_id)` → `Q = Q.filter(scope.filter(Col))` with columns: 96/114 `ProductionEntry.client_id`; 176 `QualityEntry.client_id`; 226 `DowntimeEntry.client_id`; 256 `AttendanceEntry.client_id`; 292 `HoldEntry.client_id`; 323 `WorkOrder.client_id`. **Line 159–162 is different** — it's `ClientConfig.client_id == effective_client_id` used to fetch a single config row (`.first()`), not a scoped list query. Convert to: `if scope.as_single(): cc = db.query(ClientConfig).filter(ClientConfig.client_id == scope.as_single()).first()` (a single-client config lookup; None/all → skip, matching the original `if effective_client_id` guard).

- [ ] **Step 1: Write the failing test** (append)

```python
def test_operator_cannot_read_other_clients_cause(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/availability/cause", params={"date": "2026-07-14", "client_id": "CLIENT-B"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_operator_cannot_read_other_clients_dashboard(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/dashboard", params={"client_id": "CLIENT-B"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```

(Adjust the dashboard path if the route differs — confirm with `git grep '"/dashboard"' backend/routes/kpi/dashboard.py`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py -k "cause or dashboard" -v`
Expected: FAIL — 200 instead of 403.

- [ ] **Step 3: Apply the recipe to cause.py and dashboard.py**

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_kpi/ -v`
Expected: PASS (new + existing, including the SP2 cause tests)

- [ ] **Step 5: Commit**

```bash
git add backend/routes/kpi/cause.py backend/routes/kpi/dashboard.py backend/tests/test_kpi/test_client_scope_enforced.py
git commit -m "fix(authz): enforce client scope on KPI cause + dashboard"
```

---

### Task 4: Migrate quality routes (8 sites)

**Files:**
- Modify: `backend/routes/quality/fpy_rty.py` (block 69 → filters 83/97/116 `QualityEntry.client_id`; block 213 → echo 227), `backend/routes/quality/pareto.py` (block 88 → filter 109 `DefectDetail.client_id_fk`; block 158 → filter 177 `QualityEntry.client_id`), `backend/routes/quality/ppm_dpmo.py` (blocks 61/127/189 → filters 75/140/202 `QualityEntry.client_id`; block 276 → scalar 280 + echo 284)
- Test: `backend/tests/test_kpi/test_client_scope_enforced.py` (append a quality case)

**Interfaces:** Consumes `ClientScope`, `resolve_client_scope`.

Recipe specifics:
- `pareto.py:109` is the one `client_id_fk` column: `scope.filter(DefectDetail.client_id_fk)`.
- `ppm_dpmo.py:280` `calculate_dpmo_with_part_lookup(db, start_date, end_date, effective_client_id)` → `scope.as_single()`; echo 284 → `client_id`.
- `fpy_rty.py:227` echo → `client_id`.

- [ ] **Step 1: Write the failing test** (append)

```python
def test_operator_cannot_read_other_clients_defects(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/quality/kpi/defects-by-type", params={"client_id": "CLIENT-B"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py -k defects -v`
Expected: FAIL — 200 instead of 403.

- [ ] **Step 3: Apply the recipe to fpy_rty.py, pareto.py, ppm_dpmo.py**

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py backend/tests/test_calculations -k "ppm or quality or defect or fpy" -v` (adjust to existing quality test locations) and `pytest tests/ -k quality -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routes/quality/fpy_rty.py backend/routes/quality/pareto.py backend/routes/quality/ppm_dpmo.py backend/tests/test_kpi/test_client_scope_enforced.py
git commit -m "fix(authz): enforce client scope on quality routes"
```

---

### Task 5: Migrate ops routes (attendance/downtime/holds/jobs/data_completeness) + onboarding + fix buggy test

**Files:**
- Modify: `backend/routes/attendance.py` (block 326 → filters 354/375/398/422/445; block 511 → filter 528), `backend/routes/downtime.py` (block 176 → scalar 185 + filter 202), `backend/routes/holds.py` (block 354 → filter 363 `HoldEntry.client_id`), `backend/routes/jobs.py` (block 223 → scalar 227), `backend/routes/data_completeness.py` (block 125 → filter 136 + scalar calls 163/167/171/175/179 + echo 197), `backend/routes/onboarding.py` (`_resolve_client_id`)
- Modify: `backend/tests/test_api/test_data_completeness.py` (rewrite the buggy `test_non_admin_uses_assigned_client`, ~lines 454-468)
- Test: `backend/tests/test_kpi/test_client_scope_enforced.py` (append an attendance/holds case)

**Interfaces:** Consumes `ClientScope`, `resolve_client_scope`.

Recipe specifics:
- `attendance.py:375` filters `Shift.client_id`; 354/398/422/445/528 filter `AttendanceEntry.client_id`.
- `downtime.py:185` is a scalar service call `..., work_order_id, target_date, effective_client_id` → `scope.as_single()`; `downtime.py:202` filter `DowntimeEntry.client_id`.
- `holds.py:363` filter `HoldEntry.client_id`.
- `jobs.py:227` `calculate_job_rty_summary(db, start_date, end_date, effective_client_id)` → `scope.as_single()`.
- `data_completeness.py`: filter 136 keeps its `hasattr(model, "client_id")` guard → `if hasattr(model, "client_id"): query = query.filter(scope.filter(model.client_id))`; the 5 `calculate_expected_entries(db, target_date, shift_id, effective_client_id, ...)` calls → `scope.as_single()`; echo 197 → `client_id`.
- `onboarding._resolve_client_id(client_id, current_user)` (lines 32-…): it currently returns a caller-supplied `client_id` verbatim. Change it to authorize first — reuse `get_user_client_filter`: if `client_id` is provided and the user is scoped and `client_id` not in their allowed list, raise `ClientAccessError` (403); keep the existing "admin must pass explicitly / else first assigned / else 400" fallbacks. It stays a helper (not a FastAPI dependency).

- [ ] **Step 1: Write the failing tests**

Append to `test_client_scope_enforced.py`:

```python
def test_operator_cannot_read_other_clients_wip_aging(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/wip-aging", params={"client_id": "CLIENT-B"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```

Rewrite `backend/tests/test_api/test_data_completeness.py::test_non_admin_uses_assigned_client` (which currently reimplements the buggy inline block) to assert the corrected dependency:

```python
def test_non_admin_uses_assigned_client(operator_user_client_a):
    from backend.auth.jwt import resolve_client_scope
    # omitted client_id -> scoped to own client
    assert resolve_client_scope(client_id=None, current_user=operator_user_client_a, db=None).client_ids == ("CLIENT-A",)
    # requesting another client -> 403 (no silent cross-tenant read)
    from backend.middleware.client_auth import ClientAccessError
    import pytest
    with pytest.raises(ClientAccessError):
        resolve_client_scope(client_id="CLIENT-B", current_user=operator_user_client_a, db=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py -k wip_aging tests/test_api/test_data_completeness.py::test_non_admin_uses_assigned_client -v`
Expected: FAIL — wip_aging returns 200; the data_completeness test still imports the old inline logic.

- [ ] **Step 3: Apply the recipe to the 6 route files + onboarding**

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py tests/test_api/test_data_completeness.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routes/attendance.py backend/routes/downtime.py backend/routes/holds.py backend/routes/jobs.py backend/routes/data_completeness.py backend/routes/onboarding.py backend/tests/test_api/test_data_completeness.py backend/tests/test_kpi/test_client_scope_enforced.py
git commit -m "fix(authz): enforce client scope on ops routes + onboarding"
```

---

### Task 6: Whole-suite verification + grep guard

**Files:**
- Test: `backend/tests/test_security/test_no_inline_client_scope.py` (create — a static guard)

**Interfaces:** none produced.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_security/test_no_inline_client_scope.py
import pathlib

ROUTES = pathlib.Path(__file__).resolve().parents[1].parent / "routes"


def test_no_route_reintroduces_the_buggy_inline_scope_block():
    """The trust-the-caller block (role != 'admin' fallback) must not return —
    all client scoping goes through resolve_client_scope now."""
    offenders = []
    for p in ROUTES.rglob("*.py"):
        text = p.read_text()
        if 'current_user.role != "admin" and current_user.client_id_assigned' in text:
            offenders.append(str(p.relative_to(ROUTES)))
    assert offenders == [], f"buggy inline client-scope block still present in: {offenders}"
```

- [ ] **Step 2: Run it (passes only once all sites are migrated)**

Run: `cd backend && pytest tests/test_security/test_no_inline_client_scope.py -v`
Expected: PASS (Tasks 2–5 removed every occurrence). If it FAILS, it names the file(s) still carrying the block — migrate them.

- [ ] **Step 3: Full suite**

Run: `cd backend && pytest tests/ -q`
Expected: PASS, coverage ≥75%. Existing tenant-isolation tests (`test_all_endpoints.py` 403 gates, `test_hold_catalog_tenant_isolation.py`) green.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_security/test_no_inline_client_scope.py
git commit -m "test(authz): static guard against reintroducing the inline scope block"
```

---

## Post-merge: End-to-end browser smoke test (REQUIRED gate — user standpoint)

After merge + VM deploy, run a full browser-agent e2e smoke test (this is a hard "done" gate per the spec — API tests are not sufficient for a tenant-boundary change). Steps:

1. **All-client user** (`verify_bot`): log in; confirm the KPI dashboard + all 10 diagnostic charts load, the client selector switches between DEMO clients, and SP2 cause tooltips + WIP-Aging/OTD (from #142/#143) still render correctly.
2. **Scoped user**: create (confirmed, non-destructive) a scoped DEMO user bound to one DEMO client on the VM if none exists; log in as them; confirm they see only their client's data, the app never loads another client's data, and any attempt to reach another client's data is refused (no cross-tenant data appears).
3. Report walked steps + per-role observations + screenshot/DOM evidence. **Any cross-tenant data visible to the scoped user is a release blocker.**

## Self-Review

**1. Spec coverage:** ClientScope+dependency → Task 1; all 28 sites → Tasks 2 (12) + 3 (8: cause 1 + dashboard 7) + 4 (8) + 5 (attendance 5 + downtime 2 + holds 1 + jobs 1 + data_completeness 6 = wait, recount below); onboarding + buggy test → Task 5; grep guard + full suite → Task 6; browser e2e → post-merge gate. ✅
   - Site recount: trends 9 + efficiency 1 + otd 2 = 12 (Task 2). cause 1 + dashboard 8 filter/echo = Task 3. fpy_rty 3+echo + pareto 2 + ppm_dpmo 3+1scalar = 8 sites (Task 4). attendance 5 (326-block: 354/375/398/422/445) + attendance 1 (528) + downtime scalar+filter + holds 1 + jobs scalar + data_completeness filter+5scalar = Task 5. Every `effective_client_id` occurrence from the inventory is assigned to a task. ✅
**2. Placeholder scan:** The recipe + per-site column map is a complete, unambiguous transformation (not "add validation"); every test step has concrete code. No TBD.
**3. Type consistency:** `ClientScope`/`resolve_client_scope` signatures identical across Tasks 1–5; `scope.filter(col)` and `scope.as_single()` used consistently; the 403 is `ClientAccessError`, the multi-leader-scalar 400 is from `as_single`. Fixtures `admin_user`/`operator_user_client_a`/`operator_user_client_b`/`leader_user_multi_client` used consistently.

## Global verification command

`cd backend && pytest tests/test_security/test_client_scope.py tests/test_security/test_no_inline_client_scope.py tests/test_kpi/test_client_scope_enforced.py tests/ -q`
