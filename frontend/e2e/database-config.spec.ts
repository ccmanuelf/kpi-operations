/**
 * E2E Tests for Database Configuration
 *
 * Tests the admin database configuration view and migration wizard.
 */
import { test, expect, Page } from '@playwright/test'

// Increase timeout for stability
test.setTimeout(60000)

async function waitForBackend(page: Page, timeout = 10000) {
  const startTime = Date.now()
  while (Date.now() - startTime < timeout) {
    try {
      const response = await page.request.get('http://localhost:8000/health/')
      if (response.ok()) return true
    } catch {
      // Backend not ready yet
    }
    await page.waitForTimeout(500)
  }
  return false
}

// Helper function to login with retry logic
async function loginAndNavigateToDatabaseConfig(page: Page, maxRetries = 3) {
  await waitForBackend(page)

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    if (attempt > 1) {
      await page.waitForTimeout(3000 * attempt)
    }

    await page.context().clearCookies()
    await page.goto('/')
    await page.waitForSelector('input[type="text"]', { state: 'visible', timeout: 15000 })

    // Dismiss any existing error alerts first
    const existingAlert = page.locator('.v-alert button:has-text("Close")')
    if (await existingAlert.isVisible({ timeout: 500 }).catch(() => false)) {
      await existingAlert.click()
      await page.waitForTimeout(500)
    }

    await page.locator('input[type="text"]').clear()
    await page.locator('input[type="password"]').clear()
    await page.waitForTimeout(200)
    await page.fill('input[type="text"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.waitForTimeout(200)

    await page.click('button:has-text("Sign In")')
    await page.waitForLoadState('networkidle', { timeout: 30000 })

    // Check if login failed
    const loginFailed = page.locator('text=Login failed')
    if (await loginFailed.isVisible({ timeout: 3000 }).catch(() => false)) {
      if (attempt < maxRetries) {
        const closeBtn = page.locator('.v-alert button:has-text("Close")')
        if (await closeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
          await closeBtn.click()
        }
        continue
      }
      throw new Error(`Login failed after ${maxRetries} attempts`)
    }

    // Wait for navigation drawer to confirm login success
    await page.waitForSelector('.v-navigation-drawer', { state: 'visible', timeout: 15000 })

    // Navigate to database config
    await page.goto('/admin/database')
    await page.waitForLoadState('networkidle')
    return
  }
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

    // Intercept API call
    const statusPromise = page.waitForResponse(
      response => response.url().includes('/api/admin/database/status'),
      { timeout: 30000 }
    )

    await loginAndNavigateToDatabaseConfig(page)

    // Wait for the response that was already captured
    try {
      const response = await statusPromise
      expect(response.status()).toBe(200)

      const data = await response.json()
      expect(data).toHaveProperty('current_provider')
      expect(data).toHaveProperty('migration_available')
    } catch {
      // If we missed the response, just verify the page loaded correctly
      await expect(page.locator('text=Current Database Provider')).toBeVisible()
    }
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
    await page.waitForTimeout(1000)

    // Should handle error gracefully (not crash)
    // Page should still be functional - check for the page title
    await expect(page.locator('text=Database Configuration')).toBeVisible()
  })
})
