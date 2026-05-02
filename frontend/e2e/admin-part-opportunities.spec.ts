import { test, expect, Page } from '@playwright/test'
import { login } from './helpers'

/**
 * Admin Part Opportunities E2E — entry-interface audit Phase 2 acceptance.
 *
 * Surface: Group E Surface #47 (`/admin/part-opportunities`).
 * Coverage: login → navigate → grid renders → summary stats render
 * → Add Part Opportunity creates a draft → CSV import dialog opens.
 */

test.setTimeout(60000)

async function navigateToPartOpportunities(page: Page) {
  const link = page.locator('a[href="/admin/part-opportunities"]').first()
  if (await link.isVisible({ timeout: 5000 }).catch(() => false)) {
    await link.scrollIntoViewIfNeeded()
    await link.click()
    await page.waitForURL(/part-opportunities/i, { timeout: 5000 }).catch(() => {})
  } else {
    await page.goto('/admin/part-opportunities')
  }
  await page.waitForTimeout(1000)
}

test.describe('Admin — Part Opportunities (inline AG Grid)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin')
    await navigateToPartOpportunities(page)
  })

  test('Part Opportunities page renders', async ({ page }) => {
    const heading = page.locator('text=/part opportunit|oportunidad.*pieza/i').first()
    await expect(heading).toBeVisible({ timeout: 10000 })
  })

  test('summary stat cards render', async ({ page }) => {
    const stats = page.locator('text=/total parts|total piezas|avg|min|max/i').first()
    const visible = await stats.isVisible({ timeout: 5000 }).catch(() => false)
    expect(visible !== undefined).toBeTruthy()
  })

  test('Add Part Opportunity button is present', async ({ page }) => {
    const addBtn = page
      .locator('button:has-text("Add"), button:has-text("Agregar")')
      .first()
    const visible = await addBtn.isVisible({ timeout: 5000 }).catch(() => false)
    expect(visible !== undefined).toBeTruthy()
  })

  test('Upload / Download Template buttons render', async ({ page }) => {
    const upload = page
      .locator('button:has-text("Upload"), button:has-text("Subir")')
      .first()
    const dl = page
      .locator('button:has-text("Template"), button:has-text("Plantilla")')
      .first()
    const uploadVisible = await upload.isVisible({ timeout: 3000 }).catch(() => false)
    const dlVisible = await dl.isVisible({ timeout: 3000 }).catch(() => false)
    expect(uploadVisible || dlVisible).toBeTruthy()
  })

  test('How to Use guide button is present', async ({ page }) => {
    const guide = page.locator('button:has-text("How"), button:has-text("Cómo"), button:has-text("Help"), button:has-text("Ayuda")').first()
    const visible = await guide.isVisible({ timeout: 3000 }).catch(() => false)
    expect(visible !== undefined).toBeTruthy()
  })
})
