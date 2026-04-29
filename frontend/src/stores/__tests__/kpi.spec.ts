/**
 * Unit tests for KPI Store (kpi.js)
 * Tests KPI metrics fetching, predictions, and data management
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useKPIStore } from '../kpi'

// Mock the API module
vi.mock('@/services/api', () => ({
  default: {
    getKPIDashboard: vi.fn(),
    getEfficiency: vi.fn(),
    getEfficiencyTrend: vi.fn(),
    getWIPAging: vi.fn(),
    getWIPAgingTrend: vi.fn(),
    getOnTimeDelivery: vi.fn(),
    getOnTimeDeliveryTrend: vi.fn(),
    getAvailability: vi.fn(),
    getAvailabilityTrend: vi.fn(),
    getPerformance: vi.fn(),
    getPerformanceTrend: vi.fn(),
    getQuality: vi.fn(),
    getQualityTrend: vi.fn(),
    getOEE: vi.fn(),
    getOEETrend: vi.fn(),
    getAbsenteeism: vi.fn(),
    getAbsenteeismTrend: vi.fn(),
    getDefectRates: vi.fn(),
    getThroughputTime: vi.fn(),
    getPrediction: vi.fn(),
    getAllPredictions: vi.fn(),
    getPredictionBenchmarks: vi.fn(),
    getKPIHealth: vi.fn()
  }
}))

import api from '@/services/api'

describe('KPI Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('initializes with null KPI values', () => {
      const store = useKPIStore()

      expect(store.efficiency).toBeNull()
      expect(store.wipAging).toBeNull()
      expect(store.onTimeDelivery).toBeNull()
      expect(store.availability).toBeNull()
      expect(store.performance).toBeNull()
      expect(store.quality).toBeNull()
      expect(store.oee).toBeNull()
      expect(store.absenteeism).toBeNull()
    })

    it('initializes with default date range of 30 days', () => {
      const store = useKPIStore()

      expect(store.dateRange.start).toBeDefined()
      expect(store.dateRange.end).toBeDefined()
    })

    it('initializes with empty trends', () => {
      const store = useKPIStore()

      expect(store.trends.efficiency).toEqual([])
      expect(store.trends.performance).toEqual([])
    })

    it('initializes with empty predictions', () => {
      const store = useKPIStore()

      expect(store.predictions.efficiency).toBeNull()
      expect(store.predictions.performance).toBeNull()
    })
  })

  describe('Getters - kpiStatus', () => {
    it('returns gray when value is null', () => {
      const store = useKPIStore()

      expect(store.kpiStatus(null, 100, true)).toBe('gray')
    })

    it('returns gray when target is null', () => {
      const store = useKPIStore()

      expect(store.kpiStatus(50, null, true)).toBe('gray')
    })

    it('returns success for high values when higher is better', () => {
      const store = useKPIStore()

      expect(store.kpiStatus(95, 100, true)).toBe('success')
      expect(store.kpiStatus(100, 100, true)).toBe('success')
    })

    it('returns warning for medium values when higher is better', () => {
      const store = useKPIStore()

      expect(store.kpiStatus(85, 100, true)).toBe('warning')
      expect(store.kpiStatus(80, 100, true)).toBe('warning')
    })

    it('returns error for low values when higher is better', () => {
      const store = useKPIStore()

      expect(store.kpiStatus(70, 100, true)).toBe('error')
    })

    it('returns success for low values when lower is better', () => {
      const store = useKPIStore()

      expect(store.kpiStatus(4, 100, false)).toBe('success')
    })

    it('returns warning for medium values when lower is better', () => {
      const store = useKPIStore()

      expect(store.kpiStatus(15, 100, false)).toBe('warning')
    })

    it('returns error for high values when lower is better', () => {
      const store = useKPIStore()

      expect(store.kpiStatus(30, 100, false)).toBe('error')
    })
  })

  describe('Getters - kpiIcon', () => {
    it('returns minus-circle when value is null', () => {
      const store = useKPIStore()

      expect(store.kpiIcon(null, 100, true)).toBe('mdi-minus-circle')
    })

    it('returns check-circle for good status', () => {
      const store = useKPIStore()

      expect(store.kpiIcon(95, 100, true)).toBe('mdi-check-circle')
    })

    it('returns alert-circle for warning status', () => {
      const store = useKPIStore()

      expect(store.kpiIcon(85, 100, true)).toBe('mdi-alert-circle')
    })

    it('returns close-circle for error status', () => {
      const store = useKPIStore()

      expect(store.kpiIcon(70, 100, true)).toBe('mdi-close-circle')
    })
  })

  describe('Getters - allKPIs', () => {
    it('returns array of KPI objects', () => {
      const store = useKPIStore()

      const kpis = store.allKPIs
      expect(Array.isArray(kpis)).toBe(true)
      expect(kpis.length).toBeGreaterThan(0)
    })

    it('includes efficiency KPI with correct structure', () => {
      const store = useKPIStore()
      store.efficiency = { current: 85, target: 85 }

      const kpis = store.allKPIs
      const efficiency = kpis.find(k => k.key === 'efficiency')

      expect(efficiency).toBeDefined()
      expect(efficiency.title).toBe('Efficiency')
      expect(efficiency.value).toBe(85)
      expect(efficiency.unit).toBe('%')
      expect(efficiency.higherBetter).toBe(true)
    })

    it('includes absenteeism with higherBetter false', () => {
      const store = useKPIStore()

      const kpis = store.allKPIs
      const absenteeism = kpis.find(k => k.key === 'absenteeism')

      expect(absenteeism.higherBetter).toBe(false)
    })
  })

  describe('Actions - setClient and setDateRange', () => {
    it('sets selected client', () => {
      const store = useKPIStore()

      store.setClient(1)

      expect(store.selectedClient).toBe(1)
    })

    it('sets date range', () => {
      const store = useKPIStore()

      store.setDateRange('2024-01-01', '2024-01-31')

      expect(store.dateRange.start).toBe('2024-01-01')
      expect(store.dateRange.end).toBe('2024-01-31')
    })
  })

  describe('Actions - fetchDashboard', () => {
    it('fetches dashboard data successfully', async () => {
      const mockData = { kpis: [{ name: 'Efficiency', value: 85 }] }
      api.getKPIDashboard.mockResolvedValue({ data: mockData })

      const store = useKPIStore()
      const result = await store.fetchDashboard()

      expect(result).toEqual(mockData)
      expect(store.dashboard).toEqual(mockData)
      expect(store.loading).toBe(false)
    })

    it('handles dashboard fetch error', async () => {
      api.getKPIDashboard.mockRejectedValue({
        response: { data: { detail: 'Server error' } }
      })
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const store = useKPIStore()
      const result = await store.fetchDashboard()

      expect(result).toBeNull()
      expect(store.error).toBe('Server error')
      consoleSpy.mockRestore()
    })
  })

  describe('Actions - fetchEfficiency', () => {
    it('fetches efficiency data and trend', async () => {
      const mockData = { current: 85, target: 85 }
      const mockTrend = [{ date: '2024-01-01', value: 84 }]
      api.getEfficiency.mockResolvedValue({ data: mockData })
      api.getEfficiencyTrend.mockResolvedValue({ data: mockTrend })

      const store = useKPIStore()
      const result = await store.fetchEfficiency()

      expect(result).toEqual(mockData)
      expect(store.efficiency).toEqual(mockData)
      expect(store.trends.efficiency).toEqual(mockTrend)
    })
  })

  describe('Actions - fetchWIPAging', () => {
    it('fetches WIP aging data', async () => {
      const mockData = { average_days: 5 }
      api.getWIPAging.mockResolvedValue({ data: mockData })
      api.getWIPAgingTrend.mockResolvedValue({ data: [] })

      const store = useKPIStore()
      const result = await store.fetchWIPAging()

      expect(result).toEqual(mockData)
      expect(store.wipAging).toEqual(mockData)
    })
  })

  describe('Actions - Predictions', () => {
    it('fetches prediction for specific KPI', async () => {
      const mockPrediction = {
        predictions: [{ date: '2024-02-01', predicted_value: 87 }]
      }
      api.getPrediction.mockResolvedValue({ data: mockPrediction })

      const store = useKPIStore()
      const result = await store.fetchPrediction('efficiency', 7, 30, 'auto')

      expect(result).toEqual(mockPrediction)
      expect(store.predictions.efficiency).toEqual(mockPrediction)
    })

    it('fetches all predictions at once', async () => {
      const mockData = {
        efficiency: { predictions: [] },
        performance: { predictions: [] }
      }
      api.getAllPredictions.mockResolvedValue({ data: mockData })

      const store = useKPIStore()
      const result = await store.fetchAllPredictions()

      expect(result).toEqual(mockData)
      expect(store.allPredictions).toEqual(mockData)
    })

    it('fetches benchmarks', async () => {
      const mockBenchmarks = { efficiency: { industry_avg: 80 } }
      api.getPredictionBenchmarks.mockResolvedValue({ data: mockBenchmarks })

      const store = useKPIStore()
      const result = await store.fetchBenchmarks()

      expect(result).toEqual(mockBenchmarks)
      expect(store.benchmarks).toEqual(mockBenchmarks)
    })

    it('fetches KPI health', async () => {
      const mockHealth = { status: 'good', score: 85 }
      api.getKPIHealth.mockResolvedValue({ data: mockHealth })

      const store = useKPIStore()
      const result = await store.fetchKPIHealth('efficiency')

      expect(result).toEqual(mockHealth)
    })
  })

  describe('getForecastChartData', () => {
    it('returns null when prediction is null', () => {
      const store = useKPIStore()

      expect(store.getForecastChartData(null)).toBeNull()
    })

    it('returns null when predictions array is missing', () => {
      const store = useKPIStore()

      expect(store.getForecastChartData({ other: 'data' })).toBeNull()
    })

    it('generates chart data from predictions', () => {
      const store = useKPIStore()
      const prediction = {
        predictions: [
          { date: '2024-02-01', predicted_value: 85, lower_bound: 80, upper_bound: 90 },
          { date: '2024-02-02', predicted_value: 86, lower_bound: 81, upper_bound: 91 }
        ]
      }

      const chartData = store.getForecastChartData(prediction)

      expect(chartData.labels).toHaveLength(2)
      expect(chartData.datasets).toHaveLength(3)
      expect(chartData.datasets[0].label).toBe('Forecast')
      expect(chartData.datasets[0].data).toEqual([85, 86])
    })

    it('uses custom color for chart', () => {
      const store = useKPIStore()
      const prediction = {
        predictions: [
          { date: '2024-02-01', predicted_value: 85, lower_bound: 80, upper_bound: 90 }
        ]
      }

      const chartData = store.getForecastChartData(prediction, '#ff0000')

      expect(chartData.datasets[0].borderColor).toBe('#ff0000')
    })
  })

  describe('Loading State', () => {
    it('sets loading to true during fetch and false after', async () => {
      let resolvePromise
      api.getKPIDashboard.mockImplementation(() =>
        new Promise(resolve => {
          resolvePromise = () => resolve({ data: {} })
        })
      )

      const store = useKPIStore()
      const fetchPromise = store.fetchDashboard()

      expect(store.loading).toBe(true)

      resolvePromise()
      await fetchPromise

      expect(store.loading).toBe(false)
    })
  })

  describe('_buildParams', () => {
    it('builds params with date range', () => {
      const store = useKPIStore()
      store.dateRange = { start: '2024-01-01', end: '2024-01-31' }

      const params = store._buildParams()

      expect(params.start_date).toBe('2024-01-01')
      expect(params.end_date).toBe('2024-01-31')
    })

    it('includes client_id when selected', () => {
      const store = useKPIStore()
      store.selectedClient = 1

      const params = store._buildParams()

      expect(params.client_id).toBe(1)
    })

    it('excludes client_id when not selected', () => {
      const store = useKPIStore()
      store.selectedClient = null

      const params = store._buildParams()

      expect(params.client_id).toBeUndefined()
    })
  })
})
