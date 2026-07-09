/**
 * E2E Tests for Database Configuration
 *
 * Tests the admin database configuration view: a read-only status panel
 * (current provider, connection info, Alembic-managed-schema notice).
 * The runtime migration wizard and its API were removed as part of the
 * C5 schema-evolution collapse (Alembic-only; no in-app migration).
 */
import { test, expect, Page } from '@playwright/test'
import { login, waitForBackend } from './helpers'

// Increase timeout for stability
test.setTimeout(60000)

// Helper function to login and navigate to database config
async function loginAndNavigateToDatabaseConfig(page: Page, maxRetries = 3) {
  await login(page, 'admin', maxRetries)

  // Navigate to database config
  await page.goto('/admin/database')
  await page.waitForLoadState('networkidle')
}

test.describe('Database Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndNavigateToDatabaseConfig(page)
  })

  test('displays current provider status', async ({ page }) => {
    // Should show current provider info
    await expect(page.locator('text=Current Database Provider')).toBeVisible()
    // Look for SQLite text specifically (since demo uses SQLite)
    await expect(page.getByText('SQLite').first()).toBeVisible()
  })

  test('renders the read-only status panel with no migration UI', async ({ page }) => {
    // Status card + the Alembic-only notice are the entire panel now.
    await expect(page.locator('text=Current Database Provider')).toBeVisible()
    await expect(
      page.getByText(/Schema is managed exclusively by Alembic migrations/)
    ).toBeVisible()

    // The runtime migration wizard was deleted alongside the
    // /api/admin/database/test-connection endpoint (C5 collapse) —
    // assert its marker text is absent rather than conditionally
    // skipping, since the old page's stepper/wizard no longer exists.
    await expect(page.locator('text=Migrate to Production Database')).toHaveCount(0)
  })
})

test.describe('SQLite Status Variant', () => {
  test('status card shows the SQLite info branch, not the production-active branch', async ({ page }) => {
    await loginAndNavigateToDatabaseConfig(page)

    // On a SQLite-backed run, the v-if/v-else in DatabaseConfigView.vue
    // must render the sqliteInfo copy and never the productionActive
    // copy — they're mutually exclusive branches of the same alert.
    await expect(
      page.getByText(/SQLite is fully supported for demo and prove-in phases/)
    ).toBeVisible()
    await expect(page.getByText('Production database configured and active.')).toHaveCount(0)
  })
})

test.describe('API Integration', () => {
  test('fetches database status on load', async ({ page }) => {
    await waitForBackend(page)

    await loginAndNavigateToDatabaseConfig(page)

    // Verify the page loaded with data from the API
    await expect(page.locator('text=Current Database Provider')).toBeVisible({ timeout: 10000 })
    // Provider type proves API call succeeded
    await expect(page.getByText('SQLite').first()).toBeVisible({ timeout: 5000 })
  })

  test('status and providers endpoints reject unauthenticated callers', async ({ request }) => {
    // Hit via the configured baseURL so Render/local both work; no auth
    // header is provided so both admin-only endpoints must respond 401.
    // (test-connection was deleted with the runtime migration API.)
    const statusResponse = await request.get('/api/admin/database/status')
    expect(statusResponse.status()).toBe(401)

    const providersResponse = await request.get('/api/admin/database/providers')
    expect(providersResponse.status()).toBe(401)
  })
})

test.describe('Error Handling', () => {
  test('handles API errors gracefully', async ({ page }) => {
    await waitForBackend(page)

    // First login normally
    await page.context().clearCookies()
    await page.goto('/')
    await page.waitForSelector('input[type="text"]', { state: 'visible', timeout: 15000 })

    await page.fill('input[type="text"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button:has-text("Sign In")')
    await page.waitForSelector('.v-navigation-drawer', { state: 'visible', timeout: 15000 })

    // Intercept and fail the API call
    await page.route('**/api/admin/database/status', route => {
      route.fulfill({
        status: 500,
        body: JSON.stringify({ detail: 'Server error' })
      })
    })

    await page.goto('/admin/database')
    await page.waitForLoadState('networkidle')

    // Should handle error gracefully (not crash)
    // Page should still be functional - check for the page title
    await expect(page.locator('text=Database Configuration')).toBeVisible({ timeout: 10000 })
  })
})
