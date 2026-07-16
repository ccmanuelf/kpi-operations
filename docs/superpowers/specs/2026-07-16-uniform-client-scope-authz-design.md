# Uniform Client-Scope Authorization (Design) — Comprehensive Audit

**Date:** 2026-07-16 (revised after full-surface audit)
**Status:** Approved design (scope broadened per user) → ready for revised implementation plan
**Class:** Broken Access Control (horizontal privilege / cross-tenant read) — pre-existing, discovered during SP2 (#142) and seed-polish (#143) reviews; a prior partial fix ("VULN-003") fixed some endpoints but was applied inconsistently.

## Scope decision

Initial recon found one buggy pattern (the `effective_client_id` block). A full audit revealed the vulnerability has **multiple shapes** across the route surface, plus three endpoints with **no tenant filter at all**. Per user decision, this fixes the **entire vulnerability class** in one effort — all vulnerable read endpoints, the 3 missing-scope leaks, the config/reference catalogs, the product-keyed quality-score, the INLINEROLE/leader-broken endpoints, and the 3 holds write-ownership checks.

## Root cause (all shapes share it)

Endpoints trust a caller-supplied `client_id`, and/or use `role != "admin"` (which omits **`poweruser`**, an all-clients role) and treat `client_id_assigned` (a **comma-separated list**) as a scalar. Correct primitives already exist in `backend/middleware/client_auth.py`:
- `get_user_client_filter(user, db)` → `None` for admin/poweruser, the authorized list for scoped users, raises `ClientAccessError` (403) if a scoped user has no assignment.
- `verify_client_access(user, client_id, db)` → 403 if the user isn't authorized for `client_id` (admin/poweruser always pass).
- `build_client_filter_clause(user, column)` → `None` for all-client roles, else `column.in_(clients)`.

## Core unit (from Task 1, already shipped on the branch)

`backend/auth/jwt.py`:
- `ClientScope(client_ids: Optional[tuple[str,...]])` — `.filter(column)` → `true()` if None else `column.in_(client_ids)`; `.as_single()` → None / the one id / 400 if multiple.
- `resolve_client_scope(client_id=Query(None), current_user=Depends(get_current_user), db=Depends(get_db)) -> ClientScope` — admin/poweruser → all (or narrow to a passed client); scoped user + authorized client_id → that client; scoped + unauthorized client_id → **403**; scoped + omitted → their full authorized set; scoped + no assignment → **403**.

## The five fix patterns (by bucket)

**Pattern A — read endpoint WITH a `client_id` query param** (BLOCK, BAREIF, IFELIF, config catalogs): delete the inline scoping; add `scope: ClientScope = Depends(resolve_client_scope)`; replace `if client_id/effective_client_id: q = q.filter(Col == …)` with `q = q.filter(scope.filter(Col))`; scalar-service arg → `scope.as_single()`; response echo → the raw `client_id` param. Delegating endpoints (e.g. `top-defects`, `hold-catalogs`, `thresholds`) pass `scope.as_single()` into their helper OR the helper gains a `ClientScope`/list param — whichever is minimal for that helper (the plan specifies per site).

**Pattern B — read endpoint with NO `client_id` param** (INLINEROLE reads: `otd/by-client`, `work-order rty`, `holds/pending-approvals`, `my_shift ×3`; and `metric_results.list_results`): add `scope: ClientScope = Depends(resolve_client_scope)` (its `client_id` defaults `None` → the caller's full authorized set, `None`=all for admin/poweruser); delete the `if role != "admin" …` line; apply `scope.filter(Col)` to each scoped query. `metric_results` keeps honoring an explicit `client_id` for all-client roles — `resolve_client_scope` already expresses that.

**Pattern C — MISSING-SCOPE, no filter at all** (`/api/kpi/late-orders` → `identify_late_orders`, `/api/kpi/chronic-holds` → `identify_chronic_holds`, `/api/quality/kpi/quality-score` → `calculate_quality_score`): thread the user's scope into the helper and filter. For the two hold/otd helpers, add a client-scope filter (pass `scope`/client list; apply `build_client_filter_clause`-style `.in_`). For `quality-score` (keyed by `product_id`, and `Product` carries `client_id`), verify the product's owning client is in the caller's scope — a **product→client ownership check** (load the product, `verify_client_access(current_user, product.client_id, db)`), 403 otherwise.

**Pattern D — write-ownership checks** (holds `approve-hold` / `request-resume` / `approve-resume`, POST): after loading the target hold row, `verify_client_access(current_user, hold.client_id, db)` before mutating (403 if not authorized), replacing the buggy `if role != "admin" and client_id_assigned` scalar comparison.

**Already-correct / out of scope (DO NOT TOUCH):** everything using `verify_client_access`/`build_client_filter_clause`/`scope.filter` today — `kpi/trends.py` (all), `kpi/otd.py:24`/`:178`, `kpi/efficiency.py:150` trend, `quality/entries.py`, `attendance.py:162`, `capacity/*`, `alerts/*`, `reports/*`, `analytics/*`, `reference.py`, `export.py`, `predictions.py`, `dual_view_calculate.py`, `qr.py`, etc.; admin/planner-gated writes (`users.py`, `thresholds` PUT/DELETE); and forces-own writes (`floating_pool` create). The Task-2 commit already moved the KPI trend/efficiency/otd endpoints into this column.

## Authoritative migration inventory

**Pattern A (has client_id param):**
- `attendance.py:292` absenteeism, `attendance.py:484` absenteeism/trend
- `data_completeness.py:91` (+ delegated `:234`, `:296`)
- `downtime.py:140` availability
- `holds.py:330` wip-aging
- `holds.py:428` wip-aging/top (IFELIF), `holds.py:473` wip-aging/trend (IFELIF)
- `jobs.py:191` rty-summary
- `kpi/cause.py:33`, `kpi/dashboard.py:26`
- `kpi/efficiency.py:29` by-shift (BAREIF), `kpi/efficiency.py:92` by-product (BAREIF)
- `quality/ppm_dpmo.py:30/107/152/243`, `quality/pareto.py:25` top-defects (BAREIF, +default-scope), `quality/pareto.py:58/128`, `quality/fpy_rty.py:40/173`
- config catalogs: `kpi/thresholds.py:24`, `break_times.py:29`, `hold_catalogs.py:47`, `hold_catalogs.py:126`

**Pattern B (no client_id param):**
- `kpi/otd.py:111` by-client, `jobs.py:163` work-order rty, `holds.py:294` pending-approvals, `my_shift.py:89`/`:298`/`:357`, `metric_results.py:117` list_results

**Pattern C (missing-scope):**
- `kpi/otd.py:96` late-orders (`calculations/otd.py:identify_late_orders`), `holds.py:521` chronic-holds (`calculations/wip_aging.py:identify_chronic_holds`), `quality/fpy_rty.py:271` quality-score (`calculate_quality_score`, product→client)

**Pattern D (writes):**
- `holds.py:163` approve-hold, `holds.py:202` request-resume, `holds.py:239` approve-resume

## Behavior preservation

- The `client_id` query param stays on Pattern-A/B read endpoints → OpenAPI route set + tags unchanged → `test_openapi_surface.py` stays green without regeneration. Pattern-C endpoints that gain scoping do **not** add a route; if any signature change alters the OpenAPI surface, that is a review flag.
- Authorized requests (admin any client; scoped users on their own/assigned clients; leaders on any of theirs) return exactly what they did before.
- Portability: `true()`, `.in_(tuple)` on SQLite + MariaDB.
- Coverage gate ≥75% stays green; every existing tenant-isolation test stays green.

## Testing

**Unit** (Task 1, done): `ClientScope`/`resolve_client_scope` matrix.

**Integration (HTTP) — per pattern, representative + the severe cases:**
- Pattern A: operator-CLIENT-A + `?client_id=CLIENT-B` → **403** on a BLOCK (`/api/kpi/availability` or `/api/quality/kpi/ppm`), a BAREIF (`/api/kpi/efficiency/by-shift`), an IFELIF (`/api/kpi/wip-aging/top`), and a config catalog (`/api/kpi-thresholds`); own client → 200; admin narrows to any → 200; leader authorized/unauthorized → 200/403.
- Pattern B: operator-A on `/api/kpi/otd/by-client` and `/api/my-shift/summary` returns ONLY CLIENT-A data (no CLIENT-B rows); poweruser sees all; leader sees their set.
- Pattern C (severe): a scoped user hitting `/api/kpi/late-orders`, `/api/kpi/chronic-holds`, `/api/quality/kpi/quality-score` (for another client's product) does **not** receive other clients' data (403 or empty-for-others, per endpoint).
- Pattern D: operator-A approving a CLIENT-B hold → **403**.
- Rewrite the buggy `test_data_completeness.py` test.

**Whole-suite:** `pytest tests/` green, coverage ≥75%; existing tenant-isolation tests green.

**Static guard:** a test asserting no route reintroduces `role != "admin" and current_user.client_id_assigned` **and** no vulnerable bare `if client_id:`-without-verify pattern in the migrated files.

**End-to-end browser smoke test (REQUIRED gate — user standpoint):** after merge + VM deploy, a full browser-agent e2e from the real user's standpoint: (1) all-client user (`verify_bot`) — dashboards/10 charts/client-switching/SP2 tooltips/WIP/OTD all work; (2) a scoped DEMO user (created confirmed + non-destructively, bound to one DEMO client) — sees only their client, the app never loads another client's data, cross-tenant attempts are refused. Report walked steps + per-role evidence. Any cross-tenant data visible to the scoped user is a release blocker.

## Related Memory

[[user-roles-dialog-fix]], [[diagnostic-kpi-charts]], [[verify-rigorously-not-sample]], [[production-deployment-planning]].
