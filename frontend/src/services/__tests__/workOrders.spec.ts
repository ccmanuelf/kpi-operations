/**
 * Unit tests for Work Orders API Service
 * Phase 8: Increase test coverage
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock axios
vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() }
      }
    }))
  }
}))

// Import after mocking
import * as workOrdersApi from '../api/workOrders'
import api from '../api/client'

describe('Work Orders API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getWorkOrders', () => {
    it('fetches work orders with params', async () => {
      const mockResponse = { data: [{ id: 1, work_order_number: 'WO-001' }] }
      api.get.mockResolvedValueOnce(mockResponse)

      const params = { status: 'active', page: 1 }
      const result = await workOrdersApi.getWorkOrders(params)

      expect(api.get).toHaveBeenCalledWith('/work-orders', { params })
      expect(result).toEqual(mockResponse)
    })

    it('fetches all work orders without params', async () => {
      const mockResponse = { data: [] }
      api.get.mockResolvedValueOnce(mockResponse)

      await workOrdersApi.getWorkOrders()

      expect(api.get).toHaveBeenCalledWith('/work-orders', { params: undefined })
    })
  })

  describe('getWorkOrder', () => {
    it('fetches single work order by ID', async () => {
      const mockResponse = { data: { id: 1, work_order_number: 'WO-001' } }
      api.get.mockResolvedValueOnce(mockResponse)

      const result = await workOrdersApi.getWorkOrder(1)

      expect(api.get).toHaveBeenCalledWith('/work-orders/1')
      expect(result).toEqual(mockResponse)
    })

    it('handles string ID', async () => {
      api.get.mockResolvedValueOnce({ data: {} })

      await workOrdersApi.getWorkOrder('WO-001')

      expect(api.get).toHaveBeenCalledWith('/work-orders/WO-001')
    })
  })

  describe('getWorkOrdersByStatus', () => {
    it('fetches work orders by status', async () => {
      const mockResponse = { data: [] }
      api.get.mockResolvedValueOnce(mockResponse)

      await workOrdersApi.getWorkOrdersByStatus('completed', { page: 1 })

      expect(api.get).toHaveBeenCalledWith('/work-orders/status/completed', { params: { page: 1 } })
    })

    it('fetches without additional params', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await workOrdersApi.getWorkOrdersByStatus('pending')

      expect(api.get).toHaveBeenCalledWith('/work-orders/status/pending', { params: undefined })
    })
  })

  describe('getWorkOrdersByDateRange', () => {
    it('fetches work orders within date range', async () => {
      const mockResponse = { data: [] }
      api.get.mockResolvedValueOnce(mockResponse)

      await workOrdersApi.getWorkOrdersByDateRange('2024-01-01', '2024-01-31', { client_id: 1 })

      expect(api.get).toHaveBeenCalledWith('/work-orders/date-range', {
        params: {
          start_date: '2024-01-01',
          end_date: '2024-01-31',
          client_id: 1
        }
      })
    })

    it('fetches without additional params', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await workOrdersApi.getWorkOrdersByDateRange('2024-01-01', '2024-01-31')

      expect(api.get).toHaveBeenCalledWith('/work-orders/date-range', {
        params: {
          start_date: '2024-01-01',
          end_date: '2024-01-31'
        }
      })
    })
  })

  describe('createWorkOrder', () => {
    it('creates new work order', async () => {
      const newWorkOrder = {
        work_order_number: 'WO-002',
        client_id: 1,
        product_id: 1,
        quantity_ordered: 1000
      }
      const mockResponse = { data: { id: 2, ...newWorkOrder } }
      api.post.mockResolvedValueOnce(mockResponse)

      const result = await workOrdersApi.createWorkOrder(newWorkOrder)

      expect(api.post).toHaveBeenCalledWith('/work-orders', newWorkOrder)
      expect(result).toEqual(mockResponse)
    })
  })

  describe('updateWorkOrder', () => {
    it('updates existing work order', async () => {
      const updates = { quantity_ordered: 1500 }
      const mockResponse = { data: { id: 1, quantity_ordered: 1500 } }
      api.put.mockResolvedValueOnce(mockResponse)

      const result = await workOrdersApi.updateWorkOrder(1, updates)

      expect(api.put).toHaveBeenCalledWith('/work-orders/1', updates)
      expect(result).toEqual(mockResponse)
    })
  })

  describe('deleteWorkOrder', () => {
    it('deletes work order by ID', async () => {
      api.delete.mockResolvedValueOnce({ data: { success: true } })

      await workOrdersApi.deleteWorkOrder(1)

      expect(api.delete).toHaveBeenCalledWith('/work-orders/1')
    })
  })

  describe('updateWorkOrderStatus', () => {
    it('updates only status field', async () => {
      api.put.mockResolvedValueOnce({ data: { id: 1, status: 'completed' } })

      await workOrdersApi.updateWorkOrderStatus(1, 'completed')

      expect(api.put).toHaveBeenCalledWith('/work-orders/1', { status: 'completed' })
    })
  })

  describe('getWorkOrderProgress', () => {
    it('fetches work order progress', async () => {
      const mockProgress = {
        data: {
          total_ordered: 1000,
          total_produced: 750,
          percent_complete: 75
        }
      }
      api.get.mockResolvedValueOnce(mockProgress)

      const result = await workOrdersApi.getWorkOrderProgress(1)

      expect(api.get).toHaveBeenCalledWith('/work-orders/1/progress')
      expect(result).toEqual(mockProgress)
    })
  })

  describe('getWorkOrderTimeline', () => {
    it('fetches work order activity timeline', async () => {
      const mockTimeline = {
        data: [
          { timestamp: '2024-01-15T10:00:00Z', action: 'created' },
          { timestamp: '2024-01-16T08:00:00Z', action: 'started' }
        ]
      }
      api.get.mockResolvedValueOnce(mockTimeline)

      const result = await workOrdersApi.getWorkOrderTimeline(1)

      expect(api.get).toHaveBeenCalledWith('/work-orders/1/timeline')
      expect(result).toEqual(mockTimeline)
    })
  })

  describe('getClientWorkOrders', () => {
    it('fetches work orders for specific client', async () => {
      const mockResponse = { data: [] }
      api.get.mockResolvedValueOnce(mockResponse)

      await workOrdersApi.getClientWorkOrders('client_1', { status: 'active' })

      expect(api.get).toHaveBeenCalledWith('/clients/client_1/work-orders', { params: { status: 'active' } })
    })

    it('fetches without params', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await workOrdersApi.getClientWorkOrders('client_2')

      expect(api.get).toHaveBeenCalledWith('/clients/client_2/work-orders', { params: undefined })
    })
  })
})
