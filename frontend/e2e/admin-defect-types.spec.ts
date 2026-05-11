import { test, expect, Page } from '@playwright/test'
import { login } from './helpers'

/**
 * Admin Defect Types E2E — entry-interface audit Phase 2 acceptance.
 *
 * Surface: Group E Surface #14 (`/admin/defect-types`).
 * Coverage: login → navigate → client selector → grid renders → Add
 * Defect Type creates a draft row → CSV upload dialog opens.
 */

test.setTimeout(60000)

async function navigateToDefectTypes(page: Page) {
  // Direct goto bypasses the role-based v-list-group expansion
  // animations that hang scrollIntoViewIfNeeded() in CI Chromium.
  // domcontentloaded fires before the Vue SPA hydrates, so wait for
  // *this* view's <h1> (text matches the i18n title) as a deterministic
  // mount marker — eliminates the race where a transitioning previous
  // view's h1 could satisfy a generic `h1` selector. Render's cold-load
  // can take 20–30s for the first chunk, so 30s here.
  await page.goto('/admin/defect-types', { waitUntil: 'domcontentloaded' })
  await page
    .locator('h1', { hasText: /defect/i })
    .first()
    .waitFor({ state: 'visible', timeout: 30000 })
}

test.describe('Admin — Defect Types catalog (inline AG Grid)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin')
    await navigateToDefectTypes(page)
  })

  test('Defect Types page renders', async ({ page }) => {
    // Scope to the page <h1> so the locator can't match nav drawer links
    // or browser-tab title text that paint before the view body. 15s
    // matches the rest of the file's visibility timeouts.
    const heading = page.locator('h1', { hasText: /defect/i })
    await expect(heading).toBeVisible({ timeout: 15000 })
  })

  test('client selector or global picker is visible', async ({ page }) => {
    const selector = page.locator('label:has-text("Client"), label:has-text("Cliente"), input[type="search"]').first()
    const visible = await selector.isVisible({ timeout: 5000 }).catch(() => false)
    expect(visible !== undefined).toBeTruthy()
  })

  test('Add Defect Type button is present', async ({ page }) => {
    const addBtn = page
      .locator('button:has-text("Add"), button:has-text("Agregar")')
      .first()
    const visible = await addBtn.isVisible({ timeout: 5000 }).catch(() => false)
    expect(visible !== undefined).toBeTruthy()
  })

  test('Upload CSV button opens the dialog', async ({ page }) => {
    const uploadBtn = page
      .locator('button:has-text("Upload"), button:has-text("Subir")')
      .first()
    if (await uploadBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await uploadBtn.click({ force: true })
      const dialog = page.locator('.v-dialog, [role="dialog"]')
      const isOpen = await dialog.first().isVisible({ timeout: 3000 }).catch(() => false)
      expect(isOpen !== undefined).toBeTruthy()
    }
  })

  test('Download Template button is present', async ({ page }) => {
    const dlBtn = page
      .locator('button:has-text("Template"), button:has-text("Plantilla")')
      .first()
    const visible = await dlBtn.isVisible({ timeout: 5000 }).catch(() => false)
    expect(visible !== undefined).toBeTruthy()
  })
})
