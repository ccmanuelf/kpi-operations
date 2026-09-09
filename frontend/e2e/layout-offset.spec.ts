/**
 * The main content area must sit BESIDE the navigation drawer, not under it.
 *
 * Vuetify computes `--v-layout-left` from the drawer's width and applies it as
 * `.v-main{padding-left:...}` from its `vuetify-components` layer. Tailwind 4's
 * preflight `*{padding:0}` lives in `base`, and when `base` ends up ordered
 * above that layer it wins: v-main spans the full viewport and the first ~280px
 * of EVERY screen is covered by the drawer -- the heading, the first filter,
 * the primary action.
 *
 * Nothing else catches it. Unit tests never mount the layout, the contrast gate
 * reads colours rather than geometry, and the page still "renders" -- it is
 * simply unusable down its left edge. It took looking at a screenshot of the
 * running app.
 */
import { test, expect } from '@playwright/test'

import { login } from './helpers'

test.describe('layout: content is not clipped under the nav drawer', () => {
  test('v-main carries the drawer offset Vuetify computed', async ({ page }) => {
    await login(page, 'admin')
    await page.goto('/data-entry/attendance', { waitUntil: 'networkidle' })

    const drawer = page.locator('nav.v-navigation-drawer').first()
    await expect(drawer).toBeVisible({ timeout: 20000 })

    const measured = await page.evaluate(() => {
      const main = document.querySelector('main.v-main') as HTMLElement | null
      const nav = document.querySelector('nav.v-navigation-drawer') as HTMLElement | null
      if (!main || !nav) return null
      const cs = getComputedStyle(main)
      return {
        paddingLeft: parseFloat(cs.paddingLeft) || 0,
        layoutLeft: parseFloat(cs.getPropertyValue('--v-layout-left')) || 0,
        drawerWidth: nav.getBoundingClientRect().width,
      }
    })

    expect(measured, 'main.v-main / nav drawer not found').not.toBeNull()
    const { paddingLeft, layoutLeft, drawerWidth } = measured!

    // Vuetify knows how wide the drawer is...
    expect(layoutLeft).toBeGreaterThan(0)
    expect(Math.round(layoutLeft)).toBe(Math.round(drawerWidth))

    // ...and the content must actually be offset by it. This is the assertion
    // that fails when the cascade order regresses.
    expect(
      paddingLeft,
      `v-main padding-left is ${paddingLeft}px but the drawer is ${drawerWidth}px wide — content sits under it`,
    ).toBe(Math.round(layoutLeft))
  })
})
