/**
 * Unit tests for useOEEData composable.
 *
 * Covers the OEE KPI detail page's logic surface — the view itself
 * (`views/kpi/OEE.vue`) is a thin presentation layer; testing this
 * composable lifts both files from 0% line coverage. Asserts:
 *   - reactive state defaults
 *   - threshold-based color tokens (statusColor with OEE thresholds 85/65,
 *     getEfficiencyColor, getPerformanceColor)
 *   - components computed (availability/performance/quality with defaults)
 *   - formatters (formatValue, formatDate)
 *   - i18n-resolved historyHeaders
 *   - async actions (loadClients via initialize, refreshData success + error,
 *     onClientChange/onDateChange side effects, initialize)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

const { mockApi, kpiStoreState } = vi.hoisted(() => ({
  mockApi: {
    getClients: vi.fn(),
  },
  kpiStoreState: {
    oee: null as Record<string, unknown> | null,
    availability: null as Record<string, unknown> | null,
    performance: null as Record<string, unknown> | null,
    quality: null as Record<string, unknown> | null,
    dashboard: [] as unknown[],
    fetchOEE: vi.fn(),
    fetchAvailability: vi.fn(),
    fetchPerformance: vi.fn(),
    fetchQuality: vi.fn(),
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

import useOEEData from '../useOEEData'

describe('useOEEData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockApi.getClients.mockReset().mockResolvedValue({ data: [] })
    kpiStoreState.oee = null
    kpiStoreState.availability = null
    kpiStoreState.performance = null
    kpiStoreState.quality = null
    kpiStoreState.dashboard = []
    kpiStoreState.fetchOEE.mockReset().mockResolvedValue(undefined)
    kpiStoreState.fetchAvailability.mockReset().mockResolvedValue(undefined)
    kpiStoreState.fetchPerformance.mockReset().mockResolvedValue(undefined)
    kpiStoreState.fetchQuality.mockReset().mockResolvedValue(undefined)
    kpiStoreState.fetchDashboard.mockReset().mockResolvedValue(undefined)
    kpiStoreState.setClient.mockReset()
    kpiStoreState.setDateRange.mockReset()
  })

  describe('initial state', () => {
    it('has loading=false and empty collections', () => {
      const c = useOEEData()
      expect(c.loading.value).toBe(false)
      expect(c.clients.value).toEqual([])
      expect(c.historicalData.value).toEqual([])
      expect(c.selectedClient.value).toBeNull()
      expect(c.tableSearch.value).toBe('')
    })

    it('initializes startDate to 30 days ago and endDate to today', () => {
      const c = useOEEData()
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
      [90, 'var(--cds-support-success)'],
      [85, 'var(--cds-support-success)'],
      [70, '#b45309'],
      [65, '#b45309'],
      [60, 'var(--cds-support-error)'],
      [0, 'var(--cds-support-error)'],
    ])('statusColor for OEE=%d returns %s', (oee, expected) => {
      kpiStoreState.oee = { percentage: oee }
      const c = useOEEData()
      expect(c.statusColor.value).toBe(expected)
    })

    it('null OEE → error (treats as 0)', () => {
      kpiStoreState.oee = null
      const c = useOEEData()
      expect(c.statusColor.value).toBe('var(--cds-support-error)')
    })

    it.each([
      [90, 'success'],
      [85, 'success'],
      [80, 'amber-darken-3'],
      [70, 'amber-darken-3'],
      [50, 'error'],
    ])('getEfficiencyColor(%d) returns %s', (val, expected) => {
      const c = useOEEData()
      expect(c.getEfficiencyColor(val)).toBe(expected)
    })

    it.each([
      [99, 'success'],
      [95, 'success'],
      [90, 'amber-darken-3'],
      [80, 'amber-darken-3'],
      [70, 'error'],
    ])('getPerformanceColor(%d) returns %s', (val, expected) => {
      const c = useOEEData()
      expect(c.getPerformanceColor(val)).toBe(expected)
    })
  })

  describe('components (computed)', () => {
    it('reads availability/performance/quality from store getters', () => {
      kpiStoreState.availability = { percentage: 90 }
      kpiStoreState.performance = { percentage: 95 }
      kpiStoreState.quality = { fpy: 99 }
      const c = useOEEData()
      expect(c.components.value).toEqual({
        availability: 90,
        performance: 95,
        quality: 99,
      })
    })

    it('falls back to default values when store getters are null', () => {
      const c = useOEEData()
      expect(c.components.value).toEqual({
        availability: 91.5,
        performance: 92,
        quality: 97,
      })
    })
  })

  describe('formatters', () => {
    it('formatValue returns 1-decimal string for finite numbers', () => {
      const c = useOEEData()
      expect(c.formatValue(80)).toBe('80.0')
      expect(c.formatValue(80.456)).toBe('80.5')
    })

    it('formatValue returns the i18n n/a key when value is null/undefined', () => {
      const c = useOEEData()
      expect(c.formatValue(null)).toBe('common.na')
      expect(c.formatValue(undefined)).toBe('common.na')
    })

    it('formatDate formats valid date strings (MMM dd, yyyy)', () => {
      const c = useOEEData()
      const out = c.formatDate('2026-05-07T12:00:00')
      expect(out).toBe('May 07, 2026')
    })

    it('formatDate returns the input when parsing fails', () => {
      const c = useOEEData()
      expect(c.formatDate('not-a-date')).toBe('not-a-date')
    })
  })

  describe('table headers (i18n-resolved)', () => {
    it('historyHeaders has date, total_units, avg_efficiency, avg_performance, entry_count', () => {
      const c = useOEEData()
      expect(c.historyHeaders.value.map((h) => h.key)).toEqual([
        'date',
        'total_units',
        'avg_efficiency',
        'avg_performance',
        'entry_count',
      ])
    })
  })

  describe('refreshData', () => {
    it('calls all 5 store fetchers in parallel and toggles loading', async () => {
      kpiStoreState.dashboard = [{ date: '2026-05-07' }]
      const c = useOEEData()
      const promise = c.refreshData()
      expect(c.loading.value).toBe(true)
      await promise
      expect(kpiStoreState.fetchOEE).toHaveBeenCalled()
      expect(kpiStoreState.fetchAvailability).toHaveBeenCalled()
      expect(kpiStoreState.fetchPerformance).toHaveBeenCalled()
      expect(kpiStoreState.fetchQuality).toHaveBeenCalled()
      expect(kpiStoreState.fetchDashboard).toHaveBeenCalled()
      expect(c.historicalData.value).toEqual([{ date: '2026-05-07' }])
      expect(c.loading.value).toBe(false)
    })

    it('clears loading even when fetchOEE throws', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      kpiStoreState.fetchOEE.mockRejectedValueOnce(new Error('boom'))
      const c = useOEEData()
      await c.refreshData()
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })

  describe('onClientChange / onDateChange', () => {
    it('onClientChange updates store and refreshes data', async () => {
      const c = useOEEData()
      c.selectedClient.value = 'ACME-MFG'
      c.onClientChange()
      await flushPromises()
      expect(kpiStoreState.setClient).toHaveBeenCalledWith('ACME-MFG')
      expect(kpiStoreState.fetchOEE).toHaveBeenCalled()
    })

    it('onDateChange updates store with current dates and refreshes data', async () => {
      const c = useOEEData()
      c.startDate.value = '2026-01-01'
      c.endDate.value = '2026-02-01'
      c.onDateChange()
      await flushPromises()
      expect(kpiStoreState.setDateRange).toHaveBeenCalledWith('2026-01-01', '2026-02-01')
      expect(kpiStoreState.fetchOEE).toHaveBeenCalled()
    })
  })

  describe('initialize', () => {
    it('loads clients, sets date range on store, and refreshes', async () => {
      mockApi.getClients.mockResolvedValueOnce({ data: [{ client_id: 'C1' }] })
      const c = useOEEData()
      await c.initialize()
      expect(c.clients.value).toEqual([{ client_id: 'C1' }])
      expect(kpiStoreState.setDateRange).toHaveBeenCalled()
      expect(kpiStoreState.fetchOEE).toHaveBeenCalled()
      expect(c.loading.value).toBe(false)
    })

    it('still clears loading on getClients failure', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockApi.getClients.mockRejectedValueOnce(new Error('500'))
      const c = useOEEData()
      await c.initialize()
      expect(c.clients.value).toEqual([])
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })
})
