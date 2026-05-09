# Phase B.3 — 0%-coverage Vue views audit

**Status**: 🔄 in progress (started 2026-05-07)
**Scope**: All `frontend/src/views/**/*.vue` files reporting 0% line coverage in the latest `vitest run --coverage` snapshot.

## Inventory (47 files, 0% line coverage)

Snapshot from `frontend/coverage/coverage-final.json` (re-generated 2026-05-07 after B.2 closeout):

### Bucket 1 — KPI detail pages (8 files)

Each is a thin presentation layer that delegates **all logic** to a `useXData.ts` + `useXCharts.ts` composable pair. The composables themselves are also at 0%.

| View (statements) | Composable backing it |
|---|---|
| `kpi/Efficiency.vue` (151) | `useEfficiencyData.ts` (111) + `useEfficiencyCharts.ts` (10) |
| `kpi/Performance.vue` (151) | `usePerformanceData.ts` (108) + `usePerformanceCharts.ts` (10) |
| `kpi/Quality.vue` (247) | `useQualityData.ts` (124) + `useQualityCharts.ts` (13) |
| `kpi/Availability.vue` (171) | **inline** — no composable |
| `kpi/OEE.vue` (157) | **inline** — no composable |
| `kpi/Absenteeism.vue` (185) | **inline** — no composable |
| `kpi/OnTimeDelivery.vue` (167) | **inline** — no composable |
| `kpi/WIPAging.vue` (189) | **inline** — no composable |

Only 3 of 8 KPI views have been refactored to a composable. The other 5 retain inline `<script setup>` logic. This is a refactoring debt independent of B.3 — flagging as a follow-up but not extracting in-scope here.

**Common surface (verified on Efficiency)**:
- Reactive state: `loading`, `clients`, `selectedClient`, `startDate`, `endDate`, `predictionData`, `forecastDays`, `showForecast`
- Computed: `statusColor` (threshold lookup → vuetify token), `gapColor`, three `*Headers` arrays (i18n-resolved table headers)
- Color helpers: `getEfficiencyColor`, `getHealthColor`, `getTrendColor`, `getTrendIcon`
- Formatters: `formatValue`, `formatDate`
- Async: `loadClients`, `fetchPrediction`, `refreshData`, `initialize`
- Side-effect handlers: `onForecastToggle`, `onClientChange`, `onDateChange`

### Bucket 2 — Admin pages (11 files, 3147 stmts)

Active in production. Each performs CRUD against `services/api.js` for one resource. Most have inline `<v-data-table>` and `<v-form>` (legacy — see entry-interface audit notes for migration status).

| View | Statements | E2E coverage |
|---|---|---|
| AdminUsers.vue | 191 | none |
| AdminClients.vue | 256 | none |
| AdminSettings.vue | 215 | none |
| AdminDefectTypes.vue | 89 | `admin-defect-types.spec.ts` ✅ |
| FloatingPoolManagement.vue | 88 | none (has unit test `FloatingPoolManagement.spec.ts`) |
| PartOpportunities.vue | 99 | `admin-part-opportunities.spec.ts` ✅ |
| AssumptionVarianceReport.vue | 90 | none |
| ClientConfigView.vue | 123 | none |
| WorkflowConfigView.vue | 205 | none |
| WorkflowDesignerView.vue | 77 | none |
| DatabaseConfigView.vue | 67 | `database-config.spec.ts` ✅ (e2e only) |

### Bucket 3 — Capacity Planning sub-components (16 files)

Sub-components rendered inside `CapacityPlanningView.vue` (also 0%). All exercised by `capacity-planning.spec.ts`, `capacity-bom.spec.ts`, `capacity-scenarios.spec.ts`, `capacity-kpi-tracking.spec.ts` (E2E). Many already have grid composable unit tests (e.g. `useBOMGridData.spec.ts`).

### Bucket 4 — Entry pages (4 files, 32 stmts total)

`AttendanceEntry.vue`, `DowntimeEntry.vue`, `HoldResumeEntry.vue`, `QualityEntry.vue` — each is 8 statements. Post-AGGridBase migration, these are pure 1:1 wrappers around their grid composable. The composables (`useAttendanceGridData.ts` etc.) are unit-tested. **No incremental test value** — coverage stays at 0% by design.

### Bucket 5 — Misc large views (8 files)

| View | Statements | Notes |
|---|---|---|
| LoginView.vue | 153 | Critical entrypoint. No tests. |
| MyShiftDashboard.vue | 183 | Operator landing page. Large, business-critical. |
| SimulationV2View.vue | 924 | Simulation v2 work shipped 2026-05-04. E2E covers happy path. |
| AlertsView.vue | 1 | One-line view. |
| HelpCenter.vue | 72 | Static content. |
| PlanVsActualView.vue | 87 | Dual-view assumption-variance display. |
| WorkOrderManagement.vue | 73 | E2E covered (`work-order-management.spec.ts`) |
| `CapacityPlanning/CapacityPlanningView.vue` | 222 | E2E covered |

## Strategy

The user mandate is **real coverage, not coverage padding**. Acceptance criterion in the tracker:

> "≥1 unit test per non-trivial computed property... `npx vitest run --coverage` shows no view at 0% lines (≥1% is acceptable; 0% is not)"

Three modes of attack, in execution order:

### Mode A — Composable-first (KPI bucket)

For KPI detail pages (Bucket 1), test the composable, not the view. The view is template + `useXData()` destructure. Testing the composable:

- Hits 100% of the view's logic surface (all computed properties resolve through the composable).
- Lifts both the composable AND the view from 0%.
- Single test file per KPI = 8 tests; high coverage payoff per LoC.

Pattern (template):

```typescript
// frontend/src/composables/__tests__/useEfficiencyData.spec.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import useEfficiencyData from '../useEfficiencyData'

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (k: string) => k }) }))
vi.mock('@/services/api', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getPrediction: vi.fn(() => Promise.resolve({ data: { health_assessment: {} } })),
  },
}))
vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => ({
    efficiency: null,
    dashboard: [],
    fetchEfficiency: vi.fn(() => Promise.resolve()),
    fetchDashboard: vi.fn(() => Promise.resolve()),
    setClient: vi.fn(),
    setDateRange: vi.fn(),
  }),
}))

describe('useEfficiencyData', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('exposes initial reactive state', () => {
    const c = useEfficiencyData()
    expect(c.loading.value).toBe(false)
    expect(c.showForecast.value).toBe(true)
    expect(c.forecastDays.value).toBe(7)
  })

  // statusColor returns 'success' / 'amber-darken-3' / 'error' based on threshold
  it.each([
    [90, 'success'],
    [80, 'amber-darken-3'],
    [50, 'error'],
  ])('statusColor for value %d returns %s', (value, expected) => { /* ... */ })

  // ...similar for getEfficiencyColor, getPerformanceColor, getHealthColor,
  //                getTrendColor, getTrendIcon, formatValue, formatDate
  // ...async tests for fetchPrediction (success + error), refreshData,
  //                onClientChange (calls setClient + refreshData), initialize
})
```

### Mode B — Wrapper smoke test (entry bucket)

For Bucket 4 (entry pages, 8 stmts each), the view is a pure wrapper. A single mount-test asserts the view loads and the composable is called. Coverage moves from 0% to ≥80% per file.

### Mode C — View shallow-mount (admin + misc)

For Buckets 2 and 5, the view contains its own logic (no composable abstraction). Use `shallowMount` with mocked dependencies. Cover:
- Mount succeeds (component compiles + renders)
- Initial data fetch is dispatched
- Form submission path (CRUD endpoint called)
- Error state is rendered when API fails

## Execution plan

1. **Bucket 1** (KPI composables) — 8 composable tests, target ≥30% coverage per composable. **Now.**
2. **Bucket 5** subset — `LoginView.vue` (critical), `MyShiftDashboard.vue` (operator landing), `AlertsView.vue` (1-stmt smoke).
3. **Bucket 2** — write tests for the 8 admin views with no E2E coverage (skip the 3 with E2E for now, document gap).
4. **Bucket 4** — single-file smoke test per entry-page wrapper.
5. **Bucket 3** — defer; sub-components are exercised via E2E + composable tests already, raising priority only if total view coverage stays below the new floor.

## Acceptance

- [ ] All 47 files have a documented decision (test added | E2E covered | dead).
- [ ] No view at 0% lines after this audit (≥1% acceptable; ratchet floor in `vitest.config.ts` to the new minimum).
- [ ] Frontend test count strictly ≥ pre-B.3 count (1826 baseline post-A.13).
- [ ] Frontend lint warnings count must not increase.
- [ ] All new tests pass; no `it.skip` without a `// FIXME(YYYY-MM-DD)` justification per `scripts/check-skipped-tests.sh`.

## Live progress

| When | Bucket | Step | Outcome |
|---|---|---|---|
| 2026-05-07 | (init) | inventory | 47 files at 0% confirmed via coverage-final.json. Strategy doc shipped. |
