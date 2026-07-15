# Diagnostic KPI Charts SP1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every KPI dashboard card (all 10) its own independently-filterable trend chart (this week / last week / last month / last 90 days) that auto-highlights out-of-control points (adaptive KPIThreshold-band + SPC ±3σ) with rule-based tooltips, plus latest-point enrichment from active Alerts.

**Architecture:** Two new backend trend endpoints (PPM, Throughput) mirroring the existing ones; a pure frontend OOC engine + a range-preset composable (both unit-tested in isolation); a reusable self-contained `KpiTrendChart.vue`; the dashboard renders ten of them from one config table and drops the inline charts + the no-op 7/30/90 toggle.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (backend); Vue 3.5 `<script setup>` + Pinia + vue-chartjs/chart.js 4 + date-fns + vue-i18n (frontend); pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-07-15-diagnostic-kpi-charts-sp1-design.md`.

## Global Constraints

- **All 10 cards get a chart:** Efficiency, Performance, Quality (FPY), Availability, OEE, WIP Aging, On-Time Delivery, Absenteeism, PPM, Throughput. No card left chart-less.
- **Own OOC engine from `KPIThreshold`** (not Alerts). Adaptive: threshold-critical-breach arm (direction-aware via `higher_is_better`) + SPC mean±3σ arm (when `points.length >= 8`); flag on either applicable arm; degrade gracefully; guard flat (sd=0) / non-finite.
- **Alerts = light enrichment of the latest point only** (current-snapshot); never the per-point mechanism.
- **No new frontend dependency:** native chart.js per-point styling + flat line datasets (chart.js 4.4.1 / vue-chartjs 5.3.0; no annotation plugin).
- **Metric-key normalization in ONE config table** so trend-fetch key, `KPIThreshold` key, and alert `kpi_key` never diverge (`quality`↔`quality_rate`, `on-time-delivery`↔`otd`).
- **Range presets:** this week (`startOfWeek`→today), last week, last month (calendar-bounded via date-fns, Monday week-start), last 90 days (today−89→today). Default per chart = `last90Days`.
- Backend: `pytest tests/` from `backend/`, coverage ≥75, portable SQLite+MariaDB (ORM only, no dialect SQL). Frontend: `npm run test`/`lint`/`typecheck`, coverage 32/25/25/34, contrast a11y + e2e a11y gates stay green. Conventional commits. Files < 500 lines.

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/routes/quality/ppm_dpmo.py` | Modify | Add `GET /quality/kpi/ppm/trend` (daily PPM series) |
| `backend/routes/kpi/trends.py` | Modify | Add `GET /kpi/throughput-time/trend` (daily throughput series) |
| `backend/tests/test_kpi/test_trend_endpoints_ppm_throughput.py` | Create | Endpoint tests (range, empty, per-client) |
| `frontend/src/utils/outOfControl.ts` | Create | Pure adaptive OOC engine |
| `frontend/src/utils/__tests__/outOfControl.spec.ts` | Create | OOC unit tests |
| `frontend/src/composables/useKpiChartRange.ts` | Create | 4 calendar-bounded range presets |
| `frontend/src/composables/__tests__/useKpiChartRange.spec.ts` | Create | Range preset unit tests |
| `frontend/src/services/api/kpi.ts` | Modify | `getPpmTrend`, `getThroughputTrend`, `fetchActiveAlertsForKpi` |
| `frontend/src/i18n/locales/en.json`, `es.json` | Modify | `kpi.last90Days` key |
| `frontend/src/components/kpi/KpiTrendChart.vue` | Create | Reusable self-contained chart |
| `frontend/src/components/kpi/__tests__/KpiTrendChart.spec.ts` | Create | Component behavior test |
| `frontend/src/components/kpi/kpiChartConfig.ts` | Create | The 10-metric config table |
| `frontend/src/views/KPIDashboard.vue` | Modify | Render 10 `KpiTrendChart`; remove inline charts + `trendPeriod` |

---

### Task 1: Backend — PPM daily-trend endpoint

**Files:**
- Modify: `backend/routes/quality/ppm_dpmo.py`
- Test: `backend/tests/test_kpi/test_trend_endpoints_ppm_throughput.py`

**Interfaces:**
- Produces: `GET /quality/kpi/ppm/trend?start_date&end_date&client_id` → `[{ "date": "YYYY-MM-DD", "value": <ppm float> }]`, daily, defaulting to last 30 days. Lower-is-better metric.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_kpi/test_trend_endpoints_ppm_throughput.py`:

```python
from datetime import date, datetime, timedelta
from decimal import Decimal

from backend.db.factories import TestDataFactory


def _auth(client, db_session):
    """Returns (headers, admin_user). Reuses an existing admin if present."""
    from backend.auth.jwt import create_access_token
    from backend.orm import User
    user = db_session.query(User).filter_by(role="admin").first()
    if user is None:
        user = TestDataFactory.create_user(db_session, username="trend_admin", role="admin")
        db_session.commit()
    token = create_access_token({"sub": user.user_id, "role": "admin"})
    return {"Authorization": f"Bearer {token}"}, user


def test_ppm_trend_returns_daily_series(client, db_session):
    headers, admin = _auth(client, db_session)
    TestDataFactory.create_client(db_session, client_id="PPM-T")
    wo = TestDataFactory.create_work_order(db_session, client_id="PPM-T")
    day = date(2026, 6, 15)
    # 2 quality entries same day: 1000 inspected, 10 defective -> 10000 ppm
    for _ in range(2):
        TestDataFactory.create_quality_entry(
            db_session, work_order_id=wo.work_order_id, client_id="PPM-T",
            inspector_id=admin.user_id, inspection_date=day,
            units_inspected=500, units_defective=5,
        )
    db_session.commit()
    r = client.get("/quality/kpi/ppm/trend",
                   params={"start_date": "2026-06-14", "end_date": "2026-06-16", "client_id": "PPM-T"},
                   headers=headers)
    assert r.status_code == 200
    rows = r.json()
    hit = [row for row in rows if row["date"] == "2026-06-15"]
    assert len(hit) == 1
    assert abs(hit[0]["value"] - 10000.0) < 1.0


def test_ppm_trend_empty_range_is_empty_list(client, db_session):
    headers, _admin = _auth(client, db_session)
    r = client.get("/quality/kpi/ppm/trend",
                   params={"start_date": "2026-01-01", "end_date": "2026-01-02", "client_id": "NOPE"},
                   headers=headers)
    assert r.status_code == 200
    assert r.json() == []
```

(Confirm the test fixtures `client`/`db_session` exist in `backend/tests/conftest.py`; `create_quality_entry` signature is in `backend/db/factories.py` — pass `inspector_id` as a real user id. If `create_quality_entry` requires an existing inspector USER row, create one and use its `user_id`.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_kpi/test_trend_endpoints_ppm_throughput.py::test_ppm_trend_returns_daily_series -q`
Expected: FAIL — 404 (endpoint not defined).

- [ ] **Step 3: Implement the endpoint**

In `backend/routes/quality/ppm_dpmo.py`, mirror the point PPM calc but grouped by day. Add:

```python
@ppm_dpmo_router.get("/kpi/ppm/trend")
def get_ppm_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Daily PPM defect-rate series ((defects/inspected)*1e6 per day). Lower is better."""
    from datetime import timedelta
    from backend.orm.quality_entry import QualityEntry
    from sqlalchemy import func
    from backend.utils.date_range import validate_date_range

    validate_date_range(start_date, end_date)
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = (
        db.query(
            func.date(QualityEntry.shift_date).label("date"),
            func.sum(QualityEntry.units_inspected).label("inspected"),
            func.sum(QualityEntry.units_defective).label("defects"),
        )
        .filter(
            QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
            QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
        )
    )
    if effective_client_id:
        query = query.filter(QualityEntry.client_id == effective_client_id)
    query = query.group_by(func.date(QualityEntry.shift_date)).order_by(func.date(QualityEntry.shift_date))

    out = []
    for row in query.all():
        inspected = row.inspected or 0
        defects = row.defects or 0
        ppm = (defects / inspected * 1_000_000) if inspected > 0 else 0.0
        out.append({"date": str(row.date), "value": round(float(ppm), 2)})
    return out
```

Ensure `Any`, `Optional`, `date`, `datetime`, `Session`, `Depends`, `get_db`, `get_current_user`, `User` are imported at the top of the module (the point endpoint already imports most; add any missing).

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_kpi/test_trend_endpoints_ppm_throughput.py -q`
Expected: the 2 PPM tests PASS. (`func.date()` returns a `date`/str consistently across SQLite+MariaDB; `str(row.date)` normalizes to `YYYY-MM-DD`.)

- [ ] **Step 5: Commit**

```bash
git add backend/routes/quality/ppm_dpmo.py backend/tests/test_kpi/test_trend_endpoints_ppm_throughput.py
git commit -m "feat(kpi): daily PPM trend endpoint"
```

---

### Task 2: Backend — Throughput daily-trend endpoint

**Files:**
- Modify: `backend/routes/kpi/trends.py`
- Test: `backend/tests/test_kpi/test_trend_endpoints_ppm_throughput.py`

**Interfaces:**
- Produces: `GET /kpi/throughput-time/trend?start_date&end_date&client_id` → `[{ "date", "value" }]`, daily average throughput hours = `min(24, (Σ run_time_hours / Σ units_produced) * 100)` per day. Lower-is-better.

- [ ] **Step 1: Write the failing test**

Append to `test_trend_endpoints_ppm_throughput.py`:

```python
def test_throughput_trend_returns_daily_series(client, db_session):
    headers, admin = _auth(client, db_session)
    TestDataFactory.create_client(db_session, client_id="TP-T")
    product = TestDataFactory.create_product(db_session, client_id="TP-T")
    shift = TestDataFactory.create_shift(db_session, client_id="TP-T")
    day = date(2026, 6, 15)
    # 100 units, 8 run hours -> (8/100)*100 = 8.0h
    TestDataFactory.create_production_entry(
        db_session, client_id="TP-T", product_id=product.product_id, shift_id=shift.shift_id,
        entered_by=admin.user_id, production_date=day, units_produced=100,
        run_time_hours=Decimal("8.0"),
    )
    db_session.commit()
    r = client.get("/kpi/throughput-time/trend",
                   params={"start_date": "2026-06-14", "end_date": "2026-06-16", "client_id": "TP-T"},
                   headers=headers)
    assert r.status_code == 200
    hit = [row for row in r.json() if row["date"] == "2026-06-15"]
    assert len(hit) == 1
    assert abs(hit[0]["value"] - 8.0) < 0.01


def test_throughput_trend_caps_at_24(client, db_session):
    headers, admin = _auth(client, db_session)
    TestDataFactory.create_client(db_session, client_id="TP-CAP")
    product = TestDataFactory.create_product(db_session, client_id="TP-CAP")
    shift = TestDataFactory.create_shift(db_session, client_id="TP-CAP")
    TestDataFactory.create_production_entry(
        db_session, client_id="TP-CAP", product_id=product.product_id, shift_id=shift.shift_id,
        entered_by=admin.user_id, production_date=date(2026, 6, 15), units_produced=1,
        run_time_hours=Decimal("50.0"),  # (50/1)*100 = 5000 -> capped 24
    )
    db_session.commit()
    r = client.get("/kpi/throughput-time/trend",
                   params={"start_date": "2026-06-14", "end_date": "2026-06-16", "client_id": "TP-CAP"},
                   headers=headers)
    hit = [row for row in r.json() if row["date"] == "2026-06-15"]
    assert hit and hit[0]["value"] == 24.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_kpi/test_trend_endpoints_ppm_throughput.py::test_throughput_trend_returns_daily_series -q`
Expected: FAIL — 404.

- [ ] **Step 3: Implement the endpoint**

In `backend/routes/kpi/trends.py`, add (mirrors the frontend point formula: `(ΣrunHours/Σunits)*100`, capped 24):

```python
@trends_router.get("/throughput-time/trend")
def get_throughput_time_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Daily average throughput hours = min(24, (sum run_time_hours / sum units_produced)*100). Lower is better."""
    from backend.orm.production_entry import ProductionEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = (
        db.query(
            func.date(ProductionEntry.shift_date).label("date"),
            func.sum(ProductionEntry.run_time_hours).label("run_hours"),
            func.sum(ProductionEntry.units_produced).label("units"),
        )
        .filter(
            ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
            ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
        )
    )
    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)
    query = query.group_by(func.date(ProductionEntry.shift_date)).order_by(func.date(ProductionEntry.shift_date))

    out = []
    for row in query.all():
        units = float(row.units or 0)
        run_hours = float(row.run_hours or 0)
        value = min(24.0, (run_hours / units) * 100) if units > 0 else 0.0
        out.append({"date": str(row.date), "value": round(value, 2)})
    return out
```

`func`, `datetime`, `timedelta`, `date`, `Optional`, `Any` are already imported at the top of `trends.py` (confirm; add if missing).

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_kpi/test_trend_endpoints_ppm_throughput.py -q`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/routes/kpi/trends.py backend/tests/test_kpi/test_trend_endpoints_ppm_throughput.py
git commit -m "feat(kpi): daily throughput-time trend endpoint"
```

---

### Task 3: Frontend — pure OOC engine

**Files:**
- Create: `frontend/src/utils/outOfControl.ts`, `frontend/src/utils/__tests__/outOfControl.spec.ts`

**Interfaces:**
- Produces:
```ts
export interface OocPoint { date: string; value: number; ooc: boolean; reasons: OocReason[] }
export interface OocReason { key: string; args: Record<string, number> }   // key = i18n key
export interface OocThreshold { target?: number|null; warning?: number|null; critical?: number|null; higher_is_better?: boolean }
export interface OocResult {
  points: OocPoint[]; mean: number|null; ucl: number|null; lcl: number|null;
  target: number|null; critical: number|null;
}
export function computeOutOfControl(
  points: { date: string; value: number }[],
  threshold: OocThreshold | null,
  opts?: { minSpcPoints?: number },
): OocResult
```

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/utils/__tests__/outOfControl.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { computeOutOfControl } from '../outOfControl'

const pts = (vals: number[]) => vals.map((v, i) => ({ date: `2026-06-${(i + 1).toString().padStart(2, '0')}`, value: v }))

describe('computeOutOfControl', () => {
  it('threshold arm (higher-is-better): flags below critical', () => {
    const r = computeOutOfControl(pts([90, 55, 88]), { critical: 60, higher_is_better: true })
    expect(r.points.map((p) => p.ooc)).toEqual([false, true, false])
    expect(r.points[1].reasons[0].key).toContain('belowCritical')
  })

  it('threshold arm (lower-is-better): flags above critical', () => {
    const r = computeOutOfControl(pts([5000, 21000, 4000]), { critical: 20000, higher_is_better: false })
    expect(r.points.map((p) => p.ooc)).toEqual([false, true, false])
    expect(r.points[1].reasons[0].key).toContain('aboveCritical')
  })

  it('SPC arm: flags points beyond ±3σ when >= 8 points', () => {
    // 8 points ~84 with one outlier at 20
    const r = computeOutOfControl(pts([84, 85, 83, 86, 84, 85, 20, 84]), null)
    expect(r.ucl).not.toBeNull()
    expect(r.points[6].ooc).toBe(true)
    expect(r.points[6].reasons[0].key).toContain('beyondLcl')
  })

  it('degrades: < 8 points and no threshold -> no flags, no SPC limits', () => {
    const r = computeOutOfControl(pts([84, 20, 85]), null)
    expect(r.ucl).toBeNull()
    expect(r.points.every((p) => !p.ooc)).toBe(true)
  })

  it('flat series (sd=0) -> no SPC flags', () => {
    const r = computeOutOfControl(pts([80, 80, 80, 80, 80, 80, 80, 80]), null)
    expect(r.points.every((p) => !p.ooc)).toBe(true)
  })

  it('union: point flagged by either arm; reasons accumulate', () => {
    const r = computeOutOfControl(pts([84, 85, 83, 86, 84, 85, 40, 84]), { critical: 60, higher_is_better: true })
    expect(r.points[6].ooc).toBe(true)
    expect(r.points[6].reasons.length).toBeGreaterThanOrEqual(1)
  })

  it('ignores non-finite values without throwing', () => {
    const r = computeOutOfControl([{ date: 'x', value: NaN }, ...pts([84, 85])], { critical: 60, higher_is_better: true })
    expect(r.points[0].ooc).toBe(false)
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/utils/__tests__/outOfControl.spec.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/utils/outOfControl.ts`:

```ts
export interface OocReason {
  key: string
  args: Record<string, number>
}
export interface OocPoint {
  date: string
  value: number
  ooc: boolean
  reasons: OocReason[]
}
export interface OocThreshold {
  target?: number | null
  warning?: number | null
  critical?: number | null
  higher_is_better?: boolean
}
export interface OocResult {
  points: OocPoint[]
  mean: number | null
  ucl: number | null
  lcl: number | null
  target: number | null
  critical: number | null
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

export function computeOutOfControl(
  raw: { date: string; value: number }[],
  threshold: OocThreshold | null,
  opts: { minSpcPoints?: number } = {},
): OocResult {
  const minSpc = opts.minSpcPoints ?? 8
  const points: OocPoint[] = raw.map((p) => ({ date: p.date, value: p.value, ooc: false, reasons: [] }))

  const critical = threshold && isNum(threshold.critical) ? (threshold.critical as number) : null
  const target = threshold && isNum(threshold.target) ? (threshold.target as number) : null
  const higherBetter = threshold?.higher_is_better !== false // default true

  // Threshold arm
  if (critical !== null) {
    for (const p of points) {
      if (!isNum(p.value)) continue
      if (higherBetter && p.value < critical) {
        p.ooc = true
        p.reasons.push({ key: 'kpi.ooc.belowCritical', args: { value: p.value, critical } })
      } else if (!higherBetter && p.value > critical) {
        p.ooc = true
        p.reasons.push({ key: 'kpi.ooc.aboveCritical', args: { value: p.value, critical } })
      }
    }
  }

  // SPC arm
  let mean: number | null = null
  let ucl: number | null = null
  let lcl: number | null = null
  const finite = points.filter((p) => isNum(p.value))
  if (finite.length >= minSpc) {
    const vals = finite.map((p) => p.value)
    mean = vals.reduce((a, b) => a + b, 0) / vals.length
    const variance = vals.reduce((a, b) => a + (b - (mean as number)) ** 2, 0) / (vals.length - 1)
    const sd = Math.sqrt(variance)
    if (sd > 0) {
      ucl = mean + 3 * sd
      lcl = mean - 3 * sd
      for (const p of points) {
        if (!isNum(p.value)) continue
        if (p.value > ucl) {
          p.ooc = true
          p.reasons.push({ key: 'kpi.ooc.beyondUcl', args: { value: p.value, limit: ucl } })
        } else if (p.value < lcl) {
          p.ooc = true
          p.reasons.push({ key: 'kpi.ooc.beyondLcl', args: { value: p.value, limit: lcl } })
        }
      }
    }
  }

  return { points, mean, ucl, lcl, target, critical }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run src/utils/__tests__/outOfControl.spec.ts`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/outOfControl.ts frontend/src/utils/__tests__/outOfControl.spec.ts
git commit -m "feat(kpi): pure adaptive out-of-control engine (threshold + SPC)"
```

---

### Task 4: Frontend — range-preset composable

**Files:**
- Create: `frontend/src/composables/useKpiChartRange.ts`, `frontend/src/composables/__tests__/useKpiChartRange.spec.ts`

**Interfaces:**
- Produces: `export type KpiRangeKey = 'thisWeek'|'lastWeek'|'lastMonth'|'last90Days'`; `export function computeKpiRange(key: KpiRangeKey, today?: Date): { start: string; end: string }` (YYYY-MM-DD); `export const KPI_RANGE_KEYS: KpiRangeKey[]`; `export function useKpiChartRange()` returning `{ options }` (label i18n key + value) for the selector.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/composables/__tests__/useKpiChartRange.spec.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { computeKpiRange, KPI_RANGE_KEYS } from '../useKpiChartRange'

// Fixed "today" = Wednesday 2026-06-17 (ISO week Mon 2026-06-15 .. Sun 2026-06-21)
const TODAY = new Date(2026, 5, 17)

describe('computeKpiRange', () => {
  it('exposes exactly the four keys', () => {
    expect(KPI_RANGE_KEYS).toEqual(['thisWeek', 'lastWeek', 'lastMonth', 'last90Days'])
  })
  it('thisWeek = Monday of this week .. today', () => {
    expect(computeKpiRange('thisWeek', TODAY)).toEqual({ start: '2026-06-15', end: '2026-06-17' })
  })
  it('lastWeek = previous Mon..Sun', () => {
    expect(computeKpiRange('lastWeek', TODAY)).toEqual({ start: '2026-06-08', end: '2026-06-14' })
  })
  it('lastMonth = first..last day of previous month', () => {
    expect(computeKpiRange('lastMonth', TODAY)).toEqual({ start: '2026-05-01', end: '2026-05-31' })
  })
  it('last90Days = today-89 .. today', () => {
    expect(computeKpiRange('last90Days', TODAY)).toEqual({ start: '2026-03-20', end: '2026-06-17' })
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/composables/__tests__/useKpiChartRange.spec.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/composables/useKpiChartRange.ts`:

```ts
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format, startOfWeek, endOfWeek, subWeeks, startOfMonth, endOfMonth, subMonths, subDays } from 'date-fns'

export type KpiRangeKey = 'thisWeek' | 'lastWeek' | 'lastMonth' | 'last90Days'
export const KPI_RANGE_KEYS: KpiRangeKey[] = ['thisWeek', 'lastWeek', 'lastMonth', 'last90Days']

const WEEK_OPTS = { weekStartsOn: 1 as const } // Monday, manufacturing-week convention
const fmt = (d: Date) => format(d, 'yyyy-MM-dd')

export function computeKpiRange(key: KpiRangeKey, today: Date = new Date()): { start: string; end: string } {
  switch (key) {
    case 'thisWeek':
      return { start: fmt(startOfWeek(today, WEEK_OPTS)), end: fmt(today) }
    case 'lastWeek': {
      const lw = subWeeks(today, 1)
      return { start: fmt(startOfWeek(lw, WEEK_OPTS)), end: fmt(endOfWeek(lw, WEEK_OPTS)) }
    }
    case 'lastMonth': {
      const lm = subMonths(today, 1)
      return { start: fmt(startOfMonth(lm)), end: fmt(endOfMonth(lm)) }
    }
    case 'last90Days':
      return { start: fmt(subDays(today, 89)), end: fmt(today) }
  }
}

export function useKpiChartRange() {
  const { t } = useI18n()
  const options = computed(() =>
    KPI_RANGE_KEYS.map((key) => ({
      value: key,
      title: t(`kpi.${key}`),
    })),
  )
  return { options }
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run src/composables/__tests__/useKpiChartRange.spec.ts`
Expected: 5 passed. (If date-fns week boundary differs, re-derive expected dates from the same `weekStartsOn:1`.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useKpiChartRange.ts frontend/src/composables/__tests__/useKpiChartRange.spec.ts
git commit -m "feat(kpi): calendar-bounded chart range presets (this/last week, last month, 90d)"
```

---

### Task 5: Frontend — api trend fns, alert fetch, i18n keys

**Files:**
- Modify: `frontend/src/services/api/kpi.ts`, `frontend/src/i18n/locales/en.json`, `frontend/src/i18n/locales/es.json`
- Test: `frontend/src/services/__tests__/kpi.spec.ts` (extend)

**Interfaces:**
- Produces: `getPpmTrend(params)`, `getThroughputTrend(params)`, `fetchActiveAlertsForKpi(kpiKey, clientId)`; i18n keys `kpi.last90Days`, `kpi.ooc.belowCritical`, `kpi.ooc.aboveCritical`, `kpi.ooc.beyondUcl`, `kpi.ooc.beyondLcl`, `kpi.outOfControl`, `kpi.controlLimit`, `kpi.target`, `kpi.criticalLine`.

- [ ] **Step 1: Write the failing test**

Extend `frontend/src/services/__tests__/kpi.spec.ts` (match its existing mock-axios pattern — read the file first):

```ts
import { getPpmTrend, getThroughputTrend } from '@/services/api/kpi'
// ... within the existing describe, using the file's existing `api` mock:
it('getPpmTrend hits /quality/kpi/ppm/trend with params', async () => {
  await getPpmTrend({ start_date: '2026-06-01', end_date: '2026-06-30', client_id: 'C' })
  expect(mockGet).toHaveBeenCalledWith('/quality/kpi/ppm/trend', {
    params: { start_date: '2026-06-01', end_date: '2026-06-30', client_id: 'C' },
  })
})
it('getThroughputTrend hits /kpi/throughput-time/trend', async () => {
  await getThroughputTrend({ start_date: '2026-06-01', end_date: '2026-06-30' })
  expect(mockGet).toHaveBeenCalledWith('/kpi/throughput-time/trend', {
    params: { start_date: '2026-06-01', end_date: '2026-06-30' },
  })
})
```

(Adapt `mockGet`/`api` names to the file's actual mock setup.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/services/__tests__/kpi.spec.ts`
Expected: FAIL — `getPpmTrend`/`getThroughputTrend` not exported.

- [ ] **Step 3: Implement**

In `frontend/src/services/api/kpi.ts`, next to the other `get*Trend`:

```ts
export const getPpmTrend = (params?: Params) =>
  api.get('/quality/kpi/ppm/trend', { params }).catch(trendCatch('PPM'))

export const getThroughputTrend = (params?: Params) =>
  api.get('/kpi/throughput-time/trend', { params }).catch(trendCatch('throughput'))

export const fetchActiveAlertsForKpi = (kpiKey: string, clientId?: string | null) =>
  api
    .get('/alerts/', { params: { kpi_key: kpiKey, client_id: clientId ?? undefined, status: 'active', limit: 5 } })
    .then((r) => r.data ?? [])
    .catch(() => [])
```

Add i18n keys under the existing `kpi` object in BOTH `en.json` and `es.json`:

```json
"last90Days": "Last 90 Days",
"outOfControl": "Out of control",
"target": "Target",
"criticalLine": "Critical",
"controlLimit": "Control limit",
"ooc": {
  "belowCritical": "{value} — below critical ({critical})",
  "aboveCritical": "{value} — above critical ({critical})",
  "beyondUcl": "{value} — beyond +3σ (UCL {limit})",
  "beyondLcl": "{value} — beyond −3σ (LCL {limit})"
}
```

(Spanish: translate the strings — `last90Days`:"Últimos 90 días", `outOfControl`:"Fuera de control", `target`:"Objetivo", `criticalLine`:"Crítico", `controlLimit`:"Límite de control", and the ooc templates translated with the same `{value}`/`{critical}`/`{limit}` placeholders.) Keep the exact placeholder names — the OOC reasons pass `{value, critical}` / `{value, limit}`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run src/services/__tests__/kpi.spec.ts && npx vitest run src/theme/__tests__/contrast.a11y.spec.ts`
Expected: api tests pass; the i18n `referenced-keys` gate + `no-raw-text` lint stay green (run `npm run lint` in Step for Task 8). Confirm the new keys resolve in both locales.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/api/kpi.ts frontend/src/i18n/locales/en.json frontend/src/i18n/locales/es.json frontend/src/services/__tests__/kpi.spec.ts
git commit -m "feat(kpi): ppm/throughput trend fetchers, active-alert fetch, OOC i18n keys"
```

---

### Task 6: Frontend — `KpiTrendChart` component + config table

**Files:**
- Create: `frontend/src/components/kpi/KpiTrendChart.vue`, `frontend/src/components/kpi/kpiChartConfig.ts`, `frontend/src/components/kpi/__tests__/KpiTrendChart.spec.ts`

**Interfaces:**
- Consumes: `computeOutOfControl` (Task 3), `computeKpiRange`/`useKpiChartRange` (Task 4), the api trend fns + `fetchActiveAlertsForKpi` (Task 5).
- Produces: `<KpiTrendChart :metric-key :title :threshold :client-id :unit :fetch-trend :alert-key />`; `KPI_CHART_CONFIG: KpiChartConfigItem[]` (10 entries).

- [ ] **Step 1: Write the failing test**

Per the repo convention (VTU can't reach `<script setup>` internals — test observable behavior + extracted logic). Create `frontend/src/components/kpi/__tests__/KpiTrendChart.spec.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createVuetify } from 'vuetify'
import KpiTrendChart from '../KpiTrendChart.vue'

// stub the Line chart so we can assert the data it receives without a canvas
vi.mock('vue-chartjs', () => ({ Line: { name: 'Line', props: ['data', 'options'], template: '<div class="line-stub" />' } }))

const i18n = createI18n({ legacy: false, locale: 'en', messages: { en: {
  kpi: { thisWeek: 'This Week', lastWeek: 'Last Week', lastMonth: 'Last Month', last90Days: 'Last 90 Days',
         outOfControl: 'Out of control', target: 'Target', criticalLine: 'Critical', controlLimit: 'Control limit',
         ooc: { belowCritical: '{value} below {critical}', aboveCritical: '{value} above {critical}',
                beyondUcl: '{value} > {limit}', beyondLcl: '{value} < {limit}' } } } } })

const mountChart = (fetchTrend: any, threshold: any = { critical: 60, higher_is_better: true }) =>
  mount(KpiTrendChart, {
    props: { metricKey: 'efficiency', title: 'Efficiency', threshold, clientId: 'C', unit: '%', fetchTrend, alertKey: null },
    global: { plugins: [i18n, createVuetify()] },
  })

describe('KpiTrendChart', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches its trend on mount and renders the Line', async () => {
    const fetchTrend = vi.fn().mockResolvedValue([{ date: '2026-06-10', value: 90 }, { date: '2026-06-11', value: 88 }])
    const w = mountChart(fetchTrend)
    await flushPromises()
    expect(fetchTrend).toHaveBeenCalledTimes(1)
    expect(w.find('.line-stub').exists()).toBe(true)
  })

  it('refetches when the range selector changes', async () => {
    const fetchTrend = vi.fn().mockResolvedValue([])
    const w = mountChart(fetchTrend)
    await flushPromises()
    // simulate range change through the component's exposed handler
    ;(w.vm as any).onRangeChange?.('lastWeek')
    await flushPromises()
    expect(fetchTrend.mock.calls.length).toBeGreaterThanOrEqual(2)
    // second call carries a different start/end than the first
    expect(fetchTrend.mock.calls[1][0].start_date).not.toBe(fetchTrend.mock.calls[0][0].start_date)
  })
})
```

If VTU cannot invoke `onRangeChange` on `<script setup>`, `defineExpose({ onRangeChange })` in the component so the test can drive it (a deliberate, documented test seam).

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/components/kpi/__tests__/KpiTrendChart.spec.ts`
Expected: FAIL — component not found.

- [ ] **Step 3: Implement the config table**

Create `frontend/src/components/kpi/kpiChartConfig.ts` (maps each card so keys never diverge):

```ts
import {
  getEfficiencyTrend, getPerformanceTrend, getQualityTrend, getAvailabilityTrend, getOEETrend,
  getWIPAgingTrend, getOnTimeDeliveryTrend, getAbsenteeismTrend, getPpmTrend, getThroughputTrend,
} from '@/services/api/kpi'

export interface KpiChartConfigItem {
  metricKey: string          // stable id for the chart
  titleKey: string           // i18n key for the card title
  thresholdKey: string       // KPIThreshold.kpi_key
  alertKey: string | null    // Alert.kpi_key for latest-point enrichment (null if none)
  unit: string
  fetchTrend: (params: Record<string, unknown>) => Promise<{ data: { date: string; value: number }[] } | any>
}

// unwrap the api `{ data: [...] }` (or `[...]`) into a plain points array
export const unwrapTrend = (res: any): { date: string; value: number }[] => {
  const d = res?.data ?? res
  return Array.isArray(d) ? d.map((r: any) => ({ date: String(r.date), value: Number(r.value) })) : []
}

export const KPI_CHART_CONFIG: KpiChartConfigItem[] = [
  { metricKey: 'efficiency', titleKey: 'kpi.efficiency', thresholdKey: 'efficiency', alertKey: 'efficiency', unit: '%', fetchTrend: getEfficiencyTrend },
  { metricKey: 'performance', titleKey: 'kpi.performance', thresholdKey: 'performance', alertKey: null, unit: '%', fetchTrend: getPerformanceTrend },
  { metricKey: 'quality', titleKey: 'kpi.quality', thresholdKey: 'quality_rate', alertKey: 'quality', unit: '%', fetchTrend: getQualityTrend },
  { metricKey: 'availability', titleKey: 'kpi.availability', thresholdKey: 'availability', alertKey: null, unit: '%', fetchTrend: getAvailabilityTrend },
  { metricKey: 'oee', titleKey: 'kpi.oee', thresholdKey: 'oee', alertKey: null, unit: '%', fetchTrend: getOEETrend },
  { metricKey: 'wipAging', titleKey: 'kpi.wipAging', thresholdKey: 'wip_aging', alertKey: 'hold_approval', unit: 'd', fetchTrend: getWIPAgingTrend },
  { metricKey: 'otd', titleKey: 'kpi.onTimeDelivery', thresholdKey: 'otd', alertKey: 'otd', unit: '%', fetchTrend: getOnTimeDeliveryTrend },
  { metricKey: 'absenteeism', titleKey: 'kpi.absenteeism', thresholdKey: 'absenteeism', alertKey: null, unit: '%', fetchTrend: getAbsenteeismTrend },
  { metricKey: 'ppm', titleKey: 'kpi.ppm', thresholdKey: 'ppm', alertKey: null, unit: 'ppm', fetchTrend: getPpmTrend },
  { metricKey: 'throughput', titleKey: 'kpi.throughputTime', thresholdKey: 'throughput', alertKey: null, unit: 'h', fetchTrend: getThroughputTrend },
]
```

(Confirm each `titleKey` resolves to an existing i18n string — the dashboard already labels these cards; reuse those keys. `thresholdKey` must match the seeded `KPIThreshold.kpi_key` values; where a card has no threshold row, the OOC engine falls back to SPC-only — that's expected.)

- [ ] **Step 4: Implement `KpiTrendChart.vue`**

Create `frontend/src/components/kpi/KpiTrendChart.vue` — a `<script setup lang="ts">` component that: holds `rangeKey` (default `'last90Days'`), on mount + on `rangeKey`/`clientId` change calls `props.fetchTrend(computeKpiRange(rangeKey) + client_id)` → `unwrapTrend` → `computeOutOfControl(points, props.threshold)`; builds chart.js datasets (main line with per-point `pointRadius`/`pointBackgroundColor` arrays where `ooc` points get an enlarged red ring; plus flat dashed datasets for `target`, `critical`, `ucl`, `lcl` when non-null); a tooltip `callbacks.label` that appends the localized `reasons` for OOC points (and the enrichment alert message on the last point); a `v-select`/menu bound to `useKpiChartRange().options` calling `onRangeChange`. Register the needed chart.js components (`Chart.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend)`) once. `defineExpose({ onRangeChange })` for the test seam. Use theme tokens for colors (no hard-coded hex that breaks dark mode / the contrast gate) — reuse the palette the existing dashboard charts used (grab it from `useKPIChartData.ts` before deleting those in Task 7). Show an inline empty/error state when points are empty or the fetch rejects. Keep the file < 300 lines.

- [ ] **Step 5: Run to verify it passes**

Run: `cd frontend && npx vitest run src/components/kpi/__tests__/KpiTrendChart.spec.ts && npm run typecheck`
Expected: component tests pass; `vue-tsc` clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/kpi/
git commit -m "feat(kpi): reusable KpiTrendChart (per-chart range, OOC highlighting, alert enrichment) + config table"
```

---

### Task 7: Frontend — wire ten charts into the dashboard, remove the no-op toggle

**Files:**
- Modify: `frontend/src/views/KPIDashboard.vue`, `frontend/src/composables/useKPIDashboardData.ts`
- Test: extend `frontend/src/components/kpi/__tests__/KpiTrendChart.spec.ts` or add a small `KPIDashboard` render test

**Interfaces:**
- Consumes: `KpiTrendChart`, `KPI_CHART_CONFIG` (Task 6); the KPI store's per-metric `KPIThreshold` data.

- [ ] **Step 1: Replace the inline charts + toggle**

In `KPIDashboard.vue`: remove the four inline `<Line>` charts (`:204-213`), the "Performance Trend" `v-btn-toggle` (`:194-199`), and the `trendPeriod` state + its usage in `useKPIDashboardData.ts` (`:34`, plus the now-dead `refreshData` trend branch). Render the ten charts from the config:

```vue
<div class="kpi-charts-grid">
  <KpiTrendChart
    v-for="cfg in KPI_CHART_CONFIG"
    :key="cfg.metricKey"
    :metric-key="cfg.metricKey"
    :title="t(cfg.titleKey)"
    :threshold="thresholdFor(cfg.thresholdKey)"
    :client-id="kpiStore.selectedClientId"
    :unit="cfg.unit"
    :fetch-trend="cfg.fetchTrend"
    :alert-key="cfg.alertKey"
  />
</div>
```

Add `thresholdFor(key)` (reads the per-KPI threshold object the store already holds, or `null`), import `KPI_CHART_CONFIG` + `KpiTrendChart`, and keep the 10 metric CARDS + the global `FilterBar` exactly as-is (they still drive the cards). Remove now-unused chart computeds in `useKPIChartData.ts` if nothing else references them (grep first).

- [ ] **Step 2: Run the frontend suite + typecheck + lint**

Run: `cd frontend && npm run test && npm run typecheck && npm run lint`
Expected: all pass; no `trendPeriod` references remain (`grep -rn trendPeriod src` → none); coverage thresholds met.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/KPIDashboard.vue frontend/src/composables/useKPIDashboardData.ts frontend/src/composables/useKPIChartData.ts
git commit -m "feat(kpi): render ten diagnostic KpiTrendCharts on the dashboard; drop no-op trend toggle"
```

---

### Task 8: Integration — full suites, a11y, verification

**Files:** none new (verification + any fixups)

- [ ] **Step 1: Backend full suite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: green incl. the 2 new endpoint tests; coverage ≥75.

- [ ] **Step 2: Frontend full suite + lint + typecheck**

Run: `cd frontend && npm run test && npm run lint && npm run typecheck`
Expected: green; coverage 32/25/25/34 met; i18n referenced-keys gate + contrast a11y gate green.

- [ ] **Step 3: a11y / visual sanity**

Confirm the e2e browser a11y gate (14 screens light/dark) is unaffected — the dashboard still renders; no hard-coded colors introduced (grep the new component for `#` hex literals → none, or only via theme tokens). If the e2e snapshot asserts on the dashboard structure, update it intentionally for the ten-chart layout.

- [ ] **Step 4: Commit any fixups**

```bash
git add -A
git commit -m "test(kpi): integration fixups for diagnostic charts SP1"
```

---

## Verification (whole-PR definition of done)

1. `cd backend && python -m pytest tests/ -q` and `cd frontend && npm run test && npm run lint && npm run typecheck` all green; coverage gates upheld.
2. `git diff main...HEAD --stat` shows only the files in the File Structure table (+ the spec/plan docs).
3. All 10 cards have an independent `KpiTrendChart` with a working this-week/last-week/last-month/last-90-days selector; the no-op 7/30/90 toggle is gone; PPM + Throughput backed by their new trend endpoints.
4. OOC points highlighted per the adaptive threshold+SPC rule with target/critical/UCL/LCL reference lines and rule-based tooltips; latest point enriched from an active Alert when one exists.
5. Final whole-branch review + `/code-review` + `/cross-review`; all 7 CI checks green; merge on user confirmation.
6. Post-merge: deploy frontend + backend to the VM; live-verify on a seeded DEMO client that each chart filters independently and flags out-of-control points.
