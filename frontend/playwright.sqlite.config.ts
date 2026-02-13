import { defineConfig, devices } from '@playwright/test';

/**
 * KPI Operations Platform - Playwright E2E Test Configuration (SQLite Sequential)
 *
 * This configuration is optimized for SQLite database testing where concurrent
 * database access can cause locking issues. Tests run sequentially with a single
 * worker to avoid database contention.
 *
 * Use this configuration when:
 * - Running with SQLite backend (development/testing)
 * - Debugging flaky tests caused by database locking
 * - Running comprehensive test suites that require consistent database state
 *
 * For parallel execution (with MariaDB/PostgreSQL), use the default playwright.config.ts
 *
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './e2e',

  /* Sequential execution for SQLite compatibility */
  fullyParallel: false,
  workers: 1,

  /* Retry failed tests once to handle transient issues */
  retries: 1,

  /* Fail CI if test.only is accidentally committed */
  forbidOnly: !!process.env.CI,

  reporter: [
    ['html', { open: 'never', outputFolder: 'playwright-report-sqlite' }],
    ['json', { outputFile: 'e2e-results-sqlite.json' }],
    ['list']
  ],

  /* Longer timeout for sequential execution */
  timeout: 45000,

  /* Global test timeout */
  expect: {
    timeout: 10000,
  },

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',

    /* Add action timeout for more stability */
    actionTimeout: 15000,
    navigationTimeout: 30000,
  },

  /* Run only on chromium for faster sequential execution */
  projects: [
    {
      name: 'chromium-sqlite',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  /* Run local dev server before starting the tests */
  webServer: [
    {
      command: 'cd ../backend && source venv/bin/activate && PYTHONPATH=.. DISABLE_RATE_LIMIT=1 uvicorn main:app --host 0.0.0.0 --port 8000',
      url: 'http://localhost:8000/health/',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 120 * 1000,
    },
  ],
});
