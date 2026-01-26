/**
 * Unit tests for Reference Data API Service
 * Phase 8: Increase test coverage
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock the performance utility
vi.mock('@/utils/performance', () => ({
  referenceDataCache: {
    get: vi.fn((key, fetcher, options) => fetcher()),
    invalidatePattern: vi.fn(),
    invalidate: vi.fn(),
    getStats: vi.fn(() => ({
      hits: 10,
      misses: 5,
      size: 5
    }))
  }
}))

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

import * as referenceApi from '../api/reference'
import api from '../api/client'
import { referenceDataCache } from '@/utils/performance'

describe('Reference Data API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getProducts', () => {
    it('fetches products with caching', async () => {
      const mockProducts = { data: [{ id: 1, name: 'Product A' }] }
      api.get.mockResolvedValueOnce(mockProducts)

      const result = await referenceApi.getProducts()

      expect(referenceDataCache.get).toHaveBeenCalledWith(
        'reference:products',
        expect.any(Function),
        expect.objectContaining({
          staleWhileRevalidate: true,
          forceRefresh: false
        })
      )
    })

    it('respects forceRefresh option', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await referenceApi.getProducts({ forceRefresh: true })

      expect(referenceDataCache.get).toHaveBeenCalledWith(
        'reference:products',
        expect.any(Function),
        expect.objectContaining({
          forceRefresh: true
        })
      )
    })
  })

  describe('getShifts', () => {
    it('fetches shifts with caching', async () => {
      const mockShifts = { data: [{ id: 1, name: 'Day Shift' }] }
      api.get.mockResolvedValueOnce(mockShifts)

      await referenceApi.getShifts()

      expect(referenceDataCache.get).toHaveBeenCalledWith(
        'reference:shifts',
        expect.any(Function),
        expect.objectContaining({
          staleWhileRevalidate: true
        })
      )
    })

    it('calls shifts endpoint via fetcher', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      // Call the fetcher directly
      await referenceApi.getShifts()

      expect(api.get).toHaveBeenCalledWith('/shifts')
    })
  })

  describe('getDowntimeReasons', () => {
    it('fetches downtime reasons with caching', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await referenceApi.getDowntimeReasons()

      expect(referenceDataCache.get).toHaveBeenCalledWith(
        'reference:downtime-reasons',
        expect.any(Function),
        expect.any(Object)
      )
    })

    it('calls downtime-reasons endpoint', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await referenceApi.getDowntimeReasons()

      expect(api.get).toHaveBeenCalledWith('/downtime-reasons')
    })
  })

  describe('getClients', () => {
    it('fetches clients with caching', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await referenceApi.getClients()

      expect(referenceDataCache.get).toHaveBeenCalledWith(
        'reference:clients',
        expect.any(Function),
        expect.any(Object)
      )
    })

    it('calls admin/clients endpoint', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await referenceApi.getClients()

      expect(api.get).toHaveBeenCalledWith('/admin/clients')
    })
  })

  describe('getDefectTypes', () => {
    it('fetches defect types with caching', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await referenceApi.getDefectTypes()

      expect(referenceDataCache.get).toHaveBeenCalledWith(
        'reference:defect-types',
        expect.any(Function),
        expect.any(Object)
      )
    })

    it('calls admin/defect-types endpoint', async () => {
      api.get.mockResolvedValueOnce({ data: [] })

      await referenceApi.getDefectTypes()

      expect(api.get).toHaveBeenCalledWith('/admin/defect-types')
    })
  })

  describe('invalidateReferenceCache', () => {
    it('invalidates all reference data caches', () => {
      referenceApi.invalidateReferenceCache()

      expect(referenceDataCache.invalidatePattern).toHaveBeenCalledWith('^reference:')
    })
  })

  describe('invalidateReferenceType', () => {
    it('invalidates specific reference type cache', () => {
      referenceApi.invalidateReferenceType('products')

      expect(referenceDataCache.invalidate).toHaveBeenCalledWith('reference:products')
    })

    it('invalidates shifts cache', () => {
      referenceApi.invalidateReferenceType('shifts')

      expect(referenceDataCache.invalidate).toHaveBeenCalledWith('reference:shifts')
    })
  })

  describe('prefetchReferenceData', () => {
    it('prefetches all reference data', async () => {
      api.get.mockResolvedValue({ data: [] })

      await referenceApi.prefetchReferenceData()

      // Should have called get for products, shifts, downtime-reasons, clients
      expect(referenceDataCache.get).toHaveBeenCalledTimes(4)
    })

    it('continues even if some prefetch fails', async () => {
      // First call succeeds, second fails
      referenceDataCache.get
        .mockResolvedValueOnce({ data: [] })
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [] })

      // Should not throw
      await expect(referenceApi.prefetchReferenceData()).resolves.not.toThrow()
    })
  })

  describe('getReferenceDataCacheStats', () => {
    it('returns cache statistics', () => {
      const stats = referenceApi.getReferenceDataCacheStats()

      expect(referenceDataCache.getStats).toHaveBeenCalled()
      expect(stats).toEqual({
        hits: 10,
        misses: 5,
        size: 5
      })
    })
  })
})
