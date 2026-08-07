import { test, expect } from '@playwright/test'
import { login } from './helpers'

/**
 * Summaries screen (Cycle 4 PR-B, Task 5) — e2e smoke.
 *
 * Coverage: login -> /summaries -> all 5 pivot tabs render -> switching to
 * the Q2 (downtime) tab and changing the time bucket re-queries
 * /pivot/downtime -> CSV download produces a pivot_downtime_* file.
 */

test.setTimeout(60000)

test.describe('Summaries screen', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin')
  })

  test('tabs render, bucket switch re-queries, CSV downloads', async ({ page }) => {
    // A client-side auth guard redirect mid-navigation can abort the
    // initial goto (net::ERR_ABORTED) — same race noted in
    // a11y-contrast.spec.ts. 'commit' + a single retry covers it.
    await page.goto('/summaries', { waitUntil: 'commit' }).catch(async () => {
      await page.waitForTimeout(400)
      await page.goto('/summaries', { waitUntil: 'commit' })
    })

    await expect(page.getByTestId('pivot-tab-q1')).toBeVisible({ timeout: 15000 })
    await expect(page.getByTestId('pivot-tab-q5')).toBeVisible()

    await page.getByTestId('pivot-tab-q2').click()

    // v-window keeps every v-window-item mounted (CSS-grid stacking, not
    // v-destroy), so all tab panels' bucket selects share the testid.
    // Scope to the panel Vuetify marks active rather than :visible — the
    // slide transition briefly gives the outgoing panel a non-zero
    // bounding box too, which makes :visible ambiguous mid-flight.
    const activePanel = page.locator('.v-window-item--active')
    const req = page.waitForRequest((r) => r.url().includes('/pivot/downtime'), { timeout: 15000 })
    await activePanel.getByTestId('pivot-bucket-select').click()
    await page.locator('.v-list-item').filter({ hasText: /^Quarter$/i }).first().click()
    await req

    const downloadPromise = page.waitForEvent('download', { timeout: 15000 })
    await activePanel.getByTestId('pivot-download').click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toContain('pivot_downtime')
  })
})
