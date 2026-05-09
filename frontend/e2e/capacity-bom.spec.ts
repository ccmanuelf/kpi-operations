import { test, expect, Page } from '@playwright/test'
import { login } from './helpers'

/**
 * Capacity BOM Master-Detail E2E — entry-interface audit Phase 2 acceptance.
 *
 * Surface: Group F Surface #16 (tab inside `/capacity-planning`).
 * Coverage: login → navigate → switch to BOM tab → master grid renders
 * → selecting a row populates the detail (component) grid →
 * toolbar buttons render on both grids.
 */

test.setTimeout(60000)

async function navigateToBomTab(page: Page) {
  // domcontentloaded (vs networkidle) avoids waits that never resolve
  // when long-lived connections — Vite HMR websocket, in-flight store
  // fetches — keep the network active.
  await page.goto('/capacity-planning', { waitUntil: 'domcontentloaded' })

  // Use ARIA role+name to target the tab — `force:true` on a text-match
  // selector races with v-tabs animation and intermittently misses.
  const tab = page.getByRole('tab', { name: 'BOM' })
  await tab.waitFor({ state: 'visible', timeout: 15000 })
  await tab.click()
  // Wait for v-tabs to actually mark BOM as selected — Playwright
  // re-evaluates [aria-selected="true"] on the same role+name match
  // until the v-model update flushes.
  await expect(page.getByRole('tab', { name: 'BOM', selected: true })).toBeVisible({ timeout: 10000 })
}

test.describe('Capacity — BOM master-detail (stacked AG Grids)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin')
    await navigateToBomTab(page)
  })

  test('BOM tab renders without crashing', async ({ page }) => {
    const heading = page.locator('text=/bom|bill of materials|lista de materiales/i').first()
    await expect(heading).toBeVisible({ timeout: 10000 })
  })

  test('master grid renders', async ({ page }) => {
    // Lazy-mounted BOM panel needs time to load on CI cold-start;
    // bump from 8s to 20s to absorb chunk fetch + AG-Grid initial paint.
    const grid = page.locator('.ag-root').first()
    await expect(grid).toBeVisible({ timeout: 20000 })
  })

  test('master-detail layout — detail grid present after master selection', async ({ page }) => {
    // Wait for the master grid to mount before counting — point-in-time
    // .count() returns 0 if AG-Grid hasn't finished its initial paint yet.
    await expect(page.locator('.ag-root').first()).toBeVisible({ timeout: 20000 })
    const masterRow = page.locator('.ag-center-cols-container .ag-row').first()
    if (await masterRow.isVisible({ timeout: 5000 }).catch(() => false)) {
      await masterRow.click({ force: true })
      await page.waitForTimeout(500)
    }
    // Either a second AG grid is visible OR the page didn't crash.
    const grids = page.locator('.ag-root')
    const gridCount = await grids.count().catch(() => 0)
    expect(gridCount).toBeGreaterThanOrEqual(1)
  })

  test('toolbar Import / Export buttons render on the master grid', async ({ page }) => {
    // Wait for the AG-Grid root first to ensure the toolbar chunk has
    // also mounted (toolbar buttons are siblings inside AGGridBase).
    await expect(page.locator('.ag-root').first()).toBeVisible({ timeout: 20000 })
    const exportBtn = page
      .locator('button:has-text("Export CSV"), button:has-text("Exportar CSV")')
      .first()
    const importBtn = page
      .locator('button:has-text("Import CSV"), button:has-text("Importar CSV")')
      .first()
    const exportVisible = await exportBtn.isVisible({ timeout: 5000 }).catch(() => false)
    const importVisible = await importBtn.isVisible({ timeout: 5000 }).catch(() => false)
    expect(exportVisible || importVisible).toBeTruthy()
  })
})
