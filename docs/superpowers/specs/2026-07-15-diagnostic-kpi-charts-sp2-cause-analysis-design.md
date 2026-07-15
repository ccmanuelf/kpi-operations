# Diagnostic KPI Charts SP2 — Data-Driven Cause Analysis (Design)

**Date:** 2026-07-15
**Status:** Approved design → ready for implementation plan
**Predecessor:** SP1 (`2026-07-15-diagnostic-kpi-charts-sp1-design.md`, shipped PR #141) — built the per-chart time filter, the adaptive out-of-control (OOC) engine (`frontend/src/utils/outOfControl.ts`), and the `KpiTrendChart` tooltip seam.

## Goal

When a KPI trend point is flagged out-of-control, enrich its tooltip with the **dominant contributing factor** drawn from that day's operational data (top downtime reason / defect type / absence type / late deliveries / oldest hold). Where no reliable per-day driver exists, keep exactly the SP1 rule-based value + hint. Every one of the 10 dashboard charts receives the SP2 tooltip treatment; the *source* of the cause line differs per metric.

## Non-Goals (YAGNI)

- No new UI surface, panel, or drill-down. The cause is one extra tooltip line on the existing chart.
- No caching layer, no pre-computation, no stored "cause" column. Causes are computed on demand from live operational tables for the sparse set of OOC dates only.
- No multi-factor / regression attribution. A cause is a single dominant factor from a real reason table, or nothing (→ SP1 hint). We never manufacture an attribution for a metric that lacks a reason table.
- No change to the OOC engine, the trend endpoints, or the SP1 rule-based hints.

## Core Principle: honest attribution

A cause line appears **only** when a metric has a real per-day reason table behind it. For metrics that do not (efficiency, performance, throughput), the tooltip keeps the SP1 value + hint unchanged. This avoids pointing an operator at a plausible-but-wrong lever.

## Cause Mapping (finalized against the actual calc layer)

**Real data-driven cause (7 metrics):**

| Metric | Cause source | Driver query |
|---|---|---|
| `oee` | loss-decomposition (see below) | dominant of availability-loss/performance-loss/quality-loss → that loss's driver |
| `availability` | top downtime reason | `DowntimeEntry` grouped by `downtime_reason`, sum of `downtime_duration_minutes` |
| `quality` (FPY) | top defect type | reuse `defects-by-type` logic (`DefectDetail.defect_type` × sum `defect_count`, dated via `QualityEntry.shift_date`) |
| `ppm` | top defect type | same defect-type driver as quality |
| `absenteeism` | top absence type | reuse attendance `by_reason` (`coalesce(AttendanceEntry.absence_type,'Unspecified')` × count) |
| `otd` | late work orders due that day | net-new client-scoped per-day `WorkOrder` query |
| `wip_aging` | oldest / most-chronic active hold | reuse `HoldEntry` (oldest `hold_date` among active holds; report its `hold_reason`) |

**Fallback to SP1 value + hint (3 metrics):** `efficiency`, `performance`, `throughput`.

- **Efficiency** is a labor-productivity metric (`(units_produced × ideal_cycle_time) / (employees_count × scheduled_hours)`, `backend/calculations/efficiency.py:44`), **not** an OEE component — it is not decomposable into A/P/Q losses, and no single reliable per-day driver exists.
- **Performance** (`(ideal_cycle × units) / run_time`, `performance.py:23`) is a speed metric whose loss (minor stops / speed loss) has no reason table.
- **Throughput-time** is a ratio with no reason table.

These three return `null` from the cause endpoint and the frontend keeps the SP1 hint.

## The OEE Loss-Decomposition (the one true composite)

OEE is the only metric that is a genuine `A × P × Q` composite, so it is the only one that gets decomposed. The decomposition **must mirror the OEE trend endpoint's own per-day math** (`backend/routes/kpi/trends.py`, the `/oee/trend` handler) so the value the cause engine decomposes equals the point plotted on the chart:

- **availability** for the day = `((scheduled − downtime) / scheduled) × 100`, where `scheduled = count(production_entries that day) × 8`, `downtime = sum(DowntimeEntry.downtime_duration_minutes)/60`.
- **performance** for the day = `avg(ProductionEntry.performance_percentage)` (the trend's default when null is 95).
- **quality** for the day = `sum(QualityEntry.units_passed) / sum(QualityEntry.units_inspected) × 100` (the trend's default when null is 97).

Decomposition algorithm for an OEE OOC day:

1. Compute the three component values above for `(client_id, day)`.
2. Compute each loss as `100 − min(component, 100)`.
3. Pick the **dominant loss** (largest).
4. Route to its driver:
   - availability-loss dominant → **top downtime reason** for that day.
   - quality-loss dominant → **top defect type** for that day.
   - performance-loss dominant → return a cause naming the performance component as the dominant drag **with no deeper factor** (frontend renders it as a component label; there is no reason table to name). If it prefers, the frontend may treat this like the SP1 hint — but the endpoint still returns the dominant-component identification so the tooltip can say "driven by performance".
5. If the dominant loss's driver query returns no rows (e.g. availability-loss dominant but zero downtime rows — inconsistent data), fall back to returning the dominant component label without a factor.

> **Design note — denominator consistency.** The cause service replicates the `trends.py` inline math, **not** the `backend/services/calculations/*` dual-view layer (which uses different denominators and a defect/scrap quality definition). This is a deliberate reuse-vs-consistency tradeoff: consistency with the plotted value wins, because the tooltip must explain the point the user is hovering.

## Architecture

Three units, each independently testable.

### 1. Backend cause service — `backend/services/kpi_cause_service.py` (new)

Pure-ish query functions, one per driver family. Each takes an open `Session`, `client_id: Optional[str]`, and `day: date`, and returns a `CauseResult | None`.

```python
@dataclass
class CauseResult:
    factor: str          # e.g. "Changeover", "Burr", "Sick leave", "Late: 3 orders", "Hold: QA-hold (12 days)"
    value: float | None  # magnitude behind the factor (minutes / count / days); None when not applicable
    unit: str            # "min" | "count" | "days" | ""
    share: float | None  # 0..1 fraction of the day's total this factor represents; None when not meaningful

def top_downtime_reason(session, client_id, day) -> CauseResult | None
def top_defect_type(session, client_id, day) -> CauseResult | None
def top_absence_type(session, client_id, day) -> CauseResult | None
def late_work_orders(session, client_id, day) -> CauseResult | None
def oldest_active_hold(session, client_id, day) -> CauseResult | None
def oee_dominant_loss(session, client_id, day) -> CauseResult | None   # decomposition; may delegate to downtime/defect
```

- All queries are **client-scoped** (respect `effective_client_id` from the endpoint) and **portable** (SQLite + MariaDB): date bounds via `datetime.combine(day, min/max.time())` or `func.date(shift_date) == day`, no `julianday`/`strftime`-only constructs (see [[holds-julianday-mariadb-bug]] — use `backend/db/sql_functions.py` helpers if any date arithmetic is needed for hold age).
- `top_defect_type` and `top_absence_type` reuse the existing aggregate SQL shapes (`backend/routes/quality/pareto.py`, `backend/routes/attendance.py`) — factored into the service so both the existing endpoints and the cause service share one query definition where practical, or, if extraction risks the existing endpoints' behavior, replicate the exact grouping (characterize with a test either way).
- `late_work_orders` is net-new and **must not** reuse `identify_late_orders` (`backend/calculations/otd.py:200`) — that is a today-snapshot, is not client-scoped, and uses `ProductionEntry.confirmed_by` rather than `WorkOrder.required_date`. Write a fresh per-day query: work orders whose `required_date == day` and (`actual_delivery_date IS NULL` OR `actual_delivery_date > required_date`); factor = count of late orders for that day.

### 2. Backend endpoint — dispatching `/cause` route

`GET /api/kpi/{metric}/cause?date=<YYYY-MM-DD>&client_id=<optional>`

- Lives alongside the trend routes (e.g. `backend/routes/kpi/cause.py`, registered in the KPI router).
- Auth + client-scoping copy the trend-endpoint convention verbatim: `Depends(get_current_user)`; `effective_client_id` fallback to `current_user.client_id_assigned` for non-admins.
- `metric` is validated against the known set; unknown → 422.
- Dispatch table maps each of the 7 real-driver metrics to its service function; the 3 fallback metrics (`efficiency`, `performance`, `throughput`) short-circuit to a null response.
- **Response shape (200):** `{ "date": "YYYY-MM-DD", "metric": "<metric>", "factor": <str|null>, "value": <number|null>, "unit": "<str>", "share": <number|null> }` — the four `CauseResult` fields plus `date`/`metric` echo. When there is no cause (fallback metric, or a real-driver metric with no rows that day): return **`200` with `factor: null`** (and `value`/`share` null, `unit` ""), a stable shape the frontend checks, rather than 204 — simpler for the batch client and OpenAPI snapshot.
- **OpenAPI golden master:** the new route MUST be added to `backend/tests/test_bootstrap/openapi_surface.json` via the test's own `current_surface()` regeneration, or `backend-tests` CI fails (this bit SP1 — see [[diagnostic-kpi-charts]]).
- Portability: exercised by the `mariadb-portability` CI job; the cause queries run against both engines in that job's scope.

### 3. Frontend integration — `KpiTrendChart.vue` + a fetch helper

- SP1 already computes OOC points client-side; the OOC dates are known after `computeOutOfControl`. These are **sparse** (often zero).
- After a successful trend load and OOC computation, if there are OOC points **and** the metric is a real-driver metric, fire **one batch fetch** for those OOC dates' causes (a small helper in `frontend/src/services/api/kpi.ts`, e.g. `fetchKpiCauses(metricKey, dates, clientId)` that either calls the endpoint per date concurrently or, preferably, a batch — see decision below). No OOC points → no request. Fallback metric → no request.
- The fetched causes are stored keyed by date. In `tooltipLabel` (`KpiTrendChart.vue:199`), after the SP1 reasons loop (line ~208) and before/around the alert line, if a cause exists for `point.date`, push a localized cause line: `t('kpi.cause.<driver>', { factor, value, unit, share })`. If no cause, the existing SP1 reasons/hint remain untouched.
- The batch fetch reuses SP1's `loadSeq` monotonic guard discipline so a stale cause response cannot overwrite a newer one.

**Batch vs per-date decision:** the endpoint is defined per `(metric, date)` for a clean REST contract and OpenAPI snapshot. The frontend issues one request per OOC date **concurrently** (`Promise.all`), guarded by `loadSeq`. Because OOC dates are sparse (typically 0–3 per 90-day window), this is a handful of small requests, not N-per-point. A dedicated multi-date batch endpoint is deferred (YAGNI) unless profiling shows the concurrent per-date calls are a problem.

## Data Flow

```
KpiTrendChart.load()
  → fetchTrend()                         (SP1, unchanged)
  → computeOutOfControl()                (SP1, unchanged) → OOC dates
  → if real-driver metric && OOC dates:
       fetchKpiCauses(metric, oocDates, clientId)   (SP2, concurrent, loadSeq-guarded)
       → GET /api/kpi/{metric}/cause per date
            → dispatch(metric) → kpi_cause_service.<driver>(session, client, day)
            → { factor, value, unit, share } | { factor: null }
  → store causes keyed by date
tooltipLabel(point)
  → base value line                      (SP1)
  → SP1 OOC reason hints                 (SP1)
  → SP2 cause line if cause[point.date]  (NEW)
  → latest-point alert message           (SP1)
```

## i18n

New keys under `kpi.cause.*` in **both** `en` and `es` locale files. Because template-literal keys (`t(\`kpi.cause.${driver}\`)`) **evade the referenced-keys gate** (a known SP1 gotcha), the plan MUST add every concrete key explicitly and a test asserting each resolves in both locales. Proposed keys:

- `kpi.cause.downtime` — e.g. "Top downtime: {factor} ({value} min, {share}%)"
- `kpi.cause.defect` — "Top defect: {factor} ({value}, {share}%)"
- `kpi.cause.absence` — "Top absence: {factor} ({value})"
- `kpi.cause.lateOrders` — "{value} order(s) due today ran late"
- `kpi.cause.hold` — "Oldest hold: {factor} ({value} days)"
- `kpi.cause.oeeComponent` — "Driven by {factor}" (performance-loss-dominant case with no deeper factor)

## Error Handling

- Cause enrichment is **best-effort**, exactly like SP1's alert enrichment: any failure of the cause fetch is swallowed and the chart still renders with the SP1 tooltip. A failed or empty cause never blocks the chart or removes the SP1 hint.
- Backend: a driver query returning no rows is a normal "no cause" (`factor: null`), not an error.

## Testing

- **Backend unit tests** per driver function (`top_downtime_reason`, `top_defect_type`, `top_absence_type`, `late_work_orders`, `oldest_active_hold`, `oee_dominant_loss`): seed a day, assert the dominant factor + value + share, assert empty-day → `None`.
- **OEE decomposition tests:** construct days where each of availability/performance/quality is the dominant loss; assert the correct driver is chosen; assert the day value mirrors the trend endpoint's math.
- **MariaDB portability:** the cause queries run in the `mariadb-portability` CI job with FK enforcement on; a FK-enforcement regression test covers any new query touching `DefectDetail`/`DowntimeEntry` (see [[seed-sample-client-feature]] insert-order class).
- **Endpoint tests:** auth required; client-scoping for non-admin; the 3 fallback metrics return `factor: null`; unknown metric → 422; OpenAPI surface regenerated.
- **Frontend:** `KpiTrendChart.spec.ts` — a real-driver metric with an OOC point fetches causes and injects the cause line into the tooltip; a fallback metric fires **no** cause request; a stale cause response is discarded by the `loadSeq` guard; a cause fetch failure leaves the SP1 tooltip intact.
- **Cause-service unit test** for the pure decomposition logic extracted from `KpiTrendChart` if any lands in a composable (per [[frontend-script-setup-testing]], test the composable, not the component internals).

## MariaDB / portability constraints (Global)

- All date filtering portable across SQLite + MariaDB — no `julianday()`/SQLite-only functions; use `datetime.combine` bounds or `func.date()` and the `backend/db/sql_functions.py` helpers for any age arithmetic.
- Any query inserting/reading FK-linked rows respects the MariaDB FK-enforcement class (children after parents; `DefectDetail` dated via `QualityEntry`).
- Coverage gate ≥75% (backend) stays green; frontend coverage thresholds stay green.

## Out of Scope / Deferred

- A dedicated multi-date batch cause endpoint (only if concurrent per-date calls profile poorly).
- Causes for `efficiency`/`performance`/`throughput` (no reliable driver; keep SP1 hint).
- Historical cause trends, cause aggregation, or a "top causes this month" view.

## Related Memory

[[diagnostic-kpi-charts]] (SP1), [[seed-sample-client-feature]] (the demo data these charts validate against), [[holds-julianday-mariadb-bug]] (portability class), [[frontend-script-setup-testing]], [[verify-rigorously-not-sample]].
