import { describe, it, expect, vi, afterEach } from 'vitest'
import { getWakeOrigin, wakeBackend, pingWake } from '@/services/backendWake'

const setMeta = (content: string) => {
  const m = document.createElement('meta')
  m.setAttribute('name', 'backend-wake-origin')
  m.setAttribute('content', content)
  document.head.appendChild(m)
}

afterEach(() => {
  document.querySelector('meta[name="backend-wake-origin"]')?.remove()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('backendWake', () => {
  it('getWakeOrigin returns null when the meta tag is absent', () => {
    expect(getWakeOrigin()).toBeNull()
  })

  it('getWakeOrigin returns the origin with trailing slashes stripped', () => {
    setMeta('https://kpi-operations-api.onrender.com/')
    expect(getWakeOrigin()).toBe('https://kpi-operations-api.onrender.com')
  })

  it('wakeBackend no-ops (no fetch) when no wake origin is configured', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(undefined as unknown as Response)
    await wakeBackend()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('wakeBackend fetches <origin>/health/live in cors mode', async () => {
    setMeta('https://kpi-operations-api.onrender.com')
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(undefined as unknown as Response)
    await wakeBackend()
    expect(String(fetchSpy.mock.calls[0]?.[0])).toBe('https://kpi-operations-api.onrender.com/health/live')
    expect((fetchSpy.mock.calls[0]?.[1] as RequestInit).mode).toBe('cors')
  })

  it('wakeBackend never throws when the fetch rejects', async () => {
    setMeta('https://kpi-operations-api.onrender.com')
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('backend asleep'))
    await expect(wakeBackend()).resolves.toBeUndefined()
  })

  it('pingWake no-ops (no fetch) when no wake origin is configured', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(undefined as unknown as Response)
    await pingWake()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('pingWake aborts the request after timeoutMs and resolves without throwing', async () => {
    vi.useFakeTimers()
    setMeta('https://kpi-operations-api.onrender.com')
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () =>
            reject(new DOMException('aborted', 'AbortError')),
          )
        }) as Promise<Response>,
    )
    const done = pingWake(12000)
    await vi.advanceTimersByTimeAsync(12000)
    await expect(done).resolves.toBeUndefined()
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })
})
