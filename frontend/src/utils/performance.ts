/**
 * Performance utilities for the KPI Operations Platform — debouncing,
 * throttling, request caching with TTL, performance monitoring, lazy
 * loading, memory-leak prevention.
 */
import { ref, onUnmounted, watch, shallowRef, type Ref, type ShallowRef } from 'vue'

// ============================================
// DEBOUNCE / THROTTLE
// ============================================

export interface DebounceOptions {
  leading?: boolean
  trailing?: boolean
  maxWait?: number
}

export interface DebouncedFn<TArgs extends unknown[], TResult> {
  (...args: TArgs): TResult | undefined
  cancel: () => void
  flush: () => TResult | undefined
  pending: () => boolean
}

export function debounce<TArgs extends unknown[], TResult>(
  func: (...args: TArgs) => TResult,
  wait: number = 300,
  options: DebounceOptions = {},
): DebouncedFn<TArgs, TResult> {
  const { leading = false, trailing = true } = options
  let timeoutId: ReturnType<typeof setTimeout> | null = null
  let lastArgs: TArgs | null = null
  let lastThis: unknown = null
  let result: TResult | undefined
  let lastCallTime = 0
  let lastInvokeTime = 0

  function invokeFunc(time: number): TResult | undefined {
    const args = lastArgs
    const thisArg = lastThis
    lastArgs = null
    lastThis = null
    lastInvokeTime = time
    if (args !== null) {
      result = func.apply(thisArg, args)
    }
    return result
  }

  function shouldInvoke(time: number): boolean {
    const timeSinceLastCall = time - lastCallTime
    const timeSinceLastInvoke = time - lastInvokeTime

    return (
      lastCallTime === 0 ||
      timeSinceLastCall >= wait ||
      timeSinceLastCall < 0 ||
      timeSinceLastInvoke >= wait
    )
  }

  function trailingEdge(time: number): TResult | undefined {
    timeoutId = null
    if (trailing && lastArgs) {
      return invokeFunc(time)
    }
    lastArgs = null
    lastThis = null
    return result
  }

  function timerExpired(): TResult | undefined {
    const time = Date.now()
    if (shouldInvoke(time)) {
      return trailingEdge(time)
    }
    timeoutId = setTimeout(timerExpired, wait - (time - lastCallTime))
    return result
  }

  function leadingEdge(time: number): TResult | undefined {
    lastInvokeTime = time
    timeoutId = setTimeout(timerExpired, wait)
    return leading ? invokeFunc(time) : result
  }

  const debounced = function (this: unknown, ...args: TArgs): TResult | undefined {
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
  } as DebouncedFn<TArgs, TResult>

  debounced.cancel = function (): void {
    if (timeoutId !== null) {
      clearTimeout(timeoutId)
    }
    lastArgs = null
    lastThis = null
    lastCallTime = 0
    lastInvokeTime = 0
    timeoutId = null
  }

  debounced.flush = function (): TResult | undefined {
    if (timeoutId !== null) {
      return trailingEdge(Date.now())
    }
    return result
  }

  debounced.pending = function (): boolean {
    return timeoutId !== null
  }

  return debounced
}

export function throttle<TArgs extends unknown[], TResult>(
  func: (...args: TArgs) => TResult,
  wait: number = 100,
  options: DebounceOptions = {},
): DebouncedFn<TArgs, TResult> {
  const { leading = true, trailing = true } = options
  return debounce(func, wait, { leading, trailing, maxWait: wait })
}

// ============================================
// REQUEST CACHE MANAGER
// ============================================

export interface RequestCacheOptions<T = unknown> {
  defaultTTL?: number
  maxSize?: number
  onEvict?: ((key: string, data: T) => void) | null
}

export interface CacheGetOptions {
  ttl?: number
  staleWhileRevalidate?: boolean
  forceRefresh?: boolean
}

interface CacheEntry<T = unknown> {
  data: T
  expiresAt: number
  createdAt: number
}

export interface CacheStatsEntry {
  key: string
  expiresIn: number
  isExpired: boolean
  age: number
}

export interface CacheStats {
  size: number
  pendingRequests: number
  entries: CacheStatsEntry[]
}

export class RequestCacheManager {
  // The cache is keyed by string and holds heterogeneous payloads
  // (each call site has its own type). `get<T>()` is generic so
  // the caller's fetcher inference flows through; the underlying
  // store is `unknown`.
  private cache: Map<string, CacheEntry<unknown>>
  private pendingRequests: Map<string, Promise<unknown>>
  private defaultTTL: number
  private maxSize: number
  private onEvict: ((key: string, data: unknown) => void) | null

  constructor(options: RequestCacheOptions<unknown> = {}) {
    this.cache = new Map()
    this.pendingRequests = new Map()
    this.defaultTTL = options.defaultTTL || 5 * 60 * 1000
    this.maxSize = options.maxSize || 100
    this.onEvict = options.onEvict || null
  }

  async get<T>(
    key: string,
    fetcher: () => Promise<T>,
    options: CacheGetOptions = {},
  ): Promise<T> {
    const { ttl = this.defaultTTL, staleWhileRevalidate = false, forceRefresh = false } = options

    const cached = this.cache.get(key)
    const now = Date.now()

    if (cached && !forceRefresh) {
      const isExpired = now > cached.expiresAt

      if (!isExpired) {
        return cached.data as T
      }

      if (staleWhileRevalidate && cached.data !== undefined) {
        this._revalidateInBackground(key, fetcher, ttl)
        return cached.data as T
      }
    }

    const pending = this.pendingRequests.get(key)
    if (pending) {
      return pending as Promise<T>
    }

    const fetchPromise = this._fetchAndCache(key, fetcher, ttl)
    this.pendingRequests.set(key, fetchPromise)

    try {
      return await fetchPromise
    } finally {
      this.pendingRequests.delete(key)
    }
  }

  private async _fetchAndCache<T>(
    key: string,
    fetcher: () => Promise<T>,
    ttl: number,
  ): Promise<T> {
    try {
      const data = await fetcher()
      this._set(key, data, ttl)
      return data
    } catch (error) {
      const cached = this.cache.get(key)
      if (cached && cached.data !== undefined) {
        // eslint-disable-next-line no-console
        console.warn(`[RequestCache] Error fetching ${key}, returning stale data:`, error)
        return cached.data as T
      }
      throw error
    }
  }

  private _revalidateInBackground<T>(
    key: string,
    fetcher: () => Promise<T>,
    ttl: number,
  ): void {
    if (this.pendingRequests.has(key)) {
      return
    }

    const revalidatePromise: Promise<T> = fetcher()
      .then((data) => {
        this._set(key, data, ttl)
        return data
      })
      .catch((error) => {
        // eslint-disable-next-line no-console
        console.warn(`[RequestCache] Background revalidation failed for ${key}:`, error)
        return undefined as unknown as T
      })
      .finally(() => {
        this.pendingRequests.delete(key)
      })

    this.pendingRequests.set(key, revalidatePromise)
  }

  private _set<T>(key: string, data: T, ttl: number): void {
    if (this.cache.size >= this.maxSize && !this.cache.has(key)) {
      const oldestKey = this.cache.keys().next().value
      if (oldestKey !== undefined) this._evict(oldestKey)
    }

    this.cache.delete(key)
    this.cache.set(key, {
      data,
      expiresAt: Date.now() + ttl,
      createdAt: Date.now(),
    })
  }

  private _evict(key: string): void {
    const entry = this.cache.get(key)
    this.cache.delete(key)
    if (this.onEvict && entry) {
      this.onEvict(key, entry.data)
    }
  }

  invalidate(key: string): void {
    this.cache.delete(key)
    this.pendingRequests.delete(key)
  }

  invalidatePattern(pattern: string): void {
    const regex = new RegExp(pattern)
    for (const key of this.cache.keys()) {
      if (regex.test(key)) {
        this.invalidate(key)
      }
    }
  }

  clear(): void {
    this.cache.clear()
    this.pendingRequests.clear()
  }

  getStats(): CacheStats {
    const entries = Array.from(this.cache.entries())
    const now = Date.now()

    return {
      size: this.cache.size,
      pendingRequests: this.pendingRequests.size,
      entries: entries.map(([key, entry]) => ({
        key,
        expiresIn: Math.max(0, entry.expiresAt - now),
        isExpired: now > entry.expiresAt,
        age: now - entry.createdAt,
      })),
    }
  }
}

export const referenceDataCache = new RequestCacheManager({
  defaultTTL: 5 * 60 * 1000,
  maxSize: 50,
})

// ============================================
// PERFORMANCE MONITORING
// ============================================

export interface PerformanceMonitorOptions {
  enabled?: boolean
  sampleRate?: number
  maxMetrics?: number
}

export interface MeasureHandle {
  id: string
  name: string
  startTime: number
}

export interface MeasureResult {
  name: string
  duration: number
  timestamp: number
}

export interface AggregatedMetric {
  name: string
  count: number
  avg: number
  min: number
  max: number
  p50: number
  p95: number
  p99: number
}

interface MetricBucket {
  count: number
  total: number
  min: number
  max: number
  samples: number[]
}

export class PerformanceMonitor {
  private enabled: boolean
  private sampleRate: number
  private metrics: Map<string, MetricBucket>
  private maxMetrics: number

  constructor(options: PerformanceMonitorOptions = {}) {
    this.enabled = options.enabled !== false
    this.sampleRate = options.sampleRate || 1.0
    this.metrics = new Map()
    this.maxMetrics = options.maxMetrics || 1000
  }

  startMeasure(name: string): MeasureHandle | null {
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
      startTime: performance.now(),
    }
  }

  endMeasure(measure: MeasureHandle | null): MeasureResult | null {
    if (!measure) return null

    const endTime = performance.now()
    const duration = endTime - measure.startTime

    if (typeof performance !== 'undefined' && performance.mark) {
      performance.mark(`${measure.id}-end`)
      try {
        performance.measure(measure.name, `${measure.id}-start`, `${measure.id}-end`)
      } catch {
        // Ignore if marks don't exist
      }
    }

    this._recordMetric(measure.name, duration)

    return {
      name: measure.name,
      duration,
      timestamp: Date.now(),
    }
  }

  async measureAsync<T>(name: string, fn: () => Promise<T>): Promise<T> {
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

  private _recordMetric(name: string, duration: number): void {
    if (!this.metrics.has(name)) {
      this.metrics.set(name, {
        count: 0,
        total: 0,
        min: Infinity,
        max: -Infinity,
        samples: [],
      })
    }

    const metric = this.metrics.get(name)!
    metric.count++
    metric.total += duration
    metric.min = Math.min(metric.min, duration)
    metric.max = Math.max(metric.max, duration)

    metric.samples.push(duration)
    if (metric.samples.length > 100) {
      metric.samples.shift()
    }

    if (this.metrics.size > this.maxMetrics) {
      const oldestKey = this.metrics.keys().next().value
      if (oldestKey !== undefined) this.metrics.delete(oldestKey)
    }
  }

  getMetrics(name: string): AggregatedMetric | null {
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
      p99: sorted[p99Index] || 0,
    }
  }

  getAllMetrics(): Record<string, AggregatedMetric> {
    const result: Record<string, AggregatedMetric> = {}
    for (const name of this.metrics.keys()) {
      const metric = this.getMetrics(name)
      if (metric) result[name] = metric
    }
    return result
  }

  clear(): void {
    this.metrics.clear()
    if (typeof performance !== 'undefined' && performance.clearMarks) {
      performance.clearMarks()
      performance.clearMeasures()
    }
  }

  logReport(): void {
    const metrics = this.getAllMetrics()
    // eslint-disable-next-line no-console
    console.group('[Performance Report]')

    const sorted = Object.entries(metrics).sort(([, a], [, b]) => b.avg - a.avg)

    for (const [name, data] of sorted) {
      // eslint-disable-next-line no-console
      console.log(
        `${name}: avg=${data.avg.toFixed(2)}ms, ` +
          `p95=${data.p95.toFixed(2)}ms, ` +
          `count=${data.count}`,
      )
    }

    // eslint-disable-next-line no-console
    console.groupEnd()
  }
}

// `process.env.NODE_ENV` was the JS-original way to detect dev mode;
// switched to `import.meta.env.DEV` when porting i18n in slice 10
// for consistency with Vite's canonical API.
export const performanceMonitor = new PerformanceMonitor({
  enabled: import.meta.env.DEV,
  sampleRate: 0.1,
})

// ============================================
// VUE COMPOSABLES
// ============================================

export function useDebouncedRef<T>(initialValue: T, delay: number = 300) {
  const value = ref(initialValue) as Ref<T>
  const debouncedValue = ref(initialValue) as Ref<T>

  const updateDebounced = debounce((newValue: T) => {
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
    debouncedValue,
  }
}

export function useThrottledCallback<TArgs extends unknown[]>(
  callback: (...args: TArgs) => void,
  limit: number = 100,
) {
  const throttledFn = throttle(callback, limit)

  onUnmounted(() => {
    throttledFn.cancel()
  })

  return throttledFn
}

export interface UseCachedDataOptions {
  ttl?: number
  staleWhileRevalidate?: boolean
  immediate?: boolean
}

export function useCachedData<T>(
  cacheKey: string,
  fetcher: () => Promise<T>,
  options: UseCachedDataOptions = {},
) {
  const { ttl = 5 * 60 * 1000, staleWhileRevalidate = true, immediate = true } = options

  const data: ShallowRef<T | null> = shallowRef(null)
  const loading = ref(false)
  const error = ref<unknown | null>(null)

  async function fetchData(forceRefresh: boolean = false): Promise<T | null> {
    loading.value = true
    error.value = null

    try {
      const result = await referenceDataCache.get<T>(cacheKey, fetcher, {
        ttl,
        staleWhileRevalidate,
        forceRefresh,
      })
      data.value = result
      return result
    } catch (e) {
      error.value = e
      // eslint-disable-next-line no-console
      console.error(`[useCachedData] Error fetching ${cacheKey}:`, e)
      return null
    } finally {
      loading.value = false
    }
  }

  function refresh(): Promise<T | null> {
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
    fetch: fetchData,
  }
}

export function useRenderPerformance(componentName: string) {
  let measure: MeasureHandle | null = null

  function startRender(): void {
    measure = performanceMonitor.startMeasure(`render:${componentName}`)
  }

  function endRender(): void {
    if (measure) {
      const result = performanceMonitor.endMeasure(measure)
      if (result && result.duration > 100) {
        // eslint-disable-next-line no-console
        console.warn(
          `[Performance] Slow render detected: ${componentName} took ${result.duration.toFixed(2)}ms`,
        )
      }
    }
  }

  return {
    startRender,
    endRender,
  }
}

// ============================================
// LAZY LOADING
// ============================================

export interface LazyLoadOptions {
  delay?: number
  timeout?: number
  loadingComponent?: unknown | null
  errorComponent?: unknown | null
}

export interface LazyComponentDefinition {
  loader: () => Promise<unknown>
  delay: number
  timeout: number
  loadingComponent: unknown | null
  errorComponent: unknown | null
  onError: (
    error: unknown,
    retry: () => void,
    fail: () => void,
    attempts: number,
  ) => void
}

export function lazyLoadComponent(
  importFn: () => Promise<unknown>,
  options: LazyLoadOptions = {},
): LazyComponentDefinition {
  const {
    delay = 200,
    timeout = 10000,
    loadingComponent = null,
    errorComponent = null,
  } = options

  return {
    loader: importFn,
    delay,
    timeout,
    loadingComponent,
    errorComponent,
    onError(error, retry, fail, attempts) {
      if (attempts <= 3) {
        // eslint-disable-next-line no-console
        console.warn(`[LazyLoad] Retry attempt ${attempts}:`, error)
        retry()
      } else {
        // eslint-disable-next-line no-console
        console.error('[LazyLoad] Failed to load component:', error)
        fail()
      }
    },
  }
}

export function preloadComponent(importFn: () => Promise<unknown>): void {
  if (typeof requestIdleCallback !== 'undefined') {
    requestIdleCallback(() => {
      importFn().catch((err) => {
        // eslint-disable-next-line no-console
        console.warn('[Preload] Failed to preload component:', err)
      })
    })
  } else {
    setTimeout(() => {
      importFn().catch((err) => {
        // eslint-disable-next-line no-console
        console.warn('[Preload] Failed to preload component:', err)
      })
    }, 100)
  }
}

// ============================================
// MEMORY LEAK PREVENTION
// ============================================

export function useAbortController(): AbortController {
  const controller = new AbortController()

  onUnmounted(() => {
    controller.abort()
  })

  return controller
}

export interface CleanupRegistry {
  register: (fn: () => void) => void
  cleanup: () => void
}

export function useCleanup(): CleanupRegistry {
  const cleanupFns: (() => void)[] = []

  function register(fn: () => void): void {
    cleanupFns.push(fn)
  }

  function cleanup(): void {
    cleanupFns.forEach((fn) => {
      try {
        fn()
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn('[Cleanup] Error during cleanup:', e)
      }
    })
    cleanupFns.length = 0
  }

  onUnmounted(cleanup)

  return {
    register,
    cleanup,
  }
}

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
  useCleanup,
}
