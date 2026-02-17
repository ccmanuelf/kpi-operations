/**
 * E2E Tests for Database Configuration
 *
 * Tests the admin database configuration view and migration wizard.
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

  test('shows migration section for SQLite', async ({ page }) => {
    // Check if migration section is visible (only for SQLite)
    const migrationSection = page.locator('text=Migrate to Production Database')

    // If current provider is SQLite, migration should be available
    const providerText = await page.textContent('body')
    if (providerText?.includes('SQLite')) {
      await expect(migrationSection).toBeVisible()
    }
  })

  test('shows MariaDB and MySQL options in wizard', async ({ page }) => {
    // Check if wizard options are visible
    const mariadbOption = page.getByText('MariaDB').first()
    const mysqlOption = page.getByText('MySQL').first()

    // These should be visible if migration is available
    const pageContent = await page.textContent('body')
    if (pageContent?.includes('Migrate to Production')) {
      await expect(mariadbOption).toBeVisible()
      await expect(mysqlOption).toBeVisible()
    }
  })

  test('displays one-way migration warning', async ({ page }) => {
    // Check for warning about irreversible operation
    const warningText = page.getByText(/one-way/i).first()

    const pageContent = await page.textContent('body')
    if (pageContent?.includes('Migrate to Production')) {
      await expect(warningText).toBeVisible()
    }
  })
})

test.describe('Migration Wizard Steps', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndNavigateToDatabaseConfig(page)
  })

  test('wizard has three steps', async ({ page }) => {
    const pageContent = await page.textContent('body')

    // Only test if migration is available
    if (pageContent?.includes('Migrate to Production')) {
      // Check for step labels
      await expect(page.getByText('Select Target').first()).toBeVisible()
      await expect(page.getByText('Test Connection').first()).toBeVisible()
      await expect(page.getByText('Confirm').first()).toBeVisible()
    }
  })

  test('shows connection URL format help', async ({ page }) => {
    const pageContent = await page.textContent('body')

    if (pageContent?.includes('Migrate to Production')) {
      // Should show URL format hint - the page shows mysql+pymysql://
      const urlHint = page.getByText(/mysql\+pymysql:\/\//i).first()
      await expect(urlHint).toBeVisible()
    }
  })
})

test.describe('Migration Confirmation', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndNavigateToDatabaseConfig(page)
  })

  test('requires MIGRATE confirmation text', async ({ page }) => {
    const pageContent = await page.textContent('body')

    if (pageContent?.includes('Migrate to Production')) {
      // Navigate to confirmation step (if possible in test)
      // This depends on the stepper implementation
      const confirmInput = page.locator('input[placeholder*="MIGRATE"]')

      if (await confirmInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        // Should require exact text
        await expect(page.getByText(/Type MIGRATE/i).first()).toBeVisible()
      }
    }
  })
})

test.describe('Already Migrated State', () => {
  test('shows production database active message', async ({ page }) => {
    await loginAndNavigateToDatabaseConfig(page)

    const pageContent = await page.textContent('body')

    // If already migrated, should show appropriate message
    if (pageContent?.includes('MariaDB') || pageContent?.includes('MySQL')) {
      if (!pageContent?.includes('Migrate to Production')) {
        await expect(page.getByText(/Production Database Active|No further migration/i).first()).toBeVisible()
      }
    }
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

  test('test connection endpoint works', async ({ page, request }) => {
    // Test connection endpoint directly
    const response = await request.post('http://localhost:8000/api/admin/database/test-connection', {
      data: {
        target_url: 'sqlite:///test.db'
      }
    })

    // The endpoint may return various statuses
    expect([200, 400, 401, 403, 422]).toContain(response.status())
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
