/**
 * Performance utilities for the KPI Operations Platform
 *
 * Provides debouncing, throttling, request caching, and performance monitoring
 * optimized for manufacturing floor environments with mobile devices.
 */

// ============================================
// DEBOUNCE / THROTTLE UTILITIES
// ============================================

/**
 * Creates a debounced function that delays invoking func until after wait
 * milliseconds have elapsed since the last time the debounced function was invoked.
 *
 * @param {Function} func - The function to debounce
 * @param {number} wait - The number of milliseconds to delay (default: 300ms)
 * @param {Object} options - Options object
 * @param {boolean} options.leading - Invoke on the leading edge (default: false)
 * @param {boolean} options.trailing - Invoke on the trailing edge (default: true)
 * @returns {Function} The debounced function with cancel() and flush() methods
 *
 * @example
 * // Debounce search input (300ms default)
 * const debouncedSearch = debounce((query) => api.search(query))
 *
 * // Debounce with immediate execution on first call
 * const debouncedSave = debounce(save, 500, { leading: true })
 */
export function debounce(func, wait = 300, options = {}) {
  const { leading = false, trailing = true } = options
  let timeoutId = null
  let lastArgs = null
  let lastThis = null
  let result = null
  let lastCallTime = 0
  let lastInvokeTime = 0

  function invokeFunc(time) {
    const args = lastArgs
    const thisArg = lastThis
    lastArgs = null
    lastThis = null
    lastInvokeTime = time
    result = func.apply(thisArg, args)
    return result
  }

  function shouldInvoke(time) {
    const timeSinceLastCall = time - lastCallTime
    const timeSinceLastInvoke = time - lastInvokeTime

    return (
      lastCallTime === 0 ||
      timeSinceLastCall >= wait ||
      timeSinceLastCall < 0 ||
      timeSinceLastInvoke >= wait
    )
  }

  function trailingEdge(time) {
    timeoutId = null
    if (trailing && lastArgs) {
      return invokeFunc(time)
    }
    lastArgs = null
    lastThis = null
    return result
  }

  function timerExpired() {
    const time = Date.now()
    if (shouldInvoke(time)) {
      return trailingEdge(time)
    }
    timeoutId = setTimeout(timerExpired, wait - (time - lastCallTime))
  }

  function leadingEdge(time) {
    lastInvokeTime = time
    timeoutId = setTimeout(timerExpired, wait)
    return leading ? invokeFunc(time) : result
  }

  function debounced(...args) {
    const time = Date.now()
    const isInvoking = shouldInvoke(time)

    lastArgs = args
    lastThis = this
    lastCallTime = time

    if (isInvoking) {
      if (timeoutId === null) {
        return leadingEdge(time)
      }
      if (leading) {
        timeoutId = setTimeout(timerExpired, wait)
        return invokeFunc(time)
      }
    }
    if (timeoutId === null) {
      timeoutId = setTimeout(timerExpired, wait)
    }
    return result
  }

  debounced.cancel = function() {
    if (timeoutId !== null) {
      clearTimeout(timeoutId)
    }
    lastArgs = null
    lastThis = null
    lastCallTime = 0
    lastInvokeTime = 0
    timeoutId = null
  }

  debounced.flush = function() {
    if (timeoutId !== null) {
      return trailingEdge(Date.now())
    }
    return result
  }

  debounced.pending = function() {
    return timeoutId !== null
  }

  return debounced
}

/**
 * Creates a throttled function that only invokes func at most once per every
 * wait milliseconds. Useful for scroll/resize handlers and rate limiting.
 *
 * @param {Function} func - The function to throttle
 * @param {number} wait - The number of milliseconds to throttle (default: 100ms)
 * @param {Object} options - Options object
 * @param {boolean} options.leading - Invoke on the leading edge (default: true)
 * @param {boolean} options.trailing - Invoke on the trailing edge (default: true)
 * @returns {Function} The throttled function with cancel() method
 *
 * @example
 * // Throttle scroll handler
 * const throttledScroll = throttle(handleScroll, 100)
 * window.addEventListener('scroll', throttledScroll)
 */
export function throttle(func, wait = 100, options = {}) {
  const { leading = true, trailing = true } = options
  return debounce(func, wait, { leading, trailing, maxWait: wait })
}

// ============================================
// REQUEST CACHE MANAGER
// ============================================

/**
 * Request cache manager for API calls with TTL and stale-while-revalidate support.
 * Optimized for reference data that changes infrequently (products, shifts, clients).
 *
 * @example
 * const cache = new RequestCacheManager()
 *
 * // Cache products for 5 minutes
 * const products = await cache.get('products', () => api.getProducts(), { ttl: 5 * 60 * 1000 })
 *
 * // Use stale-while-revalidate pattern
 * const clients = await cache.get('clients', fetchClients, {
 *   ttl: 5 * 60 * 1000,
 *   staleWhileRevalidate: true
 * })
 */
export class RequestCacheManager {
  constructor(options = {}) {
    this.cache = new Map()
    this.pendingRequests = new Map()
    this.defaultTTL = options.defaultTTL || 5 * 60 * 1000 // 5 minutes default
    this.maxSize = options.maxSize || 100 // Max cached items
    this.onEvict = options.onEvict || null
  }

  /**
   * Get cached data or fetch fresh data
   *
   * @param {string} key - Cache key
   * @param {Function} fetcher - Async function to fetch data if not cached
   * @param {Object} options - Cache options
   * @param {number} options.ttl - Time-to-live in milliseconds
   * @param {boolean} options.staleWhileRevalidate - Return stale data while fetching fresh
   * @param {boolean} options.forceRefresh - Force a fresh fetch
   * @returns {Promise<any>} Cached or fetched data
   */
  async get(key, fetcher, options = {}) {
    const {
      ttl = this.defaultTTL,
      staleWhileRevalidate = false,
      forceRefresh = false
    } = options

    // Check for existing cache entry
    const cached = this.cache.get(key)
    const now = Date.now()

    // Return cached data if valid and not force refreshing
    if (cached && !forceRefresh) {
      const isExpired = now > cached.expiresAt

      if (!isExpired) {
        return cached.data
      }

      // Stale-while-revalidate: return stale data and refresh in background
      if (staleWhileRevalidate && cached.data !== undefined) {
        this._revalidateInBackground(key, fetcher, ttl)
        return cached.data
      }
    }

    // Deduplicate concurrent requests for the same key
    if (this.pendingRequests.has(key)) {
      return this.pendingRequests.get(key)
    }

    // Fetch fresh data
    const fetchPromise = this._fetchAndCache(key, fetcher, ttl)
    this.pendingRequests.set(key, fetchPromise)

    try {
      const result = await fetchPromise
      return result
    } finally {
      this.pendingRequests.delete(key)
    }
  }

  /**
   * Fetch data and store in cache
   */
  async _fetchAndCache(key, fetcher, ttl) {
    try {
      const data = await fetcher()
      this._set(key, data, ttl)
      return data
    } catch (error) {
      // On error, return stale data if available
      const cached = this.cache.get(key)
      if (cached && cached.data !== undefined) {
        console.warn(`[RequestCache] Error fetching ${key}, returning stale data:`, error)
        return cached.data
      }
      throw error
    }
  }

  /**
   * Revalidate cache entry in background without blocking
   */
  _revalidateInBackground(key, fetcher, ttl) {
    // Don't start revalidation if already pending
    if (this.pendingRequests.has(key)) {
      return
    }

    const revalidatePromise = fetcher()
      .then(data => {
        this._set(key, data, ttl)
      })
      .catch(error => {
        console.warn(`[RequestCache] Background revalidation failed for ${key}:`, error)
      })
      .finally(() => {
        this.pendingRequests.delete(key)
      })

    this.pendingRequests.set(key, revalidatePromise)
  }

  /**
   * Set cache entry with LRU eviction
   */
  _set(key, data, ttl) {
    // Enforce max size with LRU eviction
    if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
      const oldestKey = this.cache.keys().next().value
      this._evict(oldestKey)
    }

    // Delete and re-add to maintain insertion order (for LRU)
    this.cache.delete(key)
    this.cache.set(key, {
      data,
      expiresAt: Date.now() + ttl,
      createdAt: Date.now()
    })
  }

  /**
   * Evict a cache entry
   */
  _evict(key) {
    const entry = this.cache.get(key)
    this.cache.delete(key)
    if (this.onEvict && entry) {
      this.onEvict(key, entry.data)
    }
  }

  /**
   * Invalidate a specific cache key
   */
  invalidate(key) {
    this.cache.delete(key)
    this.pendingRequests.delete(key)
  }

  /**
   * Invalidate all cache entries matching a pattern
   */
  invalidatePattern(pattern) {
    const regex = new RegExp(pattern)
    for (const key of this.cache.keys()) {
      if (regex.test(key)) {
        this.invalidate(key)
      }
    }
  }

  /**
   * Clear entire cache
   */
  clear() {
    this.cache.clear()
    this.pendingRequests.clear()
  }

  /**
   * Get cache statistics
   */
  getStats() {
    const entries = Array.from(this.cache.entries())
    const now = Date.now()

    return {
      size: this.cache.size,
      pendingRequests: this.pendingRequests.size,
      entries: entries.map(([key, entry]) => ({
        key,
        expiresIn: Math.max(0, entry.expiresAt - now),
        isExpired: now > entry.expiresAt,
        age: now - entry.createdAt
      }))
    }
  }
}

// Global cache instance for reference data
export const referenceDataCache = new RequestCacheManager({
  defaultTTL: 5 * 60 * 1000, // 5 minutes for reference data
  maxSize: 50
})

// ============================================
// PERFORMANCE MONITORING
// ============================================

/**
 * Performance monitoring utilities for tracking component render times,
 * API call durations, and identifying bottlenecks.
 */
export class PerformanceMonitor {
  constructor(options = {}) {
    this.enabled = options.enabled !== false
    this.sampleRate = options.sampleRate || 1.0 // 100% by default
    this.metrics = new Map()
    this.maxMetrics = options.maxMetrics || 1000
  }

  /**
   * Mark the start of a performance measurement
   */
  startMeasure(name) {
    if (!this.enabled || Math.random() > this.sampleRate) {
      return null
    }

    const id = `${name}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

    if (typeof performance !== 'undefined' && performance.mark) {
      performance.mark(`${id}-start`)
    }

    return {
      id,
      name,
      startTime: performance.now()
    }
  }

  /**
   * End a performance measurement and record the result
   */
  endMeasure(measure) {
    if (!measure) return null

    const endTime = performance.now()
    const duration = endTime - measure.startTime

    if (typeof performance !== 'undefined' && performance.mark) {
      performance.mark(`${measure.id}-end`)
      try {
        performance.measure(measure.name, `${measure.id}-start`, `${measure.id}-end`)
      } catch (e) {
        // Ignore if marks don't exist
      }
    }

    this._recordMetric(measure.name, duration)

    return {
      name: measure.name,
      duration,
      timestamp: Date.now()
    }
  }

  /**
   * Measure an async operation
   */
  async measureAsync(name, fn) {
    const measure = this.startMeasure(name)
    try {
      const result = await fn()
      this.endMeasure(measure)
      return result
    } catch (error) {
      this.endMeasure(measure)
      throw error
    }
  }

  /**
   * Record a metric
   */
  _recordMetric(name, duration) {
    if (!this.metrics.has(name)) {
      this.metrics.set(name, {
        count: 0,
        total: 0,
        min: Infinity,
        max: -Infinity,
        samples: []
      })
    }

    const metric = this.metrics.get(name)
    metric.count++
    metric.total += duration
    metric.min = Math.min(metric.min, duration)
    metric.max = Math.max(metric.max, duration)

    // Keep last N samples for percentile calculations
    metric.samples.push(duration)
    if (metric.samples.length > 100) {
      metric.samples.shift()
    }

    // Cleanup old metrics if too many
    if (this.metrics.size > this.maxMetrics) {
      const oldestKey = this.metrics.keys().next().value
      this.metrics.delete(oldestKey)
    }
  }

  /**
   * Get aggregated metrics for a measurement name
   */
  getMetrics(name) {
    const metric = this.metrics.get(name)
    if (!metric) return null

    const sorted = [...metric.samples].sort((a, b) => a - b)
    const p50Index = Math.floor(sorted.length * 0.5)
    const p95Index = Math.floor(sorted.length * 0.95)
    const p99Index = Math.floor(sorted.length * 0.99)

    return {
      name,
      count: metric.count,
      avg: metric.total / metric.count,
      min: metric.min,
      max: metric.max,
      p50: sorted[p50Index] || 0,
      p95: sorted[p95Index] || 0,
      p99: sorted[p99Index] || 0
    }
  }

  /**
   * Get all recorded metrics
   */
  getAllMetrics() {
    const result = {}
    for (const name of this.metrics.keys()) {
      result[name] = this.getMetrics(name)
    }
    return result
  }

  /**
   * Clear all metrics
   */
  clear() {
    this.metrics.clear()
    if (typeof performance !== 'undefined' && performance.clearMarks) {
      performance.clearMarks()
      performance.clearMeasures()
    }
  }

  /**
   * Log a performance report to console
   */
  logReport() {
    const metrics = this.getAllMetrics()
    console.group('[Performance Report]')

    // Sort by average duration (slowest first)
    const sorted = Object.entries(metrics)
      .sort(([, a], [, b]) => b.avg - a.avg)

    for (const [name, data] of sorted) {
      console.log(
        `${name}: avg=${data.avg.toFixed(2)}ms, ` +
        `p95=${data.p95.toFixed(2)}ms, ` +
        `count=${data.count}`
      )
    }

    console.groupEnd()
  }
}

// Global performance monitor instance
export const performanceMonitor = new PerformanceMonitor({
  enabled: process.env.NODE_ENV !== 'production',
  sampleRate: 0.1 // Sample 10% in development
})

// ============================================
// VUE COMPOSABLES FOR PERFORMANCE
// ============================================

import { ref, onUnmounted, watch, shallowRef } from 'vue'

/**
 * Composable for debounced refs - useful for search inputs
 *
 * @param {any} initialValue - Initial value
 * @param {number} delay - Debounce delay in milliseconds
 * @returns {Object} { value, debouncedValue }
 *
 * @example
 * const { value: searchQuery, debouncedValue } = useDebouncedRef('', 300)
 *
 * watch(debouncedValue, (query) => {
 *   api.search(query)
 * })
 */
export function useDebouncedRef(initialValue, delay = 300) {
  const value = ref(initialValue)
  const debouncedValue = ref(initialValue)

  const updateDebounced = debounce((newValue) => {
    debouncedValue.value = newValue
  }, delay)

  watch(value, (newValue) => {
    updateDebounced(newValue)
  })

  onUnmounted(() => {
    updateDebounced.cancel()
  })

  return {
    value,
    debouncedValue
  }
}

/**
 * Composable for throttled callbacks - useful for scroll/resize handlers
 *
 * @param {Function} callback - Function to throttle
 * @param {number} limit - Throttle limit in milliseconds
 * @returns {Function} Throttled function (auto-cleaned up on unmount)
 *
 * @example
 * const throttledScroll = useThrottledCallback(handleScroll, 100)
 * onMounted(() => window.addEventListener('scroll', throttledScroll))
 */
export function useThrottledCallback(callback, limit = 100) {
  const throttledFn = throttle(callback, limit)

  onUnmounted(() => {
    throttledFn.cancel()
  })

  return throttledFn
}

/**
 * Composable for cached API data with automatic refresh
 *
 * @param {string} cacheKey - Unique cache key
 * @param {Function} fetcher - Async function to fetch data
 * @param {Object} options - Options for caching behavior
 * @returns {Object} { data, loading, error, refresh }
 *
 * @example
 * const { data: products, loading, refresh } = useCachedData(
 *   'products',
 *   () => api.getProducts(),
 *   { ttl: 5 * 60 * 1000 }
 * )
 */
export function useCachedData(cacheKey, fetcher, options = {}) {
  const {
    ttl = 5 * 60 * 1000,
    staleWhileRevalidate = true,
    immediate = true
  } = options

  const data = shallowRef(null)
  const loading = ref(false)
  const error = ref(null)

  async function fetchData(forceRefresh = false) {
    loading.value = true
    error.value = null

    try {
      const result = await referenceDataCache.get(cacheKey, fetcher, {
        ttl,
        staleWhileRevalidate,
        forceRefresh
      })
      data.value = result
      return result
    } catch (e) {
      error.value = e
      console.error(`[useCachedData] Error fetching ${cacheKey}:`, e)
      return null
    } finally {
      loading.value = false
    }
  }

  function refresh() {
    return fetchData(true)
  }

  if (immediate) {
    fetchData()
  }

  return {
    data,
    loading,
    error,
    refresh,
    fetch: fetchData
  }
}

/**
 * Composable for measuring component render performance
 *
 * @param {string} componentName - Name of the component
 * @returns {Object} { startRender, endRender }
 *
 * @example
 * const { startRender, endRender } = useRenderPerformance('KPIDashboard')
 *
 * onBeforeMount(() => startRender())
 * onMounted(() => endRender())
 */
export function useRenderPerformance(componentName) {
  let measure = null

  function startRender() {
    measure = performanceMonitor.startMeasure(`render:${componentName}`)
  }

  function endRender() {
    if (measure) {
      const result = performanceMonitor.endMeasure(measure)
      if (result && result.duration > 100) {
        console.warn(
          `[Performance] Slow render detected: ${componentName} took ${result.duration.toFixed(2)}ms`
        )
      }
    }
  }

  return {
    startRender,
    endRender
  }
}

// ============================================
// LAZY LOADING UTILITIES
// ============================================

/**
 * Lazy load a heavy component only when needed
 *
 * @param {Function} importFn - Dynamic import function
 * @param {Object} options - Loading options
 * @returns {Object} Vue async component definition
 *
 * @example
 * const LazyChart = lazyLoadComponent(
 *   () => import('vue-chartjs'),
 *   { delay: 200 }
 * )
 */
export function lazyLoadComponent(importFn, options = {}) {
  const {
    delay = 200,
    timeout = 10000,
    loadingComponent = null,
    errorComponent = null
  } = options

  return {
    loader: importFn,
    delay,
    timeout,
    loadingComponent,
    errorComponent,
    onError(error, retry, fail, attempts) {
      if (attempts <= 3) {
        console.warn(`[LazyLoad] Retry attempt ${attempts}:`, error)
        retry()
      } else {
        console.error('[LazyLoad] Failed to load component:', error)
        fail()
      }
    }
  }
}

/**
 * Preload a component in the background (during idle time)
 *
 * @param {Function} importFn - Dynamic import function
 *
 * @example
 * // Preload chart component when user hovers over dashboard
 * preloadComponent(() => import('vue-chartjs'))
 */
export function preloadComponent(importFn) {
  if (typeof requestIdleCallback !== 'undefined') {
    requestIdleCallback(() => {
      importFn().catch(err => {
        console.warn('[Preload] Failed to preload component:', err)
      })
    })
  } else {
    setTimeout(() => {
      importFn().catch(err => {
        console.warn('[Preload] Failed to preload component:', err)
      })
    }, 100)
  }
}

// ============================================
// MEMORY LEAK PREVENTION
// ============================================

/**
 * Create an AbortController that auto-aborts on component unmount
 *
 * @returns {AbortController} Controller that cancels on unmount
 *
 * @example
 * const controller = useAbortController()
 *
 * async function fetchData() {
 *   const response = await fetch(url, { signal: controller.signal })
 * }
 */
export function useAbortController() {
  const controller = new AbortController()

  onUnmounted(() => {
    controller.abort()
  })

  return controller
}

/**
 * Create a cleanup registry for manual cleanup tasks
 *
 * @returns {Object} { register, cleanup }
 *
 * @example
 * const { register } = useCleanup()
 *
 * onMounted(() => {
 *   const timer = setInterval(tick, 1000)
 *   register(() => clearInterval(timer))
 * })
 */
export function useCleanup() {
  const cleanupFns = []

  function register(fn) {
    cleanupFns.push(fn)
  }

  function cleanup() {
    cleanupFns.forEach(fn => {
      try {
        fn()
      } catch (e) {
        console.warn('[Cleanup] Error during cleanup:', e)
      }
    })
    cleanupFns.length = 0
  }

  onUnmounted(cleanup)

  return {
    register,
    cleanup
  }
}

// ============================================
// EXPORT DEFAULT INSTANCES
// ============================================

export default {
  debounce,
  throttle,
  RequestCacheManager,
  referenceDataCache,
  PerformanceMonitor,
  performanceMonitor,
  useDebouncedRef,
  useThrottledCallback,
  useCachedData,
  useRenderPerformance,
  lazyLoadComponent,
  preloadComponent,
  useAbortController,
  useCleanup
}
