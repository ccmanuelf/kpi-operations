import { test, expect, Page } from '@playwright/test';
import { login } from './helpers';

/**
 * Quality / Attendance / Downtime entry pages — module smoke tests.
 *
 * All three were migrated from form-based UI to AGGridBase as part of
 * the entry-interface audit (2026-05-02). Rewritten 2026-05-06.
 *
 * Asserts on `[data-testid="ag-grid-wrapper"]` (the AGGridBase
 * top-level marker) instead of per-grid headers — the header testids
 * are nested inside `<v-card-title>` which Vuetify sometimes renders
 * lazily; the wrapper is the most robust handle.
 */

test.setTimeout(60000);

async function navigateVia(page: Page, href: string) {
  // Direct goto bypasses the role-based v-list-group expansion
  // animations that hang scrollIntoViewIfNeeded() in CI Chromium.
  await page.goto(href);
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
}

test.describe('Quality Entry — AG Grid surface', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateVia(page, '/data-entry/quality');
  });

  test('grid renders', async ({ page }) => {
    await expect(page.locator('[data-testid="ag-grid-wrapper"]').first()).toBeVisible({ timeout: 20000 });
  });

  test('Save button is part of the grid surface', async ({ page }) => {
    // Save testid exists when the grid mounts; it's part of the grid
    // header card (inside the v-card-title where Vuetify wraps the
    // bound class). The wrapper-first assertion above already proved
    // the grid mounts; here we confirm the save control is reachable.
    await expect(page.locator('[data-testid="quality-save-btn"]')).toBeAttached({ timeout: 20000 });
  });
});

test.describe('Attendance Entry — AG Grid surface', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateVia(page, '/data-entry/attendance');
  });

  test('grid renders', async ({ page }) => {
    await expect(page.locator('[data-testid="ag-grid-wrapper"]').first()).toBeVisible({ timeout: 20000 });
  });

  test('load-employees control is part of the surface', async ({ page }) => {
    await expect(page.locator('[data-testid="attendance-load-employees-btn"]')).toBeAttached({ timeout: 20000 });
  });
});

test.describe('Downtime Entry — AG Grid surface', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateVia(page, '/data-entry/downtime');
  });

  test('grid renders', async ({ page }) => {
    await expect(page.locator('[data-testid="ag-grid-wrapper"]').first()).toBeVisible({ timeout: 20000 });
  });

  test('Save button is part of the grid surface', async ({ page }) => {
    await expect(page.locator('[data-testid="downtime-save-btn"]')).toBeAttached({ timeout: 20000 });
  });
});

test.describe('Admin — Client Management (admin role only)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('admin nav drawer is rendered', async ({ page }) => {
    // The Client Management surface route name has changed historically;
    // the single contract here is "after admin login the nav drawer is
    // present". Per-link checks belong in an admin-routes spec.
    await expect(page.locator('.v-navigation-drawer').first()).toBeVisible({ timeout: 10000 });
  });
});
