import { request, FullConfig } from '@playwright/test'

/**
 * Render free-tier services spin down after ~15 min of inactivity. The
 * cold-wake can take 60s+ — longer than any single test's budget. Running
 * the warm-up inside a `beforeEach` (via waitForBackend) is unwinnable in
 * that case: the test times out *while* the backend is still booting.
 *
 * This globalSetup runs once before any test, with a much larger budget
 * (5 min) so even a deep-cold backend has enough time to come up. After
 * this returns, the per-test waitForBackend probes all hit a warm backend
 * and resolve in <500 ms.
 *
 * No-op when BACKEND_HEALTH_URL is unset (local sqlite runs against
 * webServer in the playwright config — no remote warm-up needed).
 */
export default async function globalSetup(_config: FullConfig): Promise<void> {
  const healthUrl = process.env.BACKEND_HEALTH_URL
  if (!healthUrl) return

  const budgetMs = 5 * 60_000
  const perRequestMs = 4_000
  const pollIntervalMs = 2_000
  const start = Date.now()
  let attempts = 0

  const ctx = await request.newContext()
  try {
    while (Date.now() - start < budgetMs) {
      attempts += 1
      try {
        const res = await ctx.get(healthUrl, { timeout: perRequestMs })
        if (res.ok()) {
          const elapsed = ((Date.now() - start) / 1000).toFixed(1)
          // eslint-disable-next-line no-console
          console.log(`[globalSetup] backend warm after ${elapsed}s (${attempts} attempts)`)
          return
        }
      } catch {
        // Backend still spinning up; keep polling.
      }
      await new Promise((r) => setTimeout(r, pollIntervalMs))
    }
    throw new Error(
      `[globalSetup] backend at ${healthUrl} did not respond within ${budgetMs / 1000}s ` +
        `(${attempts} attempts) — aborting test run`,
    )
  } finally {
    await ctx.dispose()
  }
}
