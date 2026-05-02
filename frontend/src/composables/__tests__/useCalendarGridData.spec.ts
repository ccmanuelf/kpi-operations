/**
 * Unit tests for useCalendarGridData composable —
 * Group D Surface #12 (Master Calendar worksheet).
 *
 * Verifies column-shape conformance to backend CalendarEntryCreate schema,
 * conditional shift2_hours editability, monthly auto-generation, and
 * store-bound CRUD wrappers.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { storeApi } = vi.hoisted(() => ({
  storeApi: {
    addRow: vi.fn(),
    removeRow: vi.fn(),
    importData: vi.fn(),
    worksheets: {
      masterCalendar: { data: [] as unknown[], dirty: false },
    },
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/stores/capacityPlanningStore', () => ({
  useCapacityPlanningStore: () => storeApi,
}))

import useCalendarGridData, { type CalendarRow } from '../useCalendarGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean | ((params: { data: CalendarRow }) => boolean)
  cellEditor?: string
  cellEditorParams?: { values?: unknown[]; min?: number; max?: number }
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

describe('useCalendarGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeApi.worksheets.masterCalendar = { data: [], dirty: false }
    vi.clearAllMocks()
  })

  describe('column definitions match backend schema', () => {
    it('exposes calendar_date as date editor (pinned left)', () => {
      const { columnDefs } = useCalendarGridData()
      const col = findCol(columnDefs.value, 'calendar_date')!
      expect(col.cellEditor).toBe('agDateStringCellEditor')
      expect(col.pinned).toBe('left')
    })

    it('exposes is_working_day as checkbox editor', () => {
      const { columnDefs } = useCalendarGridData()
      const col = findCol(columnDefs.value, 'is_working_day')!
      expect(col.cellEditor).toBe('agCheckboxCellEditor')
    })

    it('exposes shifts_available as select editor with values [1,2,3]', () => {
      const { columnDefs } = useCalendarGridData()
      const col = findCol(columnDefs.value, 'shifts_available')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toEqual([1, 2, 3])
    })

    it('exposes shift1_hours as numeric (min:0, max:24)', () => {
      const { columnDefs } = useCalendarGridData()
      const col = findCol(columnDefs.value, 'shift1_hours')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, max: 24, precision: 2 })
    })

    it('exposes shift2_hours as numeric', () => {
      const { columnDefs } = useCalendarGridData()
      const col = findCol(columnDefs.value, 'shift2_hours')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
    })

    it('exposes holiday_name as text editor', () => {
      const { columnDefs } = useCalendarGridData()
      const col = findCol(columnDefs.value, 'holiday_name')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('exposes _actions column pinned right', () => {
      const { columnDefs } = useCalendarGridData()
      const col = findCol(columnDefs.value, '_actions')!
      expect(col.pinned).toBe('right')
    })
  })

  describe('conditional shift2_hours editability', () => {
    it('shift2_hours editable when shifts_available === 2', () => {
      const { columnDefs } = useCalendarGridData()
      const col = findCol(columnDefs.value, 'shift2_hours')!
      const editable = col.editable as (params: { data: CalendarRow }) => boolean
      expect(editable({ data: { shifts_available: 2 } })).toBe(true)
    })

    it('shift2_hours editable when shifts_available === 3', () => {
      const { columnDefs } = useCalendarGridData()
      const col = findCol(columnDefs.value, 'shift2_hours')!
      const editable = col.editable as (params: { data: CalendarRow }) => boolean
      expect(editable({ data: { shifts_available: 3 } })).toBe(true)
    })

    it('shift2_hours NOT editable when shifts_available === 1', () => {
      const { columnDefs } = useCalendarGridData()
      const col = findCol(columnDefs.value, 'shift2_hours')!
      const editable = col.editable as (params: { data: CalendarRow }) => boolean
      expect(editable({ data: { shifts_available: 1 } })).toBe(false)
    })
  })

  describe('generateMonth helper', () => {
    it('returns daysInMonth entries for a typical month', () => {
      const { generateMonth } = useCalendarGridData()
      const entries = generateMonth(2026, 5) // May 2026 — 31 days
      expect(entries).toHaveLength(31)
    })

    it('marks weekends (Sat=6, Sun=0) as non-working days with 0 shift1_hours', () => {
      const { generateMonth } = useCalendarGridData()
      // 2026-05-02 is a Saturday, 2026-05-03 is a Sunday.
      const entries = generateMonth(2026, 5)
      const saturday = entries.find((e) => e.calendar_date === '2026-05-02')!
      const sunday = entries.find((e) => e.calendar_date === '2026-05-03')!
      expect(saturday.is_working_day).toBe(false)
      expect(saturday.shift1_hours).toBe(0)
      expect(sunday.is_working_day).toBe(false)
      expect(sunday.shift1_hours).toBe(0)
    })

    it('marks weekdays as working with default 8-hour shift1', () => {
      const { generateMonth } = useCalendarGridData()
      // 2026-05-04 is a Monday.
      const entries = generateMonth(2026, 5)
      const monday = entries.find((e) => e.calendar_date === '2026-05-04')!
      expect(monday.is_working_day).toBe(true)
      expect(monday.shift1_hours).toBe(8.0)
    })

    it('handles February in a leap year (29 days)', () => {
      const { generateMonth } = useCalendarGridData()
      const entries = generateMonth(2024, 2) // Feb 2024 = 29 days
      expect(entries).toHaveLength(29)
    })

    it('handles February in a non-leap year (28 days)', () => {
      const { generateMonth } = useCalendarGridData()
      const entries = generateMonth(2025, 2)
      expect(entries).toHaveLength(28)
    })
  })

  describe('importGeneratedMonth integration', () => {
    it('delegates to store.importData with masterCalendar worksheet name', () => {
      const { importGeneratedMonth } = useCalendarGridData()
      importGeneratedMonth(2026, 5)
      expect(storeApi.importData).toHaveBeenCalledWith(
        'masterCalendar',
        expect.arrayContaining([
          expect.objectContaining({ calendar_date: expect.any(String) }),
        ]),
      )
    })
  })

  describe('store-bound CRUD wrappers', () => {
    it("addRow delegates to store.addRow('masterCalendar')", () => {
      const { addRow } = useCalendarGridData()
      addRow()
      expect(storeApi.addRow).toHaveBeenCalledWith('masterCalendar')
    })

    it("removeRow delegates to store.removeRow('masterCalendar', index)", () => {
      const { removeRow } = useCalendarGridData()
      removeRow(5)
      expect(storeApi.removeRow).toHaveBeenCalledWith('masterCalendar', 5)
    })

    it('onCellValueChanged marks the worksheet dirty', () => {
      const { onCellValueChanged } = useCalendarGridData()
      expect(storeApi.worksheets.masterCalendar.dirty).toBe(false)
      onCellValueChanged()
      expect(storeApi.worksheets.masterCalendar.dirty).toBe(true)
    })
  })
})
