/**
 * Unit tests for useOnTimeDeliveryData composable.
 *
 * Covers the OTD KPI detail page's logic surface — the view itself
 * (`views/kpi/OnTimeDelivery.vue`) is a thin presentation layer; testing
 * this composable lifts both files from 0% line coverage. Asserts:
 *   - reactive state defaults
 *   - threshold-based color tokens (statusColor 95/85/else, getOTDColor,
 *     getEfficiencyColor)
 *   - formatters (formatValue, formatDate)
 *   - i18n-resolved table headers (clientHeaders, lateHeaders, historyHeaders)
 *   - async actions (loadClients via initialize, refreshData success +
 *     error, onClientChange/onDateChange side effects, initialize)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

const { mockApi, kpiStoreState } = vi.hoisted(() => ({
  mockApi: {
    getClients: vi.fn(),
  },
  kpiStoreState: {
    onTimeDelivery: null as Record<string, unknown> | null,
    dashboard: [] as unknown[],
    fetchOnTimeDelivery: vi.fn(),
    fetchDashboard: vi.fn(),
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

import useOnTimeDeliveryData from '../useOnTimeDeliveryData'

describe('useOnTimeDeliveryData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockApi.getClients.mockReset().mockResolvedValue({ data: [] })
    kpiStoreState.onTimeDelivery = null
    kpiStoreState.dashboard = []
    kpiStoreState.fetchOnTimeDelivery.mockReset().mockResolvedValue(undefined)
    kpiStoreState.fetchDashboard.mockReset().mockResolvedValue(undefined)
    kpiStoreState.setClient.mockReset()
    kpiStoreState.setDateRange.mockReset()
  })

  describe('initial state', () => {
    it('has loading=false and empty collections', () => {
      const c = useOnTimeDeliveryData()
      expect(c.loading.value).toBe(false)
      expect(c.clients.value).toEqual([])
      expect(c.historicalData.value).toEqual([])
      expect(c.selectedClient.value).toBeNull()
      expect(c.tableSearch.value).toBe('')
    })

    it('initializes startDate to 30 days ago and endDate to today', () => {
      const c = useOnTimeDeliveryData()
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
      [98, 'success'],
      [95, 'success'],
      [90, 'amber-darken-3'],
      [85, 'amber-darken-3'],
      [80, 'error'],
      [0, 'error'],
    ])('getOTDColor(%d) returns %s', (val, expected) => {
      const c = useOnTimeDeliveryData()
      expect(c.getOTDColor(val)).toBe(expected)
    })

    it.each([
      [90, 'success'],
      [85, 'success'],
      [80, 'amber-darken-3'],
      [70, 'amber-darken-3'],
      [50, 'error'],
    ])('getEfficiencyColor(%d) returns %s', (val, expected) => {
      const c = useOnTimeDeliveryData()
      expect(c.getEfficiencyColor(val)).toBe(expected)
    })
  })

  describe('statusColor (computed) reflects OTD percentage', () => {
    it.each([
      [98, 'success'],
      [95, 'success'],
      [90, 'amber-darken-3'],
      [80, 'error'],
    ])('percentage=%d → %s', (percentage, expected) => {
      kpiStoreState.onTimeDelivery = { percentage }
      const c = useOnTimeDeliveryData()
      expect(c.statusColor.value).toBe(expected)
    })

    it('null OTD → error (treats as 0)', () => {
      kpiStoreState.onTimeDelivery = null
      const c = useOnTimeDeliveryData()
      expect(c.statusColor.value).toBe('error')
    })
  })

  describe('formatters', () => {
    it('formatValue returns 1-decimal string for finite numbers', () => {
      const c = useOnTimeDeliveryData()
      expect(c.formatValue(95)).toBe('95.0')
      expect(c.formatValue(95.456)).toBe('95.5')
    })

    it('formatValue returns the i18n n/a key when value is null/undefined', () => {
      const c = useOnTimeDeliveryData()
      expect(c.formatValue(null)).toBe('common.na')
      expect(c.formatValue(undefined)).toBe('common.na')
    })

    it('formatDate formats valid date strings (MMM dd, yyyy)', () => {
      const c = useOnTimeDeliveryData()
      const out = c.formatDate('2026-05-07T12:00:00')
      expect(out).toBe('May 07, 2026')
    })

    it('formatDate returns the input when parsing fails', () => {
      const c = useOnTimeDeliveryData()
      expect(c.formatDate('not-a-date')).toBe('not-a-date')
    })
  })

  describe('table headers (i18n-resolved)', () => {
    it('clientHeaders has client_name, total_deliveries, on_time, otd_percentage', () => {
      const c = useOnTimeDeliveryData()
      expect(c.clientHeaders.value.map((h) => h.key)).toEqual([
        'client_name',
        'total_deliveries',
        'on_time',
        'otd_percentage',
      ])
    })

    it('lateHeaders has delivery_date, work_order, client, delay_hours', () => {
      const c = useOnTimeDeliveryData()
      expect(c.lateHeaders.value.map((h) => h.key)).toEqual([
        'delivery_date',
        'work_order',
        'client',
        'delay_hours',
      ])
    })

    it('historyHeaders has date, total_units, avg_efficiency, entry_count', () => {
      const c = useOnTimeDeliveryData()
      expect(c.historyHeaders.value.map((h) => h.key)).toEqual([
        'date',
        'total_units',
        'avg_efficiency',
        'entry_count',
      ])
    })
  })

  describe('refreshData', () => {
    it('calls store.fetchOnTimeDelivery + fetchDashboard and toggles loading', async () => {
      kpiStoreState.dashboard = [{ date: '2026-05-07' }]
      const c = useOnTimeDeliveryData()
      const promise = c.refreshData()
      expect(c.loading.value).toBe(true)
      await promise
      expect(kpiStoreState.fetchOnTimeDelivery).toHaveBeenCalled()
      expect(kpiStoreState.fetchDashboard).toHaveBeenCalled()
      expect(c.historicalData.value).toEqual([{ date: '2026-05-07' }])
      expect(c.loading.value).toBe(false)
    })

    it('clears loading even when fetchOnTimeDelivery throws', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      kpiStoreState.fetchOnTimeDelivery.mockRejectedValueOnce(new Error('boom'))
      const c = useOnTimeDeliveryData()
      await c.refreshData()
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })

  describe('onClientChange / onDateChange', () => {
    it('onClientChange updates store and refreshes data', async () => {
      const c = useOnTimeDeliveryData()
      c.selectedClient.value = 'ACME-MFG'
      c.onClientChange()
      await flushPromises()
      expect(kpiStoreState.setClient).toHaveBeenCalledWith('ACME-MFG')
      expect(kpiStoreState.fetchOnTimeDelivery).toHaveBeenCalled()
    })

    it('onDateChange updates store with current dates and refreshes data', async () => {
      const c = useOnTimeDeliveryData()
      c.startDate.value = '2026-01-01'
      c.endDate.value = '2026-02-01'
      c.onDateChange()
      await flushPromises()
      expect(kpiStoreState.setDateRange).toHaveBeenCalledWith('2026-01-01', '2026-02-01')
      expect(kpiStoreState.fetchOnTimeDelivery).toHaveBeenCalled()
    })
  })

  describe('initialize', () => {
    it('loads clients, sets date range on store, and refreshes', async () => {
      mockApi.getClients.mockResolvedValueOnce({ data: [{ client_id: 'C1' }] })
      const c = useOnTimeDeliveryData()
      await c.initialize()
      expect(c.clients.value).toEqual([{ client_id: 'C1' }])
      expect(kpiStoreState.setDateRange).toHaveBeenCalled()
      expect(kpiStoreState.fetchOnTimeDelivery).toHaveBeenCalled()
      expect(c.loading.value).toBe(false)
    })

    it('still clears loading on getClients failure', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockApi.getClients.mockRejectedValueOnce(new Error('500'))
      const c = useOnTimeDeliveryData()
      await c.initialize()
      expect(c.clients.value).toEqual([])
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })
})
