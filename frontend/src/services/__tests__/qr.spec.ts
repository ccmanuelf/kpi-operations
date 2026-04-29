/**
 * Unit tests for QR Code API Service
 * Phase 8: Increase test coverage
 * Note: getWorkOrderQR, getProductQR, getJobQR, getEmployeeQR, generateQR removed (DC-FE-24: unused)
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
