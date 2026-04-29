/**
 * Unit tests for My Shift API Service
 * Phase 8: Increase test coverage
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
          shift_date: '2024-01-15',
          shift_number: 1,
          operator_id: 'OP001',
          total_produced: 500,
          efficiency: 85.5,
          quality_rate: 98.2
        }
      }
      api.get.mockResolvedValueOnce(mockSummary)

      const params = {
        shift_date: '2024-01-15',
        shift_number: 1,
        operator_id: 'OP001'
      }
      const result = await myShiftApi.getMyShiftSummary(params)

      expect(api.get).toHaveBeenCalledWith('/my-shift/summary', { params })
      expect(result).toEqual(mockSummary)
    })

    it('handles different shift numbers', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await myShiftApi.getMyShiftSummary({
        shift_date: '2024-01-15',
        shift_number: 2,
        operator_id: 'OP002'
      })

      expect(api.get).toHaveBeenCalledWith('/my-shift/summary', {
        params: {
          shift_date: '2024-01-15',
          shift_number: 2,
          operator_id: 'OP002'
        }
      })
    })

    it('works with night shift (shift 3)', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await myShiftApi.getMyShiftSummary({
        shift_date: '2024-01-15',
        shift_number: 3,
        operator_id: 'OP003'
      })

      expect(api.get).toHaveBeenCalledWith('/my-shift/summary', {
        params: expect.objectContaining({ shift_number: 3 })
      })
    })
  })

  describe('getMyShiftStats', () => {
    it('fetches lightweight stats', async () => {
      const mockStats = {
        data: {
          units_produced: 250,
          defects: 3,
          downtime_minutes: 15
        }
      }
      api.get.mockResolvedValueOnce(mockStats)

      const params = { shift_date: '2024-01-15', shift_number: 1 }
      const result = await myShiftApi.getMyShiftStats(params)

      expect(api.get).toHaveBeenCalledWith('/my-shift/stats', { params })
      expect(result).toEqual(mockStats)
    })

    it('fetches stats without operator_id', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await myShiftApi.getMyShiftStats({ shift_date: '2024-01-15' })

      expect(api.get).toHaveBeenCalledWith('/my-shift/stats', {
        params: { shift_date: '2024-01-15' }
      })
    })
  })

  describe('getMyShiftActivity', () => {
    it('fetches recent activity entries', async () => {
      const mockActivity = {
        data: [
          { id: 1, timestamp: '2024-01-15T08:30:00Z', action: 'production_entry' },
          { id: 2, timestamp: '2024-01-15T09:15:00Z', action: 'quality_check' }
        ]
      }
      api.get.mockResolvedValueOnce(mockActivity)

      const params = {
        shift_date: '2024-01-15',
        shift_number: 1,
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
        shift_number: 1,
        limit: 50
      })

      expect(api.get).toHaveBeenCalledWith('/my-shift/activity', {
        params: expect.objectContaining({ limit: 50 })
      })
    })

    it('fetches without limit (default)', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await myShiftApi.getMyShiftActivity({
        shift_date: '2024-01-15',
        shift_number: 2
      })

      expect(api.get).toHaveBeenCalledWith('/my-shift/activity', {
        params: {
          shift_date: '2024-01-15',
          shift_number: 2
        }
      })
    })
  })
})
