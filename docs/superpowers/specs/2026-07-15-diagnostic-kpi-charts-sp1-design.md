# Diagnostic KPI Charts — Sub-Project 1 (per-chart filtering + out-of-control highlighting) — Design

**Date:** 2026-07-15
**Status:** Design revised 2026-07-15 (scope widened to all 10 cards + 2 new backend trend endpoints; Alerts evaluated → light-enrichment only) — pending user review
**Trigger:** During the 2A UI-validation of the seeded VM demo data, the KPI dashboard's trend charts shared one global time window and the "Performance Trend" 7/30/90 toggle was a no-op. The user wants each metric chart to be independently filterable (current week / last week / last month / last 90 days) and to automatically highlight out-of-control points, so the charts are diagnostic rather than static.

**Scope (user-confirmed, no slicing):** SP1 covers **every KPI card on the dashboard — all 10**: Efficiency, Performance, Quality (FPY), Availability, OEE, WIP Aging, On-Time Delivery, Absenteeism (the 8 with existing backend trend endpoints), **plus PPM and Throughput Time** (the 2 cards with only a point endpoint today — SP1 adds their backend trend endpoints). No card is left as a chart-less exception.

**Decomposition (agreed):** This is SP1 of two. SP1 (this doc) = per-chart time-range filtering + out-of-control (OOC) highlighting + rule-based tooltips for all 10 metrics, including the two new backend trend endpoints (PPM, Throughput) — so SP1 is **mostly frontend with a small, well-bounded backend slice**. SP2 (separate, later) = data-driven cause analysis (a backend driver-lookup that enriches the OOC tooltip with the dominant contributing factor, falling back to SP1's rule-based hint). A separate small seed-credibility fix (backdate holds for WIP-aging; balance work-order deliveries + `required_date` for OTD) is tracked independently of this feature.

**Alerts subsystem (investigated per user):** The existing `Alert` system was evaluated as a source for OOC/cause and found unsuitable as the *engine* — it is a current-snapshot / active-status system (one active alert per subject, not one row per day), its generation is on-demand and stubbed for most KPIs (only OTD/hold/capacity emit alerts), its `kpi_key` values mismatch the trend keys (only `otd`; `quality` vs `quality_rate`), and its thresholds are hardcoded rather than read from `KPIThreshold`. Therefore OOC detection uses our own engine sourced from `KPIThreshold`; Alerts are reused only as **light enrichment of the latest point** (see §Alert enrichment) — not reinvented, but not the per-point mechanism.

## Goal

Replace the single shared trend window (and the no-op 7/30/90 toggle) with a reusable, self-contained `KpiTrendChart` component, rendered once per KPI card (all 10). Each chart owns its own time-range selector and independently fetches, computes control status, and highlights out-of-control points.

## Grounding (current state)

- Route `/kpi-dashboard` → `frontend/src/views/KPIDashboard.vue`. Global range lives in the embedded `FilterBar` (`useFilterBarData.ts` `useDatePresets`) and writes one shared `kpiStore.dateRange` consumed by all 10 cards + 4 trend charts.
- The 4 trend charts are inline `<Line>` (vue-chartjs) at `KPIDashboard.vue:204-213`, data from `useKPIChartData.ts` computeds off `kpiStore.trends.*`.
- The `trendPeriod` 7/30/90 `v-btn-toggle` (`KPIDashboard.vue:194-199`) is bound but never feeds fetch params — a real no-op to remove.
- Backend trend endpoints exist for **8** metrics and already accept `start_date`/`end_date` (`backend/routes/kpi/trends.py`: efficiency, performance, quality, availability, oee, otd, wip-aging; `backend/routes/.../absenteeism/trend`); `services/api/kpi.ts` exposes per-metric `fetch*Trend(params)`.
- **PPM and Throughput Time have only point endpoints** (`/quality/kpi/ppm`, throughput in `services/api/kpi.ts:getThroughputTime`) — **no trend endpoint**. SP1 adds two new backend trend endpoints for them (see §Backend).
- `date-fns` is a dependency. i18n has `kpi.thisWeek` / `kpi.lastWeek` / `kpi.lastMonth` (en+es); `filterBar.presets.last90Days` exists.
- **Metric-key normalization:** the threshold/seed keys are `efficiency, performance, quality_rate, oee, availability, otd`; the frontend trend fetches use `quality`, `on-time-delivery`, `wip-aging`, `absenteeism`. The chart config maps each card to (its trend fetch fn, its `KPIThreshold` key, its alert `kpi_key`) explicitly in one table so the three never silently diverge (`quality`→`quality_rate`, `on-time-delivery`→`otd`).
- charting = chart.js `^4.4.1` + vue-chartjs `^5.3.0`; **no annotation plugin** → use native per-point styling + flat line datasets (no new dependency).

## Architecture

### New component: `frontend/src/components/kpi/KpiTrendChart.vue`
One trend chart, fully self-contained.
- **Props:** `metricKey: string` (one of the 10), `title: string`, `threshold: KpiThresholdLike | null` (`{ target, warning, critical, higher_is_better } | null`), `clientId?: string | null`, `unit?: string` (default `'%'`), `fetchTrend: (params) => Promise<Point[]>` (the metric's trend fetch, injected from the config table so the component stays metric-agnostic), `alertKey?: string | null` (the alert `kpi_key` for enrichment, if any).
- **Owns:** a local `rangeKey` ref (default `'last90Days'`), the fetched trend series for that range, a loading/error state, and the computed OOC annotations.
- **Behavior:** on mount and whenever `rangeKey` (or `clientId`) changes → compute `{start,end}` via `useKpiChartRange` → call `fetchTrend({start_date, end_date, client_id})` → store the returned points locally → run `computeOutOfControl` → (optionally) fetch active alerts for `alertKey` and attach to the latest point → render.
- **Does NOT** read or write `kpiStore.dateRange` (that still drives the cards). The chart is independent by construction.
- `KPIDashboard.vue` renders **ten** `<KpiTrendChart>` (one per card metric) from a single `KPI_CHART_CONFIG` table `[{ metricKey, title-i18n-key, thresholdKey, alertKey, fetchTrend, unit }]`, passing each metric's `KPIThreshold` (from the KPI store data). The old inline `<Line>` charts and the `trendPeriod` toggle + its state are removed.

### Backend: two new trend endpoints (PPM, Throughput)
Mirror the existing trend endpoints in `backend/routes/kpi/trends.py` (same `start_date`/`end_date`/`client_id` params, same `[{date, value}]` response shape, same `validate_date_range`, same auth):
- `GET /quality/kpi/ppm/trend` — defect PPM per day over the range, from `QUALITY_ENTRY`/`DEFECT_DETAIL` (reuse the existing point-PPM calculation logic per day; PPM is lower-is-better).
- `GET /kpi/throughput-time/trend` — average throughput time per day over the range, from `PRODUCTION_ENTRY` (reuse the point-throughput calc; lower-is-better). Cap/units consistent with the point endpoint.
Add corresponding `fetchPpmTrend`/`fetchThroughputTrend` to `services/api/kpi.ts`. Both endpoints are portable SQLite+MariaDB (ORM/portable date helpers — no dialect SQL; use the existing `date_diff_days` helper convention if any date math is needed). Backend tests mirror the existing trend-endpoint tests (range param, empty range, per-client scoping).

### Alert enrichment (light reuse, latest point only)
- A thin `fetchActiveAlertsForKpi(alertKey, clientId)` in the api service calls the existing `GET /alerts/?kpi_key=<alertKey>&client_id=<...>&status=active` (normalizing `quality→quality_rate` etc. is unnecessary here because the config table stores the exact `alertKey`; where an alert `kpi_key` genuinely differs from the threshold key the table records the alert value explicitly).
- If an active alert exists for the metric, the component attaches its `message`/`recommendation` to the **most-recent** point's tooltip only (alerts are current-snapshot, not historical). No alert → nothing added. This is optional enrichment; the per-point OOC engine is the source of truth for which points are flagged. Coverage today is realistically only `otd`/`hold`; the seam is generic so it lights up as alert generation is implemented.

### Range presets: `frontend/src/composables/useKpiChartRange.ts`
- Exposes the 4 presets with i18n labels and a `computeRange(key): { start: string; end: string }` (YYYY-MM-DD), using `date-fns`:
  - `thisWeek` → `startOfWeek(today, {weekStartsOn:1})` … `today`
  - `lastWeek` → `startOfWeek(subWeeks(today,1), …)` … `endOfWeek(subWeeks(today,1), …)`
  - `lastMonth` → `startOfMonth(subMonths(today,1))` … `endOfMonth(subMonths(today,1))`
  - `last90Days` → `subDays(today,89)` … `today`
- `weekStartsOn` = Monday (1) to match manufacturing-week convention; documented in the composable.
- Labels: `kpi.thisWeek`, `kpi.lastWeek`, `kpi.lastMonth`, and a new `kpi.last90Days` (add to en+es).

### OOC engine: `frontend/src/utils/outOfControl.ts`
Pure, deterministic (unit-tested in isolation):
```
type Point = { date: string; value: number }
type Threshold = { target?: number; warning?: number; critical?: number; higher_is_better?: boolean } | null
type OOCPoint = { date: string; value: number; ooc: boolean; reasons: string[]; /* i18n keys + args */ }
type OOCResult = { points: OOCPoint[]; mean: number|null; ucl: number|null; lcl: number|null; target: number|null; critical: number|null }
computeOutOfControl(points: Point[], threshold: Threshold, opts?: { minSpcPoints?: number }): OOCResult
```
- **Threshold arm** (when `threshold?.critical != null`): a point is OOC if it breaches critical in the adverse direction — `higher_is_better !== false` → value < critical; else (lower-is-better, e.g. PPM/absenteeism) → value > critical. Reason: `ooc.belowCritical` / `ooc.aboveCritical` with (value, critical).
- **SPC arm** (when `points.length >= minSpcPoints`, default 8): `mean = avg(values)`, `sd = sample stddev`, `UCL = mean + 3sd`, `LCL = mean - 3sd`; a point is OOC if `value > UCL || value < LCL`. Reason: `ooc.beyondUcl` / `ooc.beyondLcl` with (value, limit).
- **Combine:** point is OOC if flagged by **either applicable** arm; `reasons` accumulates all that fired. Graceful degradation: no threshold → SPC only; `< minSpcPoints` → threshold only; neither applicable → all `ooc:false`. `ucl/lcl` null when SPC arm inapplicable; `target/critical` null when no threshold.
- Guards: ignore non-finite values; `sd === 0` (flat series) → no SPC flags (avoid divide/degenerate limits).

### Rendering (native chart.js, no plugin)
- Main dataset: the metric series. `pointRadius`/`pointBackgroundColor`/`pointBorderColor` are **per-point arrays** — OOC points get an enlarged radius + a distinct red ring; normal points the theme color.
- Reference lines drawn as additional flat datasets (constant y across the x-range, no points, dashed): **target** (theme accent), **critical** (red), and **UCL/LCL** (grey) when present. Legend distinguishes them.
- Tooltip callback: for an OOC point, render the value + each breached-rule reason (localized), e.g. "Efficiency 58% — below critical (60%)" or "71% — beyond −3σ (LCL 75%)". Non-OOC points show the plain value. (SP2 will append the data-driven cause line here.)
- Colors come from the existing theme tokens / the dashboard's current chart palette (no hard-coded hexes that break dark mode / the WCAG-AA gate).

## Data flow

`KpiTrendChart` mount / `rangeKey` change → `useKpiChartRange.computeRange` → `kpiApi.fetch<Metric>Trend({start_date,end_date,client_id})` → local `points` → `computeOutOfControl(points, threshold)` → chart datasets + annotations + tooltip model. The dashboard's cards + FilterBar are untouched.

## Error / edge handling

- Fetch failure → the chart shows an inline error/empty state (reuse the dashboard's existing chart empty/error styling); other charts unaffected (each is independent).
- Empty series (no data in the window) → "no data for this range" empty state, no OOC.
- 1–7 points → chart renders, threshold arm only (SPC needs ≥ 8); no UCL/LCL lines.
- `client_id` changes (client switch) → all charts refetch for their current range.

## Testing

- **`outOfControl.spec.ts`** (pure unit): threshold-only (higher- and lower-is-better), SPC-only (≥8 points beyond ±3σ flagged, within not), both-arms union, graceful degradation (no threshold / <8 points / neither), flat-series (sd=0 → no SPC), non-finite guard. Deterministic fixtures.
- **`useKpiChartRange.spec.ts`**: each preset computes the expected start/end for a fixed "today" (inject/monkeypatch today so it's deterministic — mirror the frozen-clock pattern used elsewhere); Monday week start; labels resolve in en+es.
- **`KpiTrendChart.spec.ts`** (component): renders the range selector with 4 options; changing the range triggers a refetch with the new start/end (mock the api service) and re-renders; OOC points receive the enlarged/red point style; the removed `trendPeriod` no-op is gone. Follow the repo's `<script setup>` testing convention (test the composable/util logic directly where the component can't expose internals).
- **Backend (new endpoints):** `pytest tests/` — PPM-trend + throughput-trend endpoints tested like the existing trend endpoints (range params, empty/edge range, per-client scoping, portable on SQLite+MariaDB); coverage gate ≥75% upheld.
- **i18n**: add `kpi.last90Days` (en+es); the referenced-keys gate must stay green; no raw-text lint violations.
- Frontend gates: `npm run test`, `npm run lint`, `npm run typecheck`; coverage thresholds 32/25/25/34 upheld; the deterministic contrast a11y gate + e2e browser a11y gate stay green (no color/token regression).

## Out of scope (SP1)

- The data-driven cause analysis + backend driver endpoint (that is SP2; SP1 leaves a clear tooltip seam for it, and enriches the latest point from active Alerts where they exist).
- Custom absolute date-range picker per chart (the 4 presets only; the global FilterBar keeps Custom Range for the cards).
- Implementing the stubbed alert-generation for efficiency/quality/etc. (SP1 only *consumes* whatever active alerts exist; it does not fix alert generation).
- The seed-credibility polish (WIP-aging holds / OTD deliveries) — separate seeder fix.
- Persisting each chart's selected range across reloads.

## Definition of done

- **Ten** independent `KpiTrendChart`s on the dashboard (Efficiency, Performance, Quality/FPY, Availability, OEE, WIP Aging, OTD, Absenteeism, PPM, Throughput), each with its own working this-week/last-week/last-month/last-90-days selector; the no-op toggle removed. PPM + Throughput backed by their new trend endpoints.
- Out-of-control points auto-highlighted per the adaptive threshold+SPC rule, with target/critical/UCL/LCL reference lines where applicable and rule-based tooltips; the latest point enriched from an active Alert when one exists.
- Pure OOC + range logic unit-tested deterministically; the two new trend endpoints tested; component behavior tested; all frontend + backend CI gates green; `/code-review` + `/cross-review`; merge on user confirmation.
