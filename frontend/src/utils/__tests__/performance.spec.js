/**
 * Performance Utilities Tests
 *
 * Tests for debounce, throttle, request caching, and performance monitoring.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  debounce,
  throttle,
  RequestCacheManager,
  PerformanceMonitor
} from '../performance'

describe('Performance Utilities', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('debounce', () => {
    it('should delay function execution', () => {
      const fn = vi.fn()
      const debouncedFn = debounce(fn, 300)

      debouncedFn()
      expect(fn).not.toHaveBeenCalled()

      vi.advanceTimersByTime(299)
      expect(fn).not.toHaveBeenCalled()

      vi.advanceTimersByTime(1)
      expect(fn).toHaveBeenCalledTimes(1)
    })

    it('should only execute once for rapid calls', () => {
      const fn = vi.fn()
      const debouncedFn = debounce(fn, 300)

      // Call multiple times rapidly
      debouncedFn('a')
      debouncedFn('b')
      debouncedFn('c')

      // Should not have been called yet
      vi.advanceTimersByTime(299)
      expect(fn).toHaveBeenCalledTimes(0)

      // After wait period, should be called once with last args
      vi.advanceTimersByTime(1)
      expect(fn).toHaveBeenCalledTimes(1)
      expect(fn).toHaveBeenCalledWith('c')
    })

    it('should execute immediately with leading option', () => {
      const fn = vi.fn()
      const debouncedFn = debounce(fn, 300, { leading: true })

      debouncedFn()
      expect(fn).toHaveBeenCalledTimes(1)

      // Subsequent calls during wait should be debounced
      debouncedFn()
      debouncedFn()
      expect(fn).toHaveBeenCalledTimes(1)
    })

    it('should have cancel method', () => {
      const fn = vi.fn()
      const debouncedFn = debounce(fn, 300)

      debouncedFn()
      debouncedFn.cancel()
      vi.advanceTimersByTime(500)

      expect(fn).not.toHaveBeenCalled()
    })

    it('should have flush method', () => {
      const fn = vi.fn()
      const debouncedFn = debounce(fn, 300)

      debouncedFn('arg1', 'arg2')
      debouncedFn.flush()

      expect(fn).toHaveBeenCalledTimes(1)
      expect(fn).toHaveBeenCalledWith('arg1', 'arg2')
    })

    it('should pass arguments correctly', () => {
      const fn = vi.fn()
      const debouncedFn = debounce(fn, 300)

      debouncedFn('a', 'b', 'c')
      vi.advanceTimersByTime(300)

      expect(fn).toHaveBeenCalledWith('a', 'b', 'c')
    })
  })

  describe('throttle', () => {
    it('should limit function execution rate', () => {
      const fn = vi.fn()
      const throttledFn = throttle(fn, 100)

      throttledFn()
      expect(fn).toHaveBeenCalledTimes(1)

      throttledFn()
      throttledFn()
      expect(fn).toHaveBeenCalledTimes(1)

      vi.advanceTimersByTime(100)
      expect(fn).toHaveBeenCalledTimes(2)
    })
  })

  describe('RequestCacheManager', () => {
    it('should cache successful requests', async () => {
      vi.useRealTimers()

      const cache = new RequestCacheManager({ defaultTTL: 5000 })
      const fetcher = vi.fn().mockResolvedValue({ data: 'test' })

      const result1 = await cache.get('key', fetcher)
      const result2 = await cache.get('key', fetcher)

      expect(fetcher).toHaveBeenCalledTimes(1)
      expect(result1).toEqual({ data: 'test' })
      expect(result2).toEqual({ data: 'test' })
    })

    it('should deduplicate concurrent requests', async () => {
      vi.useRealTimers()

      const cache = new RequestCacheManager()
      const fetcher = vi.fn().mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve('data'), 100))
      )

      const promise1 = cache.get('key', fetcher)
      const promise2 = cache.get('key', fetcher)

      const [result1, result2] = await Promise.all([promise1, promise2])

      expect(fetcher).toHaveBeenCalledTimes(1)
      expect(result1).toBe('data')
      expect(result2).toBe('data')
    })

    it('should force refresh when requested', async () => {
      vi.useRealTimers()

      const cache = new RequestCacheManager()
      const fetcher = vi.fn()
        .mockResolvedValueOnce('first')
        .mockResolvedValueOnce('second')

      await cache.get('key', fetcher)
      const result = await cache.get('key', fetcher, { forceRefresh: true })

      expect(fetcher).toHaveBeenCalledTimes(2)
      expect(result).toBe('second')
    })

    it('should invalidate cache entries', async () => {
      vi.useRealTimers()

      const cache = new RequestCacheManager()
      const fetcher = vi.fn()
        .mockResolvedValueOnce('first')
        .mockResolvedValueOnce('second')

      await cache.get('key', fetcher)
      cache.invalidate('key')
      const result = await cache.get('key', fetcher)

      expect(fetcher).toHaveBeenCalledTimes(2)
      expect(result).toBe('second')
    })

    it('should invalidate by pattern', async () => {
      vi.useRealTimers()

      const cache = new RequestCacheManager()
      const fetcher1 = vi.fn().mockResolvedValue('data1')
      const fetcher2 = vi.fn().mockResolvedValue('data2')

      await cache.get('prefix:key1', fetcher1)
      await cache.get('prefix:key2', fetcher2)
      await cache.get('other:key', fetcher1)

      cache.invalidatePattern('^prefix:')

      await cache.get('prefix:key1', fetcher1)
      await cache.get('other:key', fetcher1)

      // prefix:key1 was invalidated, other:key was not
      expect(fetcher1).toHaveBeenCalledTimes(3)
    })

    it('should return stale data on error when available', async () => {
      vi.useRealTimers()

      const cache = new RequestCacheManager({ defaultTTL: 0 })
      const fetcher = vi.fn()
        .mockResolvedValueOnce('cached')
        .mockRejectedValueOnce(new Error('fail'))

      await cache.get('key', fetcher)

      // Wait for TTL to expire
      await new Promise(r => setTimeout(r, 10))

      const result = await cache.get('key', fetcher)

      expect(result).toBe('cached')
    })

    it('should provide cache statistics', async () => {
      vi.useRealTimers()

      const cache = new RequestCacheManager()
      await cache.get('key1', async () => 'data1')
      await cache.get('key2', async () => 'data2')

      const stats = cache.getStats()

      expect(stats.size).toBe(2)
      expect(stats.entries).toHaveLength(2)
      expect(stats.entries.some(e => e.key === 'key1')).toBe(true)
    })

    it('should enforce max size with LRU eviction', async () => {
      vi.useRealTimers()

      const cache = new RequestCacheManager({ maxSize: 2 })

      await cache.get('key1', async () => 'data1')
      await cache.get('key2', async () => 'data2')
      await cache.get('key3', async () => 'data3')

      const stats = cache.getStats()
      expect(stats.size).toBe(2)
      expect(stats.entries.some(e => e.key === 'key1')).toBe(false)
      expect(stats.entries.some(e => e.key === 'key2')).toBe(true)
      expect(stats.entries.some(e => e.key === 'key3')).toBe(true)
    })
  })

  describe('PerformanceMonitor', () => {
    it('should measure operation duration', () => {
      vi.useRealTimers()

      const monitor = new PerformanceMonitor({ enabled: true, sampleRate: 1 })

      const measure = monitor.startMeasure('test-op')

      // Simulate some work
      let sum = 0
      for (let i = 0; i < 1000; i++) sum += i

      const result = monitor.endMeasure(measure)

      expect(result.name).toBe('test-op')
      expect(result.duration).toBeGreaterThanOrEqual(0)
    })

    it('should aggregate metrics correctly', () => {
      const monitor = new PerformanceMonitor({ enabled: true, sampleRate: 1 })

      // Simulate measurements
      for (let i = 0; i < 10; i++) {
        monitor._recordMetric('test', i * 10)
      }

      const metrics = monitor.getMetrics('test')

      expect(metrics.count).toBe(10)
      expect(metrics.min).toBe(0)
      expect(metrics.max).toBe(90)
      expect(metrics.avg).toBe(45)
    })

    it('should return null when disabled', () => {
      const monitor = new PerformanceMonitor({ enabled: false })

      const measure = monitor.startMeasure('test')
      expect(measure).toBeNull()
    })

    it('should respect sample rate with mocked random', () => {
      // Mock Math.random to return a predictable value
      const originalRandom = Math.random
      Math.random = vi.fn().mockReturnValue(0.5)

      // With sampleRate 0.3, Math.random() (0.5) > 0.3 is true, so should return null
      const monitor = new PerformanceMonitor({ enabled: true, sampleRate: 0.3 })
      const measure = monitor.startMeasure('test')
      expect(measure).toBeNull()

      // With sampleRate 0.8, Math.random() (0.5) > 0.8 is false, so should return measure
      const monitor2 = new PerformanceMonitor({ enabled: true, sampleRate: 0.8 })
      const measure2 = monitor2.startMeasure('test2')
      expect(measure2).not.toBeNull()

      // Restore
      Math.random = originalRandom
    })

    it('should measure async operations', async () => {
      vi.useRealTimers()

      const monitor = new PerformanceMonitor({ enabled: true, sampleRate: 1 })

      const result = await monitor.measureAsync('async-op', async () => {
        await new Promise(r => setTimeout(r, 10))
        return 'result'
      })

      expect(result).toBe('result')
      expect(monitor.getMetrics('async-op')).toBeTruthy()
    })

    it('should clear metrics', () => {
      const monitor = new PerformanceMonitor({ enabled: true, sampleRate: 1 })

      monitor._recordMetric('test1', 100)
      monitor._recordMetric('test2', 200)

      monitor.clear()

      expect(monitor.getMetrics('test1')).toBeNull()
      expect(monitor.getMetrics('test2')).toBeNull()
    })
  })
})
