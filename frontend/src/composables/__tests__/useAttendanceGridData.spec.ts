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
import { setActivePinia, createPinia } from 'pinia'

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
  cellEditorParams?: { values?: unknown[]; min?: number; max?: number }
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
      const { columnDefs } = useAttendanceGridData()
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
      const { columnDefs } = useAttendanceGridData()
      const col = findCol(columnDefs.value, 'scheduled_hours')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams!.max).toBe(24)
    })

    it('exposes actual_hours column with numeric editor', () => {
      const { columnDefs } = useAttendanceGridData()
      const col = findCol(columnDefs.value, 'actual_hours')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams!.max).toBe(24)
    })

    it('does NOT expose late_minutes column (vestigial)', () => {
      const { columnDefs } = useAttendanceGridData()
      expect(findCol(columnDefs.value, 'late_minutes')).toBeUndefined()
    })

    it('does NOT expose is_excused column (vestigial)', () => {
      const { columnDefs } = useAttendanceGridData()
      expect(findCol(columnDefs.value, 'is_excused')).toBeUndefined()
    })

    it('clock_in column field stays user-friendly (HH:MM string)', () => {
      const { columnDefs } = useAttendanceGridData()
      const col = findCol(columnDefs.value, 'clock_in')!
      expect(col.editable).toBe(true)
    })

    it('clock_out column field stays user-friendly (HH:MM string)', () => {
      const { columnDefs } = useAttendanceGridData()
      const col = findCol(columnDefs.value, 'clock_out')!
      expect(col.editable).toBe(true)
    })
  })

  describe('statusCounts', () => {
    it('counts Present', () => {
      const { attendanceData, statusCounts } = useAttendanceGridData()
      attendanceData.value = [
        { status: 'Present' } as AttendanceRow,
        { status: 'Present' } as AttendanceRow,
      ]
      expect(statusCounts.value.present).toBe(2)
    })

    it('counts Absent', () => {
      const { attendanceData, statusCounts } = useAttendanceGridData()
      attendanceData.value = [{ status: 'Absent' } as AttendanceRow]
      expect(statusCounts.value.absent).toBe(1)
    })

    it('counts Late', () => {
      const { attendanceData, statusCounts } = useAttendanceGridData()
      attendanceData.value = [{ status: 'Late' } as AttendanceRow]
      expect(statusCounts.value.late).toBe(1)
    })

    it('counts Leave + Vacation + Medical together', () => {
      const { attendanceData, statusCounts } = useAttendanceGridData()
      attendanceData.value = [
        { status: 'Leave' } as AttendanceRow,
        { status: 'Vacation' } as AttendanceRow,
        { status: 'Medical' } as AttendanceRow,
      ]
      expect(statusCounts.value.leave).toBe(3)
    })

    it('counts Half Day separately', () => {
      const { attendanceData, statusCounts } = useAttendanceGridData()
      attendanceData.value = [{ status: 'Half Day' } as AttendanceRow]
      expect(statusCounts.value.halfDay).toBe(1)
    })
  })

  describe('initial state', () => {
    it('initialises attendanceData empty', () => {
      const { attendanceData } = useAttendanceGridData()
      expect(attendanceData.value).toEqual([])
    })

    it('initialises selectedDate to today', () => {
      const { selectedDate } = useAttendanceGridData()
      expect(selectedDate.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })

    it('initialises hasChanges false', () => {
      const { hasChanges } = useAttendanceGridData()
      expect(hasChanges.value).toBe(false)
    })
  })
})
