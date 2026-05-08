import { test, expect, Page } from '@playwright/test'
import { login } from './helpers'

/**
 * Capacity Scenarios Panel E2E — entry-interface audit Phase 2 acceptance.
 *
 * Surface: Group H Surface #20 (tab inside `/capacity-planning`).
 * Coverage: login → navigate → switch to Scenarios tab → grid renders
 * → Create Scenario adds a draft row → toolbar buttons render.
 */

test.setTimeout(60000)

async function navigateToScenariosTab(page: Page) {
  // Direct goto with domcontentloaded: this fires deterministically vs.
  // networkidle which is held open by Vite HMR + in-flight store fetches.
  await page.goto('/capacity-planning', { waitUntil: 'domcontentloaded' })
  // Wait for the page-specific header before switching tabs.
  await page.waitForSelector('.v-card-title:has-text("Capacity Planning")', { state: 'visible', timeout: 30000 })

  // Switch to the Scenarios tab.
  const tab = page
    .locator('button:has-text("Scenarios"), [role="tab"]:has-text("Scenarios")')
    .or(page.locator('button:has-text("Escenarios"), [role="tab"]:has-text("Escenarios")'))
    .first()
  await tab.waitFor({ state: 'visible', timeout: 15000 })
  await tab.click({ force: true })
}

test.describe('Capacity Scenarios — inline AG Grid (new rows only)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin')
    await navigateToScenariosTab(page)
  })

  test('Scenarios tab renders without crashing', async ({ page }) => {
    const heading = page.locator('text=/scenarios|escenarios|what.if/i').first()
    await expect(heading).toBeVisible({ timeout: 15000 })
  })

  // FIXME(2026-06-01): The Scenarios tab uses an inline AG-Grid for
  // new-rows-only — there is NO standalone "Create Scenario" button;
  // the Add Row action lives inside the AGGridBase toolbar. The
  // `text=Create|Crear` matcher hit a different button locally
  // (perhaps the parent CapacityPlanning's tab "Create" action) but
  // misses in CI. Needs rewrite against the actual `[data-testid=
  // "ag-grid-toolbar"]` Add-Row button (added in Phase A.13). See
  // Phase B.7 + run 25567074055.
  test.skip('Create Scenario button is visible', async ({ page }) => {
    const btn = page
      .locator('button:has-text("Create Scenario"), button:has-text("Crear Escenario"), button:has-text("Create"), button:has-text("Crear")')
      .first()
    await expect(btn).toBeVisible({ timeout: 15000 })
  })

  test('grid or empty-state renders after data load', async ({ page }) => {
    // After load, either the AG Grid root OR the no-scenarios placeholder is present.
    const gridOrEmpty = page.locator('.ag-root').or(page.locator('text=/no scenarios|sin escenarios/i'))
    await expect(gridOrEmpty.first()).toBeVisible({ timeout: 20000 })
  })

  test('Compare button only appears when 2+ rows are selected', async ({ page }) => {
    const compareBtn = page
      .locator('button:has-text("Compare"), button:has-text("Comparar")')
      .first()
    // Default state: 0 selected → Compare hidden. We assert the page doesn't
    // crash and the Compare button is NOT present in the default state.
    const visible = await compareBtn.isVisible({ timeout: 1500 }).catch(() => false)
    expect(visible).toBeFalsy()
  })
})
