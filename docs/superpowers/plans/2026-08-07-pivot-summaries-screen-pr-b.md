# Summaries Screen (Cycle 4 PR-B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the "Summaries" screen — five curated management views (Q1–Q5) over `/api/pivot` with bucket/grouping selectors and CSV download — plus the delivery-basis switch to delivered-orders, per amended spec `docs/superpowers/specs/2026-08-06-pivot-summarization-layer-design.md` §4 (delivery basis) + §6.

**Architecture:** One backend amendment (the `fetch_delivery` hook switches from true-OTD to the delivered-orders basis, mirroring `calculate_true_otd`'s *standard* loop; goldens retarget). The frontend adds a declarative **view-preset registry** (which datasets, groupings, and columns each Q-view shows), one **`usePivotView` composable** owning all fetch/merge/download logic (the `<script setup>` testability lesson), and one **`PivotSummaries.vue`** screen with five tabs rendering `AGGridBase` from the presets. Q5 additionally reads the WIP-aging triad from the existing endpoints via `useWIPAgingData` (spec: the triad is not a pivot measure).

**Tech Stack:** Vue 3.5 `<script setup>` + Vuetify 4.1, AG Grid Community via `@/components/grids/AGGridBase.vue` + `useAGGridBase`, vue-i18n (en+es), Pinia stores, axios client at `@/services/api/client`, Vitest + Playwright. Backend: existing pytest harness.

## Global Constraints

- Delivery basis (spec §4 amendment, 2026-08-07): `fetch_delivery` mirrors `calculate_true_otd`'s **standard** loop verbatim (`backend/calculations/otd.py:380-433`): all orders with `actual_delivery_date` in window regardless of status; skip when no planned date inferable (out of denominator); on-time = `actual <= inferred`; justified-late only among late; net = on-time + justified-late. Golden retargets to the `standard_otd` section.
- PR-B must handle BOTH empty-window shapes (spec §5): SQL-path ratios arrive as `null`; hook-path ratio keys may be **absent**. Grid renders "—" for null or missing — plain text, never a grey-styled placeholder (the grey-dash class was eradicated for a11y in Cycle 2).
- Null-group sentinels are per-dataset vocabulary (spec §5): `"unknown"` (SQL path), `"none"` (delivery delay_reason), `"unclassified"` (labor class) — label them via i18n, do not remap.
- Q3 `delay_reason` grouping shows **late counts by reason**, never per-reason OTD% (spec §6).
- i18n: all user-visible strings via statically analyzable keys in BOTH `frontend/src/i18n/locales/en.json` and `es.json` (no template-literal keys — referenced-keys gate scans `.ts` too).
- a11y: the screen joins `SCREENS` in `frontend/e2e/a11y/screens.ts` (WCAG-AA, light + dark).
- One expected status code per test assertion; frontend logic tested at composable level, not via `wrapper.vm`.
- Verification: backend `pytest tests/` from `backend/` (coverage ≥75%); frontend `npm run test` + `npm run lint` from `frontend/`.
- Branch: `feat/pivot-summaries-screen` (spec amendment already committed there). No openapi change expected (no new/changed routes) — if the surface test fails, something is wrong: stop.

## File Structure

- Modify `backend/pivot/hooks.py` — `fetch_delivery` basis switch (Task 1).
- Modify `backend/tests/test_pivot/test_hooks_golden.py` — golden retarget + basis regression test (Task 1).
- Create `frontend/src/composables/pivotPresets.ts` — the five view presets (datasets, groupings, columns) (Task 2).
- Create `frontend/src/composables/usePivotView.ts` — fetch/merge/format/download logic (Task 2).
- Modify `frontend/src/composables/useCSVExport.ts` — add path-based download used by pivot CSV (Task 3).
- Create `frontend/src/views/PivotSummaries.vue` — the screen (Task 4).
- Modify `frontend/src/router/index.ts`, `frontend/src/App.vue`, `frontend/src/i18n/locales/{en,es}.json` (Task 4).
- Modify `frontend/e2e/a11y/screens.ts` (Task 5). Create `frontend/e2e/summaries.spec.ts` (Task 5).
- Tests: `frontend/src/composables/__tests__/usePivotView.spec.ts`, `pivotPresets.spec.ts`, `useCSVExport.spec.ts` additions.

---

### Task 1: Delivery-basis switch (backend)

**Files:**
- Modify: `backend/pivot/hooks.py` (the `fetch_delivery` query + docstring)
- Test: `backend/tests/test_pivot/test_hooks_golden.py`

**Interfaces:**
- Consumes: `calculate_true_otd` return dict — read `backend/calculations/otd.py:436-505` FIRST to pin the exact `standard_otd` keys (they are `on_time`, `total`, `percentage`, `net_percentage`, plus metadata).
- Produces: `fetch_delivery` with identical signature and yield shape; only the order-selection rule changes. Everything downstream (registry, engine, routes) is untouched.

- [ ] **Step 1: Write the failing tests**

In `test_hooks_golden.py`: (a) retarget the delivery goldens from `golden["true_otd"]` to `golden["standard_otd"]` (rename `test_delivery_totals_equal_calculate_true_otd` → `test_delivery_totals_equal_standard_otd`; the golden's key names differ from true_otd's — `total` not `total_orders`); (b) add a basis regression test:

```python
def test_delivery_counts_shipped_and_closed_orders(db_session):
    """Delivered-orders basis (spec §4 amendment 2026-08-07): status is
    irrelevant — a SHIPPED and a CLOSED order with delivery dates both count.
    Under the old COMPLETED-only basis this window reported delivered == 0
    (the §10-A finding on real VM data)."""
    from datetime import datetime

    from backend.orm.work_order import WorkOrder

    for i, status in enumerate(["SHIPPED", "CLOSED"]):
        db_session.add(
            WorkOrder(
                work_order_id=f"PVT-BASIS-{i}",
                client_id="PIVOT-CLI",
                style_model="BASIS-STYLE",
                planned_quantity=10,
                status=status,
                planned_ship_date=datetime(2026, 5, 10),
                actual_delivery_date=datetime(2026, 5, 9),
            )
        )
    db_session.commit()
    out = run_pivot(
        db_session, "delivery", "month", None,
        date(2026, 5, 1), date(2026, 5, 31), ["PIVOT-CLI"],
    )
    assert out["totals"]["delivered"] == 2
    assert out["totals"]["on_time"] == 2
    assert out["totals"]["otd_gross_pct"] == 100.0
```

Implementer notes: the existing seeded golden fixture uses COMPLETED WOs — under the standard basis they still count (any status), so the parity assertions keep working once retargeted; the existing absolute anchors (`delivered == 3` etc.) must be re-derived against `standard_otd` — if the fixture seeds additional non-COMPLETED WOs with delivery dates, the standard section counts MORE than true did: recompute the literals from the fixture, don't force the old numbers. `WorkOrder.status` accepts the enum's string values via SQLAlchemy's `SQLEnum` — pass `WorkOrderStatus.SHIPPED` / `WorkOrderStatus.CLOSED` if bare strings are rejected.

- [ ] **Step 2: Run to verify failure**

Run from `backend/`: `pytest tests/test_pivot/test_hooks_golden.py -v`
Expected: the new basis test FAILS (`delivered == 0` under the old filter); retargeted goldens may fail on key names until the hook changes.

- [ ] **Step 3: Implement the basis switch**

In `backend/pivot/hooks.py::fetch_delivery`: delete the `WorkOrder.status == WorkOrderStatus.COMPLETED` filter line (keep every other filter identical); update the docstring to cite the standard loop (`otd.py:380-433`) and the spec §4 amendment; drop the now-unused `WorkOrderStatus` import if nothing else uses it. The per-order loop is already identical to the standard loop's rules (skip-if-no-inferable-date, `actual <= inferred`, justified-late only among late) — verify against `otd.py:403-421` and do NOT touch it.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_pivot/ -v` — all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/pivot/hooks.py backend/tests/test_pivot/test_hooks_golden.py
git commit -m "feat(pivot): delivery dataset -> delivered-orders basis (standard OTD), golden retargeted"
```

---

### Task 2: View presets + usePivotView composable

**Files:**
- Create: `frontend/src/composables/pivotPresets.ts`
- Create: `frontend/src/composables/usePivotView.ts`
- Test: `frontend/src/composables/__tests__/pivotPresets.spec.ts`, `frontend/src/composables/__tests__/usePivotView.spec.ts`

**Interfaces:**
- Consumes: axios `api` from `@/services/api/client` (`api.get('/pivot/${dataset}', { params })` — the client already carries the `/api` base and auth header).
- Produces (Task 4 relies on these exact names):

```typescript
// pivotPresets.ts
export interface PivotColumn { key: string; headerKey: string; kind: 'number' | 'percent' | 'count' }
export interface PivotGrouping { value: string | null; labelKey: string }   // null = time-only
export interface PivotViewPreset {
  id: 'q1' | 'q2' | 'q3' | 'q4' | 'q5'
  titleKey: string
  datasets: string[]                 // 1 or 2; two => merged client-side
  groupings: PivotGrouping[]         // intersection valid for ALL datasets of the view
  columns: PivotColumn[]
  showWipTriad?: boolean             // q5 only
}
export const PIVOT_VIEWS: PivotViewPreset[]
export const VALID_BUCKETS = ['week', 'month', 'quarter', 'year'] as const

// usePivotView.ts
export function mergePivotRows(primary: PivotRow[], secondary: PivotRow[]): PivotRow[]
export function displayValue(row: Record<string, unknown>, col: PivotColumn): string
export function usePivotView(preset: PivotViewPreset): {
  bucket: Ref<string>; groupBy: Ref<string | null>;
  startDate: Ref<string>; endDate: Ref<string>; clientId: Ref<string | null>;
  loading: Ref<boolean>; error: Ref<string | null>;
  rows: Ref<PivotRow[]>; totals: Ref<Record<string, unknown>>;
  refresh(): Promise<void>; download(): Promise<void>;
}
```

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/composables/__tests__/usePivotView.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/services/api/client', () => ({ default: { get: vi.fn() } }))
vi.mock('@/composables/useCSVExport', () => ({
  useCSVExport: () => ({ downloading: { value: false }, downloadCSVByPath: vi.fn() }),
}))

import api from '@/services/api/client'
import { mergePivotRows, displayValue, usePivotView } from '@/composables/usePivotView'
import { PIVOT_VIEWS } from '@/composables/pivotPresets'

const q2 = PIVOT_VIEWS.find((v) => v.id === 'q2')!

describe('mergePivotRows', () => {
  it('joins on (bucket_start, group_key) and unions measures', () => {
    const a = [{ bucket_start: '2026-03-01', group_key: null, units: 300, run_hours: 20 }]
    const b = [{ bucket_start: '2026-03-01', group_key: null, actual: 40, billed: 30 }]
    const merged = mergePivotRows(a, b)
    expect(merged).toHaveLength(1)
    expect(merged[0]).toMatchObject({ units: 300, run_hours: 20, actual: 40, billed: 30 })
  })

  it('keeps unmatched rows from both sides', () => {
    const a = [{ bucket_start: '2026-03-01', group_key: null, units: 1 }]
    const b = [{ bucket_start: '2026-04-01', group_key: null, actual: 2 }]
    expect(mergePivotRows(a, b)).toHaveLength(2)
  })
})

describe('displayValue', () => {
  const pct = { key: 'otd_gross_pct', headerKey: 'x', kind: 'percent' as const }
  it('renders em dash for null AND for absent key (spec §5 asymmetry)', () => {
    expect(displayValue({ otd_gross_pct: null }, pct)).toBe('—')
    expect(displayValue({}, pct)).toBe('—')
  })
  it('formats percent with 2 decimals and number with 2 decimals', () => {
    expect(displayValue({ otd_gross_pct: 58.82 }, pct)).toBe('58.82%')
    expect(displayValue({ h: 8.9 }, { key: 'h', headerKey: 'x', kind: 'number' })).toBe('8.90')
    expect(displayValue({ n: 4 }, { key: 'n', headerKey: 'x', kind: 'count' })).toBe('4')
  })
})

describe('usePivotView', () => {
  beforeEach(() => vi.mocked(api.get).mockReset())

  it('fetches every dataset of the preset with current selection', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { rows: [], totals: {} } })
    const view = usePivotView(q2)
    view.bucket.value = 'month'
    await view.refresh()
    expect(api.get).toHaveBeenCalledWith('/pivot/downtime', {
      params: expect.objectContaining({ bucket: 'month' }),
    })
  })

  it('surfaces API failure as error, not a throw', async () => {
    vi.mocked(api.get).mockRejectedValue({ response: { data: { detail: 'boom' } } })
    const view = usePivotView(q2)
    await view.refresh()
    expect(view.error.value).toContain('boom')
    expect(view.loading.value).toBe(false)
  })
})
```

```typescript
// frontend/src/composables/__tests__/pivotPresets.spec.ts
import { describe, it, expect } from 'vitest'
import { PIVOT_VIEWS } from '@/composables/pivotPresets'

describe('PIVOT_VIEWS structural invariants', () => {
  it('declares exactly q1..q5 in order', () => {
    expect(PIVOT_VIEWS.map((v) => v.id)).toEqual(['q1', 'q2', 'q3', 'q4', 'q5'])
  })
  it('every view has >=1 dataset, >=1 grouping incl. time-only, >=2 columns', () => {
    for (const v of PIVOT_VIEWS) {
      expect(v.datasets.length).toBeGreaterThanOrEqual(1)
      expect(v.groupings.some((g) => g.value === null)).toBe(true)
      expect(v.columns.length).toBeGreaterThanOrEqual(2)
    }
  })
  it('q3 delay_reason grouping exposes late counts, never a per-reason OTD% (spec §6)', () => {
    const q3 = PIVOT_VIEWS.find((v) => v.id === 'q3')!
    expect(q3.groupings.map((g) => g.value)).toContain('delay_reason')
    expect(q3.columns.some((c) => c.key === 'justified_late')).toBe(true)
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run from `frontend/`: `npx vitest run src/composables/__tests__/usePivotView.spec.ts src/composables/__tests__/pivotPresets.spec.ts`
Expected: FAIL (modules don't exist).

- [ ] **Step 3: Implement `pivotPresets.ts`**

```typescript
// frontend/src/composables/pivotPresets.ts
/** Declarative presets for the five Summaries views (spec §6). The backend
 * registry (backend/pivot/registry.py) is the authority for datasets,
 * group_by allow-lists, and measure keys — these presets must reference
 * only keys that exist there. */
export interface PivotColumn { key: string; headerKey: string; kind: 'number' | 'percent' | 'count' }
export interface PivotGrouping { value: string | null; labelKey: string }
export interface PivotViewPreset {
  id: 'q1' | 'q2' | 'q3' | 'q4' | 'q5'
  titleKey: string
  datasets: string[]
  groupings: PivotGrouping[]
  columns: PivotColumn[]
  showWipTriad?: boolean
}

export const VALID_BUCKETS = ['week', 'month', 'quarter', 'year'] as const

const timeOnly: PivotGrouping = { value: null, labelKey: 'pivot.grouping.timeOnly' }
const byClient: PivotGrouping = { value: 'client', labelKey: 'pivot.grouping.client' }

export const PIVOT_VIEWS: PivotViewPreset[] = [
  {
    // Q1: the cross-metric hours-basis view — production + labor merged per bucket.
    // Groupings limited to the intersection both datasets support (time-only, client).
    id: 'q1',
    titleKey: 'pivot.views.q1',
    datasets: ['production', 'labor'],
    groupings: [timeOnly, byClient],
    columns: [
      { key: 'units', headerKey: 'pivot.cols.units', kind: 'count' },
      { key: 'earned_hours', headerKey: 'pivot.cols.earnedHours', kind: 'number' },
      { key: 'run_hours', headerKey: 'pivot.cols.runHours', kind: 'number' },
      { key: 'actual', headerKey: 'pivot.cols.attendanceHours', kind: 'number' },
      { key: 'operators', headerKey: 'pivot.cols.operators', kind: 'count' },
      { key: 'normal', headerKey: 'pivot.cols.otNormal', kind: 'number' },
      { key: 'double', headerKey: 'pivot.cols.otDouble', kind: 'number' },
      { key: 'triple', headerKey: 'pivot.cols.otTriple', kind: 'number' },
      { key: 'billed', headerKey: 'pivot.cols.billed', kind: 'number' },
      { key: 'available_for_efficiency', headerKey: 'pivot.cols.available', kind: 'number' },
      { key: 'efficiency_available_basis', headerKey: 'pivot.cols.efficiency', kind: 'percent' },
    ],
  },
  {
    id: 'q2',
    titleKey: 'pivot.views.q2',
    datasets: ['downtime'],
    groupings: [
      timeOnly, byClient,
      { value: 'category', labelKey: 'pivot.grouping.category' },
      { value: 'reason', labelKey: 'pivot.grouping.reason' },
      { value: 'line', labelKey: 'pivot.grouping.line' },
    ],
    columns: [
      { key: 'downtime_hours', headerKey: 'pivot.cols.downtimeHours', kind: 'number' },
      { key: 'events', headerKey: 'pivot.cols.events', kind: 'count' },
      { key: 'share_of_window_pct', headerKey: 'pivot.cols.share', kind: 'percent' },
    ],
  },
  {
    // Q3: quality + delivery merged. delay_reason grouping shows LATE COUNTS
    // by reason — never a per-reason OTD% (spec §6; on-time orders all land
    // in the "none" bucket, making per-reason OTD% structurally meaningless).
    id: 'q3',
    titleKey: 'pivot.views.q3',
    datasets: ['quality', 'delivery'],
    groupings: [
      timeOnly, byClient,
      { value: 'style', labelKey: 'pivot.grouping.style' },
      { value: 'delay_reason', labelKey: 'pivot.grouping.delayReason' },
    ],
    columns: [
      { key: 'inspected', headerKey: 'pivot.cols.inspected', kind: 'count' },
      { key: 'defects', headerKey: 'pivot.cols.defects', kind: 'count' },
      { key: 'fpy_pct', headerKey: 'pivot.cols.fpy', kind: 'percent' },
      { key: 'delivered', headerKey: 'pivot.cols.delivered', kind: 'count' },
      { key: 'on_time', headerKey: 'pivot.cols.onTime', kind: 'count' },
      { key: 'justified_late', headerKey: 'pivot.cols.justifiedLate', kind: 'count' },
      { key: 'otd_gross_pct', headerKey: 'pivot.cols.otdGross', kind: 'percent' },
      { key: 'otd_net_pct', headerKey: 'pivot.cols.otdNet', kind: 'percent' },
    ],
  },
  {
    // Q4 ships rendering what the engine serves today (downtime lens);
    // PR-C's transitions dataset + correlation block light it up fully.
    id: 'q4',
    titleKey: 'pivot.views.q4',
    datasets: ['downtime'],
    groupings: [timeOnly, byClient, { value: 'line', labelKey: 'pivot.grouping.line' }],
    columns: [
      { key: 'downtime_hours', headerKey: 'pivot.cols.downtimeHours', kind: 'number' },
      { key: 'events', headerKey: 'pivot.cols.events', kind: 'count' },
    ],
  },
  {
    id: 'q5',
    titleKey: 'pivot.views.q5',
    datasets: ['holds'],
    showWipTriad: true,
    groupings: [
      timeOnly, byClient,
      { value: 'reason_category', labelKey: 'pivot.grouping.holdCategory' },
      { value: 'reason', labelKey: 'pivot.grouping.holdReason' },
    ],
    columns: [
      { key: 'holds', headerKey: 'pivot.cols.holds', kind: 'count' },
      { key: 'hold_days', headerKey: 'pivot.cols.holdDays', kind: 'number' },
      { key: 'avg_days_per_hold', headerKey: 'pivot.cols.avgDaysPerHold', kind: 'number' },
    ],
  },
]
```

Note: q3's `delay_reason` grouping is only valid for the `delivery` dataset — the quality dataset 422s on it. `usePivotView` must fetch a dataset only with a `group_by` that dataset supports: when the selected grouping isn't in a dataset's allow-list, fetch that dataset time-only and merge on `bucket_start` alone (documented in the merge contract below). The per-dataset allow-lists are: production client|line|product; labor client|labor_class; downtime client|category|reason|line; quality client|style; delivery client|style|delay_reason; holds client|reason_category|reason. Encode this as `DATASET_GROUPINGS: Record<string, string[]>` exported next to `PIVOT_VIEWS` and unit-test that every preset grouping is valid for at least one of its view's datasets.

- [ ] **Step 4: Implement `usePivotView.ts`**

```typescript
// frontend/src/composables/usePivotView.ts
/** All Summaries view logic lives here (not in <script setup>) so it is
 * unit-testable — the VTU-can't-reach-script-setup lesson. */
import { ref, type Ref } from 'vue'
import api from '@/services/api/client'
import { useCSVExport } from '@/composables/useCSVExport'
import {
  DATASET_GROUPINGS, type PivotColumn, type PivotViewPreset,
} from '@/composables/pivotPresets'

export type PivotRow = Record<string, unknown> & { bucket_start: string; group_key: string | null }

function iso(d: Date): string { return d.toISOString().slice(0, 10) }

export function mergePivotRows(primary: PivotRow[], secondary: PivotRow[]): PivotRow[] {
  const byKey = new Map<string, PivotRow>()
  for (const r of primary) byKey.set(`${r.bucket_start}|${r.group_key}`, { ...r })
  for (const r of secondary) {
    const k = `${r.bucket_start}|${r.group_key}`
    const existing = byKey.get(k)
    if (existing) Object.assign(existing, r)
    else byKey.set(k, { ...r })
  }
  return [...byKey.values()].sort((a, b) =>
    a.bucket_start === b.bucket_start
      ? String(a.group_key).localeCompare(String(b.group_key))
      : a.bucket_start.localeCompare(b.bucket_start))
}

export function displayValue(row: Record<string, unknown>, col: PivotColumn): string {
  const v = row[col.key]
  if (v === null || v === undefined) return '—'  // null AND absent (spec §5 asymmetry)
  const n = Number(v)
  if (col.kind === 'percent') return `${n.toFixed(2)}%`
  if (col.kind === 'count') return String(Math.round(n))
  return n.toFixed(2)
}

export function usePivotView(preset: PivotViewPreset) {
  const bucket = ref<string>('month')
  const groupBy = ref<string | null>(null)
  const end = new Date()
  const start = new Date(end.getTime() - 90 * 24 * 3600 * 1000)
  const startDate = ref(iso(start))
  const endDate = ref(iso(end))
  const clientId: Ref<string | null> = ref(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const rows = ref<PivotRow[]>([])
  const totals = ref<Record<string, unknown>>({})
  const { downloading, downloadCSVByPath } = useCSVExport()

  function paramsFor(dataset: string): Record<string, unknown> {
    const p: Record<string, unknown> = {
      bucket: bucket.value, start_date: startDate.value, end_date: endDate.value,
    }
    // A grouping the dataset doesn't support falls back to time-only for
    // that dataset; its rows then merge on bucket_start alone.
    if (groupBy.value && (DATASET_GROUPINGS[dataset] ?? []).includes(groupBy.value)) {
      p.group_by = groupBy.value
    }
    if (clientId.value) p.client_id = clientId.value
    return p
  }

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      let merged: PivotRow[] = []
      let mergedTotals: Record<string, unknown> = {}
      for (const ds of preset.datasets) {
        const { data } = await api.get(`/pivot/${ds}`, { params: paramsFor(ds) })
        merged = merged.length ? mergePivotRows(merged, data.rows) : data.rows
        mergedTotals = { ...mergedTotals, ...data.totals }
      }
      rows.value = merged
      totals.value = mergedTotals
    } catch (e) {
      const ax = e as { response?: { data?: { detail?: unknown } }; message?: string }
      error.value = String(ax?.response?.data?.detail ?? ax?.message ?? 'load failed')
    } finally {
      loading.value = false
    }
  }

  async function download(): Promise<void> {
    // One CSV per dataset of the view — each grid slice is downloadable as
    // its own underlying data (data-first position; composite views issue
    // one file per dataset).
    for (const ds of preset.datasets) {
      await downloadCSVByPath(`/pivot/${ds}/csv`, paramsFor(ds),
        `pivot_${ds}_${bucket.value}_${startDate.value}_${endDate.value}.csv`)
    }
  }

  return { bucket, groupBy, startDate, endDate, clientId, loading, error, rows, totals, downloading, refresh, download }
}
```

- [ ] **Step 5: Run tests** — `npx vitest run src/composables/__tests__/ -t pivot` then the two new spec files fully. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/composables/pivotPresets.ts frontend/src/composables/usePivotView.ts frontend/src/composables/__tests__/pivotPresets.spec.ts frontend/src/composables/__tests__/usePivotView.spec.ts
git commit -m "feat(summaries): view presets + usePivotView composable (fetch/merge/format/download)"
```

---

### Task 3: Path-based CSV download in useCSVExport

**Files:**
- Modify: `frontend/src/composables/useCSVExport.ts`
- Test: `frontend/src/composables/__tests__/useCSVExport.spec.ts` (extend the existing file if present; create following the existing composable-test style otherwise)

**Interfaces:**
- Produces: `downloadCSVByPath(path: string, params: CSVExportParams, filename: string | null): Promise<void>` exported from `useCSVExport()` alongside the existing `downloadCSV`; `downloadCSV(entityType, ...)` becomes a delegate calling `downloadCSVByPath('/export/' + entityType, ...)`. The blob/anchor/notification behavior is IDENTICAL for both (single implementation).

- [ ] **Step 1: Write the failing test** — mock `@/services/api/client` and the notification store (mirror the existing mocking style in `frontend/src/composables/__tests__/`); assert `downloadCSVByPath('/pivot/downtime/csv', { bucket: 'month' }, 'x.csv')` calls `api.get('/pivot/downtime/csv', { params: { bucket: 'month' }, responseType: 'blob' })`, and that `downloadCSV('production-entries', {})` still hits `/export/production-entries` (delegation intact).
- [ ] **Step 2: Run to verify failure** — `npx vitest run src/composables/__tests__/useCSVExport.spec.ts`.
- [ ] **Step 3: Implement** — extract the current body of `downloadCSV` into `downloadCSVByPath(path, params, filename)` (replace the `/export/${entityType}` URL with `path`; keep the content-disposition filename sniffing, blob anchor, and success/error notifications verbatim); reimplement `downloadCSV(entityType, params, filename)` as `return downloadCSVByPath('/export/' + entityType, params, filename ?? entityType + '_export.csv')`. Return both from the composable.
- [ ] **Step 4: Run tests** — the new spec plus every existing test that touches `useCSVExport` (`npx vitest run src/composables/__tests__/`). Expected: PASS, no behavior change for existing callers.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useCSVExport.ts frontend/src/composables/__tests__/useCSVExport.spec.ts
git commit -m "refactor(csv): path-based downloadCSVByPath; entity export delegates"
```

---

### Task 4: PivotSummaries.vue + route + nav + i18n

**Files:**
- Create: `frontend/src/views/PivotSummaries.vue`
- Modify: `frontend/src/router/index.ts` (new route), `frontend/src/App.vue` (nav entry), `frontend/src/i18n/locales/en.json` + `es.json` (all `pivot.*` + `navigation.summaries` keys)
- Test: `frontend/src/views/__tests__/PivotSummaries.spec.ts` (shallow render assertions only — logic is already covered at composable level)

**Interfaces:**
- Consumes: `PIVOT_VIEWS`, `VALID_BUCKETS` (Task 2), `usePivotView`, `displayValue` (Task 2), `AGGridBase` from `@/components/grids/AGGridBase.vue` (see `frontend/src/views/WorkOrderManagement.vue:154,220` for the working consumer pattern), `useWIPAgingData` from `@/composables/useWIPAgingData` (Q5 triad — spec: not a pivot measure).
- Produces: route `/summaries` (name `summaries`, `meta: { requiresAuth: true }`, lazy import — copy the exact route-object shape of the `/kpi-dashboard` entry at `frontend/src/router/index.ts:42-46`).

- [ ] **Step 1: Write the failing view test**

```typescript
// frontend/src/views/__tests__/PivotSummaries.spec.ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/services/api/client', () => ({ default: { get: vi.fn().mockResolvedValue({ data: { rows: [], totals: {} } }) } }))

import PivotSummaries from '@/views/PivotSummaries.vue'
// Mirror the global-plugins test setup (vuetify + i18n + pinia) used by the
// existing view specs in frontend/src/views/__tests__/ — copy their mount
// helper/imports exactly.

describe('PivotSummaries', () => {
  it('renders five tabs, one per management question', () => {
    const wrapper = mount(PivotSummaries, { global: { /* per existing view-spec helper */ } })
    expect(wrapper.findAll('[data-testid^="pivot-tab-"]')).toHaveLength(5)
  })
  it('renders bucket selector with the four buckets and a download button', () => {
    const wrapper = mount(PivotSummaries, { global: { /* per existing view-spec helper */ } })
    expect(wrapper.find('[data-testid="pivot-bucket-select"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pivot-download"]').exists()).toBe(true)
  })
})
```

Implementer note: the `global:` mount options placeholder above is deliberate — copy the working plugin/mocks setup verbatim from an existing spec in `frontend/src/views/__tests__/` (they share a vuetify+i18n+pinia harness); do not invent a new one.

- [ ] **Step 2: Run to verify failure** — `npx vitest run src/views/__tests__/PivotSummaries.spec.ts`.

- [ ] **Step 3: Implement the view**

```vue
<!-- frontend/src/views/PivotSummaries.vue -->
<template>
  <v-container fluid class="pa-4">
    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">{{ $t('pivot.title') }}</h1>
        <p class="text-subtitle-1 text-medium-emphasis">{{ $t('pivot.subtitle') }}</p>
      </v-col>
    </v-row>

    <v-tabs v-model="activeTab" class="mt-2">
      <v-tab v-for="view in PIVOT_VIEWS" :key="view.id" :value="view.id"
             :data-testid="`pivot-tab-${view.id}`">
        {{ $t(view.titleKey) }}
      </v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <v-window-item v-for="view in PIVOT_VIEWS" :key="view.id" :value="view.id">
        <PivotViewPanel :preset="view" />
      </v-window-item>
    </v-window>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { PIVOT_VIEWS } from '@/composables/pivotPresets'
import PivotViewPanel from '@/components/PivotViewPanel.vue'

const activeTab = ref('q1')
</script>
```

Create `frontend/src/components/PivotViewPanel.vue` (one panel = selectors + grid + download; all logic from `usePivotView`):

```vue
<!-- frontend/src/components/PivotViewPanel.vue -->
<template>
  <div class="mt-4">
    <v-row density="compact">
      <v-col cols="6" md="2">
        <v-select v-model="view.bucket.value" :items="bucketItems" item-title="title" item-value="value"
                  :label="$t('pivot.bucket')" density="compact" variant="outlined"
                  data-testid="pivot-bucket-select" @update:model-value="view.refresh" />
      </v-col>
      <v-col cols="6" md="2">
        <v-select v-model="view.groupBy.value" :items="groupingItems" item-title="title" item-value="value"
                  :label="$t('pivot.groupBy')" density="compact" variant="outlined"
                  data-testid="pivot-grouping-select" @update:model-value="view.refresh" />
      </v-col>
      <v-col cols="6" md="2">
        <v-text-field v-model="view.startDate.value" type="date" :label="$t('filters.startDate')"
                      density="compact" variant="outlined" @change="view.refresh" />
      </v-col>
      <v-col cols="6" md="2">
        <v-text-field v-model="view.endDate.value" type="date" :label="$t('filters.endDate')"
                      density="compact" variant="outlined" @change="view.refresh" />
      </v-col>
      <v-col cols="12" md="2">
        <v-btn color="primary" block :loading="view.downloading.value" data-testid="pivot-download"
               @click="view.download">
          <v-icon start>mdi-download</v-icon>{{ $t('pivot.downloadCsv') }}
        </v-btn>
      </v-col>
    </v-row>

    <v-alert v-if="view.error.value" type="error" density="compact" class="mb-2">{{ view.error.value }}</v-alert>

    <AGGridBase :row-data="gridRows" :column-defs="columnDefs" :loading="view.loading.value" />

    <WipTriadBlock v-if="preset.showWipTriad" class="mt-4" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import WipTriadBlock from '@/components/WipTriadBlock.vue'
import { VALID_BUCKETS, type PivotViewPreset } from '@/composables/pivotPresets'
import { displayValue, usePivotView } from '@/composables/usePivotView'

const props = defineProps<{ preset: PivotViewPreset }>()
const { t } = useI18n()
const view = usePivotView(props.preset)

const bucketItems = computed(() => VALID_BUCKETS.map((b) => ({ value: b, title: t(`pivot.buckets.${b}`) })))
const groupingItems = computed(() => props.preset.groupings.map((g) => ({ value: g.value, title: t(g.labelKey) })))
const columnDefs = computed(() => [
  { field: 'bucket_start', headerName: t('pivot.cols.bucket') },
  { field: 'group_key', headerName: t('pivot.cols.group'),
    valueFormatter: (p: { value: unknown }) => p.value == null ? '—' : String(p.value) },
  ...props.preset.columns.map((c) => ({
    field: c.key, headerName: t(c.headerKey),
    valueFormatter: (p: { data: Record<string, unknown> }) => displayValue(p.data ?? {}, c),
  })),
])
const gridRows = computed(() => view.rows.value)

onMounted(view.refresh)
</script>
```

Create `frontend/src/components/WipTriadBlock.vue` — a thin card row rendering the stalled/old/past-due triad from `useWIPAgingData` (reuse its existing fetch + formatting; no new API surface — read `frontend/src/composables/useWIPAgingData.ts` and mirror how `views/kpi/WIPAging.vue` consumes it, showing only the three headline numbers + i18n labels `pivot.wip.stalled|old|pastDue`).

Router (copy shape of `frontend/src/router/index.ts:42-46`): path `/summaries`, name `summaries`, lazy `() => import('@/views/PivotSummaries.vue')`, `meta: { requiresAuth: true }`. Nav entry in `frontend/src/App.vue` beside the Plan-vs-Actual item (line ~82): `<v-list-item prepend-icon="mdi-table-pivot" :title="$t('navigation.summaries')" to="/summaries" />` — match the surrounding group's exact prop style.

i18n: add ALL referenced keys to BOTH `en.json` and `es.json`: `navigation.summaries` ("Summaries"/"Resúmenes"), `pivot.title`, `pivot.subtitle`, `pivot.bucket`, `pivot.groupBy`, `pivot.downloadCsv`, `pivot.buckets.week|month|quarter|year`, `pivot.grouping.timeOnly|client|category|reason|line|style|delayReason|holdCategory|holdReason`, `pivot.views.q1..q5` (Q1 Efficiency / Q2 Downtime / Q3 Quality & Delivery / Q4 Re-shuffling / Q5 Holds + Spanish), `pivot.cols.*` (every headerKey used in the presets + `bucket`, `group`), `pivot.wip.stalled|old|pastDue`. The referenced-keys gate fails the suite if any key is missing in either locale — run it early (`npx vitest run` includes it).

- [ ] **Step 4: Run tests** — `npx vitest run src/views/__tests__/PivotSummaries.spec.ts` then the full `npm run test` (i18n referenced-keys + no-raw-text gates must be green). Expected: PASS.
- [ ] **Step 5: Run lint** — `npm run lint` (the `@intlify/vue-i18n/no-raw-text` rule catches any hardcoded string). Expected: clean.
- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/PivotSummaries.vue frontend/src/components/PivotViewPanel.vue frontend/src/components/WipTriadBlock.vue frontend/src/router/index.ts frontend/src/App.vue frontend/src/i18n/locales/en.json frontend/src/i18n/locales/es.json frontend/src/views/__tests__/PivotSummaries.spec.ts
git commit -m "feat(summaries): PivotSummaries screen — 5 curated views, route, nav, i18n en+es"
```

---

### Task 5: a11y enrollment + e2e smoke

**Files:**
- Modify: `frontend/e2e/a11y/screens.ts` (add the screen)
- Create: `frontend/e2e/summaries.spec.ts`

**Interfaces:**
- Consumes: the login/auth helper pattern used by existing specs — read `frontend/e2e/capacity-kpi-tracking.spec.ts` (a small, current example) and copy its setup verbatim.

- [ ] **Step 1: Enroll in the a11y gate** — append to `SCREENS` in `frontend/e2e/a11y/screens.ts`:

```typescript
  { name: 'summaries', path: '/summaries' },
```

(The gate audits light + dark automatically. If the audit flags a real contrast failure in the new screen, FIX the style — additions to `ALLOWLIST` are only for verified false-positives, per the file's own precedent notes.)

- [ ] **Step 2: Write the e2e smoke**

```typescript
// frontend/e2e/summaries.spec.ts
// Auth/setup: copy the exact login helper + test.beforeEach used by
// frontend/e2e/capacity-kpi-tracking.spec.ts (same fixture user).
import { test, expect } from '@playwright/test'

test.describe('Summaries screen', () => {
  test('tabs render, bucket switch re-queries, CSV downloads', async ({ page }) => {
    await page.goto('/summaries')
    await expect(page.getByTestId('pivot-tab-q1')).toBeVisible()
    await expect(page.getByTestId('pivot-tab-q5')).toBeVisible()

    await page.getByTestId('pivot-tab-q2').click()
    const req = page.waitForRequest((r) => r.url().includes('/api/pivot/downtime'))
    await page.getByTestId('pivot-bucket-select').click()
    await page.getByRole('option', { name: /quarter/i }).click()
    await req

    const download = page.waitForEvent('download')
    await page.getByTestId('pivot-download').click()
    expect((await download).suggestedFilename()).toContain('pivot_downtime')
  })
})
```

(Selector details may need adjusting to the Vuetify DOM — keep the three behaviors asserted: tabs visible, bucket change fires a `/api/pivot/*` request, download produces a `pivot_*` file.)

- [ ] **Step 3: Run the smoke locally** — `npx playwright test e2e/summaries.spec.ts --project=chromium` (bring the dev stack up the same way the repo's e2e workflow does — see `.github/workflows/e2e.yml` for the exact server commands). Expected: PASS.
- [ ] **Step 4: Run the a11y gate for the new screen** — `npx playwright test e2e/a11y-contrast.spec.ts --project=chromium`. Expected: PASS with zero new findings (or fix the styles).
- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/a11y/screens.ts frontend/e2e/summaries.spec.ts
git commit -m "test(summaries): a11y gate enrollment + e2e smoke (tabs, re-query, CSV)"
```

---

### Task 6: Full verification

**Files:** none new — verification only (plus any fix the suites force).

- [ ] **Step 1: Backend full suite** — from `backend/`: `pytest tests/`. Expected: 0 failures, coverage ≥75%. (Task 1 touched hooks + goldens; nothing else backend-side.)
- [ ] **Step 2: Frontend full suite + lint** — from `frontend/`: `npm run test` (includes contrast vitest gate, referenced-keys, doc-coverage) and `npm run lint`. Expected: green.
- [ ] **Step 3: Pre-commit on branch files** — from repo root: `pre-commit run --files $(git diff --name-only main...HEAD | tr '\n' ' ')`. Expected: all hooks pass.
- [ ] **Step 4: Commit anything the gates forced** (formatting only) and stop. **Ship sequence is controller/user-gated**: push, `/cross-review`, PR, merge-on-green, Render, VM deploy, then the §10-B live-verify (browser: five tabs light+dark, bucket/grouping switches re-query, Q1 cross-metric block, CSV downloads; PLUS delivery-basis check: `/api/pivot/delivery` totals on SAMPLE_REF now match `standard_otd` — expected ≈ 58.82/70.59 on the VM's seeded data instead of 0).

---

## Self-Review (completed at write time)

- **Spec coverage:** §4 delivery-basis amendment (Task 1), §6 screen/tabs/selectors/CSV/Q1-cross-metric (Tasks 2+4), §6 delay_reason-late-counts (Task 2 preset + guard test), §6 composable-extraction + i18n + a11y (Tasks 2, 4, 5), Q5 triad from existing endpoints (Task 4 WipTriadBlock), §5 null-vs-absent handling (Task 2 `displayValue` + test), e2e smoke (Task 5). Q4 renders current engine output per §6 — full lighting is PR-C.
- **Placeholder scan:** the two "copy the existing harness verbatim" notes (view-spec mount helper, e2e auth helper) are deliberate read-the-file instructions pointing at exact files, not deferred design; the WipTriadBlock is specified by its data source, consumer precedent, and displayed fields.
- **Type consistency:** `PivotViewPreset`/`PivotColumn`/`PivotGrouping`/`DATASET_GROUPINGS` defined in Task 2 and consumed by name in Task 4; `downloadCSVByPath` signature identical in Tasks 2 (mock) and 3 (implementation); `displayValue(row, col)` used in Task 4's columnDefs matches Task 2's export.
