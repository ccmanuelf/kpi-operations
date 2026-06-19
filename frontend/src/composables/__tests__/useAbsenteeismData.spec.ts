/**
 * Unit tests for useAbsenteeismData composable.
 *
 * Covers the Absenteeism KPI detail page's logic surface — the view itself
 * (`views/kpi/Absenteeism.vue`) is a thin presentation layer; testing this
 * composable lifts both files from 0% line coverage. Asserts:
 *   - reactive state defaults
 *   - INVERTED threshold-based color tokens (statusColor, getAbsenteeismColor)
 *     where lower rate = healthier
 *   - formatters (formatValue, formatDate)
 *   - i18n-resolved table headers (reason, dept, alert, attendanceHistory)
 *   - async actions (loadAttendanceHistory transforms is_absent → status,
 *     refreshData success + error, onClientChange/onDateChange side effects,
 *     initialize)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

const { mockApi, kpiStoreState } = vi.hoisted(() => ({
  mockApi: {
    getClients: vi.fn(),
    getAttendanceEntries: vi.fn(),
  },
  kpiStoreState: {
    absenteeism: null as Record<string, unknown> | null,
    fetchAbsenteeism: vi.fn(),
    setClient: vi.fn(),
    setDateRange: vi.fn(),
  },
}))

vi.mock('@/services/api', () => ({ default: mockApi }))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (k: string) => k }),
}))
vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => kpiStoreState,
}))

import useAbsenteeismData from '../useAbsenteeismData'

describe('useAbsenteeismData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockApi.getClients.mockReset().mockResolvedValue({ data: [] })
    mockApi.getAttendanceEntries.mockReset().mockResolvedValue({ data: [] })
    kpiStoreState.absenteeism = null
    kpiStoreState.fetchAbsenteeism.mockReset().mockResolvedValue(undefined)
    kpiStoreState.setClient.mockReset()
    kpiStoreState.setDateRange.mockReset()
  })

  describe('initial state', () => {
    it('has loading=false and empty collections', () => {
      const c = useAbsenteeismData()
      expect(c.loading.value).toBe(false)
      expect(c.clients.value).toEqual([])
      expect(c.attendanceHistory.value).toEqual([])
      expect(c.selectedClient.value).toBeNull()
      expect(c.tableSearch.value).toBe('')
    })

    it('initializes startDate to 30 days ago and endDate to today', () => {
      const c = useAbsenteeismData()
      expect(c.startDate.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(c.endDate.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      const start = new Date(c.startDate.value)
      const end = new Date(c.endDate.value)
      const days = Math.round((end.getTime() - start.getTime()) / 86_400_000)
      expect(days).toBe(30)
    })
  })

  describe('threshold colors (INVERTED — lower is better)', () => {
    it.each([
      [0, 'success'],
      [3, 'success'],
      [5, 'success'],
      [7, 'amber-darken-3'],
      [10, 'amber-darken-3'],
      [15, 'error'],
      [50, 'error'],
    ])('getAbsenteeismColor(%d) returns %s', (val, expected) => {
      const c = useAbsenteeismData()
      expect(c.getAbsenteeismColor(val)).toBe(expected)
    })
  })

  describe('statusColor (computed) reflects absenteeism rate (INVERTED)', () => {
    it.each([
      [3, 'success'],
      [5, 'success'],
      [7, '#b45309'],
      [12, 'error'],
    ])('rate=%d → %s', (rate, expected) => {
      kpiStoreState.absenteeism = { rate }
      const c = useAbsenteeismData()
      expect(c.statusColor.value).toBe(expected)
    })

    it('null absenteeism → success (treats as 0, inverted threshold)', () => {
      // Inverted threshold: a missing/zero rate is the BEST case, not the worst.
      kpiStoreState.absenteeism = null
      const c = useAbsenteeismData()
      expect(c.statusColor.value).toBe('success')
    })
  })

  describe('formatters', () => {
    it('formatValue returns 1-decimal string for finite numbers', () => {
      const c = useAbsenteeismData()
      expect(c.formatValue(5)).toBe('5.0')
      expect(c.formatValue(5.456)).toBe('5.5')
    })

    it('formatValue returns the i18n n/a key when value is null/undefined', () => {
      const c = useAbsenteeismData()
      expect(c.formatValue(null)).toBe('common.na')
      expect(c.formatValue(undefined)).toBe('common.na')
    })

    it('formatDate formats valid date strings (MMM dd, yyyy)', () => {
      const c = useAbsenteeismData()
      const out = c.formatDate('2026-05-07T12:00:00')
      expect(out).toBe('May 07, 2026')
    })

    it('formatDate returns the input when parsing fails', () => {
      const c = useAbsenteeismData()
      expect(c.formatDate('not-a-date')).toBe('not-a-date')
    })
  })

  describe('table headers (i18n-resolved)', () => {
    it('reasonHeaders has reason, count, percentage', () => {
      const c = useAbsenteeismData()
      expect(c.reasonHeaders.value.map((h) => h.key)).toEqual([
        'reason',
        'count',
        'percentage',
      ])
    })

    it('deptHeaders has department, workforce, absences, rate', () => {
      const c = useAbsenteeismData()
      expect(c.deptHeaders.value.map((h) => h.key)).toEqual([
        'department',
        'workforce',
        'absences',
        'rate',
      ])
    })

    it('alertHeaders has employee_id, department, absence_count, last_absence', () => {
      const c = useAbsenteeismData()
      expect(c.alertHeaders.value.map((h) => h.key)).toEqual([
        'employee_id',
        'department',
        'absence_count',
        'last_absence',
      ])
    })

    it('attendanceHistoryHeaders has shift_date, employee_id, scheduled, actual, status', () => {
      const c = useAbsenteeismData()
      expect(c.attendanceHistoryHeaders.value.map((h) => h.key)).toEqual([
        'shift_date',
        'employee_id',
        'scheduled_hours',
        'actual_hours',
        'status',
      ])
    })
  })

  describe('refreshData', () => {
    it('calls store.fetchAbsenteeism + api.getAttendanceEntries and toggles loading', async () => {
      const c = useAbsenteeismData()
      const promise = c.refreshData()
      expect(c.loading.value).toBe(true)
      await promise
      expect(kpiStoreState.fetchAbsenteeism).toHaveBeenCalled()
      expect(mockApi.getAttendanceEntries).toHaveBeenCalled()
      expect(c.loading.value).toBe(false)
    })

    it('passes start_date/end_date and threads selectedClient when set', async () => {
      const c = useAbsenteeismData()
      c.selectedClient.value = 'ACME-MFG'
      c.startDate.value = '2026-01-01'
      c.endDate.value = '2026-02-01'
      await c.refreshData()
      expect(mockApi.getAttendanceEntries).toHaveBeenCalledWith({
        start_date: '2026-01-01',
        end_date: '2026-02-01',
        client_id: 'ACME-MFG',
      })
    })

    it('omits client_id when no client selected', async () => {
      const c = useAbsenteeismData()
      await c.refreshData()
      const call = mockApi.getAttendanceEntries.mock.calls[0][0]
      expect(call).not.toHaveProperty('client_id')
    })

    it('transforms is_absent into ABSENT/PRESENT status', async () => {
      mockApi.getAttendanceEntries.mockResolvedValueOnce({
        data: [
          { employee_id: 'E1', is_absent: true },
          { employee_id: 'E2', is_absent: false },
        ],
      })
      const c = useAbsenteeismData()
      await c.refreshData()
      expect(c.attendanceHistory.value).toEqual([
        { employee_id: 'E1', is_absent: true, status: 'ABSENT' },
        { employee_id: 'E2', is_absent: false, status: 'PRESENT' },
      ])
    })

    it('clears attendanceHistory when getAttendanceEntries throws', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockApi.getAttendanceEntries.mockRejectedValueOnce(new Error('boom'))
      const c = useAbsenteeismData()
      await c.refreshData()
      expect(c.attendanceHistory.value).toEqual([])
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })

    it('clears loading even when fetchAbsenteeism throws', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      kpiStoreState.fetchAbsenteeism.mockRejectedValueOnce(new Error('boom'))
      const c = useAbsenteeismData()
      await c.refreshData()
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })

  describe('onClientChange / onDateChange', () => {
    it('onClientChange updates store and refreshes data', async () => {
      const c = useAbsenteeismData()
      c.selectedClient.value = 'ACME-MFG'
      c.onClientChange()
      await flushPromises()
      expect(kpiStoreState.setClient).toHaveBeenCalledWith('ACME-MFG')
      expect(kpiStoreState.fetchAbsenteeism).toHaveBeenCalled()
    })

    it('onDateChange updates store with current dates and refreshes data', async () => {
      const c = useAbsenteeismData()
      c.startDate.value = '2026-01-01'
      c.endDate.value = '2026-02-01'
      c.onDateChange()
      await flushPromises()
      expect(kpiStoreState.setDateRange).toHaveBeenCalledWith('2026-01-01', '2026-02-01')
      expect(kpiStoreState.fetchAbsenteeism).toHaveBeenCalled()
    })
  })

  describe('initialize', () => {
    it('loads clients, sets date range on store, and refreshes', async () => {
      mockApi.getClients.mockResolvedValueOnce({ data: [{ client_id: 'C1' }] })
      const c = useAbsenteeismData()
      await c.initialize()
      expect(c.clients.value).toEqual([{ client_id: 'C1' }])
      expect(kpiStoreState.setDateRange).toHaveBeenCalled()
      expect(kpiStoreState.fetchAbsenteeism).toHaveBeenCalled()
      expect(c.loading.value).toBe(false)
    })

    it('still clears loading on getClients failure', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockApi.getClients.mockRejectedValueOnce(new Error('500'))
      const c = useAbsenteeismData()
      await c.initialize()
      expect(c.clients.value).toEqual([])
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })
})
