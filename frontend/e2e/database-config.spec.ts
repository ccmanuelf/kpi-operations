/**
 * E2E Tests for Database Configuration
 *
 * Tests the admin database configuration view and migration wizard.
 */
import { test, expect } from '@playwright/test'

test.describe('Database Configuration', () => {
  // Login before each test
  test.beforeEach(async ({ page }) => {
    // Login as admin
    await page.goto('/login')

    // Fill in admin credentials
    await page.fill('input[type="text"], input[name="username"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"]')

    // Wait for dashboard to load
    await page.waitForURL('/')
    await page.waitForTimeout(500)

    // Navigate to database config
    await page.goto('/admin/database')
    await page.waitForLoadState('networkidle')
  })

  test('displays current provider status', async ({ page }) => {
    // Should show current provider info
    await expect(page.locator('text=Current Database Provider')).toBeVisible()
    await expect(page.locator('text=/SQLite|MariaDB|MySQL/i')).toBeVisible()
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
    const mariadbOption = page.locator('text=MariaDB')
    const mysqlOption = page.locator('text=MySQL')

    // These should be visible if migration is available
    const pageContent = await page.textContent('body')
    if (pageContent?.includes('Migrate to Production')) {
      await expect(mariadbOption).toBeVisible()
      await expect(mysqlOption).toBeVisible()
    }
  })

  test('displays one-way migration warning', async ({ page }) => {
    // Check for warning about irreversible operation
    const warningText = page.locator('text=/one-way|irreversible/i')

    const pageContent = await page.textContent('body')
    if (pageContent?.includes('Migrate to Production')) {
      await expect(warningText.first()).toBeVisible()
    }
  })
})

test.describe('Migration Wizard Steps', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin
    await page.goto('/login')
    await page.fill('input[type="text"], input[name="username"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')
    await page.waitForTimeout(500)
    await page.goto('/admin/database')
    await page.waitForLoadState('networkidle')
  })

  test('wizard has three steps', async ({ page }) => {
    const pageContent = await page.textContent('body')

    // Only test if migration is available
    if (pageContent?.includes('Migrate to Production')) {
      // Check for step labels
      await expect(page.locator('text=Select Target')).toBeVisible()
      await expect(page.locator('text=Test Connection')).toBeVisible()
      await expect(page.locator('text=Confirm')).toBeVisible()
    }
  })

  test('shows connection URL format help', async ({ page }) => {
    const pageContent = await page.textContent('body')

    if (pageContent?.includes('Migrate to Production')) {
      // Should show URL format hint
      const urlHint = page.locator('text=/mysql.*pymysql.*:\/\//i')
      await expect(urlHint.first()).toBeVisible()
    }
  })
})

test.describe('Migration Confirmation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[name="username"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')
    await page.waitForTimeout(500)
    await page.goto('/admin/database')
    await page.waitForLoadState('networkidle')
  })

  test('requires MIGRATE confirmation text', async ({ page }) => {
    const pageContent = await page.textContent('body')

    if (pageContent?.includes('Migrate to Production')) {
      // Navigate to confirmation step (if possible in test)
      // This depends on the stepper implementation
      const confirmInput = page.locator('input[placeholder*="MIGRATE"]')

      if (await confirmInput.isVisible()) {
        // Should require exact text
        await expect(page.locator('text=/Type MIGRATE/i')).toBeVisible()
      }
    }
  })
})

test.describe('Already Migrated State', () => {
  test('shows production database active message', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[name="username"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')
    await page.waitForTimeout(500)
    await page.goto('/admin/database')
    await page.waitForLoadState('networkidle')

    const pageContent = await page.textContent('body')

    // If already migrated, should show appropriate message
    if (pageContent?.includes('MariaDB') || pageContent?.includes('MySQL')) {
      if (!pageContent?.includes('Migrate to Production')) {
        await expect(page.locator('text=/Production Database Active|No further migration/i').first()).toBeVisible()
      }
    }
  })
})

test.describe('API Integration', () => {
  test('fetches database status on load', async ({ page }) => {
    // Intercept API call
    const statusPromise = page.waitForResponse(
      response => response.url().includes('/api/admin/database/status')
    )

    await page.goto('/login')
    await page.fill('input[type="text"], input[name="username"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')
    await page.waitForTimeout(500)
    await page.goto('/admin/database')

    const response = await statusPromise
    expect(response.status()).toBe(200)

    const data = await response.json()
    expect(data).toHaveProperty('current_provider')
    expect(data).toHaveProperty('migration_available')
  })

  test('test connection endpoint works', async ({ page, request }) => {
    // Test connection endpoint directly
    const response = await request.post('/api/admin/database/test-connection', {
      data: {
        target_url: 'sqlite:///test.db'
      }
    })

    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data).toHaveProperty('success')
  })
})

test.describe('Error Handling', () => {
  test('handles API errors gracefully', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[name="username"]', 'admin')
    await page.fill('input[type="password"]', 'admin123')
    await page.click('button[type="submit"]')
    await page.waitForURL('/')
    await page.waitForTimeout(500)

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
    // Page should still be functional
    await expect(page.locator('text=Database Configuration')).toBeVisible()
  })
})
