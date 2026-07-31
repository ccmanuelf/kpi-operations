import { defineConfig, devices } from '@playwright/test';

/**
 * KPI Operations Platform - Playwright E2E Test Configuration (Parallel)
 *
 * This configuration runs tests in parallel across multiple browsers.
 * Optimized for MariaDB/PostgreSQL backends that handle concurrent access well.
 *
 * For SQLite development/testing (sequential execution), use:
 *   npm run test:e2e:sqlite
 * Which uses playwright.sqlite.config.ts
 *
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { open: 'never' }],
    ['json', { outputFile: 'e2e-results.json' }],
    ['list']
  ],
  timeout: 30000,

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],

  /* Run local dev server before starting the tests */
  webServer: [
    {
      command: 'cd ../backend && PATH="$PWD/.venv/bin:$PATH" PYTHONPATH=.. DISABLE_RATE_LIMIT=1 DEMO_MODE=true uvicorn main:app --host 0.0.0.0 --port 8000',
      url: 'http://localhost:8000/health/',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
    {
      // VITE_DEMO_MODE=true keeps env parity with the backend's DEMO_MODE=true
      // above — the Register button (LoginView.vue) is gated on this flag
      // (ISSUE-006), and auth.spec.ts's Registration describe depends on it
      // being visible.
      command: 'VITE_DEMO_MODE=true npm run dev',
      url: 'http://localhost:3000',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
  ],
});
