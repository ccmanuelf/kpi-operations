/**
 * Unit tests for Predictions API Service
 * Phase 8: Increase test coverage
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock axios
vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({
      get: vi.fn(),
      post: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() }
      }
    }))
  }
}))

import * as predictionsApi from '../api/predictions'
import api from '../api/client'

describe('Predictions API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getPrediction', () => {
    it('fetches efficiency prediction', async () => {
      const mockResponse = {
        data: {
          kpi_type: 'efficiency',
          current_value: 85.5,
          predicted_value: 87.2,
          confidence_lower: 84.0,
          confidence_upper: 90.0
        }
      }
      api.get.mockResolvedValueOnce(mockResponse)

      const result = await predictionsApi.getPrediction('efficiency', { client_id: 1 })

      expect(api.get).toHaveBeenCalledWith('/predictions/efficiency', { params: { client_id: 1 } })
      expect(result).toEqual(mockResponse)
    })

    it('fetches prediction with custom forecast days', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await predictionsApi.getPrediction('oee', {
        client_id: 1,
        forecast_days: 14,
        historical_days: 30
      })

      expect(api.get).toHaveBeenCalledWith('/predictions/oee', {
        params: {
          client_id: 1,
          forecast_days: 14,
          historical_days: 30
        }
      })
    })

    it('fetches prediction with method parameter', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await predictionsApi.getPrediction('ppm', {
        client_id: 1,
        method: 'double'
      })

      expect(api.get).toHaveBeenCalledWith('/predictions/ppm', {
        params: {
          client_id: 1,
          method: 'double'
        }
      })
    })
  })

  describe('getAllPredictions', () => {
    it('fetches all KPI predictions', async () => {
      const mockDashboard = {
        data: {
          efficiency: { predicted: 87.2 },
          performance: { predicted: 90.1 },
          availability: { predicted: 95.0 }
        }
      }
      api.get.mockResolvedValueOnce(mockDashboard)

      const result = await predictionsApi.getAllPredictions({ client_id: 1 })

      expect(api.get).toHaveBeenCalledWith('/predictions/dashboard/all', { params: { client_id: 1 } })
      expect(result).toEqual(mockDashboard)
    })

    it('fetches with forecast days parameter', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await predictionsApi.getAllPredictions({
        client_id: 1,
        forecast_days: 7
      })

      expect(api.get).toHaveBeenCalledWith('/predictions/dashboard/all', {
        params: {
          client_id: 1,
          forecast_days: 7
        }
      })
    })
  })

  describe('getPredictionBenchmarks', () => {
    it('fetches benchmarks for all KPIs', async () => {
      const mockBenchmarks = {
        data: {
          efficiency: { good: 85, excellent: 95 },
          ppm: { good: 1000, excellent: 500 }
        }
      }
      api.get.mockResolvedValueOnce(mockBenchmarks)

      const result = await predictionsApi.getPredictionBenchmarks()

      expect(api.get).toHaveBeenCalledWith('/predictions/benchmarks')
      expect(result).toEqual(mockBenchmarks)
    })
  })

  describe('getKPIHealth', () => {
    it('fetches health assessment for specific KPI', async () => {
      const mockHealth = {
        data: {
          status: 'healthy',
          trend: 'improving',
          confidence: 0.85
        }
      }
      api.get.mockResolvedValueOnce(mockHealth)

      const result = await predictionsApi.getKPIHealth('efficiency', { client_id: 1 })

      expect(api.get).toHaveBeenCalledWith('/predictions/health/efficiency', { params: { client_id: 1 } })
      expect(result).toEqual(mockHealth)
    })

    it('fetches health for different KPI types', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await predictionsApi.getKPIHealth('otd', { client_id: 2 })

      expect(api.get).toHaveBeenCalledWith('/predictions/health/otd', { params: { client_id: 2 } })
    })
  })
})
