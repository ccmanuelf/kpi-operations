import { ref, type Ref } from 'vue'

export interface ColdStartLoginResult {
  success: boolean
  code?: string
  error?: string
  [key: string]: unknown
}

export type ColdStartLoginFn = (
  _credentials: Record<string, unknown>,
  _timeoutMs?: number,
) => Promise<ColdStartLoginResult>

export interface ColdStartLoginOptions {
  budgetMs?: number
  attemptTimeoutMs?: number
  retryDelayMs?: number
}

// On free hosting the backend sleeps after inactivity; a cold start was measured at ~90s
// (variable) and Render can hold the wake request open. We bound each attempt with a
// timeout so a hung request cannot block the loop, retry on a wall-clock budget that
// comfortably exceeds the cold start, and expose a live elapsed counter so the wait does
// not look frozen — without ever masking a real 401 (only `code === 'waking'` retries).
export function useColdStartLogin(
  loginFn: ColdStartLoginFn,
  options: ColdStartLoginOptions = {},
): {
  wakingUp: Ref<boolean>
  wakingElapsedSec: Ref<number>
  run: (_credentials: Record<string, unknown>) => Promise<ColdStartLoginResult>
  cancel: () => void
} {
  const budgetMs = options.budgetMs ?? 180000
  const attemptTimeoutMs = options.attemptTimeoutMs ?? 20000
  const retryDelayMs = options.retryDelayMs ?? 10000

  const wakingUp = ref(false)
  const wakingElapsedSec = ref(0)
  let ticker: ReturnType<typeof setInterval> | null = null
  let aborted = false

  function startTicker(): void {
    if (ticker !== null) return
    wakingElapsedSec.value = 0
    ticker = setInterval(() => {
      wakingElapsedSec.value += 1
    }, 1000)
  }

  function stopTicker(): void {
    if (ticker !== null) {
      clearInterval(ticker)
      ticker = null
    }
  }

  function cancel(): void {
    stopTicker()
    aborted = true
  }

  async function run(credentials: Record<string, unknown>): Promise<ColdStartLoginResult> {
    aborted = false
    const start = Date.now()
    while (true) {
      const result = await loginFn(credentials, attemptTimeoutMs)

      if (aborted) {
        stopTicker()
        wakingUp.value = false
        return result.success ? { success: false, code: 'aborted' } : result
      }

      if (result.success) {
        stopTicker()
        wakingUp.value = false
        return result
      }

      if (result.code === 'waking' && Date.now() - start < budgetMs) {
        wakingUp.value = true
        startTicker()
        await new Promise((resolve) => setTimeout(resolve, retryDelayMs))

        if (aborted) {
          stopTicker()
          wakingUp.value = false
          return result
        }

        continue
      }

      stopTicker()
      wakingUp.value = false
      return result
    }
  }

  return { wakingUp, wakingElapsedSec, run, cancel }
}
