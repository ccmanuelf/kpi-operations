# Uniform Client-Scope Authorization Implementation Plan (Comprehensive)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the entire cross-tenant read/write authorization vulnerability class by routing every scoped endpoint through the shared `resolve_client_scope` dependency (or `verify_client_access` for writes/product-ownership), so a scoped user can never read or act on another client's data; admin/poweruser keep all-client access and leaders keep multi-client access.

**Architecture:** `ClientScope` + `resolve_client_scope` (shipped in Task 1) applied via five fix patterns across ~37 read endpoints + 3 write endpoints. Delegates to `middleware/client_auth.py` primitives.

**Tech Stack:** FastAPI, SQLAlchemy (SQLite + MariaDB), pytest, browser agent (e2e gate).

## Status carried forward
- **Task 1 DONE** (`0b6b964`): `ClientScope` + `resolve_client_scope` + unit tests.
- **Task 2 DONE** (`b2ed7e4`): KPI trends (all) + efficiency/trend + otd calculate/late-deliveries migrated → now in the already-fixed column.

## Global Constraints (the five fix patterns)

**Pattern A — read endpoint WITH a `client_id` query param.** Add `scope: ClientScope = Depends(resolve_client_scope)` to the signature (this alone 403s an unauthorized `client_id` before the handler runs). Delete any inline scoping block. For **query-building** endpoints, also replace `if [effective_]client_id: q = q.filter(Col == …)` with `q = q.filter(scope.filter(Col))` so an omitted `client_id` still scopes a non-admin to their client(s). Scalar-service arg → `scope.as_single()`. Response echo → the raw `client_id` param. For **pure-delegating/config** endpoints whose existing default branch is already correct (e.g. `break_times` else-branch), the dependency alone suffices — but the plan still names each so the reviewer confirms the default path is safe.

**Pattern B — read endpoint with NO `client_id` param** (inline `if role != "admin" and client_id_assigned: filter(== client_id_assigned)`): add `scope: ClientScope = Depends(resolve_client_scope)` (its `client_id` defaults `None` → the caller's full authorized set; `None`=all for admin/poweruser). Delete the inline role check. Replace each scoped filter with `q = q.filter(scope.filter(Col))`; scalar-service arg → `scope.as_single()`.

**Pattern C — MISSING-SCOPE (no filter at all):** thread the caller's scope into the helper and filter. C1 `identify_late_orders(db, as_of_date)` → add a `client_ids: Optional[Sequence[str]] = None` param, apply `if client_ids is not None: q = q.filter(WorkOrder.client_id.in_(client_ids))`; handler passes `scope.client_ids`. C2 `identify_chronic_holds(db, threshold_days, client_id)` already has a scalar `client_id` — handler passes `scope.as_single()`; **verify the helper actually filters `HoldEntry.client_id` by it and add that filter if missing** (it currently uses `client_id` only for the threshold lookup). C3 `quality-score` (product-keyed): in the handler, load the `Product` by `product_id`; if not found → 404; else `verify_client_access(current_user, product.client_id, db)` (403 if unauthorized) before calling `calculate_quality_score`.

**Pattern D — write-ownership** (holds `approve-hold`/`request-resume`/`approve-resume`): replace the `if current_user.role != "admin" and current_user.client_id_assigned: if db_hold.client_id != current_user.client_id_assigned: raise 403` block with `verify_client_access(current_user, db_hold.client_id, db)` (import from `middleware.client_auth`; it 403s for a scoped user not authorized for `db_hold.client_id`, passes admin/poweruser and leaders-with-access).

**Binding invariants (all tasks):**
- Import in route files: `from backend.auth.jwt import ClientScope, resolve_client_scope` (Patterns A/B); `from backend.middleware.client_auth import verify_client_access` (Patterns C3/D).
- Leave the already-fixed / admin-gated / write-forces-own endpoints untouched (see spec).
- OpenAPI route set + tags unchanged → `test_openapi_surface.py` stays green WITHOUT regeneration; a route-set change is a review flag.
- Portability: `true()`, `.in_(tuple)`.
- Coverage ≥75%; every existing tenant-isolation test green.
- Fixtures: `admin_user`, `operator_user_client_a` ("CLIENT-A"), `operator_user_client_b` ("CLIENT-B"), `leader_user_multi_client` ("CLIENT-A,CLIENT-B"). HTTP tests bind `transactional_db` to `get_db` and override `get_current_user` (see `backend/tests/test_kpi/test_client_scope_enforced.py` from Task 2 for the exact fixture pattern).

---

### Task 3: Pattern A — KPI cause + dashboard + efficiency by-shift/by-product

**Files:** `backend/routes/kpi/cause.py` (block 43, scalar 61), `backend/routes/kpi/dashboard.py` (block 66, echo 76, filters 96/114/159/176/226/256/292/323), `backend/routes/kpi/efficiency.py` (bare-if 65-66 by-shift, 129-130 by-product). Test: extend `backend/tests/test_kpi/test_client_scope_enforced.py`.

Recipe per Global Constraints Pattern A. Columns: cause → `scope.as_single()` into `driver`; dashboard sub-queries → `ProductionEntry`(96/114), `QualityEntry`(176), `DowntimeEntry`(226), `AttendanceEntry`(256), `HoldEntry`(292), `WorkOrder`(323) `.client_id`, and the `ClientConfig` single-row lookup at 159–162 → `if scope.as_single(): cc = db.query(ClientConfig).filter(ClientConfig.client_id == scope.as_single()).first()`; echo 76 → `client_id`. efficiency by-shift/by-product → `scope.filter(ProductionEntry.client_id)`.

- [ ] **Step 1: failing test** — append:
```python
def test_operator_cannot_read_other_clients_cause(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi/availability/cause", params={"date": "2026-07-14", "client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_operator_cannot_read_other_clients_efficiency_by_shift(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi/efficiency/by-shift", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```
(Confirm the dashboard route path with `grep -n '@.*get(' backend/routes/kpi/dashboard.py` and add a dashboard 403 case too.)
- [ ] **Step 2:** run → FAIL (200s).
- [ ] **Step 3:** apply Pattern A to the 3 files (all sites).
- [ ] **Step 4:** `cd backend && pytest tests/test_kpi/ -v` → PASS (new + existing SP2/dashboard tests).
- [ ] **Step 5:** commit `fix(authz): scope KPI cause/dashboard/efficiency-splits`.

---

### Task 4: Pattern A — quality routes

**Files:** `backend/routes/quality/fpy_rty.py` (block 69 → filters 82/96/115 `QualityEntry.client_id`; block 213 echo 227), `backend/routes/quality/pareto.py` (block 88 → filter 108-109 `DefectDetail.client_id_fk`; block 158 → filter 176-177 `QualityEntry.client_id`; **top-defects `:25`** bare-if delegating to `identify_top_defects` — add `scope` dep AND ensure a default scope: pass `scope.as_single()` into the helper, and confirm `client_id=None` no longer returns all-clients for a scoped user), `backend/routes/quality/ppm_dpmo.py` (blocks 61/127/189 → filters 75/140/202 `QualityEntry.client_id`; block 276 → scalar 280 `scope.as_single()` + echo 284). Test: append a quality 403 case.

- [ ] **Step 1: failing test** — append:
```python
def test_operator_cannot_read_other_clients_defects(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/quality/kpi/defects-by-type", params={"client_id": "CLIENT-B"}).status_code == 403
        assert c.get("/api/quality/kpi/top-defects", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** apply Pattern A across the 3 files. For `top-defects`/`identify_top_defects` (`backend/calculations/ppm.py`): pass `scope.as_single()`; if the helper returns all clients when its `client_id` arg is None, that is now only reachable by admin/poweruser (intended) — verify.
- [ ] **Step 4:** `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py tests/ -k "ppm or defect or fpy or quality" -v` → PASS.
- [ ] **Step 5:** commit `fix(authz): scope quality routes (fpy/rty, pareto, ppm/dpmo)`.

---

### Task 5: Pattern A — ops routes (attendance, downtime, holds wip-aging, jobs rty-summary, data_completeness)

**Files:** `backend/routes/attendance.py` (block 326 → filters 353/374[`Shift.client_id`]/397/421/445 `AttendanceEntry.client_id`; block 511 → filter 527), `backend/routes/downtime.py` (block 176 → scalar 185 `scope.as_single()` + filter 201-202 `DowntimeEntry.client_id`), `backend/routes/holds.py` (block 354 → filter 362-363 `HoldEntry.client_id`; **IFELIF 454-457** wip-aging/top → `scope.filter(HoldEntry.client_id)`; **IFELIF 505-508** wip-aging/trend → `scope.filter(HoldEntry.client_id)`), `backend/routes/jobs.py` (block 223 → scalar 227 `scope.as_single()`), `backend/routes/data_completeness.py` (block 125 → filter 135-136 keep `hasattr(model,"client_id")` guard: `if hasattr(model,"client_id"): query = query.filter(scope.filter(model.client_id))`; 5 `calculate_expected_entries(..., effective_client_id, ...)` → `scope.as_single()`; echo 197 → `client_id`; the delegated `:234`/`:296` inherit the fix). Test: append attendance + wip-aging 403 cases.

- [ ] **Step 1: failing test** — append:
```python
def test_operator_cannot_read_other_clients_wip_aging(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi/wip-aging", params={"client_id": "CLIENT-B"}).status_code == 403
        assert c.get("/api/kpi/wip-aging/top", params={"client_id": "CLIENT-B"}).status_code == 403
        assert c.get("/api/attendance/kpi/absenteeism", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** apply Pattern A across the 5 files.
- [ ] **Step 4:** `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py tests/ -k "attendance or downtime or wip or hold or jobs or completeness" -v` → PASS.
- [ ] **Step 5:** commit `fix(authz): scope ops routes (attendance/downtime/holds-wip/jobs/completeness)`.

---

### Task 6: Pattern A — config/reference catalogs

**Files:** `backend/routes/kpi/thresholds.py` (`get_kpi_thresholds:24`, override block 55-60), `backend/routes/break_times.py` (`list_breaks:29`), `backend/routes/hold_catalogs.py` (`get_hold_statuses:47`, `get_hold_reasons:126`). Test: append a catalog 403 case.

These are delegating/config endpoints. Add `scope: ClientScope = Depends(resolve_client_scope)` to each signature — the dependency 403s an unauthorized `client_id` before the handler. For `thresholds`, gate the client-specific override on `scope.as_single()` (`if scope.as_single(): <load client + client_thresholds for scope.as_single()>`) so an omitted client_id yields globals and a scoped user only ever overrides with their own. For `break_times`, keep the existing branch structure (the dependency authorizes any passed `client_id`; the else-branch already uses the user's own client). For `hold_catalogs` (client_id required), the dependency 403s a mismatch.

- [ ] **Step 1: failing test** — append:
```python
def test_operator_cannot_read_other_clients_thresholds(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        assert c.get("/api/kpi-thresholds", params={"client_id": "CLIENT-B"}).status_code == 403
        assert c.get("/api/hold-catalogs/statuses", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** apply Pattern A to the 3 files.
- [ ] **Step 4:** `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py tests/ -k "threshold or break or catalog or hold_catalog" -v` → PASS.
- [ ] **Step 5:** commit `fix(authz): scope config/reference catalogs (thresholds/break-times/hold-catalogs)`.

---

### Task 7: Pattern B — no-param endpoints

**Files:** `backend/routes/kpi/otd.py` (`get_otd_by_client:111`, role-check 160-161 → `scope.filter(WorkOrder.client_id)`), `backend/routes/jobs.py` (`get_work_order_job_rty:163`, block 179-180 building `client_id` → `client_id = scope.as_single()`), `backend/routes/holds.py` (`get_pending_approvals:294`, role-check 308-309 → `scope.filter(HoldEntry.client_id)`), `backend/routes/my_shift.py` (3 endpoints; every `if role != "admin" and client_id_assigned: X_query = X_query.filter(Model.client_id == client_id_assigned)` at 118/138/147/315/326/335/372/391/408 → `X_query = X_query.filter(scope.filter(Model.client_id))` with the matching `ProductionEntry`/`DowntimeEntry`/`QualityEntry`), `backend/routes/metric_results.py` (`list_results:117`, replace the whole 131-136 role/elif block with `query = query.filter(scope.filter(MetricCalculationResult.client_id))`). Test: append a Pattern-B scoping case.

Recipe per Pattern B: add `scope: ClientScope = Depends(resolve_client_scope)`; delete the inline role checks; apply `scope.filter(Col)`.

- [ ] **Step 1: failing test** — append (Pattern B has no client_id param, so assert data isolation, not 403):
```python
def test_operator_my_shift_scoped_to_own_client(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/my-shift/summary")
        assert r.status_code == 200  # scoped to CLIENT-A only (no cross-tenant rows)
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_operator_metric_results_scoped(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        # requesting another client's results is refused (dependency 403s the param)
        assert c.get("/api/metrics/results", params={"client_id": "CLIENT-B"}).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```
(metric_results DOES accept `client_id` as an explicit narrow for all-client roles, so the dependency 403s a scoped user passing another client — assert that.)
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** apply Pattern B across the files.
- [ ] **Step 4:** `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py tests/ -k "my_shift or metric or otd_by_client or pending or work_order" -v` → PASS.
- [ ] **Step 5:** commit `fix(authz): scope no-param endpoints (otd-by-client/jobs/pending-approvals/my-shift/metric-results)`.

---

### Task 8: Pattern C (missing-scope) + Pattern D (holds writes)

**Files:** `backend/routes/kpi/otd.py` (`get_late_orders:96`) + `backend/calculations/otd.py` (`identify_late_orders:200`); `backend/routes/holds.py` (`get_chronic_holds:521`) + `backend/calculations/wip_aging.py` (`identify_chronic_holds:230`); `backend/routes/quality/fpy_rty.py` (`get_quality_score:271`); `backend/routes/holds.py` (writes `approve_hold:163`, `request_resume:202`, `approve_resume:239`). Test: append missing-scope + write-ownership cases.

Pattern C: C1 add `client_ids: Optional[Sequence[str]] = None` to `identify_late_orders` + `if client_ids is not None: q = q.filter(WorkOrder.client_id.in_(client_ids))`; handler adds `scope` dep and passes `scope.client_ids`. C2 handler passes `scope.as_single()` to `identify_chronic_holds` and ensure the helper filters `HoldEntry.client_id` by its `client_id` param (add the filter if absent). C3 `get_quality_score`: load `Product` by `product_id` (404 if none), `verify_client_access(current_user, product.client_id, db)` before `calculate_quality_score`. Pattern D: replace the 3 ownership blocks with `verify_client_access(current_user, db_hold.client_id, db)`.

- [ ] **Step 1: failing test** — append:
```python
def test_operator_late_orders_scoped(_bind, operator_user_client_a):
    c = _as(operator_user_client_a)
    try:
        r = c.get("/api/kpi/late-orders")   # must not return CLIENT-B late orders
        assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_current_user, None)

def test_operator_cannot_approve_other_clients_hold(_bind, operator_user_client_a, db_session_with_clientb_hold):
    # (build a CLIENT-B hold via factory in the test; assert 403 on approve)
    ...
```
(Flesh out the write test using `TestDataFactory` to seed a CLIENT-B hold, then POST approve-hold as operator-A → assert 403. Reuse the seeding pattern from `test_hold_catalog_tenant_isolation.py`.)
- [ ] **Step 2:** run → FAIL (late-orders returns cross-tenant; approve returns 200).
- [ ] **Step 3:** apply Patterns C and D.
- [ ] **Step 4:** `cd backend && pytest tests/test_kpi/test_client_scope_enforced.py tests/ -k "late or chronic or quality_score or approve or resume" -v` → PASS.
- [ ] **Step 5:** commit `fix(authz): close missing-scope leaks + holds write-ownership`.

---

### Task 9: Static guard + whole-suite verification

**Files:** `backend/tests/test_security/test_no_inline_client_scope.py` (create).

- [ ] **Step 1: failing test**
```python
import pathlib
ROUTES = pathlib.Path(__file__).resolve().parents[1].parent / "routes"

def test_no_route_reintroduces_buggy_scope_patterns():
    block = 'current_user.role != "admin" and current_user.client_id_assigned'
    offenders = [str(p.relative_to(ROUTES)) for p in ROUTES.rglob("*.py") if block in p.read_text()]
    assert offenders == [], f"buggy inline client-scope block still present in: {offenders}"
```
- [ ] **Step 2:** run — passes only once Tasks 3–8 removed every occurrence. If it names files, migrate them.
- [ ] **Step 3:** full suite `cd backend && pytest tests/ -q` → PASS, coverage ≥75%; `pytest tests/test_bootstrap/test_openapi_surface.py -q` green (no regen).
- [ ] **Step 4:** commit `test(authz): static guard against inline client-scope block`.

---

## Post-merge: browser e2e smoke gate (REQUIRED — user standpoint)
Per spec: all-client user (all charts/clients/SP2/WIP/OTD work) AND a scoped DEMO user (created confirmed + non-destructive, one DEMO client) sees only their client, cross-tenant refused. Any cross-tenant data visible to the scoped user is a release blocker.

## Self-Review
**Coverage:** Pattern A → Tasks 3 (KPI) + 4 (quality) + 5 (ops) + 6 (config); Pattern B → Task 7; Pattern C + D → Task 8; static guard + suite → Task 9. Every endpoint from the spec's authoritative inventory maps to a task. Tasks 1–2 (done) cover the core + KPI trends. **Placeholders:** the Pattern recipes + per-endpoint file:line/column map are complete; the one flesh-out (Task 8 write test) names the exact seeding pattern to copy. **Consistency:** `scope.filter`/`scope.as_single`/`verify_client_access` used per pattern; 403 via the dependency / `verify_client_access`, isolation asserted where no param exists.

## Global verification
`cd backend && pytest tests/test_security/ tests/test_kpi/test_client_scope_enforced.py tests/ -q`
