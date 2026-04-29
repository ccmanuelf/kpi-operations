/**
 * Unit tests for Data Entry API module
 * Tests downtime, attendance, quality, and hold entry operations
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the client module
vi.mock('../api/client', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

import api from '../api/client'
import * as dataEntryApi from '../api/dataEntry'

describe('Data Entry API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Downtime Entries', () => {
    it('createDowntimeEntry calls POST /downtime', async () => {
      const data = { equipment_id: 1, reason_id: 2, duration_minutes: 30 }
      const mockResponse = { data: { downtime_id: 1, ...data } }
      api.post.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.createDowntimeEntry(data)

      expect(api.post).toHaveBeenCalledWith('/downtime', data)
      expect(result).toEqual(mockResponse)
    })

    it('getDowntimeEntries calls GET /downtime with params', async () => {
      const params = { start_date: '2024-01-01' }
      const mockResponse = { data: [{ downtime_id: 1 }] }
      api.get.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.getDowntimeEntries(params)

      expect(api.get).toHaveBeenCalledWith('/downtime', { params })
      expect(result).toEqual(mockResponse)
    })

    it('updateDowntimeEntry calls PUT /downtime/:id', async () => {
      const data = { duration_minutes: 45 }
      const mockResponse = { data: { downtime_id: 1, duration_minutes: 45 } }
      api.put.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.updateDowntimeEntry(1, data)

      expect(api.put).toHaveBeenCalledWith('/downtime/1', data)
      expect(result).toEqual(mockResponse)
    })

    it('deleteDowntimeEntry calls DELETE /downtime/:id', async () => {
      api.delete.mockResolvedValue({})

      await dataEntryApi.deleteDowntimeEntry(1)

      expect(api.delete).toHaveBeenCalledWith('/downtime/1')
    })
  })

  describe('Attendance Entries', () => {
    it('createAttendanceEntry calls POST /attendance', async () => {
      const data = { employee_id: 1, date: '2024-01-01', hours_worked: 8 }
      const mockResponse = { data: { attendance_id: 1, ...data } }
      api.post.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.createAttendanceEntry(data)

      expect(api.post).toHaveBeenCalledWith('/attendance', data)
      expect(result).toEqual(mockResponse)
    })

    it('getAttendanceEntries calls GET /attendance with params', async () => {
      const params = { employee_id: 1 }
      const mockResponse = { data: [{ attendance_id: 1 }] }
      api.get.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.getAttendanceEntries(params)

      expect(api.get).toHaveBeenCalledWith('/attendance', { params })
      expect(result).toEqual(mockResponse)
    })

    it('updateAttendanceEntry calls PUT /attendance/:id', async () => {
      const data = { hours_worked: 7.5 }
      const mockResponse = { data: { attendance_id: 1, hours_worked: 7.5 } }
      api.put.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.updateAttendanceEntry(1, data)

      expect(api.put).toHaveBeenCalledWith('/attendance/1', data)
      expect(result).toEqual(mockResponse)
    })

    it('deleteAttendanceEntry calls DELETE /attendance/:id', async () => {
      api.delete.mockResolvedValue({})

      await dataEntryApi.deleteAttendanceEntry(1)

      expect(api.delete).toHaveBeenCalledWith('/attendance/1')
    })
  })

  describe('Quality Entries', () => {
    it('createQualityEntry calls POST /quality', async () => {
      const data = { work_order_id: 1, inspected_quantity: 100, defect_quantity: 5 }
      const mockResponse = { data: { quality_id: 1, ...data } }
      api.post.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.createQualityEntry(data)

      expect(api.post).toHaveBeenCalledWith('/quality', data)
      expect(result).toEqual(mockResponse)
    })

    it('getQualityEntries calls GET /quality with params', async () => {
      const params = { work_order_id: 1 }
      const mockResponse = { data: [{ quality_id: 1 }] }
      api.get.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.getQualityEntries(params)

      expect(api.get).toHaveBeenCalledWith('/quality', { params })
      expect(result).toEqual(mockResponse)
    })

    it('updateQualityEntry calls PUT /quality/:id', async () => {
      const data = { defect_quantity: 3 }
      const mockResponse = { data: { quality_id: 1, defect_quantity: 3 } }
      api.put.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.updateQualityEntry(1, data)

      expect(api.put).toHaveBeenCalledWith('/quality/1', data)
      expect(result).toEqual(mockResponse)
    })

    it('deleteQualityEntry calls DELETE /quality/:id', async () => {
      api.delete.mockResolvedValue({})

      await dataEntryApi.deleteQualityEntry(1)

      expect(api.delete).toHaveBeenCalledWith('/quality/1')
    })
  })

  describe('Hold Entries', () => {
    it('createHoldEntry calls POST /holds', async () => {
      const data = { work_order_id: 1, reason: 'Quality check', quantity: 50 }
      const mockResponse = { data: { hold_id: 1, ...data } }
      api.post.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.createHoldEntry(data)

      expect(api.post).toHaveBeenCalledWith('/holds', data)
      expect(result).toEqual(mockResponse)
    })

    it('updateHoldEntry calls PUT /holds/:id', async () => {
      const data = { reason: 'Updated reason' }
      const mockResponse = { data: { hold_id: 1, reason: 'Updated reason' } }
      api.put.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.updateHoldEntry(1, data)

      expect(api.put).toHaveBeenCalledWith('/holds/1', data)
      expect(result).toEqual(mockResponse)
    })

    it('deleteHoldEntry calls DELETE /holds/:id', async () => {
      api.delete.mockResolvedValue({})

      await dataEntryApi.deleteHoldEntry(1)

      expect(api.delete).toHaveBeenCalledWith('/holds/1')
    })

    it('resumeHold calls POST /holds/:id/resume', async () => {
      const data = { resume_quantity: 25, notes: 'Partial resume' }
      const mockResponse = { data: { hold_id: 1, status: 'resumed' } }
      api.post.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.resumeHold(1, data)

      expect(api.post).toHaveBeenCalledWith('/holds/1/resume', data)
      expect(result).toEqual(mockResponse)
    })

    it('getHoldEntries calls GET /holds with params', async () => {
      const params = { status: 'active' }
      const mockResponse = { data: [{ hold_id: 1 }] }
      api.get.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.getHoldEntries(params)

      expect(api.get).toHaveBeenCalledWith('/holds', { params })
      expect(result).toEqual(mockResponse)
    })

    it('getActiveHolds calls GET /holds/active with params', async () => {
      const params = { client_id: 1 }
      const mockResponse = { data: [{ hold_id: 1, status: 'active' }] }
      api.get.mockResolvedValue(mockResponse)

      const result = await dataEntryApi.getActiveHolds(params)

      expect(api.get).toHaveBeenCalledWith('/holds/active', { params })
      expect(result).toEqual(mockResponse)
    })
  })
})
