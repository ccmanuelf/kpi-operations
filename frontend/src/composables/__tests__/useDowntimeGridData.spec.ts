/**
 * Unit tests for useDowntimeGridData composable.
 * Covers column definitions (alignment to backend DowntimeEventCreate
 * schema), DOWNTIME_REASON_CODES catalog (mirrors DowntimeReasonEnum),
 * filters (date/reason/line), aggregate stats (totalHours, totalMinutes,
 * eventCount), and verification that legacy vestigial UI fields are gone.
 *
 * Migrated from the legacy form-only spec at
 * frontend/src/components/__tests__/DowntimeEntry.spec.ts (deleted in
 * the same change that re-routed /data-entry/downtime to the AG Grid
 * surface).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { withSetup } from '../../test/composable-test-utils'

const { storeState } = vi.hoisted(() => ({
  storeState: {
    downtimeEntries: [] as unknown[],
    workOrders: [] as unknown[],
    fetchReferenceData: vi.fn().mockResolvedValue(undefined),
    fetchDowntimeEntries: vi.fn().mockResolvedValue(undefined),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: 'en' } }),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ user: { client_id_assigned: 'CLIENT1' } }),
}))

vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => ({ selectedClient: null }),
}))

vi.mock('@/stores/productionDataStore', () => ({
  useProductionDataStore: () => ({
    downtimeEntries: storeState.downtimeEntries,
    workOrders: storeState.workOrders,
    fetchReferenceData: storeState.fetchReferenceData,
    fetchDowntimeEntries: storeState.fetchDowntimeEntries,
  }),
}))

import {
  default as useDowntimeGridData,
  DOWNTIME_REASON_CODES,
  applyReasonChange,
  applyCategoryChange,
  type DowntimeRow,
  type DowntimeRowTaxonomyState,
} from '../useDowntimeGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?:
    | { values?: unknown[]; min?: number; max?: number }
    | (() => { values?: unknown[] })
  cellClass?: (_params: { value?: string }) => string | undefined
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

const makeRow = (overrides: Partial<DowntimeRowTaxonomyState> = {}): DowntimeRowTaxonomyState => ({
  downtime_reason: 'OTHER',
  root_cause_category: 'other',
  ...overrides,
})

describe('DOWNTIME_REASON_CODES catalog', () => {
  it('contains the 8 backend enum codes, including OPERATOR_UNAVAILABLE', () => {
    expect(DOWNTIME_REASON_CODES).toEqual([
      'EQUIPMENT_FAILURE',
      'MATERIAL_SHORTAGE',
      'SETUP_CHANGEOVER',
      'QUALITY_HOLD',
      'MAINTENANCE',
      'POWER_OUTAGE',
      'OPERATOR_UNAVAILABLE',
      'OTHER',
    ])
  })

  it('does NOT contain legacy UI category labels', () => {
    expect(DOWNTIME_REASON_CODES).not.toContain('Planned Maintenance')
    expect(DOWNTIME_REASON_CODES).not.toContain('Unplanned Breakdown')
    expect(DOWNTIME_REASON_CODES).not.toContain('Changeover')
    expect(DOWNTIME_REASON_CODES).not.toContain('Operator Absence')
  })
})

describe('useDowntimeGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeState.downtimeEntries = []
    storeState.workOrders = []
    vi.clearAllMocks()
  })

  describe('column definitions match backend schema', () => {
    it('exposes shift_date column (not legacy downtime_start_time)', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      expect(findCol(columnDefs.value, 'shift_date')).toBeDefined()
      expect(findCol(columnDefs.value, 'downtime_start_time')).toBeUndefined()
    })

    it('exposes downtime_reason column with catalog-code select editor', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      const col = findCol(columnDefs.value, 'downtime_reason')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect((col.cellEditorParams as { values?: unknown[] }).values).toEqual(
        DOWNTIME_REASON_CODES,
      )
    })

    it('exposes downtime_duration_minutes column (not legacy duration_hours)', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      const col = findCol(columnDefs.value, 'downtime_duration_minutes')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col).toBeDefined()
      expect(findCol(columnDefs.value, 'duration_hours')).toBeUndefined()
    })

    it('downtime_duration_minutes editor enforces backend bounds (1..1440)', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      const col = findCol(columnDefs.value, 'downtime_duration_minutes')!
      const params = col.cellEditorParams as { min?: number; max?: number }
      expect(params.min).toBe(1)
      expect(params.max).toBe(1440)
    })

    it('exposes machine_id column', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      expect(findCol(columnDefs.value, 'machine_id')).toBeDefined()
    })

    it('exposes equipment_code column', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      expect(findCol(columnDefs.value, 'equipment_code')).toBeDefined()
    })

    it('exposes root_cause_category column', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      expect(findCol(columnDefs.value, 'root_cause_category')).toBeDefined()
    })

    it('offers exactly the 5 selectable categories in the category column editor', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      const col = columnDefs.value.find((c) => c.field === 'root_cause_category')
      expect(col?.cellEditor).toBe('agSelectCellEditor')
      const params =
        typeof col?.cellEditorParams === 'function' ? col.cellEditorParams() : col?.cellEditorParams
      expect(params.values).toEqual(['machine', 'materials', 'scheduling', 'attendance', 'other'])
    })

    it('reason list includes OPERATOR_UNAVAILABLE sourced from the shared constants', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      const col = columnDefs.value.find((c) => c.field === 'downtime_reason')
      const params =
        typeof col?.cellEditorParams === 'function' ? col.cellEditorParams() : col?.cellEditorParams
      expect(params.values).toContain('OPERATOR_UNAVAILABLE')
    })

    it('flags uncategorized cells with the highlight class', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      const col = columnDefs.value.find((c) => c.field === 'root_cause_category')
      expect(col?.cellClass?.({ value: 'uncategorized' })).toContain('ag-cell-warning')
      expect(col?.cellClass?.({ value: 'machine' })).toBe('')
    })

    it('exposes corrective_action column with large text editor', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      const col = findCol(columnDefs.value, 'corrective_action')!
      expect(col.cellEditor).toBe('agLargeTextCellEditor')
    })

    it('does NOT expose category column (replaced by downtime_reason enum)', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      expect(findCol(columnDefs.value, 'category')).toBeUndefined()
    })

    it('does NOT expose impact_on_wip_hours column (vestigial, not in backend)', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      expect(findCol(columnDefs.value, 'impact_on_wip_hours')).toBeUndefined()
    })

    it('does NOT expose is_resolved column (vestigial, not in backend)', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      expect(findCol(columnDefs.value, 'is_resolved')).toBeUndefined()
    })

    it('does NOT expose resolution_notes column (renamed to corrective_action)', () => {
      const { columnDefs } = withSetup(() => useDowntimeGridData())
      expect(findCol(columnDefs.value, 'resolution_notes')).toBeUndefined()
    })
  })

  describe('applyReasonChange / applyCategoryChange (auto-fill pure helpers)', () => {
    it('auto-fills default category on reason change unless user already overrode it', () => {
      const row = makeRow({ downtime_reason: 'OTHER', root_cause_category: 'other' })
      applyReasonChange(row, 'MATERIAL_SHORTAGE')
      expect(row.root_cause_category).toBe('materials')

      applyCategoryChange(row, 'scheduling')
      applyReasonChange(row, 'EQUIPMENT_FAILURE')
      expect(row.root_cause_category).toBe('scheduling')
    })

    it('applyCategoryChange marks the row as user-overridden', () => {
      const row = makeRow()
      applyCategoryChange(row, 'attendance')
      expect(row.root_cause_category).toBe('attendance')
      expect(row._categoryOverridden).toBe(true)
    })

    it('applyReasonChange falls back to the existing category for an unmapped reason', () => {
      const row = makeRow({ root_cause_category: 'machine' })
      applyReasonChange(row, 'SOME_UNKNOWN_REASON')
      expect(row.root_cause_category).toBe('machine')
    })
  })

  describe('uncategorizedCount', () => {
    it('counts filtered rows with root_cause_category === "uncategorized"', () => {
      storeState.downtimeEntries = [
        {
          root_cause_category: 'uncategorized',
          shift_date: '2026-01-01',
          downtime_duration_minutes: 60,
        } as DowntimeRow,
        {
          root_cause_category: 'machine',
          shift_date: '2026-01-02',
          downtime_duration_minutes: 30,
        } as DowntimeRow,
        {
          root_cause_category: 'uncategorized',
          shift_date: '2026-01-03',
          downtime_duration_minutes: 15,
        } as DowntimeRow,
      ]
      const { uncategorizedCount, applyFilters } = withSetup(() => useDowntimeGridData())
      applyFilters()
      expect(uncategorizedCount.value).toBe(2)
    })

    it('is 0 when no entries are uncategorized', () => {
      storeState.downtimeEntries = [
        {
          root_cause_category: 'machine',
          shift_date: '2026-01-01',
          downtime_duration_minutes: 60,
        } as DowntimeRow,
      ]
      const { uncategorizedCount, applyFilters } = withSetup(() => useDowntimeGridData())
      applyFilters()
      expect(uncategorizedCount.value).toBe(0)
    })
  })

  describe('aggregations', () => {
    it('totalMinutes sums downtime_duration_minutes across filtered entries', () => {
      storeState.downtimeEntries = [
        { downtime_duration_minutes: 60, shift_date: '2026-01-01' } as DowntimeRow,
        { downtime_duration_minutes: 30, shift_date: '2026-01-02' } as DowntimeRow,
        { downtime_duration_minutes: 45, shift_date: '2026-01-03' } as DowntimeRow,
      ]
      const { totalMinutes, applyFilters } = withSetup(() => useDowntimeGridData())
      applyFilters()
      expect(totalMinutes.value).toBe(135)
    })

    it('totalHours converts minutes to hours', () => {
      storeState.downtimeEntries = [
        { downtime_duration_minutes: 120, shift_date: '2026-01-01' } as DowntimeRow,
        { downtime_duration_minutes: 60, shift_date: '2026-01-02' } as DowntimeRow,
      ]
      const { totalHours, applyFilters } = withSetup(() => useDowntimeGridData())
      applyFilters()
      expect(totalHours.value).toBe(3)
    })

    it('eventCount returns filtered entry count', () => {
      storeState.downtimeEntries = [
        { downtime_duration_minutes: 60, shift_date: '2026-01-01' } as DowntimeRow,
        { downtime_duration_minutes: 30, shift_date: '2026-01-02' } as DowntimeRow,
      ]
      const { eventCount, applyFilters } = withSetup(() => useDowntimeGridData())
      applyFilters()
      expect(eventCount.value).toBe(2)
    })

    it('totalMinutes is 0 when no entries', () => {
      const { totalMinutes } = withSetup(() => useDowntimeGridData())
      expect(totalMinutes.value).toBe(0)
    })
  })

  describe('applyFilters', () => {
    it('filters by reason (catalog code)', () => {
      storeState.downtimeEntries = [
        {
          downtime_reason: 'EQUIPMENT_FAILURE',
          shift_date: '2026-01-01',
          downtime_duration_minutes: 60,
        } as DowntimeRow,
        {
          downtime_reason: 'OTHER',
          shift_date: '2026-01-02',
          downtime_duration_minutes: 30,
        } as DowntimeRow,
      ]
      const { reasonFilter, filteredEntries, applyFilters } = withSetup(() => useDowntimeGridData())
      reasonFilter.value = 'EQUIPMENT_FAILURE'
      applyFilters()
      expect(filteredEntries.value).toHaveLength(1)
    })

    it('filters by shift_date', () => {
      storeState.downtimeEntries = [
        { shift_date: '2026-04-30T00:00:00', downtime_duration_minutes: 60 } as DowntimeRow,
        { shift_date: '2026-04-29T00:00:00', downtime_duration_minutes: 60 } as DowntimeRow,
      ]
      const { dateFilter, filteredEntries, applyFilters } = withSetup(() => useDowntimeGridData())
      dateFilter.value = '2026-04-30'
      applyFilters()
      expect(filteredEntries.value).toHaveLength(1)
    })

    it('filters by line_id', () => {
      storeState.downtimeEntries = [
        {
          line_id: 1,
          shift_date: '2026-01-01',
          downtime_duration_minutes: 60,
        } as DowntimeRow,
        {
          line_id: 2,
          shift_date: '2026-01-02',
          downtime_duration_minutes: 60,
        } as DowntimeRow,
      ]
      const { lineFilter, filteredEntries, applyFilters } = withSetup(() => useDowntimeGridData())
      lineFilter.value = 1
      applyFilters()
      expect(filteredEntries.value).toHaveLength(1)
    })

    it('returns all entries when no filters set', () => {
      storeState.downtimeEntries = [
        { shift_date: '2026-01-01', downtime_duration_minutes: 60 } as DowntimeRow,
        { shift_date: '2026-01-02', downtime_duration_minutes: 60 } as DowntimeRow,
      ]
      const { filteredEntries, applyFilters } = withSetup(() => useDowntimeGridData())
      applyFilters()
      expect(filteredEntries.value).toHaveLength(2)
    })
  })

  describe('initial state', () => {
    it('initialises unsavedChanges as empty Set', () => {
      const { unsavedChanges } = withSetup(() => useDowntimeGridData())
      expect(unsavedChanges.value.size).toBe(0)
    })

    it('initialises hasUnsavedChanges to false', () => {
      const { hasUnsavedChanges } = withSetup(() => useDowntimeGridData())
      expect(hasUnsavedChanges.value).toBe(false)
    })

    it('exposes reasons === DOWNTIME_REASON_CODES', () => {
      const { reasons } = withSetup(() => useDowntimeGridData())
      expect(reasons).toBe(DOWNTIME_REASON_CODES)
    })
  })
})
