/**
 * Reference Data API Service
 *
 * Handles fetching of reference/lookup data with caching support.
 * Reference data (products, shifts, clients, downtime reasons) changes
 * infrequently and can be safely cached for improved performance.
 */

import api from './client'
import { referenceDataCache } from '@/utils/performance'

// Cache TTL constants (in milliseconds)
const CACHE_TTL = {
  PRODUCTS: 10 * 60 * 1000, // 10 minutes - products change occasionally
  SHIFTS: 30 * 60 * 1000,   // 30 minutes - shifts rarely change
  DOWNTIME_REASONS: 30 * 60 * 1000, // 30 minutes
  CLIENTS: 10 * 60 * 1000,  // 10 minutes
  DEFECT_TYPES: 30 * 60 * 1000 // 30 minutes
}

/**
 * Get all products with caching
 * Uses stale-while-revalidate pattern for instant responses
 *
 * @param {Object} options - Options
 * @param {boolean} options.forceRefresh - Force a fresh fetch
 * @returns {Promise<Object>} Products response
 */
export const getProducts = (options = {}) => {
  return referenceDataCache.get(
    'reference:products',
    () => api.get('/products'),
    {
      ttl: CACHE_TTL.PRODUCTS,
      staleWhileRevalidate: true,
      forceRefresh: options.forceRefresh || false
    }
  )
}

/**
 * Get all shifts with caching
 *
 * @param {Object} options - Options
 * @param {boolean} options.forceRefresh - Force a fresh fetch
 * @returns {Promise<Object>} Shifts response
 */
export const getShifts = (options = {}) => {
  return referenceDataCache.get(
    'reference:shifts',
    () => api.get('/shifts'),
    {
      ttl: CACHE_TTL.SHIFTS,
      staleWhileRevalidate: true,
      forceRefresh: options.forceRefresh || false
    }
  )
}

/**
 * Get all downtime reasons with caching
 *
 * @param {Object} options - Options
 * @param {boolean} options.forceRefresh - Force a fresh fetch
 * @returns {Promise<Object>} Downtime reasons response
 */
export const getDowntimeReasons = (options = {}) => {
  return referenceDataCache.get(
    'reference:downtime-reasons',
    () => api.get('/downtime-reasons'),
    {
      ttl: CACHE_TTL.DOWNTIME_REASONS,
      staleWhileRevalidate: true,
      forceRefresh: options.forceRefresh || false
    }
  )
}

/**
 * Get all clients with caching
 *
 * @param {Object} options - Options
 * @param {boolean} options.forceRefresh - Force a fresh fetch
 * @returns {Promise<Object>} Clients response
 */
export const getClients = (options = {}) => {
  return referenceDataCache.get(
    'reference:clients',
    () => api.get('/admin/clients'),
    {
      ttl: CACHE_TTL.CLIENTS,
      staleWhileRevalidate: true,
      forceRefresh: options.forceRefresh || false
    }
  )
}

/**
 * Get all defect types with caching
 *
 * @param {Object} options - Options
 * @param {boolean} options.forceRefresh - Force a fresh fetch
 * @returns {Promise<Object>} Defect types response
 */
export const getDefectTypes = (options = {}) => {
  return referenceDataCache.get(
    'reference:defect-types',
    () => api.get('/admin/defect-types'),
    {
      ttl: CACHE_TTL.DEFECT_TYPES,
      staleWhileRevalidate: true,
      forceRefresh: options.forceRefresh || false
    }
  )
}

/**
 * Invalidate all reference data caches
 * Call this after admin updates reference data
 */
export const invalidateReferenceCache = () => {
  referenceDataCache.invalidatePattern('^reference:')
}

/**
 * Invalidate specific reference data cache
 *
 * @param {string} type - Type of reference data ('products', 'shifts', 'clients', etc.)
 */
export const invalidateReferenceType = (type) => {
  referenceDataCache.invalidate(`reference:${type}`)
}

/**
 * Prefetch all reference data in background
 * Call this on app initialization to warm the cache
 */
export const prefetchReferenceData = async () => {
  // Use Promise.allSettled to continue even if some fail
  const results = await Promise.allSettled([
    getProducts(),
    getShifts(),
    getDowntimeReasons(),
    getClients()
  ])

  // Log any failures
  results.forEach((result, index) => {
    if (result.status === 'rejected') {
      const types = ['products', 'shifts', 'downtime-reasons', 'clients']
      console.warn(`[ReferenceData] Failed to prefetch ${types[index]}:`, result.reason)
    }
  })
}

/**
 * Get cache statistics for reference data
 */
export const getReferenceDataCacheStats = () => {
  return referenceDataCache.getStats()
}
