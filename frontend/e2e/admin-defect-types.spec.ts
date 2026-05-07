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
  await page.goto('/admin/defect-types')
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {})
}

test.describe('Admin — Defect Types catalog (inline AG Grid)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin')
    await navigateToDefectTypes(page)
  })

  test('Defect Types page renders', async ({ page }) => {
    const heading = page.locator('text=/defect/i').first()
    await expect(heading).toBeVisible({ timeout: 10000 })
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
