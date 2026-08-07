# Pivot/Summarization Layer — Cycle 4 Design

**Date:** 2026-08-06
**Roadmap:** `docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md` (Cycle 4 — largest; built once, over the enriched data)
**Grounding:** `docs/reporting/reporting-capabilities-and-gaps.md` §4 (concept register, five management questions) + §5 (active lane); shipped data from Cycles 1–3 (downtime cause taxonomy, justified-delay flag, labor-hours capture + metrics).

## 1. Problem

Management's five operations questions (Q1 efficiency, Q2 downtime causes, Q3 quality/delivery, Q4 re-shuffling, Q5 holds) are now backed by captured data, but the app has no summarization layer: no pre-defined time buckets, no pre-defined groupings, no cross-metric comparison on the common hours basis, and several register-graded "reportable today" metrics (DHU, rework-% of order, priority adherence, changeover, the Q4 correlation) have never been reported at all. Managers cannot see, e.g., downtime hours by cause category by month, or units ↔ SAM-earned hours ↔ attendance hours side by side by week.

## 2. Decisions (settled in this brainstorm)

1. **Primary surface = interactive pivot screen** ("Summaries"), backed by a generic summary API. No Excel-report changes this cycle; Excel pivots can ride the same service later if management asks.
2. **Curated views on one engine**: the frontend presents five curated views (one per management question); all are presets over a single backend pivot service. No free-form pivot builder — buckets and groupings are pre-defined (committed roadmap position).
3. **Metric scope includes the reportable-today derivations** (DHU, rework-% of order, priority adherence/demotion churn, changeover time, Q4 correlation block). They are GROUP-BY derivations over existing columns — the capture-first rule is satisfied; no new capture fields anywhere in Cycle 4.
4. **Architecture = on-the-fly SQL aggregation behind a declarative dataset registry** (approach A). No materialized rollups (staleness + two sources of truth for read speed nobody needs at this volume), no bespoke per-question endpoints (5× duplicated bucket/scope/CSV logic = the average-of-averages drift class).
5. **Ratio-of-sums is structural**: derived measures are declared as (numerator, denominator) component pairs and computed from the *summed* components per bucket/group — per the 2026-08-06 ruling (tasks/lessons.md), an average-of-averages is unrepresentable in the registry.
6. **3-PR split**: PR-A engine + API (existing measures), PR-B screen + five views, PR-C new derivations + seeder enrichment + register re-grades (§9).

## 3. Pivot engine (backend)

New package `backend/pivot/`:

- **`registry.py`** — declarative dataset definitions. Each dataset declares:
  - fact model + date column (the bucketing axis) + client-scope column;
  - allowed `group_by` dimensions: a plain column, or a labeled join (e.g. line name);
  - measures: `sum(column)`, `count()`, or `ratio(numerator_measure, denominator_measure, scale)`. Ratio measures reference other declared measures by name; the engine computes them from the per-group sums. Optional-denominator rule: a ratio is `null` when its denominator sum is `<= 0` (never divide by a fabricated/zero denominator — same contract as `efficiency_available_basis`).
- **`engine.py`** — builds one SQLAlchemy GROUP BY query from `(dataset, bucket, group_by, date range, ClientScope)`.
  - **Bucketing**: the SQL query aggregates per-*day* via `func.date(...)` (the portable idiom, correct on both MariaDB and SQLite) — no dialect-specific date arithmetic in the query itself. Those per-day rows are then rolled up into `week | month | quarter | year` buckets in pure Python (`backend/pivot/buckets.py`), eliminating dialect-specific date SQL entirely rather than reproducing the `julianday()` MariaDB bug class per-dialect. Week = ISO week, Monday start (Mexico convention). Quarter derived from month. Bucket key returned as the bucket's start date (ISO `YYYY-MM-DD`), so rows sort and label deterministically.
  - Buckets are computed over stored local dates (`shift_date` etc.) — no timezone re-derivation.
- **Scoping**: `resolve_client_scope` → `scope.client_ids` filtered in the query (`None` = all clients). Never `scope.as_single()` (the #144 leader-multi-client regression class).
- **Wire types**: all measures coerced Decimal→float before serialization (the MariaDB string-Decimal class); bucket keys are strings, measure values JSON numbers.
- No migration, no new columns, no materialization anywhere in this cycle.

## 4. Datasets and measures

Exact column bindings are pinned in the implementation plan; the register (§4 of the living doc) is the authority for what each concept means.

| Dataset | Fact source | Groupings (allow-list) | Measures |
|---|---|---|---|
| `production` | ProductionEntry | client, line, product/style | units, SAM-earned hours (Σ units × ideal_cycle_time; entries lacking ideal_cycle_time excluded and surfaced as `excluded_entries`, same contract as `/api/kpi/labor-hours`), run-time hours, downtime hours, operators (Σ `employees_present`), efficiency = Σearned/Σrun *(PR-C adds: changeover = Σ setup_time_hours)* |
| `labor` | AttendanceEntry (+ allocations) | client, labor class | scheduled, actual, normal/double/triple/unsplit, billed, available-for-efficiency, absenteeism components; efficiency_available_basis = Σearned/Σavailable (cross-checked against `/api/kpi/labor-hours`) |
| `downtime` | DowntimeEntry | client, cause category, reason, line | downtime hours, event count, share-of-total ratio |
| `quality` | QualityInspection / ProductionEntry defect+rework fields | client, style | inspected, defects, FPY components *(PR-C adds: DHU = defects per 100 units, rework-% of order via per-WO rollup)* |
| `delivery` | WorkOrder | client, style, delay reason | delivered count, on-time count, OTD gross, OTD net-of-justified, late counts by classification (cross-checked against `/api/kpi/otd`) |
| `transitions` *(PR-C)* | workflow transition history (DEMOTED) | client, line | demotion count, priority-adherence ratio |
| `holds` | HoldEntry | client, hold reason category, reason | hold count, total/avg days on hold |

`labor` and `delivery` are implemented via fetch hooks (`backend/pivot/hooks.py`) that call `summarize_labor_hours`-family and `calculate_true_otd`-family functions (including `infer_planned_delivery_date` and its counting rules) verbatim rather than re-deriving the aggregation in SQL — the cross-source consistency goldens in §8 hold by construction, not by cross-checking after the fact. Hook datasets declare their components structurally (a `Component` marker in the registry): a ratio measure is omitted where its components are structurally inapplicable to the current grouping (e.g. `labor`'s `efficiency_available_basis` under a `labor_class` group_by, since production rows carry no labor class), while a window where the components apply but sum to zero still reports `0.0` — the two cases are distinct. The Q5 WIP-aging triad (stalled/old/past-due) is **not** a pivot measure: the PR-B Q5 view reads it directly from the existing WIP-aging endpoints, so it is intentionally absent from the `holds` measures above.

**Delivery basis (PR-B amendment, user decision 2026-08-07):** §10-A on real VM data showed the true-OTD basis (COMPLETED-status only, inherited from `calculate_true_otd`) leaves the delivery pivot empty — work orders progress past COMPLETED to SHIPPED/CLOSED, while management's OTD surface reads `standard_otd` (all orders with delivery dates, any status). PR-B changes `fetch_delivery` to the **delivered-orders basis**, mirroring `calculate_true_otd`'s *standard* loop verbatim (`backend/calculations/otd.py:380-433`): all orders with `actual_delivery_date` in window regardless of status; skip when no planned date is inferable (excluded from the denominator); on-time = `actual <= inferred`; justified-late tallied only among late orders; net = on-time + justified-late. The §8 delivery golden retargets from the `true_otd` to the `standard_otd` section of `calculate_true_otd`'s return value.

**Q4 correlation block** *(PR-C)*: the Q4 view presents, per bucket, demotion count next to scheduling-category downtime hours and idle-wait hours from the same window — a co-presentation of two dataset queries, not a new stored metric. Correlation stays visual/tabular; no statistical modeling.

## 5. API

- `GET /api/pivot/{dataset}` — params `bucket` (week|month|quarter|year), `group_by` (optional, from the dataset allow-list; omitted = time-only), `start_date`, `end_date`, `client_id` (optional). Response: `{dataset, bucket, group_by, rows: [{bucket_start, group_key, <measures…>}], totals: {<measures…>}}` — `excluded_entries` is an ordinary measure inside `rows`/`totals` (not a top-level field) for datasets that declare it; `totals` recomputed as ratio-of-sums over the whole window (never a sum/average of row ratios).
- `GET /api/pivot/{dataset}/csv` — identical params, streams the same rows as CSV (the data-first "every summary downloadable as its underlying data" position; consistent with the `/api/export/*` backbone).
- Auth: authenticated tier (matches all report/KPI reads); row scope via `ClientScope`. Unknown dataset/bucket/group_by → 422 naming the allow-list. `validate_date_range` reused.
- New routes ⇒ regenerate `backend/tests/test_bootstrap/openapi_surface.json` (known gate).
- **Empty-window asymmetry**: SQL-path datasets (production, downtime, quality, holds) return ratio/share measures as `null` in `totals` for an empty window (the SQL aggregate still runs, sums to zero, and the zero-denominator rule fires). Hook-path datasets (labor, delivery) omit those keys entirely from `totals` when the window is empty (the fetch hook yields no rows at all, so the component is never "produced" — see the omit-when-never-produced rule in §4). PR-B must handle both shapes (a `null` value and an absent key), not assume one.
- **Null-group sentinels are per-dataset vocabulary**, not a single constant: the generic SQL path (`_sql_day_rows` in `engine.py`) reports an ungrouped or null group value as `"unknown"`; the `delivery` hook reports a null `delay_reason` as `"none"` (mirroring `calculate_true_otd`'s own vocabulary); the `labor` hook reports an unresolvable labor class as `"unclassified"`. Callers grouping/labeling on `group_key` must match the dataset's own sentinel, not assume `"unknown"` everywhere.

## 6. Frontend — "Summaries" screen

- New route + nav-drawer entry, `PivotSummaries.vue`, five tabs = the five curated views (Q1 Efficiency, Q2 Downtime, Q3 Quality & Delivery, Q4 Re-shuffling, Q5 Holds).
- Each tab: bucket selector (week/month/quarter/year), grouping selector from that view's preset list, one AG Grid on the shared spreadsheet-natural base (`useResponsive`/`useAGGridBase`), and a **Download CSV** button that hits `/api/pivot/{dataset}/csv` with the current selection.
- Q1 is the cross-metric hours-basis view: units, SAM-earned hours, attendance/run hours, operators, OT tiers, billed, available, efficiency side by side per bucket.
- View logic lives in a composable (`usePivotView.ts`) — the `<script setup>` testability lesson. i18n en+es with statically analyzable keys (no template-literal keys — that referenced-keys-gate evasion is on record). Screen enrolled in the a11y browser contrast gate (light + dark).
- Q4 tab ships in PR-B rendering whatever the engine serves at that point; the PR-C measures light it up fully.
- The Q3 view's `delay_reason` grouping surfaces **late counts by reason** (justified/unjustified breakdown), not per-reason OTD percentages — grouped by delay reason, on-time orders all land in the `"none"` bucket, making a per-reason OTD% structurally meaningless (cross-model review carry, 2026-08-06).

## 7. Reportable-today derivations (PR-C)

DHU, rework-% of order, priority adherence/demotion churn, changeover time, and the Q4 correlation block — all added as registry measures/datasets and wired into the Q3/Q4 views. Zero new capture columns. The demo seeder is enriched in the same PR so Q4 demos credibly (e.g. seeded DEMOTED transitions with correlated scheduling-downtime), per the uniform seeder policy. Concept-register re-grades land here too (§9).

## 8. Testing & structural guards

- **Registry structural guard**: a test introspects the registry — every ratio measure must be composed of declared sum/count components; any measure bound to a per-row percentage/average column fails. Pins the 2026-08-06 ratio-of-sums ruling permanently.
- **Cross-source consistency goldens**: for the same window/scope, pivot `labor` totals == `/api/kpi/labor-hours`; pivot `delivery` OTD gross/net == `/api/kpi/otd`.
  - **`downtime` category golden — replaced, not implemented.** No function in `backend/calculations/availability.py` (or elsewhere in `backend/calculations`/`backend/services`) computes a per-`root_cause_category` downtime-hours sum reachable over a plain `Session`: `calculate_availability` totals downtime for a single work order/date with no category breakdown at all, and `kpi_cause_service.top_downtime_reason` groups by `downtime_reason` (not `root_cause_category`) and returns only the single top reason, not a comparable per-category dict. The only place a per-category sum exists is the pivot `downtime` dataset's own `category` group-by — cross-checking it against itself would not catch engine-vs-KPI drift, it would just restate the SQL. Rather than inventing a second, HTTP-route-coupled aggregation solely to give this golden something to diff against (drift risk of its own, and scope creep beyond PR-A), the downtime dataset is instead covered by: (1) `test_engine.py::test_group_by_and_share` (Task 4), which pins the `category` group-by's per-group sums, event counts, and `share_of_window_pct` against literal expected values from known seed data; and (2) §10-A's VM MariaDB live-verify, which exercises the same SQL aggregate against real data end to end. This is a self-consistency + live-data check rather than a second-implementation cross-source golden, which is the honest characterization given no independent category-sum implementation exists to diff against.
- **Bucketing helper**: unit-tested per dialect (ISO-week edges: year boundary, week 53; quarter edges), SQLite in CI + the §10 VM pass covering MariaDB — the dialect split is exactly where past prod bugs hid.
- Per-dataset unit tests (empty window, single bucket, group_by allow-list 422s, zero-denominator → null); CSV golden per dataset; one-assert-per-status-code discipline (no permissive assertions).
- Frontend: composable unit tests, i18n referenced-keys gate, a11y gate, one Playwright e2e smoke (open screen → switch tab → change bucket → download CSV).

## 9. Delivery & success criteria

- **PR-A** — `backend/pivot/` engine + registry + `/api/pivot` + `/csv` over existing measures, guards + goldens, openapi regen.
- **PR-B** — Summaries screen with the five curated views, i18n, a11y enrollment, e2e smoke.
- **PR-C** — reportable-today derivations + `transitions` dataset + seeder enrichment + living-doc §4 re-grades (DHU partial→have, rework-% partial→have, priority adherence partial→have, Q4 correlation partial→have, changeover partial→have).
- Each PR: full SDD cycle, cross-review, merge-on-green, Render auto-deploy, VM deploy + §10 live-verify.
- Success: the five curated views answer the five management questions with downloadable data on VM MariaDB — the roadmap's engagement-completion criterion.

## 10. Live verification (VM MariaDB, per PR)

- **§10-A (after PR-A):** `verify_bot` via Caddy: for SAMPLE_REF wide range, assert `/api/pivot/labor?bucket=month` totals equal `/api/kpi/labor-hours` for the same window; `/api/pivot/delivery` OTD gross/net equal `/api/kpi/otd`; a `group_by` outside the allow-list 422s; `/csv` streams rows matching the JSON; all measures JSON numbers.
- **§10-B (after PR-B):** browser login on the VM: Summaries screen renders all five tabs light+dark, bucket + grouping switches re-query, Q1 shows the cross-metric hours block, Download CSV delivers the visible slice.
- **§10-C (after PR-C):** re-seeded demo data: Q4 view shows demotions alongside scheduling-downtime/idle in the same buckets; DHU and rework-% visible in Q3; register re-grades committed.

## 11. Out of scope

- Excel-report pivot sheets (ride the same service later if management asks).
- Free-form pivot builder / chart builder (permanent positions).
- Materialized rollups; any new capture field; `day` bucket (mandate names week/month/quarter/year).
- Operator-level production, plant/module hierarchy, and all other deferred-remainder items (capture-first).
