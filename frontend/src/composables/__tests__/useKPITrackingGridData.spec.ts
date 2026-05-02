/**
 * Unit tests for useKPITrackingGridData composable —
 * Group G Surface #18 (KPI Tracking thresholds, final Group G).
 *
 * Verifies column-shape conformance to backend KPI tracking schema,
 * variance classification thresholds (≤5/≤10/>10), aggregations, and
 * store-bound CRUD wrappers.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { storeApi } = vi.hoisted(() => ({
  storeApi: {
    addRow: vi.fn(),
    removeRow: vi.fn(),
    worksheets: {
      kpiTracking: { data: [] as unknown[], dirty: false },
    },
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/stores/capacityPlanningStore', () => ({
  useCapacityPlanningStore: () => storeApi,
}))

import useKPITrackingGridData, {
  classifyVariance,
  type KPITrackingRow,
} from '../useKPITrackingGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { precision?: number }
  pinned?: 'left' | 'right'
  valueGetter?: (params: { data: KPITrackingRow }) => unknown
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

describe('classifyVariance', () => {
  it('returns ON_TARGET for |variance| <= 5%', () => {
    expect(classifyVariance(0)).toBe('ON_TARGET')
    expect(classifyVariance(5)).toBe('ON_TARGET')
    expect(classifyVariance(-5)).toBe('ON_TARGET')
  })

  it('returns OFF_TARGET for 5% < |variance| <= 10%', () => {
    expect(classifyVariance(7)).toBe('OFF_TARGET')
    expect(classifyVariance(10)).toBe('OFF_TARGET')
    expect(classifyVariance(-9)).toBe('OFF_TARGET')
  })

  it('returns CRITICAL for |variance| > 10%', () => {
    expect(classifyVariance(11)).toBe('CRITICAL')
    expect(classifyVariance(-25)).toBe('CRITICAL')
  })

  it('returns null for null / undefined', () => {
    expect(classifyVariance(null)).toBeNull()
    expect(classifyVariance(undefined)).toBeNull()
  })
})

describe('useKPITrackingGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeApi.worksheets.kpiTracking = { data: [], dirty: false }
    vi.clearAllMocks()
  })

  describe('column definitions', () => {
    it('exposes kpi_name as text editor (pinned left)', () => {
      const { columnDefs } = useKPITrackingGridData()
      const col = findCol(columnDefs.value, 'kpi_name')!
      expect(col.cellEditor).toBe('agTextCellEditor')
      expect(col.pinned).toBe('left')
      expect(col.editable).toBe(true)
    })

    it('exposes target_value as numeric editor', () => {
      const { columnDefs } = useKPITrackingGridData()
      const col = findCol(columnDefs.value, 'target_value')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.editable).toBe(true)
    })

    it('exposes actual_value as read-only', () => {
      const { columnDefs } = useKPITrackingGridData()
      const col = findCol(columnDefs.value, 'actual_value')!
      expect(col.editable).toBe(false)
    })

    it('exposes variance_percent as read-only with chip renderer', () => {
      const { columnDefs } = useKPITrackingGridData()
      const col = findCol(columnDefs.value, 'variance_percent')!
      expect(col.editable).toBe(false)
    })

    it('exposes status as read-only with chip renderer', () => {
      const { columnDefs } = useKPITrackingGridData()
      const col = findCol(columnDefs.value, 'status')!
      expect(col.editable).toBe(false)
    })

    it('exposes _period column with date-range valueGetter', () => {
      const { columnDefs } = useKPITrackingGridData()
      const col = findCol(columnDefs.value, '_period')!
      expect(col.editable).toBe(false)
      const start = '2026-05-01'
      const end = '2026-05-07'
      const value = col.valueGetter!({
        data: { period_start: start, period_end: end } as KPITrackingRow,
      })
      expect(String(value)).toContain('-')
    })

    it('_period valueGetter returns empty string when dates missing', () => {
      const { columnDefs } = useKPITrackingGridData()
      const col = findCol(columnDefs.value, '_period')!
      expect(col.valueGetter!({ data: {} as KPITrackingRow })).toBe('')
    })

    it('exposes _actions column pinned right', () => {
      const { columnDefs } = useKPITrackingGridData()
      const col = findCol(columnDefs.value, '_actions')!
      expect(col.pinned).toBe('right')
    })
  })

  describe('aggregations', () => {
    it('onTargetCount sums rows with |variance| <= 5%', () => {
      storeApi.worksheets.kpiTracking.data = [
        { variance_percent: 3 },
        { variance_percent: -4 },
        { variance_percent: 7 },
      ]
      const { onTargetCount } = useKPITrackingGridData()
      expect(onTargetCount.value).toBe(2)
    })

    it('offTargetCount sums rows with 5% < |variance| <= 10%', () => {
      storeApi.worksheets.kpiTracking.data = [
        { variance_percent: 6 },
        { variance_percent: 10 },
        { variance_percent: 15 },
        { variance_percent: 2 },
      ]
      const { offTargetCount } = useKPITrackingGridData()
      expect(offTargetCount.value).toBe(2)
    })

    it('criticalCount sums rows with |variance| > 10%', () => {
      storeApi.worksheets.kpiTracking.data = [
        { variance_percent: 11 },
        { variance_percent: -25 },
        { variance_percent: 5 },
      ]
      const { criticalCount } = useKPITrackingGridData()
      expect(criticalCount.value).toBe(2)
    })

    it('null variance does not count toward any bucket', () => {
      storeApi.worksheets.kpiTracking.data = [
        { variance_percent: null },
        { variance_percent: undefined },
      ]
      const { onTargetCount, offTargetCount, criticalCount } = useKPITrackingGridData()
      expect(onTargetCount.value).toBe(0)
      expect(offTargetCount.value).toBe(0)
      expect(criticalCount.value).toBe(0)
    })
  })

  describe('store-bound CRUD wrappers', () => {
    it("addRow delegates to store.addRow('kpiTracking')", () => {
      const { addRow } = useKPITrackingGridData()
      addRow()
      expect(storeApi.addRow).toHaveBeenCalledWith('kpiTracking')
    })

    it("removeRow delegates to store.removeRow('kpiTracking', index)", () => {
      const { removeRow } = useKPITrackingGridData()
      removeRow(2)
      expect(storeApi.removeRow).toHaveBeenCalledWith('kpiTracking', 2)
    })

    it('onCellValueChanged marks the worksheet dirty', () => {
      const { onCellValueChanged } = useKPITrackingGridData()
      expect(storeApi.worksheets.kpiTracking.dirty).toBe(false)
      onCellValueChanged()
      expect(storeApi.worksheets.kpiTracking.dirty).toBe(true)
    })
  })

  describe('reactive store binding', () => {
    it('kpiData mirrors store.worksheets.kpiTracking.data', () => {
      const seed: KPITrackingRow[] = [{ kpi_name: 'OEE', target_value: 85 }]
      storeApi.worksheets.kpiTracking.data = seed
      const { kpiData } = useKPITrackingGridData()
      expect(kpiData.value).toBe(seed)
    })

    it('hasChanges reflects worksheet.dirty', () => {
      storeApi.worksheets.kpiTracking.dirty = true
      const { hasChanges } = useKPITrackingGridData()
      expect(hasChanges.value).toBe(true)
    })
  })
})
