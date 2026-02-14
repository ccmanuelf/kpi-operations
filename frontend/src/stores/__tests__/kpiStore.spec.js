/**
 * Unit tests for KPI Store
 * Tests Pinia store actions, getters, and state management
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useProductionDataStore } from '../productionDataStore'

// Mock the API module
vi.mock('@/services/api', () => ({
  default: {
    getProductionEntries: vi.fn(),
    createProductionEntry: vi.fn(),
    updateProductionEntry: vi.fn(),
    deleteProductionEntry: vi.fn(),
    getKPIDashboard: vi.fn(),
    getProducts: vi.fn(),
    getShifts: vi.fn(),
    getDowntimeReasons: vi.fn(),
    uploadCSV: vi.fn(),
    batchImportProduction: vi.fn(),
    getDowntimeEntries: vi.fn(),
    createDowntimeEntry: vi.fn(),
    updateDowntimeEntry: vi.fn(),
    deleteDowntimeEntry: vi.fn(),
    getHoldEntries: vi.fn(),
    createHoldEntry: vi.fn(),
    updateHoldEntry: vi.fn(),
    deleteHoldEntry: vi.fn()
  }
}))

import api from '@/services/api'

describe('KPI Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('State', () => {
    it('initializes with correct default state', () => {
      const store = useProductionDataStore()

      expect(store.productionEntries).toEqual([])
      expect(store.downtimeEntries).toEqual([])
      expect(store.holdEntries).toEqual([])
      expect(store.workOrders).toEqual([])
      expect(store.products).toEqual([])
      expect(store.shifts).toEqual([])
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('Getters', () => {
    it('recentEntries returns first 10 entries', () => {
      const store = useProductionDataStore()
      store.productionEntries = Array.from({ length: 15 }, (_, i) => ({
        entry_id: i + 1,
        units_produced: 100
      }))

      expect(store.recentEntries).toHaveLength(10)
      expect(store.recentEntries[0].entry_id).toBe(1)
    })

    it('averageEfficiency calculates correctly', () => {
      const store = useProductionDataStore()
      store.productionEntries = [
        { efficiency_percentage: 80 },
        { efficiency_percentage: 90 },
        { efficiency_percentage: 85 }
      ]

      expect(store.averageEfficiency).toBe('85.00')
    })

    it('averageEfficiency returns 0 when no entries', () => {
      const store = useProductionDataStore()
      store.productionEntries = []

      expect(store.averageEfficiency).toBe(0)
    })

    it('averageEfficiency ignores entries without efficiency', () => {
      const store = useProductionDataStore()
      store.productionEntries = [
        { efficiency_percentage: 80 },
        { efficiency_percentage: null },
        { efficiency_percentage: 90 }
      ]

      expect(store.averageEfficiency).toBe('85.00')
    })

    it('averagePerformance calculates correctly', () => {
      const store = useProductionDataStore()
      store.productionEntries = [
        { performance_percentage: 75 },
        { performance_percentage: 85 },
        { performance_percentage: 95 }
      ]

      expect(store.averagePerformance).toBe('85.00')
    })
  })

  describe('Actions - Production Entries', () => {
    it('fetchProductionEntries sets entries on success', async () => {
      const mockData = [{ entry_id: 1, units_produced: 100 }]
      api.getProductionEntries.mockResolvedValue({ data: mockData })

      const store = useProductionDataStore()
      const result = await store.fetchProductionEntries()

      expect(result.success).toBe(true)
      expect(store.productionEntries).toEqual(mockData)
      expect(store.loading).toBe(false)
    })

    it('fetchProductionEntries handles errors', async () => {
      api.getProductionEntries.mockRejectedValue({
        response: { data: { detail: 'Server error' } }
      })

      const store = useProductionDataStore()
      const result = await store.fetchProductionEntries()

      expect(result.success).toBe(false)
      expect(result.error).toBe('Server error')
      expect(store.error).toBe('Server error')
    })

    it('createProductionEntry adds entry on success', async () => {
      const newEntry = { entry_id: 1, units_produced: 100 }
      api.createProductionEntry.mockResolvedValue({ data: newEntry })

      const store = useProductionDataStore()
      const result = await store.createProductionEntry({ units_produced: 100 })

      expect(result.success).toBe(true)
      expect(store.productionEntries[0]).toEqual(newEntry)
    })

    it('updateProductionEntry updates existing entry', async () => {
      const updatedEntry = { entry_id: 1, units_produced: 150 }
      api.updateProductionEntry.mockResolvedValue({ data: updatedEntry })

      const store = useProductionDataStore()
      store.productionEntries = [{ entry_id: 1, units_produced: 100 }]

      const result = await store.updateProductionEntry(1, { units_produced: 150 })

      expect(result.success).toBe(true)
      expect(store.productionEntries[0].units_produced).toBe(150)
    })

    it('deleteProductionEntry removes entry', async () => {
      api.deleteProductionEntry.mockResolvedValue({})

      const store = useProductionDataStore()
      store.productionEntries = [
        { entry_id: 1 },
        { entry_id: 2 }
      ]

      const result = await store.deleteProductionEntry(1)

      expect(result.success).toBe(true)
      expect(store.productionEntries).toHaveLength(1)
      expect(store.productionEntries[0].entry_id).toBe(2)
    })
  })

  describe('Actions - Reference Data', () => {
    it('fetchReferenceData loads products, shifts, and reasons', async () => {
      api.getProducts.mockResolvedValue({ data: [{ product_id: 1, product_name: 'Widget' }] })
      api.getShifts.mockResolvedValue({ data: [{ shift_id: 1, shift_name: 'Day' }] })
      api.getDowntimeReasons.mockResolvedValue({ data: [{ reason_id: 1, reason: 'Maintenance' }] })

      const store = useProductionDataStore()
      const result = await store.fetchReferenceData()

      expect(result.success).toBe(true)
      expect(store.products).toHaveLength(1)
      expect(store.shifts).toHaveLength(1)
      expect(store.downtimeReasons).toHaveLength(1)
    })
  })

  describe('Actions - CSV Upload', () => {
    it('uploadCSV succeeds and refreshes entries', async () => {
      api.uploadCSV.mockResolvedValue({ data: { total_rows: 5, successful: 5, failed: 0 } })
      api.getProductionEntries.mockResolvedValue({ data: [] })

      const store = useProductionDataStore()
      const file = new File(['test'], 'test.csv')
      const result = await store.uploadCSV(file)

      expect(result.success).toBe(true)
      expect(api.uploadCSV).toHaveBeenCalledWith(file)
      expect(api.getProductionEntries).toHaveBeenCalled()
    })

    it('uploadCSV handles errors', async () => {
      api.uploadCSV.mockRejectedValue({
        response: { data: { detail: 'Invalid CSV format' } }
      })

      const store = useProductionDataStore()
      const result = await store.uploadCSV(new File([''], 'test.csv'))

      expect(result.success).toBe(false)
      expect(result.error).toBe('Invalid CSV format')
    })
  })

  describe('Actions - Downtime Entries', () => {
    it('fetchDowntimeEntries sets entries on success', async () => {
      const mockData = [{ downtime_id: 1, duration_hours: 2 }]
      api.getDowntimeEntries.mockResolvedValue({ data: mockData })

      const store = useProductionDataStore()
      const result = await store.fetchDowntimeEntries()

      expect(result.success).toBe(true)
      expect(store.downtimeEntries).toEqual(mockData)
    })

    it('createDowntimeEntry adds entry', async () => {
      const newEntry = { downtime_id: 1, duration_hours: 2 }
      api.createDowntimeEntry.mockResolvedValue({ data: newEntry })

      const store = useProductionDataStore()
      const result = await store.createDowntimeEntry({ duration_hours: 2 })

      expect(result.success).toBe(true)
      expect(store.downtimeEntries[0]).toEqual(newEntry)
    })
  })

  describe('Actions - Hold Entries', () => {
    it('fetchHoldEntries sets entries on success', async () => {
      const mockData = [{ hold_id: 1, reason: 'Quality check' }]
      api.getHoldEntries.mockResolvedValue({ data: mockData })

      const store = useProductionDataStore()
      const result = await store.fetchHoldEntries()

      expect(result.success).toBe(true)
      expect(store.holdEntries).toEqual(mockData)
    })
  })

  describe('Loading State', () => {
    it('sets loading to true during fetch and false after', async () => {
      let resolvePromise
      api.getProductionEntries.mockImplementation(() =>
        new Promise(resolve => {
          resolvePromise = () => resolve({ data: [] })
        })
      )

      const store = useProductionDataStore()
      const fetchPromise = store.fetchProductionEntries()

      expect(store.loading).toBe(true)

      resolvePromise()
      await fetchPromise

      expect(store.loading).toBe(false)
    })
  })
})
