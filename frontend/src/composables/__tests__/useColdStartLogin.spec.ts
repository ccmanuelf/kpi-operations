import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useColdStartLogin } from '@/composables/useColdStartLogin'

const OPTS = { budgetMs: 180000, attemptTimeoutMs: 20000, retryDelayMs: 10000 }
const CREDS = { username: 'admin', password: 'admin123' } // pragma: allowlist secret

describe('useColdStartLogin', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('retries while waking and resolves success within budget', async () => {
    const loginFn = vi
      .fn()
      .mockResolvedValueOnce({ success: false, code: 'waking' })
      .mockResolvedValueOnce({ success: false, code: 'waking' })
      .mockResolvedValueOnce({ success: true })
    const { run, wakingUp } = useColdStartLogin(loginFn, OPTS)

    const done = run(CREDS)
    await vi.advanceTimersByTimeAsync(0) // attempt 1
    await vi.advanceTimersByTimeAsync(10000) // wait + attempt 2
    await vi.advanceTimersByTimeAsync(10000) // wait + attempt 3 (success)
    const result = await done

    expect(result).toEqual({ success: true })
    expect(loginFn).toHaveBeenCalledTimes(3)
    expect(loginFn).toHaveBeenLastCalledWith(CREDS, 20000)
    expect(wakingUp.value).toBe(false)
  })

  it('passes the attempt timeout to loginFn on every attempt', async () => {
    const loginFn = vi.fn().mockResolvedValue({ success: true })
    const { run } = useColdStartLogin(loginFn, OPTS)

    await run(CREDS)

    expect(loginFn).toHaveBeenCalledWith(CREDS, 20000)
  })

  it('returns the waking result after the budget is exhausted', async () => {
    const loginFn = vi.fn().mockResolvedValue({ success: false, code: 'waking' })
    const { run } = useColdStartLogin(loginFn, OPTS)

    const done = run(CREDS)
    for (let i = 0; i < 20; i++) {
      await vi.advanceTimersByTimeAsync(10000)
    }
    const result = await done

    expect(result.code).toBe('waking')
    expect(result.success).toBe(false)
  })

  it('returns immediately on invalid credentials without retrying', async () => {
    const loginFn = vi
      .fn()
      .mockResolvedValue({ success: false, code: 'invalid', error: 'Bad creds' })
    const { run } = useColdStartLogin(loginFn, OPTS)

    const result = await run(CREDS)

    expect(result).toEqual({ success: false, code: 'invalid', error: 'Bad creds' })
    expect(loginFn).toHaveBeenCalledTimes(1)
  })

  it('advances the elapsed counter while waking and stops it on stopTicker', async () => {
    const loginFn = vi.fn().mockResolvedValue({ success: false, code: 'waking' })
    const { run, wakingElapsedSec, stopTicker } = useColdStartLogin(loginFn, OPTS)

    const done = run(CREDS)
    await vi.advanceTimersByTimeAsync(0) // first attempt → 'waking' starts the ticker
    await vi.advanceTimersByTimeAsync(3000) // 3 one-second ticks
    expect(wakingElapsedSec.value).toBeGreaterThanOrEqual(3)

    stopTicker()
    const before = wakingElapsedSec.value
    await vi.advanceTimersByTimeAsync(3000)
    expect(wakingElapsedSec.value).toBe(before) // no leaked interval

    // let the budget run out so the pending run() resolves and leaves no open timers
    for (let i = 0; i < 20; i++) {
      await vi.advanceTimersByTimeAsync(10000)
    }
    await done
  })
})
