/**
 * Unit tests for My Shift API Service
 * Phase 8: Increase test coverage
 *
 * Params mirror the real backend contract (backend/routes/my_shift.py):
 * shift_date, shift_id (SHIFT.shift_id FK), operator_id — all optional.
 * (There is no shift_number concept anywhere in the backend.)
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock axios
vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({
      get: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() }
      }
    }))
  }
}))

import * as myShiftApi from '../api/myShift'
import api from '../api/client'

describe('My Shift API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getMyShiftSummary', () => {
    it('fetches complete shift summary', async () => {
      const mockSummary = {
        data: {
          date: '2024-01-15',
          shift_id: 1,
          operator_id: 'OP001',
          stats: {
            units_produced: 500,
            efficiency: 85.5,
            downtime_incidents: 0,
            downtime_minutes: 0,
            quality_checks: 2,
            defect_count: 1
          },
          assigned_work_orders: [],
          recent_activity: [],
          data_completeness: {}
        }
      }
      api.get.mockResolvedValueOnce(mockSummary)

      const params = {
        shift_date: '2024-01-15',
        shift_id: 1,
        operator_id: 'OP001'
      }
      const result = await myShiftApi.getMyShiftSummary(params)

      expect(api.get).toHaveBeenCalledWith('/my-shift/summary', { params })
      expect(result).toEqual(mockSummary)
    })

    it('fetches with only shift_date', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await myShiftApi.getMyShiftSummary({ shift_date: '2024-01-15' })

      expect(api.get).toHaveBeenCalledWith('/my-shift/summary', {
        params: { shift_date: '2024-01-15' }
      })
    })

    it('defaults to an empty params object when called with no args', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await myShiftApi.getMyShiftSummary()

      expect(api.get).toHaveBeenCalledWith('/my-shift/summary', { params: {} })
    })

    it('passes a numeric shift_id through unchanged', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await myShiftApi.getMyShiftSummary({ shift_date: '2024-01-15', shift_id: 3 })

      expect(api.get).toHaveBeenCalledWith('/my-shift/summary', {
        params: expect.objectContaining({ shift_id: 3 })
      })
    })
  })

  describe('getMyShiftStats', () => {
    it('fetches lightweight stats', async () => {
      const mockStats = {
        data: {
          units_produced: 250,
          defect_count: 3,
          downtime_minutes: 15
        }
      }
      api.get.mockResolvedValueOnce(mockStats)

      const params = { shift_date: '2024-01-15' }
      const result = await myShiftApi.getMyShiftStats(params)

      expect(api.get).toHaveBeenCalledWith('/my-shift/stats', { params })
      expect(result).toEqual(mockStats)
    })

    it('fetches stats without any params', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await myShiftApi.getMyShiftStats()

      expect(api.get).toHaveBeenCalledWith('/my-shift/stats', { params: {} })
    })
  })

  describe('getMyShiftActivity', () => {
    it('fetches recent activity entries', async () => {
      const mockActivity = {
        data: {
          date: '2024-01-15',
          shift_id: null,
          activity: [
            { id: 'prod-1', type: 'production', description: 'Logged 50 units for WO-DEMO-001', timestamp: '2024-01-15T08:30:00Z' }
          ]
        }
      }
      api.get.mockResolvedValueOnce(mockActivity)

      const params = {
        shift_date: '2024-01-15',
        limit: 10
      }
      const result = await myShiftApi.getMyShiftActivity(params)

      expect(api.get).toHaveBeenCalledWith('/my-shift/activity', { params })
      expect(result).toEqual(mockActivity)
    })

    it('fetches with custom limit', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await myShiftApi.getMyShiftActivity({
        shift_date: '2024-01-15',
        limit: 50
      })

      expect(api.get).toHaveBeenCalledWith('/my-shift/activity', {
        params: expect.objectContaining({ limit: 50 })
      })
    })

    it('fetches without limit (default)', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await myShiftApi.getMyShiftActivity({ shift_date: '2024-01-15' })

      expect(api.get).toHaveBeenCalledWith('/my-shift/activity', {
        params: { shift_date: '2024-01-15' }
      })
    })
  })
})
