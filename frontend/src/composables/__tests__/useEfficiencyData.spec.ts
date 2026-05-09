/**
 * Unit tests for useEfficiencyData composable.
 *
 * Covers the Efficiency KPI detail page's logic surface — the view itself
 * (`views/kpi/Efficiency.vue`) is a thin presentation layer; testing this
 * composable lifts both files from 0% line coverage. Asserts:
 *   - reactive state defaults
 *   - threshold-based color tokens (statusColor, getEfficiencyColor,
 *     getPerformanceColor, getHealthColor, getTrendColor, getTrendIcon)
 *   - formatters (formatValue, formatDate)
 *   - i18n-resolved table headers (shiftHeaders, productHeaders, historyHeaders)
 *   - async actions (loadClients via initialize, fetchPrediction success +
 *     error paths, refreshData success + error, onClientChange/onDateChange
 *     side effects, onForecastToggle on/off)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

const { mockApi, kpiStoreState } = vi.hoisted(() => ({
  mockApi: {
    getClients: vi.fn(),
    getPrediction: vi.fn(),
  },
  kpiStoreState: {
    efficiency: null as Record<string, unknown> | null,
    dashboard: [] as unknown[],
    fetchEfficiency: vi.fn(),
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

import useEfficiencyData from '../useEfficiencyData'

describe('useEfficiencyData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockApi.getClients.mockReset().mockResolvedValue({ data: [] })
    mockApi.getPrediction.mockReset().mockResolvedValue({ data: null })
    kpiStoreState.efficiency = null
    kpiStoreState.dashboard = []
    kpiStoreState.fetchEfficiency.mockReset().mockResolvedValue(undefined)
    kpiStoreState.fetchDashboard.mockReset().mockResolvedValue(undefined)
    kpiStoreState.setClient.mockReset()
    kpiStoreState.setDateRange.mockReset()
  })

  describe('initial state', () => {
    it('has loading=false, showForecast=true, forecastDays=7', () => {
      const c = useEfficiencyData()
      expect(c.loading.value).toBe(false)
      expect(c.showForecast.value).toBe(true)
      expect(c.forecastDays.value).toBe(7)
    })

    it('initializes startDate to 30 days ago and endDate to today', () => {
      const c = useEfficiencyData()
      // YYYY-MM-DD format
      expect(c.startDate.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(c.endDate.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      const start = new Date(c.startDate.value)
      const end = new Date(c.endDate.value)
      const days = Math.round((end.getTime() - start.getTime()) / 86_400_000)
      expect(days).toBe(30)
    })

    it('clients/historicalData/predictionData/selectedClient/tableSearch start empty', () => {
      const c = useEfficiencyData()
      expect(c.clients.value).toEqual([])
      expect(c.historicalData.value).toEqual([])
      expect(c.predictionData.value).toBeNull()
      expect(c.selectedClient.value).toBeNull()
      expect(c.tableSearch.value).toBe('')
    })
  })

  describe('threshold colors', () => {
    it.each([
      [90, 'success'],
      [85, 'success'],
      [80, 'amber-darken-3'],
      [70, 'amber-darken-3'],
      [50, 'error'],
      [0, 'error'],
    ])('getEfficiencyColor(%d) returns %s', (val, expected) => {
      const c = useEfficiencyData()
      expect(c.getEfficiencyColor(val)).toBe(expected)
    })

    it.each([
      [99, 'success'],
      [95, 'success'],
      [90, 'amber-darken-3'],
      [80, 'amber-darken-3'],
      [50, 'error'],
    ])('getPerformanceColor(%d) returns %s', (val, expected) => {
      const c = useEfficiencyData()
      expect(c.getPerformanceColor(val)).toBe(expected)
    })

    it.each([
      [90, 'success'],
      [80, 'success'],
      [70, 'warning'],
      [60, 'warning'],
      [40, 'error'],
    ])('getHealthColor(%d) returns %s', (val, expected) => {
      const c = useEfficiencyData()
      expect(c.getHealthColor(val)).toBe(expected)
    })

    it.each([
      ['improving', 'success'],
      ['declining', 'error'],
      ['stable', 'grey'],
      ['unknown', 'grey'],
    ])('getTrendColor(%s) returns %s', (trend, expected) => {
      const c = useEfficiencyData()
      expect(c.getTrendColor(trend)).toBe(expected)
    })

    it.each([
      ['improving', 'mdi-trending-up'],
      ['declining', 'mdi-trending-down'],
      ['stable', 'mdi-minus'],
      ['unknown', 'mdi-minus'],
    ])('getTrendIcon(%s) returns %s', (trend, expected) => {
      const c = useEfficiencyData()
      expect(c.getTrendIcon(trend)).toBe(expected)
    })
  })

  describe('statusColor (computed) reflects efficiency value', () => {
    it.each([
      [90, 'success'],
      [80, 'amber-darken-3'],
      [50, 'error'],
    ])('current=%d → %s', (current, expected) => {
      kpiStoreState.efficiency = { current }
      const c = useEfficiencyData()
      expect(c.statusColor.value).toBe(expected)
    })

    it('null efficiency → error (treats as 0)', () => {
      kpiStoreState.efficiency = null
      const c = useEfficiencyData()
      expect(c.statusColor.value).toBe('error')
    })
  })

  describe('gapColor reflects sign of gap', () => {
    it('positive gap → text-success', () => {
      kpiStoreState.efficiency = { current: 90, gap: 5 }
      const c = useEfficiencyData()
      expect(c.gapColor.value).toBe('text-success')
    })

    it('negative gap → text-error', () => {
      kpiStoreState.efficiency = { current: 80, gap: -5 }
      const c = useEfficiencyData()
      expect(c.gapColor.value).toBe('text-error')
    })

    it('zero gap → text-success (>=0 branch)', () => {
      kpiStoreState.efficiency = { current: 85, gap: 0 }
      const c = useEfficiencyData()
      expect(c.gapColor.value).toBe('text-success')
    })
  })

  describe('formatters', () => {
    it('formatValue returns 1-decimal string for finite numbers', () => {
      const c = useEfficiencyData()
      expect(c.formatValue(85)).toBe('85.0')
      expect(c.formatValue(85.456)).toBe('85.5')
    })

    it('formatValue returns the i18n n/a key when value is null/undefined', () => {
      const c = useEfficiencyData()
      expect(c.formatValue(null)).toBe('common.na')
      expect(c.formatValue(undefined)).toBe('common.na')
    })

    it('formatDate formats valid date strings (MMM dd, yyyy)', () => {
      const c = useEfficiencyData()
      // Use ISO with offset to avoid local-tz parsing ambiguity
      const out = c.formatDate('2026-05-07T12:00:00')
      expect(out).toBe('May 07, 2026')
    })

    it('formatDate returns the input when parsing fails', () => {
      const c = useEfficiencyData()
      expect(c.formatDate('not-a-date')).toBe('not-a-date')
    })
  })

  describe('table headers (i18n-resolved)', () => {
    it('shiftHeaders has 4 columns (shift, output, expected, efficiency)', () => {
      const c = useEfficiencyData()
      const keys = c.shiftHeaders.value.map((h) => h.key)
      expect(keys).toEqual(['shift_name', 'actual_output', 'expected_output', 'efficiency'])
      // titles come from i18n stub which echoes keys
      expect(c.shiftHeaders.value[0].title).toBe('kpi.headers.shift')
    })

    it('productHeaders has 3 columns', () => {
      const c = useEfficiencyData()
      expect(c.productHeaders.value.map((h) => h.key)).toEqual([
        'product_name',
        'actual_output',
        'efficiency',
      ])
    })

    it('historyHeaders has 5 columns', () => {
      const c = useEfficiencyData()
      expect(c.historyHeaders.value.map((h) => h.key)).toEqual([
        'date',
        'total_units',
        'avg_efficiency',
        'avg_performance',
        'entry_count',
      ])
    })
  })

  describe('fetchPrediction', () => {
    it('skips fetch and clears predictionData when forecast is off', async () => {
      const c = useEfficiencyData()
      c.showForecast.value = false
      c.predictionData.value = { stale: true }
      await c.fetchPrediction()
      expect(mockApi.getPrediction).not.toHaveBeenCalled()
      expect(c.predictionData.value).toBeNull()
    })

    it('calls api.getPrediction with forecast_days/historical_days/method=auto', async () => {
      mockApi.getPrediction.mockResolvedValueOnce({ data: { health_assessment: { score: 80 } } })
      const c = useEfficiencyData()
      c.showForecast.value = true
      c.forecastDays.value = 14
      await c.fetchPrediction()
      expect(mockApi.getPrediction).toHaveBeenCalledWith('efficiency', {
        forecast_days: 14,
        historical_days: 30,
        method: 'auto',
      })
      expect(c.predictionData.value).toEqual({ health_assessment: { score: 80 } })
    })

    it('threads selectedClient into params when set', async () => {
      const c = useEfficiencyData()
      c.selectedClient.value = 'ACME-MFG'
      await c.fetchPrediction()
      expect(mockApi.getPrediction).toHaveBeenCalledWith(
        'efficiency',
        expect.objectContaining({ client_id: 'ACME-MFG' }),
      )
    })

    it('on api error, predictionData is set to null and the error is swallowed', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockApi.getPrediction.mockRejectedValueOnce(new Error('500'))
      const c = useEfficiencyData()
      c.predictionData.value = { stale: true }
      await c.fetchPrediction()
      expect(c.predictionData.value).toBeNull()
      consoleSpy.mockRestore()
    })
  })

  describe('onForecastToggle', () => {
    it('when showForecast=true after toggle, it triggers fetchPrediction', () => {
      const c = useEfficiencyData()
      c.showForecast.value = true
      c.onForecastToggle()
      expect(mockApi.getPrediction).toHaveBeenCalled()
    })

    it('when showForecast=false after toggle, predictionData is cleared without fetching', () => {
      const c = useEfficiencyData()
      c.showForecast.value = false
      c.predictionData.value = { stale: true }
      c.onForecastToggle()
      expect(mockApi.getPrediction).not.toHaveBeenCalled()
      expect(c.predictionData.value).toBeNull()
    })
  })

  describe('refreshData', () => {
    it('calls store.fetchEfficiency + store.fetchDashboard and toggles loading', async () => {
      kpiStoreState.dashboard = [{ date: '2026-05-07', avg_efficiency: 88 }]
      const c = useEfficiencyData()
      const promise = c.refreshData()
      expect(c.loading.value).toBe(true)
      await promise
      expect(kpiStoreState.fetchEfficiency).toHaveBeenCalled()
      expect(kpiStoreState.fetchDashboard).toHaveBeenCalled()
      expect(c.historicalData.value).toEqual([{ date: '2026-05-07', avg_efficiency: 88 }])
      expect(c.loading.value).toBe(false)
    })

    it('also fetches prediction when showForecast is on', async () => {
      const c = useEfficiencyData()
      c.showForecast.value = true
      await c.refreshData()
      expect(mockApi.getPrediction).toHaveBeenCalled()
    })

    it('does not fetch prediction when showForecast is off', async () => {
      const c = useEfficiencyData()
      c.showForecast.value = false
      await c.refreshData()
      expect(mockApi.getPrediction).not.toHaveBeenCalled()
    })

    it('clears loading even when fetch throws', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      kpiStoreState.fetchEfficiency.mockRejectedValueOnce(new Error('boom'))
      const c = useEfficiencyData()
      await c.refreshData()
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })

  describe('onClientChange / onDateChange', () => {
    it('onClientChange updates store and refreshes data', async () => {
      const c = useEfficiencyData()
      c.selectedClient.value = 'ACME-MFG'
      c.onClientChange()
      await flushPromises()
      expect(kpiStoreState.setClient).toHaveBeenCalledWith('ACME-MFG')
      expect(kpiStoreState.fetchEfficiency).toHaveBeenCalled()
    })

    it('onDateChange updates store with current dates and refreshes data', async () => {
      const c = useEfficiencyData()
      c.startDate.value = '2026-01-01'
      c.endDate.value = '2026-02-01'
      c.onDateChange()
      await flushPromises()
      expect(kpiStoreState.setDateRange).toHaveBeenCalledWith('2026-01-01', '2026-02-01')
      expect(kpiStoreState.fetchEfficiency).toHaveBeenCalled()
    })
  })

  describe('initialize', () => {
    it('loads clients, sets date range on store, and refreshes', async () => {
      mockApi.getClients.mockResolvedValueOnce({ data: [{ client_id: 'C1' }] })
      const c = useEfficiencyData()
      await c.initialize()
      expect(c.clients.value).toEqual([{ client_id: 'C1' }])
      expect(kpiStoreState.setDateRange).toHaveBeenCalled()
      expect(kpiStoreState.fetchEfficiency).toHaveBeenCalled()
      expect(c.loading.value).toBe(false)
    })

    it('still clears loading on getClients failure', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockApi.getClients.mockRejectedValueOnce(new Error('500'))
      const c = useEfficiencyData()
      await c.initialize()
      expect(c.clients.value).toEqual([])
      expect(c.loading.value).toBe(false)
      consoleSpy.mockRestore()
    })
  })
})
