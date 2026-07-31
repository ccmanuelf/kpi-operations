# E2E Sweep Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix every issue and observation from the 2026-07-30 e2e sweep (health 55→100), refresh seed data to current date, and live-validate each fix on the VM.

**Spec:** `docs/superpowers/specs/2026-07-30-e2e-sweep-remediation-design.md` — the fix matrix with verified root causes. Every task below references its matrix rows; the sweep report `.gstack/qa-reports/qa-report-vm-kpi-operations-2026-07-30.md` holds the failing evidence that doubles as acceptance criteria.

**Branch:** `fix/e2e-sweep-remediation` (from main @ `38721b6`).

## Global Constraints

- Root-cause fixes; class sweeps where the spec says so (#145 lesson: classify BOTH sides of every comparison/operation).
- Backend verify: `cd backend && pytest tests/` (coverage ≥75%). Frontend: `npm run lint && npm run test`. OpenAPI golden master must pass; if a fix legitimately changes the route surface (e.g. optional params), regenerate the snapshot deliberately and say so in the commit.
- No permissive assertions. Every fix lands with a test that fails before / passes after (SQLite-uncatchable classes get a schema/config-level guard + explicit live-VM validation step in Task 11).
- Commit per task; end commit messages with: Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
- Investigation-first tasks: where the matrix says "investigate", the implementer reads the code, states the root cause in the report, then fixes. Never guess-fix.

---

### Task 1: OEE float×Decimal (ISSUE-001) + mixed-arithmetic class sweep
**Files:** `backend/routes/kpi/trends.py` (or wherever `/api/kpi/oee/trend` computes), `backend/calculations/performance.py`, class sweep across `backend/calculations/` + `backend/routes/kpi/`.
Fix the captured crash site (traceback: `oee = (availability/100)*(performance/100)*(quality/100)*100` → float×Decimal). Then enumerate every arithmetic site mixing DB-sourced (potentially Decimal) values with float literals/functions in those trees; normalize each via consistent Decimal (preferred) or float coercion at the data boundary. Tests: unit test the crash path feeding `Decimal` inputs (fails before fix); repeat for each additional site found. Report must list every site classified (fixed / already-safe with reason).

### Task 2: Proxy scheme (ISSUE-012) + slash-alignment class sweep
**Files:** VM backend server config (`Dockerfile`/entrypoint/gunicorn conf — locate where workers start; add `--proxy-headers`/`FORWARDED_ALLOW_IPS` trust for the compose network), `frontend/src/**` API callers.
Class sweep: list every backend router path with trailing-slash expectation vs every frontend call string; align all slash-less callers (quality store first — captured casualty). Tests: backend test asserting redirect responses are absent for the aligned paths (frontend calls match exact routes); note the proxy-header fix is validated live in Task 11 (Location header must be https). Do not disable `redirect_slashes`.

### Task 3: client_id optional on reference endpoints (ISSUE-002/013)
**Files:** `backend/routes/production_lines.py`, `backend/routes/shifts.py` (locate exact files), using the existing `resolve_client_scope` dependency (see `docs/` + uniform-authz pattern from PR #144; NEVER `if scope.as_single():`).
Admin/poweruser with no client param → all clients; scoped roles → their scope; explicit `client_id` still honored (with scope check). Update OpenAPI snapshot deliberately (param becomes optional). Tests: per-role matrix (admin no-param 200 + all rows; leader no-param 200 + scoped; operator single-client; explicit foreign client_id → 403/filtered per existing pattern). Frontend needs no change (it already omits the param).

### Task 4: Decimal-as-string class sweep (ISSUE-011 + WIP string field)
**Files:** entity/KPI response schemas (`backend/schemas/**`), wip-aging response model.
Enumerate every response field backed by a `Numeric` column across entity list + KPI endpoints (the #145 fix covered 5 aggregate fields; this closes the rest). Apply the same JSON-number serialization mechanism #145 used. Guard test: walk the Pydantic response models and assert no Numeric-backed field serializes as str (schema-level, works on SQLite); live MariaDB validation in Task 11 (`efficiency_percentage`, `average_aging_days` arrive as numbers).

### Task 5: Alerts single source (ISSUE-008) + admin DB config auth (ISSUE-020)
**Files:** `backend/routes/alerts.py` (+ frontend alerts store if needed); admin database-config routes + `frontend/src` store for /admin/database.
Alerts: investigate the summary computation vs the empty persisted list; unify so unfiltered list length == summary total (derive list from the same breach computation, or persist at check time — follow the existing "Check Now" flow's intent). Test asserts summary.total_active == len(unfiltered list) on seeded breach data.
DB config: investigate whether the store misses the authed axios instance or the routes use a mismatched dependency; fix the wrong side; route test for admin access + store uses shared client.

### Task 6: Frontend endpoint wiring (ISSUES 016, 019, 003, 017 + thresholds obs)
**Files:** frontend stores/components for WorkOrders filter, VarianceReport, WIP card mapping, CapacityPlanning KPI strip, System Settings thresholds.
016: `/api/v1/admin/clients` → `/api/clients`; grep-kill every remaining `/api/v1/` reference. 019: variance store → `/api/assumptions/variance`. 003: WIP card consumes `average_aging_days` (+ correct lower-is-better badge). 017: wire the capacity OTD tile to the real OTD source or correct workbook computation (investigate the "textbook values" strip first). Thresholds: root-cause blank fields; saved/global values must display. Vitest per fix (mock API, assert rendered value).

### Task 7: UI polish batch (ISSUES 004, 005, 014, 015 + ES dates, y-axis, PvA overlap)
**Files:** chart config modules, `useAGGridBase`, router, i18n date renderers.
004: clamp control limits to [0,100]. 005: register Chart.js `Filler`. 014: central header ellipsis/minWidth so every grid inherits. 015: catch-all 404 route + not-found view (i18n en+es). ES dates: locale-aware date formatting in grids. Quality y-axis padding; PvA completion-bar label collision. Vitest where logic (clamp, formatter); visual items validated in Task 11 screenshots.

### Task 8: MyShift honesty (ISSUE-007)
**Files:** MyShift view/store.
Remove the mock fallback entirely (WO-2024-*, fake activity, hardcoded summary). Real data for the user's assignments; honest i18n empty state when unassigned (verify_bot case). Status rings/quick actions bind to real data or collapse into empty state. Vitest: unassigned-user renders empty state and never any mock records; assigned-user path with mocked API.

### Task 9: Help content (ISSUE-018) + Register gating (ISSUE-006) + CSP hash (obs)
**Files:** `frontend/Dockerfile` (+ build config) to ship `docs/user-guide/`; HelpCenter loader; Login view; CSP config (locate where script-src is set — frontend nginx/Caddy conf or backend middleware).
Help: guide assets present in image; loader detects HTML-instead-of-JSON and shows an explicit error (never silent "No matches"). Register: gate on demo-mode via the existing config surface (backend-wake-origin entrypoint-meta pattern or config endpoint — investigate which exists; hide on non-demo). CSP: whitelist the theme snippet via sha256 hash (value in the sweep console evidence) or externalize the script; console must be CSP-clean; pre-hydration dark restore works.

### Task 10: Seeder refresh (ISSUES 009, 010 + shipped-actuals + contacts)
**Files:** `backend/scripts/seed_sample_client*` (+ helpers).
Window must END at seed-day (relative, rolls with date). Diversify performance vs efficiency (realistic deltas, keep OOC/credibility shapes from #143). SHIPPED WOs get consistent actual_quantity/progress. Client contact fields populated. Determinism preserved. Tests: seeder unit checks (window ends today; per-entry efficiency≠performance in aggregate; shipped implies actuals>0).

### Task 11: Full verification + deploy + live validation sweep
Backend full suite; frontend lint+test; grep sweeps (no `/api/v1/`, no mock WO-2024). Push → /cross-review → PR → CI → merge → deploy Render + VM (rebuild both images, re-chown, up -d, **re-seed with --reset**) → live validation: re-check EVERY issue's original failing evidence (OEE trend 200+data, quality/attendance screens load, Location header https, alerts summary==list, WIP card real value, MyShift honest, help populated, CSP-clean console, dashboards non-zero today, per-type checks from the sweep) + fresh screenshot set + updated health score in a validation report appended to the QA report. Target: zero findings.
