/**
 * Unit tests for KPI API module
 * Tests all KPI data fetching functions with complex aggregations
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the client module
vi.mock('../api/client', () => ({
  default: {
    get: vi.fn()
  }
}))

import api from '../api/client'
import * as kpiApi from '../api/kpi'

describe('KPI API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('calculateKPIs', () => {
    it('calls GET /kpi/calculate/:id', async () => {
      api.get.mockResolvedValue({ data: { efficiency: 85 } })

      const result = await kpiApi.calculateKPIs(123)

      expect(api.get).toHaveBeenCalledWith('/kpi/calculate/123')
      expect(result.data.efficiency).toBe(85)
    })
  })

  describe('getKPIDashboard', () => {
    it('calls GET /kpi/dashboard with params', async () => {
      const params = { client_id: 1 }
      api.get.mockResolvedValue({ data: [] })

      const result = await kpiApi.getKPIDashboard(params)

      expect(api.get).toHaveBeenCalledWith('/kpi/dashboard', { params })
      expect(result.data).toEqual([])
    })
  })

  describe('getEfficiency', () => {
    it('calculates efficiency from dashboard and shift data', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/kpi/dashboard') {
          return Promise.resolve({ data: [{ avg_efficiency: 80 }, { avg_efficiency: 90 }] })
        }
        if (url === '/kpi/efficiency/by-shift') {
          return Promise.resolve({ data: [
            { actual_output: 100, expected_output: 120 },
            { actual_output: 150, expected_output: 160 }
          ]})
        }
        if (url === '/kpi/efficiency/by-product') {
          return Promise.resolve({ data: [{ product: 'A', efficiency: 85 }] })
        }
        return Promise.resolve({ data: [] })
      })

      const result = await kpiApi.getEfficiency({ client_id: 1 })

      expect(result.data.current).toBe(85) // (80 + 90) / 2
      expect(result.data.target).toBe(85)
      expect(result.data.actual_output).toBe(250)
      expect(result.data.expected_output).toBe(280)
      expect(result.data.gap).toBe(30)
    })

    it('returns default values on error', async () => {
      api.get.mockRejectedValue(new Error('Network error'))

      const result = await kpiApi.getEfficiency({})

      expect(result.data.current).toBeNull()
      expect(result.data.gap).toBe(0)
    })
  })

  describe('getWIPAging', () => {
    it('fetches and aggregates WIP aging data', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/kpi/wip-aging') {
          return Promise.resolve({ data: {
            average_aging_days: 5.5,
            total_held_quantity: 100,
            aging_0_7_days: 50,
            aging_8_14_days: 30,
            aging_15_30_days: 15,
            aging_over_30_days: 5
          }})
        }
        if (url === '/kpi/wip-aging/top') {
          return Promise.resolve({ data: [{ age: 45 }, { age: 30 }] })
        }
        return Promise.resolve({ data: {} })
      })

      const result = await kpiApi.getWIPAging({})

      expect(result.data.average_days).toBe(5.5)
      expect(result.data.total_held).toBe(100)
      expect(result.data.aging_0_7).toBe(50)
      expect(result.data.aging_15_30).toBe(15)
      expect(result.data.critical_count).toBe(20)
      expect(result.data.max_days).toBe(45)
    })

    it('returns defaults on error', async () => {
      api.get.mockRejectedValue(new Error('Error'))

      const result = await kpiApi.getWIPAging({})

      expect(result.data.average_days).toBe(0)
      expect(result.data.total_held).toBe(0)
    })
  })

  describe('getOnTimeDelivery', () => {
    it('fetches OTD data with breakdowns', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/kpi/otd') {
          return Promise.resolve({ data: {
            otd_percentage: 92.5,
            on_time_count: 185,
            total_orders: 200
          }})
        }
        if (url === '/kpi/otd/by-client') {
          return Promise.resolve({ data: [{ client: 'A', otd: 95 }] })
        }
        if (url === '/kpi/otd/late-deliveries') {
          return Promise.resolve({ data: [{ order_id: 1 }] })
        }
        return Promise.resolve({ data: {} })
      })

      const result = await kpiApi.getOnTimeDelivery({})

      expect(result.data.percentage).toBe(92.5)
      expect(result.data.on_time_count).toBe(185)
      expect(result.data.total_orders).toBe(200)
      expect(result.data.by_client).toHaveLength(1)
    })

    it('returns defaults on error', async () => {
      api.get.mockRejectedValue(new Error('Error'))

      const result = await kpiApi.getOnTimeDelivery({})

      expect(result.data.percentage).toBe(0)
    })
  })

  describe('getAvailability', () => {
    it('calculates availability from production and downtime data', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/production') {
          return Promise.resolve({ data: [
            { run_time_hours: 8 },
            { run_time_hours: 8 }
          ]})
        }
        if (url === '/downtime') {
          return Promise.resolve({ data: [
            { downtime_duration_minutes: 60, downtime_reason: 'Maintenance', machine_id: 'M1' },
            { downtime_duration_minutes: 30, downtime_reason: 'Breakdown', machine_id: 'M2' }
          ]})
        }
        return Promise.resolve({ data: [] })
      })

      const result = await kpiApi.getAvailability({})

      expect(result.data.total_time).toBe(16)
      expect(result.data.downtime).toBe(1.5) // 90 minutes = 1.5 hours
      expect(result.data.uptime).toBe(14.5)
      expect(result.data.percentage).toBeCloseTo(90.625, 1)
      expect(result.data.downtime_reasons).toHaveLength(2)
    })

    it('returns defaults on error', async () => {
      // When API fails completely, catch block returns null percentage
      api.get.mockImplementation(() => {
        throw new Error('Network error')
      })

      const result = await kpiApi.getAvailability({})

      // The implementation catches errors and returns default object
      expect(result.data).toBeDefined()
      expect(result.data.downtime_reasons).toEqual([])
    })
  })

  describe('getPerformance', () => {
    it('calculates performance metrics', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/kpi/dashboard') {
          return Promise.resolve({ data: [
            { avg_performance: 90 },
            { avg_performance: 95 }
          ]})
        }
        if (url === '/production') {
          return Promise.resolve({ data: [
            { units_produced: 100, run_time_hours: 2, ideal_cycle_time_minutes: 1 }
          ]})
        }
        if (url === '/kpi/performance/by-shift') {
          return Promise.resolve({ data: [] })
        }
        if (url === '/kpi/performance/by-product') {
          return Promise.resolve({ data: [] })
        }
        return Promise.resolve({ data: [] })
      })

      const result = await kpiApi.getPerformance({})

      expect(result.data.percentage).toBe(92.5) // (90 + 95) / 2
      expect(result.data.target).toBe(95)
      expect(result.data.total_units).toBe(100)
      expect(result.data.production_hours).toBe(2)
    })

    it('returns defaults on error', async () => {
      api.get.mockRejectedValue(new Error('Error'))

      const result = await kpiApi.getPerformance({})

      expect(result.data.percentage).toBeNull()
    })
  })

  describe('getQuality', () => {
    it('fetches quality data with FPY and defects', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/quality/kpi/fpy-rty') {
          return Promise.resolve({ data: {
            fpy_percentage: 98.5,
            rty_percentage: 96.2,
            final_yield_percentage: 97.0,
            total_units: 1000,
            first_pass_good: 985,
            total_scrapped: 15
          }})
        }
        if (url === '/quality/kpi/defects-by-type') {
          return Promise.resolve({ data: [{ type: 'Scratch', count: 10 }] })
        }
        if (url === '/quality/kpi/by-product') {
          return Promise.resolve({ data: [] })
        }
        return Promise.resolve({ data: {} })
      })

      const result = await kpiApi.getQuality({})

      expect(result.data.fpy).toBe(98.5)
      expect(result.data.rty).toBe(96.2)
      expect(result.data.total_units).toBe(1000)
      expect(result.data.defects_by_type).toHaveLength(1)
    })

    it('returns defaults on error', async () => {
      api.get.mockRejectedValue(new Error('Error'))

      const result = await kpiApi.getQuality({})

      expect(result.data.fpy).toBe(0)
    })
  })

  describe('getOEE', () => {
    it('calculates OEE from availability, performance, quality', async () => {
      api.get.mockImplementation((url) => {
        if (url === '/kpi/dashboard') {
          return Promise.resolve({ data: [
            { avg_efficiency: 90, avg_performance: 95 }
          ]})
        }
        if (url === '/quality/kpi/fpy-rty') {
          return Promise.resolve({ data: { fpy_percentage: 98 } })
        }
        if (url === '/production') {
          return Promise.resolve({ data: [{ run_time_hours: 8 }] })
        }
        if (url === '/downtime') {
          return Promise.resolve({ data: [] })
        }
        return Promise.resolve({ data: {} })
      })

      const result = await kpiApi.getOEE({})

      expect(result.data.percentage).toBeDefined()
    })

    it('returns null percentage on error', async () => {
      api.get.mockRejectedValue(new Error('Error'))

      const result = await kpiApi.getOEE({})

      expect(result.data.percentage).toBeNull()
    })
  })

  describe('getAbsenteeism', () => {
    it('fetches absenteeism data', async () => {
      api.get.mockResolvedValue({ data: {
        absenteeism_rate: 3.5,
        total_scheduled_hours: 1000,
        total_hours_absent: 35,
        total_employees: 50,
        total_absences: 10,
        by_reason: [{ reason: 'Sick', count: 5 }]
      }})

      const result = await kpiApi.getAbsenteeism({})

      expect(result.data.rate).toBe(3.5)
      expect(result.data.total_employees).toBe(50)
      expect(result.data.by_reason).toHaveLength(1)
    })

    it('returns defaults on error', async () => {
      api.get.mockRejectedValue(new Error('Error'))

      const result = await kpiApi.getAbsenteeism({})

      expect(result.data.rate).toBe(0)
    })
  })

  describe('getDefectRates', () => {
    it('fetches PPM and defect rate', async () => {
      api.get.mockResolvedValue({ data: {
        ppm: 500,
        defect_rate_percentage: 0.05
      }})

      const result = await kpiApi.getDefectRates({})

      expect(result.data.ppm).toBe(500)
      expect(result.data.defect_rate_percentage).toBe(0.05)
    })

    it('returns null on error', async () => {
      api.get.mockRejectedValue(new Error('Error'))

      const result = await kpiApi.getDefectRates({})

      expect(result.data.ppm).toBeNull()
    })
  })

  describe('getThroughputTime', () => {
    it('calculates throughput time from production entries', async () => {
      api.get.mockResolvedValue({ data: [
        { run_time_hours: 8, units_produced: 100 },
        { run_time_hours: 8, units_produced: 100 }
      ]})

      const result = await kpiApi.getThroughputTime({})

      expect(result.data.average_hours).toBeDefined()
    })

    it('returns null for empty data', async () => {
      api.get.mockResolvedValue({ data: [] })

      const result = await kpiApi.getThroughputTime({})

      expect(result.data.average_hours).toBeNull()
    })
  })

  describe('Trend Endpoints', () => {
    it('getEfficiencyTrend calls correct endpoint', async () => {
      api.get.mockResolvedValue({ data: [] })

      await kpiApi.getEfficiencyTrend({ days: 30 })

      expect(api.get).toHaveBeenCalledWith('/kpi/efficiency/trend', { params: { days: 30 } })
    })

    it('getWIPAgingTrend calls correct endpoint', async () => {
      api.get.mockResolvedValue({ data: [] })

      await kpiApi.getWIPAgingTrend({})

      expect(api.get).toHaveBeenCalledWith('/kpi/wip-aging/trend', { params: {} })
    })

    it('getOnTimeDeliveryTrend calls correct endpoint', async () => {
      api.get.mockResolvedValue({ data: [] })

      await kpiApi.getOnTimeDeliveryTrend({})

      expect(api.get).toHaveBeenCalledWith('/kpi/on-time-delivery/trend', { params: {} })
    })

    it('getAvailabilityTrend calls correct endpoint', async () => {
      api.get.mockResolvedValue({ data: [] })

      await kpiApi.getAvailabilityTrend({})

      expect(api.get).toHaveBeenCalledWith('/kpi/availability/trend', { params: {} })
    })

    it('getPerformanceTrend calls correct endpoint', async () => {
      api.get.mockResolvedValue({ data: [] })

      await kpiApi.getPerformanceTrend({})

      expect(api.get).toHaveBeenCalledWith('/kpi/performance/trend', { params: {} })
    })

    it('getQualityTrend calls correct endpoint', async () => {
      api.get.mockResolvedValue({ data: [] })

      await kpiApi.getQualityTrend({})

      expect(api.get).toHaveBeenCalledWith('/kpi/quality/trend', { params: {} })
    })

    it('getOEETrend calls correct endpoint', async () => {
      api.get.mockResolvedValue({ data: [] })

      await kpiApi.getOEETrend({})

      expect(api.get).toHaveBeenCalledWith('/kpi/oee/trend', { params: {} })
    })

    it('getAbsenteeismTrend calls correct endpoint', async () => {
      api.get.mockResolvedValue({ data: [] })

      await kpiApi.getAbsenteeismTrend({})

      expect(api.get).toHaveBeenCalledWith('/attendance/kpi/absenteeism/trend', { params: {} })
    })

    it('trend endpoints return empty array on error', async () => {
      api.get.mockRejectedValue(new Error('Not found'))

      const result = await kpiApi.getEfficiencyTrend({})

      expect(result.data).toEqual([])
    })
  })
})
