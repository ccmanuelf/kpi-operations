/**
 * Unit tests for useAvailabilityData composable.
 *
 * Covers the Availability KPI detail page's logic surface — the view itself
 * (`views/kpi/Availability.vue`) is a thin presentation layer; testing this
 * composable lifts both files from 0% line coverage. Asserts:
 *   - reactive state defaults
 *   - threshold-based color tokens (statusColor, getAvailabilityColor)
 *   - formatters (formatValue, formatDate)
 *   - i18n-resolved table headers (downtime, equipment, downtimeHistory)
 *   - async actions (loadClients via initialize, loadDowntimeHistory success
 *     + error, refreshData success + error, onClientChange/onDateChange side
 *     effects, initialize)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

const { mockApi, kpiStoreState } = vi.hoisted(() => ({
  mockApi: {
    getClients: vi.fn(),
    getDowntimeEntries: vi.fn(),
  },
  kpiStoreState: {
    availability: null as Record<string, unknown> | null,
    fetchAvailability: vi.fn(),
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

import useAvailabilityData from '../useAvailabilityData'

describe('useAvailabilityData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockApi.getClients.mockReset().mockResolvedValue({ data: [] })
    mockApi.getDowntimeEntries.mockReset().mockResolvedValue({ data: [] })
    kpiStoreState.availability = null
    kpiStoreState.fetchAvailability.mockReset().mockResolvedValue(undefined)
    kpiStoreState.setClient.mockReset()
    kpiStoreState.setDateRange.mockReset()
  })

  describe('initial state', () => {
    it('has loading=false and empty collections', () => {
      const c = useAvailabilityData()
      expect(c.loading.value).toBe(false)
      expect(c.clients.value).toEqual([])
      expect(c.downtimeHistory.value).toEqual([])
      expect(c.selectedClient.value).toBeNull()
      expect(c.tableSearch.value).toBe('')
    })

    it('initializes startDate to 30 days ago and endDate to today', () => {
      const c = useAvailabilityData()
      expect(c.startDate.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(c.endDate.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      const start = new Date(c.startDate.value)
      const end = new Date(c.endDate.value)
      const days = Math.round((end.getTime() - start.getTime()) / 86_400_000)
      expect(days).toBe(30)
    })
  })

  describe('threshold colors', () => {
    it.each([
      [95, 'success'],
      [90, 'success'],
      [85, 'amber-darken-3'],
      [80, 'amber-darken-3'],
      [70, 'error'],
      [0, 'error'],
    ])('getAvailabilityColor(%d) returns %s', (val, expected) => {
      const c = useAvailabilityData()
      expect(c.getAvailabilityColor(val)).toBe(expected)
    })
  })

  describe('statusColor (computed) reflects availability percentage', () => {
    it.each([
      [95, 'success'],
      [90, 'success'],
      [85, '#b45309'],
      [70, 'error'],
    ])('percentage=%d → %s', (percentage, expected) => {
      kpiStoreState.availability = { percentage }
      const c = useAvailabilityData()
      expect(c.statusColor.value).toBe(expected)
    })

    it('null availability → error (treats as 0)', () => {
      kpiStoreState.availability = null
      const c = useAvailabilityData()
      expect(c.statusColor.value).toBe('error')
    })
  })

  describe('formatters', () => {
    it('formatValue returns 1-decimal string for finite numbers', () => {
      const c = useAvailabilityData()
      expect(c.formatValue(91)).toBe('91.0')
      expect(c.formatValue(91.456)).toBe('91.5')
    })

    it('formatValue returns the i18n n/a key when value is null/undefined', () => {
      const c = useAvailabilityData()
      expect(c.formatValue(null)).toBe('common.na')
      expect(c.formatValue(undefined)).toBe('common.na')
    })

    it('formatDate formats valid date strings (MMM dd, yyyy)', () => {
      const c = useAvailabilityData()
      const out = c.formatDate('2026-05-07T12:00:00')
      expect(out).toBe('May 07, 2026')
    })

    it('formatDate returns the input when parsing fails', () => {
      const c = useAvailabilityData()
      expect(c.formatDate('not-a-date')).toBe('not-a-date')
    })
  })

  describe('table headers (i18n-resolved)', () => {
    it('downtimeHeaders has reason, hours, percentage', () => {
      const c = useAvailabilityData()
      expect(c.downtimeHeaders.value.map((h) => h.key)).toEqual([
        'reason',
        'hours',
        'percentage',
      ])
    })

    it('equipmentHeaders has equipment_name, uptime, downtime, availability', () => {
      const c = useAvailabilityData()
      expect(c.equipmentHeaders.value.map((h) => h.key)).toEqual([
        'equipment_name',
        'uptime',
        'downtime',
        'availability',
      ])
    })

    it('downtimeHistoryHeaders has shift_date, downtime_reason, duration, notes', () => {
      const c = useAvailabilityData()
      expect(c.downtimeHistoryHeaders.value.map((h) => h.key)).toEqual([
        'shift_date',
        'downtime_reason',
        'downtime_duration_minutes',
        'notes',
      ])
    })
  })

  describe('refreshData', () => {
    it('calls store.fetchAvailability + api.getDowntimeEntries and toggles loading', async () => {
      const c = useAvailabilityData()
      const promise = c.refreshData()
      expect(c.loading.value).toBe(true)
      await promise
      expect(kpiStoreState.fetchAvailability).toHaveBeenCalled()
      expect(mockApi.getDowntimeEntries).toHaveBeenCalled()
      expect(c.loading.value).toBe(false)
    })

    it('passes start_date/end_date and threads selectedClient when set', async () => {
      const c = useAvailabilityData()
      c.selectedClient.value = 'ACME-MFG'
      c.startDate.value = '2026-01-01'
      c.endDate.value = '2026-02-01'
      await c.refreshData()
      expect(mockApi.getDowntimeEntries).toHaveBeenCalledWith({
        start_date: '2026-01-01',
        end_date: '2026-02-01',
        client_id: 'ACME-MFG',
      })
    })

    it('omits client_id when no client selected', async () => {
      const c = useAvailabilityData()
      await c.refreshData()
      const call = mockApi.getDowntimeEntries.mock.calls[0][0]
      expect(call).not.toHaveProperty('client_id')
    })

    it('populates downtimeHistory from response', async () => {
      mockApi.getDowntimeEntries.mockResolvedValueOnce({
        data: [{ shift_date: '2026-05-07', downtime_duration_minutes: 30 }],
      })
      const c = useAvailabilityData()
      await c.refreshData()
      expect(c.downtimeHistory.value).toEqual([
        { shift_date: '2026-05-07', downtime_duration_minutes: 30 },
      ])
    })

    it('clears downtimeHistory and clears loading when getDowntimeEntries throws', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockApi.getDowntimeEntries.mockRejectedValueOnce(new Error('boom'))
      const c = useAvailabilityData()
      await c.refreshData()
      expect(c.downtimeHistory.value).toEqual([])
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })

    it('clears loading even when fetchAvailability throws', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      kpiStoreState.fetchAvailability.mockRejectedValueOnce(new Error('boom'))
      const c = useAvailabilityData()
      await c.refreshData()
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })

  describe('onClientChange / onDateChange', () => {
    it('onClientChange updates store and refreshes data', async () => {
      const c = useAvailabilityData()
      c.selectedClient.value = 'ACME-MFG'
      c.onClientChange()
      await flushPromises()
      expect(kpiStoreState.setClient).toHaveBeenCalledWith('ACME-MFG')
      expect(kpiStoreState.fetchAvailability).toHaveBeenCalled()
    })

    it('onDateChange updates store with current dates and refreshes data', async () => {
      const c = useAvailabilityData()
      c.startDate.value = '2026-01-01'
      c.endDate.value = '2026-02-01'
      c.onDateChange()
      await flushPromises()
      expect(kpiStoreState.setDateRange).toHaveBeenCalledWith('2026-01-01', '2026-02-01')
      expect(kpiStoreState.fetchAvailability).toHaveBeenCalled()
    })
  })

  describe('initialize', () => {
    it('loads clients, sets date range on store, and refreshes', async () => {
      mockApi.getClients.mockResolvedValueOnce({ data: [{ client_id: 'C1' }] })
      const c = useAvailabilityData()
      await c.initialize()
      expect(c.clients.value).toEqual([{ client_id: 'C1' }])
      expect(kpiStoreState.setDateRange).toHaveBeenCalled()
      expect(kpiStoreState.fetchAvailability).toHaveBeenCalled()
      expect(c.loading.value).toBe(false)
    })

    it('still clears loading on getClients failure', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockApi.getClients.mockRejectedValueOnce(new Error('500'))
      const c = useAvailabilityData()
      await c.initialize()
      expect(c.clients.value).toEqual([])
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })
})
