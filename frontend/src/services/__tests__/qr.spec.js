/**
 * Unit tests for QR Code API Service
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

import * as qrApi from '../api/qr'
import api from '../api/client'

describe('QR Code API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('lookupQR', () => {
    it('looks up QR code data', async () => {
      const mockResponse = {
        data: {
          entity_type: 'work_order',
          entity_id: 'WO-001',
          details: { status: 'active' }
        }
      }
      api.get.mockResolvedValueOnce(mockResponse)

      const result = await qrApi.lookupQR('QR123456')

      expect(api.get).toHaveBeenCalledWith('/qr/lookup', { params: { data: 'QR123456' } })
      expect(result).toEqual(mockResponse)
    })

    it('handles encoded QR data', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await qrApi.lookupQR('encoded%20data')

      expect(api.get).toHaveBeenCalledWith('/qr/lookup', { params: { data: 'encoded%20data' } })
    })
  })

  describe('getWorkOrderQR', () => {
    it('fetches work order QR image as blob', async () => {
      const mockBlob = new Blob(['image data'], { type: 'image/png' })
      api.get.mockResolvedValueOnce({ data: mockBlob })

      await qrApi.getWorkOrderQR('WO-001')

      expect(api.get).toHaveBeenCalledWith('/qr/work-order/WO-001/image', { responseType: 'blob' })
    })

    it('handles numeric work order ID', async () => {
      api.get.mockResolvedValueOnce({ data: new Blob() })

      await qrApi.getWorkOrderQR(123)

      expect(api.get).toHaveBeenCalledWith('/qr/work-order/123/image', { responseType: 'blob' })
    })
  })

  describe('getProductQR', () => {
    it('fetches product QR image as blob', async () => {
      const mockBlob = new Blob(['image data'], { type: 'image/png' })
      api.get.mockResolvedValueOnce({ data: mockBlob })

      await qrApi.getProductQR('PROD-001')

      expect(api.get).toHaveBeenCalledWith('/qr/product/PROD-001/image', { responseType: 'blob' })
    })

    it('handles numeric product ID', async () => {
      api.get.mockResolvedValueOnce({ data: new Blob() })

      await qrApi.getProductQR(456)

      expect(api.get).toHaveBeenCalledWith('/qr/product/456/image', { responseType: 'blob' })
    })
  })

  describe('getJobQR', () => {
    it('fetches job QR image as blob', async () => {
      api.get.mockResolvedValueOnce({ data: new Blob() })

      await qrApi.getJobQR('JOB-001')

      expect(api.get).toHaveBeenCalledWith('/qr/job/JOB-001/image', { responseType: 'blob' })
    })
  })

  describe('getEmployeeQR', () => {
    it('fetches employee QR image as blob', async () => {
      api.get.mockResolvedValueOnce({ data: new Blob() })

      await qrApi.getEmployeeQR('EMP-001')

      expect(api.get).toHaveBeenCalledWith('/qr/employee/EMP-001/image', { responseType: 'blob' })
    })
  })

  describe('generateQR', () => {
    it('generates QR code for work order', async () => {
      const mockResponse = {
        data: {
          qr_data: 'encoded_string',
          entity_type: 'work_order',
          entity_id: 'WO-001'
        }
      }
      api.post.mockResolvedValueOnce(mockResponse)

      const result = await qrApi.generateQR('work_order', 'WO-001')

      expect(api.post).toHaveBeenCalledWith('/qr/generate', {
        entity_type: 'work_order',
        entity_id: 'WO-001'
      })
      expect(result).toEqual(mockResponse)
    })

    it('generates QR code for product', async () => {
      api.post.mockResolvedValueOnce({ data: {} })

      await qrApi.generateQR('product', 123)

      expect(api.post).toHaveBeenCalledWith('/qr/generate', {
        entity_type: 'product',
        entity_id: 123
      })
    })

    it('generates QR code for employee', async () => {
      api.post.mockResolvedValueOnce({ data: {} })

      await qrApi.generateQR('employee', 'EMP-123')

      expect(api.post).toHaveBeenCalledWith('/qr/generate', {
        entity_type: 'employee',
        entity_id: 'EMP-123'
      })
    })
  })

  describe('generateQRImage', () => {
    it('generates QR image as blob', async () => {
      const mockBlob = new Blob(['image data'], { type: 'image/png' })
      api.post.mockResolvedValueOnce({ data: mockBlob })

      await qrApi.generateQRImage('work_order', 'WO-002')

      expect(api.post).toHaveBeenCalledWith(
        '/qr/generate/image',
        { entity_type: 'work_order', entity_id: 'WO-002' },
        { responseType: 'blob' }
      )
    })

    it('generates QR image for job', async () => {
      api.post.mockResolvedValueOnce({ data: new Blob() })

      await qrApi.generateQRImage('job', 'JOB-123')

      expect(api.post).toHaveBeenCalledWith(
        '/qr/generate/image',
        { entity_type: 'job', entity_id: 'JOB-123' },
        { responseType: 'blob' }
      )
    })
  })
})
