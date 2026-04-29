/**
 * Unit tests for Production API module
 * Tests production entry CRUD operations and CSV upload
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
import * as productionApi from '../api/production'

describe('Production API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('createProductionEntry', () => {
    it('calls POST /production with entry data', async () => {
      const entryData = {
        product_id: 1,
        units_produced: 100,
        run_time_hours: 8
      }
      const mockResponse = { data: { entry_id: 1, ...entryData } }
      api.post.mockResolvedValue(mockResponse)

      const result = await productionApi.createProductionEntry(entryData)

      expect(api.post).toHaveBeenCalledWith('/production', entryData)
      expect(result).toEqual(mockResponse)
    })
  })

  describe('getProductionEntries', () => {
    it('calls GET /production with params', async () => {
      const params = { client_id: 1, limit: 10 }
      const mockResponse = { data: [{ entry_id: 1 }, { entry_id: 2 }] }
      api.get.mockResolvedValue(mockResponse)

      const result = await productionApi.getProductionEntries(params)

      expect(api.get).toHaveBeenCalledWith('/production', { params })
      expect(result).toEqual(mockResponse)
    })

    it('calls GET /production without params', async () => {
      const mockResponse = { data: [] }
      api.get.mockResolvedValue(mockResponse)

      const result = await productionApi.getProductionEntries()

      expect(api.get).toHaveBeenCalledWith('/production', { params: undefined })
      expect(result).toEqual(mockResponse)
    })
  })

  describe('getProductionEntry', () => {
    it('calls GET /production/:id', async () => {
      const mockResponse = { data: { entry_id: 1, units_produced: 100 } }
      api.get.mockResolvedValue(mockResponse)

      const result = await productionApi.getProductionEntry(1)

      expect(api.get).toHaveBeenCalledWith('/production/1')
      expect(result).toEqual(mockResponse)
    })
  })

  describe('updateProductionEntry', () => {
    it('calls PUT /production/:id with data', async () => {
      const updateData = { units_produced: 150 }
      const mockResponse = { data: { entry_id: 1, units_produced: 150 } }
      api.put.mockResolvedValue(mockResponse)

      const result = await productionApi.updateProductionEntry(1, updateData)

      expect(api.put).toHaveBeenCalledWith('/production/1', updateData)
      expect(result).toEqual(mockResponse)
    })
  })

  describe('deleteProductionEntry', () => {
    it('calls DELETE /production/:id', async () => {
      api.delete.mockResolvedValue({})

      await productionApi.deleteProductionEntry(1)

      expect(api.delete).toHaveBeenCalledWith('/production/1')
    })
  })

  describe('uploadCSV', () => {
    it('calls POST /production/upload/csv with FormData', async () => {
      const file = new File(['test,data'], 'test.csv', { type: 'text/csv' })
      const mockResponse = { data: { rows_imported: 10 } }
      api.post.mockResolvedValue(mockResponse)

      const result = await productionApi.uploadCSV(file)

      expect(api.post).toHaveBeenCalledWith(
        '/production/upload/csv',
        expect.any(FormData),
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
      expect(result).toEqual(mockResponse)
    })

    it('appends file to FormData correctly', async () => {
      const file = new File(['test,data'], 'test.csv', { type: 'text/csv' })
      api.post.mockResolvedValue({ data: {} })

      await productionApi.uploadCSV(file)

      const formData = api.post.mock.calls[0][1]
      expect(formData.get('file')).toBe(file)
    })
  })

  describe('batchImportProduction', () => {
    it('calls POST /production/batch-import with entries', async () => {
      const entries = [
        { product_id: 1, units_produced: 100 },
        { product_id: 2, units_produced: 200 }
      ]
      const mockResponse = { data: { imported: 2 } }
      api.post.mockResolvedValue(mockResponse)

      const result = await productionApi.batchImportProduction(entries)

      expect(api.post).toHaveBeenCalledWith('/production/batch-import', { entries })
      expect(result).toEqual(mockResponse)
    })
  })
})
