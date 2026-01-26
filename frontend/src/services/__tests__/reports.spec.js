/**
 * Unit tests for Reports API module
 * Tests report generation and email configuration
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the client module
vi.mock('../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn()
  }
}))

import api from '../api/client'
import * as reportsApi from '../api/reports'

describe('Reports API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getDailyReport', () => {
    it('calls GET /reports/daily/:date with blob response', async () => {
      const mockBlob = new Blob(['test'], { type: 'application/pdf' })
      api.get.mockResolvedValue({ data: mockBlob })

      const result = await reportsApi.getDailyReport('2024-01-15')

      expect(api.get).toHaveBeenCalledWith('/reports/daily/2024-01-15', {
        responseType: 'blob'
      })
      expect(result.data).toBe(mockBlob)
    })
  })

  describe('getWeeklyReport', () => {
    it('calls GET /reports/weekly with date range params', async () => {
      const mockBlob = new Blob(['test'], { type: 'application/pdf' })
      api.get.mockResolvedValue({ data: mockBlob })

      const result = await reportsApi.getWeeklyReport('2024-01-08', '2024-01-14')

      expect(api.get).toHaveBeenCalledWith('/reports/weekly', {
        params: { start_date: '2024-01-08', end_date: '2024-01-14' },
        responseType: 'blob'
      })
      expect(result.data).toBe(mockBlob)
    })
  })

  describe('getMonthlyReport', () => {
    it('calls GET /reports/monthly with month and year', async () => {
      const mockBlob = new Blob(['test'], { type: 'application/pdf' })
      api.get.mockResolvedValue({ data: mockBlob })

      const result = await reportsApi.getMonthlyReport(1, 2024)

      expect(api.get).toHaveBeenCalledWith('/reports/monthly', {
        params: { month: 1, year: 2024 },
        responseType: 'blob'
      })
      expect(result.data).toBe(mockBlob)
    })
  })

  describe('exportExcel', () => {
    it('calls GET /reports/excel with params', async () => {
      const mockBlob = new Blob(['test'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      api.get.mockResolvedValue({ data: mockBlob })

      const params = { client_id: 1, start_date: '2024-01-01' }
      const result = await reportsApi.exportExcel(params)

      expect(api.get).toHaveBeenCalledWith('/reports/excel', {
        params,
        responseType: 'blob'
      })
      expect(result.data).toBe(mockBlob)
    })
  })

  describe('exportPDF', () => {
    it('calls GET /reports/pdf with params', async () => {
      const mockBlob = new Blob(['test'], { type: 'application/pdf' })
      api.get.mockResolvedValue({ data: mockBlob })

      const params = { client_id: 1, report_type: 'efficiency' }
      const result = await reportsApi.exportPDF(params)

      expect(api.get).toHaveBeenCalledWith('/reports/pdf', {
        params,
        responseType: 'blob'
      })
      expect(result.data).toBe(mockBlob)
    })
  })

  describe('getEmailReportConfig', () => {
    it('fetches email config for client', async () => {
      const mockConfig = {
        enabled: true,
        frequency: 'daily',
        recipients: ['test@example.com'],
        report_time: '06:00'
      }
      api.get.mockResolvedValue({ data: mockConfig })

      const result = await reportsApi.getEmailReportConfig(1)

      expect(api.get).toHaveBeenCalledWith('/reports/email-config', {
        params: { client_id: 1 }
      })
      expect(result.data).toEqual(mockConfig)
    })

    it('returns defaults on error', async () => {
      api.get.mockRejectedValue(new Error('Not found'))

      const result = await reportsApi.getEmailReportConfig(999)

      expect(result.data.enabled).toBe(false)
      expect(result.data.frequency).toBe('daily')
      expect(result.data.recipients).toEqual([])
    })
  })

  describe('saveEmailReportConfig', () => {
    it('calls POST /reports/email-config', async () => {
      const config = {
        client_id: 1,
        enabled: true,
        frequency: 'weekly',
        recipients: ['manager@example.com']
      }
      api.post.mockResolvedValue({ data: config })

      const result = await reportsApi.saveEmailReportConfig(config)

      expect(api.post).toHaveBeenCalledWith('/reports/email-config', config)
      expect(result.data).toEqual(config)
    })
  })

  describe('updateEmailReportConfig', () => {
    it('calls PUT /reports/email-config', async () => {
      const config = {
        client_id: 1,
        enabled: false
      }
      api.put.mockResolvedValue({ data: config })

      const result = await reportsApi.updateEmailReportConfig(config)

      expect(api.put).toHaveBeenCalledWith('/reports/email-config', config)
      expect(result.data).toEqual(config)
    })
  })

  describe('sendTestEmail', () => {
    it('calls POST /reports/email-config/test', async () => {
      api.post.mockResolvedValue({ data: { success: true } })

      const result = await reportsApi.sendTestEmail('test@example.com')

      expect(api.post).toHaveBeenCalledWith('/reports/email-config/test', {
        email: 'test@example.com'
      })
      expect(result.data.success).toBe(true)
    })
  })

  describe('triggerManualReport', () => {
    it('calls POST /reports/send-manual', async () => {
      const data = {
        client_id: 1,
        report_type: 'daily',
        recipients: ['admin@example.com']
      }
      api.post.mockResolvedValue({ data: { sent: true } })

      const result = await reportsApi.triggerManualReport(data)

      expect(api.post).toHaveBeenCalledWith('/reports/send-manual', data)
      expect(result.data.sent).toBe(true)
    })
  })
})
