import { test, expect } from '@playwright/test'
import { login } from './helpers'

/**
 * Report-button wiring guard. Before the 2026-07-21 fix, the KPIDashboard
 * Export PDF / Excel / Email buttons called /reports/{pdf,excel,email},
 * which return 404 — the unit suite stayed green because it asserted those
 * wrong paths. This test exercises the actual buttons end-to-end and asserts
 * they reach a real endpoint (< 400), so the class cannot silently regress.
 */
test.setTimeout(60000)

test.describe('KPIDashboard report buttons hit real endpoints', () => {
  test('Export PDF requests comprehensive/pdf and succeeds', async ({ page }) => {
    await login(page, 'admin')
    await page.goto('/kpi-dashboard', { waitUntil: 'domcontentloaded' })

    // Open the report menu (button labelled by reports.title) then click Export PDF.
    await page.getByRole('button', { name: /report/i }).first().click()
    const [resp] = await Promise.all([
      page.waitForResponse(/\/reports\/comprehensive\/pdf/, { timeout: 30000 }),
      page.getByText(/export pdf/i).click(),
    ])
    expect(resp.status()).toBeLessThan(400)
  })

  test('Export Excel requests comprehensive/excel and succeeds', async ({ page }) => {
    await login(page, 'admin')
    await page.goto('/kpi-dashboard', { waitUntil: 'domcontentloaded' })

    await page.getByRole('button', { name: /report/i }).first().click()
    const [resp] = await Promise.all([
      page.waitForResponse(/\/reports\/comprehensive\/excel/, { timeout: 30000 }),
      page.getByText(/export excel/i).click(),
    ])
    expect(resp.status()).toBeLessThan(400)
  })

  test('home-page (DashboardView) Export to Excel hits comprehensive/excel, not 404', async ({ page }) => {
    // Regression guard for the second instance of the bug: DashboardView's
    // "Export to Excel" button called /reports/excel (404) and silently fell
    // back to CSV. It must now reach the real comprehensive Excel endpoint.
    await login(page, 'admin')
    await page.goto('/', { waitUntil: 'domcontentloaded' })

    const [resp] = await Promise.all([
      page.waitForResponse(/\/reports\/comprehensive\/excel/, { timeout: 30000 }),
      page.getByText(/export.*excel/i).first().click(),
    ])
    expect(resp.status()).toBeLessThan(400)
  })
})
