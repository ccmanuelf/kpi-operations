import api from './client'
// `referenceDataCache` is exported from the still-JS performance util;
// shimmed as `any` until that module is ported.
import { referenceDataCache } from '@/utils/performance'

const CACHE_TTL = {
  PRODUCTS: 10 * 60 * 1000,
  SHIFTS: 30 * 60 * 1000,
  DOWNTIME_REASONS: 30 * 60 * 1000,
  CLIENTS: 10 * 60 * 1000,
  DEFECT_TYPES: 30 * 60 * 1000,
} as const

interface CacheOptions {
  forceRefresh?: boolean
}

export const getProducts = (options: CacheOptions = {}) => {
  return referenceDataCache.get('reference:products', () => api.get('/products'), {
    ttl: CACHE_TTL.PRODUCTS,
    staleWhileRevalidate: true,
    forceRefresh: options.forceRefresh || false,
  })
}

export const getShifts = (options: CacheOptions = {}) => {
  return referenceDataCache.get('reference:shifts', () => api.get('/shifts'), {
    ttl: CACHE_TTL.SHIFTS,
    staleWhileRevalidate: true,
    forceRefresh: options.forceRefresh || false,
  })
}

export const getDowntimeReasons = (options: CacheOptions = {}) => {
  return referenceDataCache.get('reference:downtime-reasons', () => api.get('/downtime-reasons'), {
    ttl: CACHE_TTL.DOWNTIME_REASONS,
    staleWhileRevalidate: true,
    forceRefresh: options.forceRefresh || false,
  })
}

export const getClients = (options: CacheOptions = {}) => {
  return referenceDataCache.get('reference:clients', () => api.get('/admin/clients'), {
    ttl: CACHE_TTL.CLIENTS,
    staleWhileRevalidate: true,
    forceRefresh: options.forceRefresh || false,
  })
}

export const getDefectTypes = (options: CacheOptions = {}) => {
  return referenceDataCache.get('reference:defect-types', () => api.get('/admin/defect-types'), {
    ttl: CACHE_TTL.DEFECT_TYPES,
    staleWhileRevalidate: true,
    forceRefresh: options.forceRefresh || false,
  })
}

export const invalidateReferenceCache = () => {
  referenceDataCache.invalidatePattern('^reference:')
}

export const invalidateReferenceType = (type: string) => {
  referenceDataCache.invalidate(`reference:${type}`)
}

export const prefetchReferenceData = async () => {
  const results = await Promise.allSettled([
    getProducts(),
    getShifts(),
    getDowntimeReasons(),
    getClients(),
  ])

  results.forEach((result, index) => {
    if (result.status === 'rejected') {
      const types = ['products', 'shifts', 'downtime-reasons', 'clients']
      // eslint-disable-next-line no-console
      console.warn(`[ReferenceData] Failed to prefetch ${types[index]}:`, result.reason)
    }
  })
}

export const getReferenceDataCacheStats = () => {
  return referenceDataCache.getStats()
}
