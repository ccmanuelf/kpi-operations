# Diagnostic KPI Charts — Sub-Project 1 (per-chart filtering + out-of-control highlighting) — Design

**Date:** 2026-07-15
**Status:** Design approved (user, 2026-07-15) — pending implementation plan
**Trigger:** During the 2A UI-validation of the seeded VM demo data, the KPI dashboard's trend charts shared one global time window and the "Performance Trend" 7/30/90 toggle was a no-op. The user wants each metric chart to be independently filterable (current week / last week / last month / last 90 days) and to automatically highlight out-of-control points, so the charts are diagnostic rather than static.

**Decomposition (agreed):** This is SP1 of two. SP1 (this doc) = per-chart time-range filtering + out-of-control (OOC) highlighting + rule-based tooltips — **frontend-only, no backend changes**. SP2 (separate, later) = data-driven cause analysis (a backend driver-lookup that enriches the OOC tooltip with the dominant contributing factor, falling back to SP1's rule-based hint). A separate small seed-credibility fix (backdate holds for WIP-aging; balance work-order deliveries + `required_date` for OTD) is tracked independently of this feature.

## Goal

Replace the single shared trend window (and the no-op 7/30/90 toggle) with a reusable, self-contained `KpiTrendChart` component: each trend chart owns its own time-range selector and independently fetches, computes control status, and highlights out-of-control points.

## Grounding (current state)

- Route `/kpi-dashboard` → `frontend/src/views/KPIDashboard.vue`. Global range lives in the embedded `FilterBar` (`useFilterBarData.ts` `useDatePresets`) and writes one shared `kpiStore.dateRange` consumed by all 10 cards + 4 trend charts.
- The 4 trend charts are inline `<Line>` (vue-chartjs) at `KPIDashboard.vue:204-213`, data from `useKPIChartData.ts` computeds off `kpiStore.trends.*`.
- The `trendPeriod` 7/30/90 `v-btn-toggle` (`KPIDashboard.vue:194-199`) is bound but never feeds fetch params — a real no-op to remove.
- Backend trend endpoints already accept `start_date`/`end_date` (`backend/routes/kpi/trends.py`); `services/api/kpi.ts` exposes per-metric `fetch*Trend(params)`. **No backend change needed.**
- `date-fns` is a dependency. i18n has `kpi.thisWeek` / `kpi.lastWeek` / `kpi.lastMonth` (en+es); `filterBar.presets.last90Days` exists.
- charting = chart.js `^4.4.1` + vue-chartjs `^5.3.0`; **no annotation plugin** → use native per-point styling + flat line datasets (no new dependency).

## Architecture

### New component: `frontend/src/components/kpi/KpiTrendChart.vue`
One trend chart, fully self-contained.
- **Props:** `metricKey: string` (e.g. `'efficiency' | 'quality' | 'availability' | 'oee'`), `title: string`, `threshold: KpiThresholdLike | null` (`{ target, warning, critical, higher_is_better } | null`), `clientId?: string | null`, `unit?: string` (default `'%'`).
- **Owns:** a local `rangeKey` ref (default `'last90Days'`), the fetched trend series for that range, a loading/error state, and the computed OOC annotations.
- **Behavior:** on mount and whenever `rangeKey` (or `clientId`) changes → compute `{start,end}` via `useKpiChartRange` → call the metric's trend fetch in `services/api/kpi.ts` with `{start_date, end_date, client_id}` → store the returned points locally → run `computeOutOfControl` → render.
- **Does NOT** read or write `kpiStore.dateRange` (that still drives the cards). The chart is independent by construction.
- `KPIDashboard.vue` renders four `<KpiTrendChart>` (one per existing trend metric), passing each metric's `KPIThreshold` (already available in the KPI store data). The old inline `<Line>` charts and the `trendPeriod` toggle + its state are removed.

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
- **i18n**: add `kpi.last90Days` (en+es); the referenced-keys gate must stay green; no raw-text lint violations.
- Frontend gates: `npm run test`, `npm run lint`, `npm run typecheck`; coverage thresholds 32/25/25/34 upheld; the deterministic contrast a11y gate + e2e browser a11y gate stay green (no color/token regression).

## Out of scope (SP1)

- The data-driven cause analysis + backend driver endpoint (that is SP2; SP1 leaves a clear tooltip seam for it).
- Adding trend charts for KPIs that don't have one today (SP1 enhances the existing 4 trend charts; the reusable component makes adding more trivial later).
- Custom absolute date-range picker per chart (the 4 presets only; the global FilterBar keeps Custom Range for the cards).
- The seed-credibility polish (WIP-aging holds / OTD deliveries) — separate seeder fix.
- Persisting each chart's selected range across reloads.

## Definition of done

- Four independent `KpiTrendChart`s on the dashboard, each with its own working this-week/last-week/last-month/last-90-days selector; the no-op toggle removed.
- Out-of-control points auto-highlighted per the adaptive threshold+SPC rule, with target/critical/UCL/LCL reference lines where applicable and rule-based tooltips.
- Pure OOC + range logic unit-tested deterministically; component behavior tested; all frontend CI gates green; `/code-review` + `/cross-review`; merge on user confirmation.
