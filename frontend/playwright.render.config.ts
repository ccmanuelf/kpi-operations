import { defineConfig, devices } from '@playwright/test';

/**
 * KPI Operations Platform — Playwright E2E config for Render deployment.
 *
 * Targets the live Render-hosted frontend (Vue prod build behind nginx)
 * and backend (FastAPI). Differs from the local sqlite config:
 *   - No `webServer`: app is already deployed, don't spin up local servers.
 *   - Longer timeouts: free-tier cold-start (~30-60s) + network latency.
 *   - baseURL points at the Render frontend; nginx proxies `/api` to backend.
 *
 * Run with:
 *   BACKEND_HEALTH_URL=https://kpi-operations-api.onrender.com/health/live \
 *   npx playwright test --config=playwright.render.config.ts --project=chromium-render
 */
export default defineConfig({
  testDir: './e2e',

  // Pre-warm the Render free-tier backend once before any test runs.
  // Cold-wake can take 60s+, longer than any per-test budget — see
  // e2e/global-setup.ts for the full reasoning.
  globalSetup: './e2e/global-setup.ts',

  fullyParallel: false,
  workers: 1,
  retries: 1,
  forbidOnly: !!process.env.CI,

  reporter: [
    ['html', { open: 'never', outputFolder: 'playwright-report-render' }],
    ['json', { outputFile: 'e2e-results-render.json' }],
    ['list'],
  ],

  // Free-tier cold-start can take 30-60s on the first request after idle.
  timeout: 90_000,

  expect: {
    timeout: 15_000,
  },

  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'https://kpi-operations-frontend.onrender.com',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 20_000,
    navigationTimeout: 60_000,
  },

  projects: [
    {
      name: 'chromium-render',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
