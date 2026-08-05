/**
 * Unit tests for useAttendanceGridData composable.
 * Covers status translation (UI -> backend is_absent + absence_type +
 * is_late), datetime combination (shift_date + HH:MM -> ISO),
 * column-shape alignment to AttendanceRecordCreate schema, and
 * statusCounts aggregation.
 *
 * No legacy form spec was migrated — none existed for Attendance —
 * so this is a net new spec at +tests for the surface.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { toRaw } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { withSetup } from '../../test/composable-test-utils'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getShifts: vi.fn().mockResolvedValue({ data: [] }),
    getAttendanceEntries: vi.fn().mockResolvedValue({ data: [] }),
    createAttendanceEntry: vi.fn().mockResolvedValue({ data: {} }),
    updateAttendanceEntry: vi.fn().mockResolvedValue({ data: {} }),
    get: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/services/api', () => ({ default: mockApi }))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ user: { client_id_assigned: 'CLIENT1' } }),
}))

vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => ({ selectedClient: null }),
}))

import useAttendanceGridData, {
  translateStatus,
  combineDateTime,
  type AttendanceRow,
} from '../useAttendanceGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: {
    values?: unknown[]
    min?: number
    max?: number
    formatValue?: (_v: unknown) => string
  }
  valueFormatter?: (_params: { value?: unknown }) => string
  cellRenderer?: (_params: { data: AttendanceRow }) => HTMLElement
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

describe('translateStatus helper', () => {
  it('Present maps to is_absent=0, no absence_type, no late', () => {
    expect(translateStatus('Present')).toEqual({
      is_absent: 0,
      absence_type: null,
      is_late: 0,
      actualHoursFactor: 1,
    })
  })

  it('Absent maps to is_absent=1, UNSCHEDULED_ABSENCE', () => {
    const result = translateStatus('Absent')
    expect(result.is_absent).toBe(1)
    expect(result.absence_type).toBe('UNSCHEDULED_ABSENCE')
    expect(result.actualHoursFactor).toBe(0)
  })

  it('Late maps to is_absent=0, is_late=1', () => {
    const result = translateStatus('Late')
    expect(result.is_absent).toBe(0)
    expect(result.absence_type).toBeNull()
    expect(result.is_late).toBe(1)
    expect(result.actualHoursFactor).toBe(1)
  })

  it('Half Day maps to is_absent=0 with 0.5 actualHoursFactor', () => {
    const result = translateStatus('Half Day')
    expect(result.is_absent).toBe(0)
    expect(result.actualHoursFactor).toBe(0.5)
  })

  it('Leave maps to is_absent=1, PERSONAL_LEAVE', () => {
    const result = translateStatus('Leave')
    expect(result.is_absent).toBe(1)
    expect(result.absence_type).toBe('PERSONAL_LEAVE')
  })

  it('Vacation maps to is_absent=1, VACATION', () => {
    const result = translateStatus('Vacation')
    expect(result.is_absent).toBe(1)
    expect(result.absence_type).toBe('VACATION')
  })

  it('Medical maps to is_absent=1, MEDICAL_LEAVE', () => {
    const result = translateStatus('Medical')
    expect(result.is_absent).toBe(1)
    expect(result.absence_type).toBe('MEDICAL_LEAVE')
  })

  it('case-insensitive matching', () => {
    expect(translateStatus('absent').is_absent).toBe(1)
    expect(translateStatus('ABSENT').is_absent).toBe(1)
    expect(translateStatus('Absent').is_absent).toBe(1)
  })

  it('falls back to Present for unknown / undefined / empty', () => {
    expect(translateStatus(undefined).is_absent).toBe(0)
    expect(translateStatus('').is_absent).toBe(0)
    expect(translateStatus('Unknown').is_absent).toBe(0)
  })
})

describe('combineDateTime helper', () => {
  it('combines YYYY-MM-DD and HH:MM into ISO datetime', () => {
    expect(combineDateTime('2026-05-01', '08:30')).toBe('2026-05-01T08:30:00')
  })

  it('pads single-digit hours', () => {
    expect(combineDateTime('2026-05-01', '8:30')).toBe('2026-05-01T08:30:00')
  })

  it('returns undefined when date is missing', () => {
    expect(combineDateTime(undefined, '08:30')).toBeUndefined()
  })

  it('returns undefined when time is missing', () => {
    expect(combineDateTime('2026-05-01', undefined)).toBeUndefined()
  })

  it('returns undefined when time is empty string', () => {
    expect(combineDateTime('2026-05-01', '')).toBeUndefined()
  })

  it('returns undefined for malformed time', () => {
    expect(combineDateTime('2026-05-01', '8:3:0')).toBeUndefined()
    expect(combineDateTime('2026-05-01', 'not a time')).toBeUndefined()
  })
})

describe('useAttendanceGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('column definitions match backend schema', () => {
    it('exposes status column with select editor', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'status')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toContain('Present')
      expect(col.cellEditorParams!.values).toContain('Absent')
      expect(col.cellEditorParams!.values).toContain('Late')
      expect(col.cellEditorParams!.values).toContain('Half Day')
      expect(col.cellEditorParams!.values).toContain('Leave')
      expect(col.cellEditorParams!.values).toContain('Vacation')
      expect(col.cellEditorParams!.values).toContain('Medical')
    })

    it('exposes scheduled_hours column with numeric editor', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'scheduled_hours')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams!.max).toBe(24)
    })

    it('exposes actual_hours column with numeric editor', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'actual_hours')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams!.max).toBe(24)
    })

    it('does NOT expose late_minutes column (vestigial)', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      expect(findCol(columnDefs.value, 'late_minutes')).toBeUndefined()
    })

    it('does NOT expose is_excused column (vestigial)', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      expect(findCol(columnDefs.value, 'is_excused')).toBeUndefined()
    })

    it('clock_in column field stays user-friendly (HH:MM string)', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'clock_in')!
      expect(col.editable).toBe(true)
    })

    it('clock_out column field stays user-friendly (HH:MM string)', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'clock_out')!
      expect(col.editable).toBe(true)
    })
  })

  describe('statusCounts', () => {
    it('counts Present', () => {
      const { attendanceData, statusCounts } = withSetup(() => useAttendanceGridData())
      attendanceData.value = [
        { status: 'Present' } as AttendanceRow,
        { status: 'Present' } as AttendanceRow,
      ]
      expect(statusCounts.value.present).toBe(2)
    })

    it('counts Absent', () => {
      const { attendanceData, statusCounts } = withSetup(() => useAttendanceGridData())
      attendanceData.value = [{ status: 'Absent' } as AttendanceRow]
      expect(statusCounts.value.absent).toBe(1)
    })

    it('counts Late', () => {
      const { attendanceData, statusCounts } = withSetup(() => useAttendanceGridData())
      attendanceData.value = [{ status: 'Late' } as AttendanceRow]
      expect(statusCounts.value.late).toBe(1)
    })

    it('counts Leave + Vacation + Medical together', () => {
      const { attendanceData, statusCounts } = withSetup(() => useAttendanceGridData())
      attendanceData.value = [
        { status: 'Leave' } as AttendanceRow,
        { status: 'Vacation' } as AttendanceRow,
        { status: 'Medical' } as AttendanceRow,
      ]
      expect(statusCounts.value.leave).toBe(3)
    })

    it('counts Half Day separately', () => {
      const { attendanceData, statusCounts } = withSetup(() => useAttendanceGridData())
      attendanceData.value = [{ status: 'Half Day' } as AttendanceRow]
      expect(statusCounts.value.halfDay).toBe(1)
    })
  })

  describe('labor-hours columns (Cycle 3 PR-A, Task 7)', () => {
    it('exposes normal_hours/double_hours/triple_hours as numeric editors', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      for (const field of ['normal_hours', 'double_hours', 'triple_hours']) {
        const col = findCol(columnDefs.value, field)!
        expect(col.editable).toBe(true)
        expect(col.cellEditor).toBe('agNumberCellEditor')
        expect(col.cellEditorParams!.max).toBe(24)
      }
    })

    it('OT split columns render EMPTY for null/undefined, not a placeholder', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      for (const field of ['normal_hours', 'double_hours', 'triple_hours']) {
        const col = findCol(columnDefs.value, field)!
        expect(col.valueFormatter!({ value: null })).toBe('')
        expect(col.valueFormatter!({ value: undefined })).toBe('')
        expect(col.valueFormatter!({ value: 4 })).toBe('4')
      }
    })

    it('labor_class_override is a select with a null (clear) option', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'labor_class_override')!
      expect(col.editable).toBe(true)
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toEqual([null, 'direct', 'indirect'])
    })

    it('labor_class_override editor formats null as Unclassified', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'labor_class_override')!
      expect(col.cellEditorParams!.formatValue!(null)).toBe('labor.unclassified')
      expect(col.cellEditorParams!.formatValue!('direct')).toBe('labor.classes.direct')
    })

    it('labor_class_override resting display is EMPTY for null (no placeholder)', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'labor_class_override')!
      expect(col.valueFormatter!({ value: null })).toBe('')
      expect(col.valueFormatter!({ value: 'indirect' })).toBe('labor.classes.indirect')
    })

    it('allocations column is read-only with a cellRenderer', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'allocations')!
      expect(col.editable).toBe(false)
      expect(col.cellRenderer).toBeTypeOf('function')
    })

    it('allocations cellRenderer shows "+" (no summary text) when nothing allocated', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'allocations')!
      const row = { allocations: [], actual_hours: 8 } as AttendanceRow
      const el = col.cellRenderer!({ data: row })
      expect(el.textContent).toBe('+')
    })

    it('allocations cellRenderer shows the allocated/actual summary once allocated', () => {
      const { columnDefs } = withSetup(() => useAttendanceGridData())
      const col = findCol(columnDefs.value, 'allocations')!
      const row = {
        allocations: [{ category: 'billed_production', hours: 5 }],
        actual_hours: 8,
      } as AttendanceRow
      const el = col.cellRenderer!({ data: row })
      expect(el.textContent).toBe('labor.allocatedSummary')
    })

    it('clicking the allocations cell opens the dialog for that row', () => {
      const { columnDefs, showAllocationDialog, allocationDialogRow } = withSetup(() =>
        useAttendanceGridData(),
      )
      const col = findCol(columnDefs.value, 'allocations')!
      const row = { employee_id: 7, allocations: [] } as AttendanceRow
      const el = col.cellRenderer!({ data: row })
      el.dispatchEvent(new Event('click'))
      expect(showAllocationDialog.value).toBe(true)
      // ref() wraps the assigned row in a reactive Proxy, so compare by
      // value (deep equal), not by reference.
      expect(allocationDialogRow.value).toEqual(row)
    })
  })

  describe('onAllocationsSaved', () => {
    it('syncs the row allocations and marks it changed', () => {
      const { onAllocationsSaved } = withSetup(() => useAttendanceGridData())
      const row = { employee_id: 1, allocations: [] } as AttendanceRow
      onAllocationsSaved({ row, items: [{ category: 'training', hours: 2 }] })
      expect(row.allocations).toEqual([{ category: 'training', hours: 2 }])
      expect(row._hasChanges).toBe(true)
    })
  })

  describe('completeness counts', () => {
    it('noSplitCount counts rows with actual_hours but no OT split', () => {
      const { attendanceData, noSplitCount } = withSetup(() => useAttendanceGridData())
      attendanceData.value = [
        { actual_hours: 8, normal_hours: null, double_hours: null, triple_hours: null } as AttendanceRow,
        { actual_hours: 8, normal_hours: 8, double_hours: 0, triple_hours: 0 } as AttendanceRow,
        { actual_hours: undefined } as AttendanceRow,
      ]
      expect(noSplitCount.value).toBe(1)
    })

    it('unallocatedCount counts rows with no hour allocations', () => {
      const { attendanceData, unallocatedCount } = withSetup(() => useAttendanceGridData())
      attendanceData.value = [
        { allocations: [] } as AttendanceRow,
        { allocations: undefined } as AttendanceRow,
        { allocations: [{ category: 'training', hours: 1 }] } as AttendanceRow,
      ]
      expect(unallocatedCount.value).toBe(2)
    })

    it('both counts are 0 for a fully-complete row', () => {
      const { attendanceData, noSplitCount, unallocatedCount } = withSetup(() =>
        useAttendanceGridData(),
      )
      attendanceData.value = [
        {
          actual_hours: 8,
          normal_hours: 8,
          double_hours: 0,
          triple_hours: 0,
          allocations: [{ category: 'billed_production', hours: 8 }],
        } as AttendanceRow,
      ]
      expect(noSplitCount.value).toBe(0)
      expect(unallocatedCount.value).toBe(0)
    })
  })

  describe('buildPayload carries labor-hours fields', () => {
    it('includes OT split, labor_class_override, and allocations on save', async () => {
      const { attendanceData, gridRef, saveAttendance, onConfirmSave } = withSetup(() =>
        useAttendanceGridData(),
      )
      const row = {
        employee_id: 1,
        shift_date: '2026-08-05',
        status: 'Present',
        actual_hours: 8,
        normal_hours: 6,
        double_hours: 2,
        triple_hours: 0,
        labor_class_override: 'direct',
        allocations: [{ category: 'billed_production', hours: 5 }],
        _hasChanges: true,
        _isNew: true,
      } as AttendanceRow
      attendanceData.value = [row]
      gridRef.value = {
        gridApi: {
          sizeColumnsToFit: vi.fn(),
          refreshCells: vi.fn(),
          applyTransaction: vi.fn(),
          forEachNode: (cb: (_n: { data: AttendanceRow }) => void) => cb({ data: row }),
        },
      }
      await saveAttendance()
      await onConfirmSave()

      expect(mockApi.createAttendanceEntry).toHaveBeenCalledWith(
        expect.objectContaining({
          normal_hours: 6,
          double_hours: 2,
          triple_hours: 0,
          labor_class_override: 'direct',
          allocations: [{ category: 'billed_production', hours: 5 }],
        }),
      )
    })

    it('defaults OT split/labor_class_override to null and allocations to [] when unset', async () => {
      const { attendanceData, gridRef, saveAttendance, onConfirmSave } = withSetup(() =>
        useAttendanceGridData(),
      )
      const row = {
        employee_id: 2,
        shift_date: '2026-08-05',
        status: 'Present',
        actual_hours: 8,
        _hasChanges: true,
        _isNew: true,
      } as AttendanceRow
      attendanceData.value = [row]
      gridRef.value = {
        gridApi: {
          sizeColumnsToFit: vi.fn(),
          refreshCells: vi.fn(),
          applyTransaction: vi.fn(),
          forEachNode: (cb: (_n: { data: AttendanceRow }) => void) => cb({ data: row }),
        },
      }
      await saveAttendance()
      await onConfirmSave()

      expect(mockApi.createAttendanceEntry).toHaveBeenCalledWith(
        expect.objectContaining({
          normal_hours: null,
          double_hours: null,
          triple_hours: null,
          labor_class_override: null,
          allocations: [],
        }),
      )
    })
  })

  // Fix round 1: AG Grid's cellValueChanged event (and the allocations
  // dialog's `saved` payload) hand back the RAW row object ag-grid-vue3
  // holds internally — mutating it bypasses Vue's reactive Proxy
  // set-trap, so a computed that already ran once and cached its result
  // never gets notified to re-derive. toRaw() here reproduces that exact
  // shape (mutate the target directly, not through the proxy) to prove
  // the editTick dirty-signal correctly forces a re-derive regardless.
  describe('editTick: raw-object mutations still flip reactive state', () => {
    it('a raw-object cell edit flips hasChanges/changedRowsCount/noSplitCount/statusCounts', () => {
      const { attendanceData, hasChanges, changedRowsCount, noSplitCount, statusCounts, markRowAsChanged } =
        withSetup(() => useAttendanceGridData())

      attendanceData.value = [
        {
          employee_id: 1,
          status: 'Present',
          actual_hours: 8,
          normal_hours: null,
          double_hours: null,
          triple_hours: null,
          allocations: [],
        } as AttendanceRow,
      ]

      // Read once so each computed caches an initial value and
      // subscribes to its dependencies (matches real render behavior).
      expect(hasChanges.value).toBe(false)
      expect(changedRowsCount.value).toBe(0)
      expect(noSplitCount.value).toBe(1)
      expect(statusCounts.value.present).toBe(1)

      const rawRow = toRaw(attendanceData.value[0])
      rawRow.normal_hours = 8
      rawRow.status = 'Absent'
      markRowAsChanged({ data: rawRow, colDef: { field: 'normal_hours' } })

      expect(hasChanges.value).toBe(true)
      expect(changedRowsCount.value).toBe(1)
      expect(noSplitCount.value).toBe(0)
      expect(statusCounts.value.present).toBe(0)
      expect(statusCounts.value.absent).toBe(1)
    })

    it('a raw-object allocations save flips hasChanges/unallocatedCount', () => {
      const { attendanceData, hasChanges, unallocatedCount, onAllocationsSaved } = withSetup(() =>
        useAttendanceGridData(),
      )

      attendanceData.value = [
        { employee_id: 1, actual_hours: 8, allocations: [] } as AttendanceRow,
      ]

      expect(hasChanges.value).toBe(false)
      expect(unallocatedCount.value).toBe(1)

      const rawRow = toRaw(attendanceData.value[0])
      onAllocationsSaved({
        row: rawRow,
        items: [{ category: 'billed_production', hours: 5 }],
      })

      expect(hasChanges.value).toBe(true)
      expect(unallocatedCount.value).toBe(0)
    })
  })

  describe('onPasteConfirm carries OT split + labor_class_override', () => {
    const mockGridApi = () => ({
      sizeColumnsToFit: vi.fn(),
      refreshCells: vi.fn(),
      applyTransaction: vi.fn(),
      forEachNode: vi.fn(),
    })

    it('pasted OT split + override values are not dropped', () => {
      // Fix round 3, item 3: onPasteConfirm now prepends into
      // attendanceData.value directly (one row store), not a grid-only
      // gridApi.applyTransaction — read the prepared row straight off it.
      const { attendanceData, onPasteConfirm } = withSetup(() => useAttendanceGridData())

      onPasteConfirm([
        {
          employee_id: 9,
          employee_name: 'Pasted Employee',
          shift_date: '2026-08-05',
          status: 'Present',
          actual_hours: 8,
          normal_hours: 8,
          double_hours: 0,
          triple_hours: 0,
          labor_class_override: 'indirect',
        },
      ])

      expect(attendanceData.value).toHaveLength(1)
      const preparedRow = attendanceData.value[0]
      expect(preparedRow.normal_hours).toBe(8)
      expect(preparedRow.double_hours).toBe(0)
      expect(preparedRow.triple_hours).toBe(0)
      expect(preparedRow.labor_class_override).toBe('indirect')
    })

    it('defaults OT split + override to null when the pasted row omits them', () => {
      const { attendanceData, onPasteConfirm } = withSetup(() => useAttendanceGridData())

      onPasteConfirm([{ employee_id: 10, shift_date: '2026-08-05', status: 'Present' }])

      const preparedRow = attendanceData.value[0]
      expect(preparedRow.normal_hours).toBeNull()
      expect(preparedRow.double_hours).toBeNull()
      expect(preparedRow.triple_hours).toBeNull()
      expect(preparedRow.labor_class_override).toBeNull()
    })

    it('pasted rows get a unique _localId and are prepended ahead of existing rows', () => {
      const { attendanceData, onPasteConfirm } = withSetup(() => useAttendanceGridData())
      attendanceData.value = [{ employee_id: 1, _localId: 'existing-row' } as AttendanceRow]

      onPasteConfirm([{ employee_id: 2, shift_date: '2026-08-05', status: 'Present' }])

      expect(attendanceData.value).toHaveLength(2)
      expect(attendanceData.value[0].employee_id).toBe(2)
      expect(attendanceData.value[0]._localId).toBeTruthy()
      expect(attendanceData.value[0]._localId).not.toBe('existing-row')
      expect(attendanceData.value[1]._localId).toBe('existing-row')
    })

    it('pasted OT split + override values survive into buildPayload on save', async () => {
      const { attendanceData, gridRef, onPasteConfirm, saveAttendance, onConfirmSave } =
        withSetup(() => useAttendanceGridData())
      const gridApi = mockGridApi()

      onPasteConfirm([
        {
          employee_id: 11,
          shift_date: '2026-08-05',
          status: 'Present',
          actual_hours: 8,
          normal_hours: 8,
          double_hours: 0,
          triple_hours: 0,
          labor_class_override: 'indirect',
        },
      ])
      const preparedRow = attendanceData.value[0]

      // saveAttendance still gathers changed rows via gridApi.forEachNode
      // (AG Grid's own truth) — mock it to reflect the row now living in
      // attendanceData.value, same as the real AG Grid rowData binding would.
      gridApi.forEachNode.mockImplementation(
        (cb: (_n: { data: AttendanceRow }) => void) => cb({ data: preparedRow }),
      )
      gridRef.value = { gridApi }

      await saveAttendance()
      await onConfirmSave()

      expect(mockApi.createAttendanceEntry).toHaveBeenCalledWith(
        expect.objectContaining({
          normal_hours: 8,
          double_hours: 0,
          triple_hours: 0,
          labor_class_override: 'indirect',
        }),
      )
    })
  })

  describe('findTrackedRow keys by row identity, not employee_id (fix round 3, item 3)', () => {
    it('editing a pasted row does not mutate an existing roster row for the same employee', () => {
      const { attendanceData, onPasteConfirm, markRowAsChanged } = withSetup(() =>
        useAttendanceGridData(),
      )

      attendanceData.value = [
        {
          employee_id: 5,
          employee_name: 'Roster Employee',
          status: 'Present',
          normal_hours: null,
          _hasChanges: false,
          _localId: 'roster-local-id',
        } as AttendanceRow,
      ]

      // A pasted row for the SAME employee_id — e.g. a floater covering an
      // already-rostered employee's shift twice, or a mis-paste.
      onPasteConfirm([{ employee_id: 5, employee_name: 'Duplicate Paste', status: 'Absent' }])

      expect(attendanceData.value).toHaveLength(2)
      const pastedRow = attendanceData.value[0]
      const rosterRow = attendanceData.value[1]
      expect(pastedRow.employee_id).toBe(5)
      expect(rosterRow.employee_id).toBe(5)
      expect(pastedRow._localId).not.toBe(rosterRow._localId)

      // Simulate AG Grid handing back a raw, disconnected copy of the
      // PASTED row (same shape cellValueChanged normally delivers).
      const rawEditedPastedRow = { ...pastedRow, normal_hours: 6 }
      markRowAsChanged({ data: rawEditedPastedRow, colDef: { field: 'normal_hours' } })

      expect(attendanceData.value[0].normal_hours).toBe(6)
      expect(attendanceData.value[0]._hasChanges).toBe(true)
      // The roster row — a DIFFERENT row that happens to share employee_id —
      // must be untouched. Under the old employee_id-keyed findTrackedRow,
      // Array.find would resolve to whichever row matched employee_id
      // FIRST (the pasted row at index 0, prepended), so this specific
      // scenario wouldn't have caught it; the point of this test is that
      // matching is now by _localId at all, not incidentally-correct
      // array ordering.
      expect(attendanceData.value[1].normal_hours).toBeNull()
      expect(attendanceData.value[1]._hasChanges).toBe(false)
    })

    it('an edit with no matching _localId in attendanceData does not corrupt any tracked row', () => {
      const { attendanceData, markRowAsChanged } = withSetup(() => useAttendanceGridData())
      attendanceData.value = [
        { employee_id: 1, status: 'Present', _localId: 'row-1' } as AttendanceRow,
      ]

      const disconnectedRow = { employee_id: 1, status: 'Absent', _localId: 'row-does-not-exist' }
      markRowAsChanged({ data: disconnectedRow, colDef: { field: 'status' } })

      // Falls back to mutating the disconnected object itself (defensive
      // — see findTrackedRow's declaration comment) rather than guessing
      // at a same-employee_id row.
      expect(attendanceData.value[0].status).toBe('Present')
      expect(attendanceData.value[0]._hasChanges).toBeFalsy()
    })
  })

  describe('bulkSetStatus routes through tracked rows + editTick (fix round 3, item 3)', () => {
    it('flips hasChanges and marks every tracked row Present, without needing gridApi', () => {
      const { attendanceData, hasChanges, bulkSetStatus } = withSetup(() =>
        useAttendanceGridData(),
      )
      attendanceData.value = [
        { employee_id: 1, status: 'Present', _hasChanges: false } as AttendanceRow,
        { employee_id: 2, status: 'Absent', _hasChanges: false } as AttendanceRow,
      ]
      expect(hasChanges.value).toBe(false)

      // No gridRef.value set at all — bulkSetStatus previously required
      // gridApi to do anything (gridApi.forEachNode); now it operates
      // purely on attendanceData.value.
      bulkSetStatus()

      expect(hasChanges.value).toBe(true)
      expect(attendanceData.value.every((r) => r.status === 'Present' && r._hasChanges)).toBe(
        true,
      )
    })
  })

  describe('initial state', () => {
    it('initialises attendanceData empty', () => {
      const { attendanceData } = withSetup(() => useAttendanceGridData())
      expect(attendanceData.value).toEqual([])
    })

    it('initialises selectedDate to today', () => {
      const { selectedDate } = withSetup(() => useAttendanceGridData())
      expect(selectedDate.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })

    it('initialises hasChanges false', () => {
      const { hasChanges } = withSetup(() => useAttendanceGridData())
      expect(hasChanges.value).toBe(false)
    })
  })
})
