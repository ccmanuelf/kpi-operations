import { test, expect, Page } from '@playwright/test';
import { login } from './helpers';

/**
 * Quality / Attendance / Downtime entry pages — module smoke tests.
 *
 * Asserts on `[data-testid="<surface>-entry-view"]` (added at the
 * view-component root in src/views/*Entry.vue) — the most reliable
 * post-mount handle. Per-grid testids inside `<v-card-title>` and
 * `<v-card-text>` work locally but render lazily in headless CI;
 * the view-level `<v-container>` mounts unconditionally on route
 * activation.
 */

test.setTimeout(60000);

async function navigateVia(page: Page, href: string) {
  await page.goto(href);
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
}

test.describe('Quality Entry — view loads', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateVia(page, '/data-entry/quality');
  });

  test('view container renders', async ({ page }) => {
    await expect(page.locator('[data-testid="quality-entry-view"]')).toBeVisible({ timeout: 20000 });
  });

  test('grid surface mounts', async ({ page }) => {
    // Wrapper is part of AGGridBase; if it doesn't render the grid
    // didn't mount, surface that distinctly from a route 404.
    await expect(page.locator('[data-testid="ag-grid-wrapper"]').first()).toBeAttached({ timeout: 20000 });
  });
});

test.describe('Attendance Entry — view loads', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateVia(page, '/data-entry/attendance');
  });

  test('view container renders', async ({ page }) => {
    await expect(page.locator('[data-testid="attendance-entry-view"]')).toBeVisible({ timeout: 20000 });
  });
});

test.describe('Downtime Entry — view loads', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateVia(page, '/data-entry/downtime');
  });

  test('view container renders', async ({ page }) => {
    await expect(page.locator('[data-testid="downtime-entry-view"]')).toBeVisible({ timeout: 20000 });
  });

  test('grid surface mounts', async ({ page }) => {
    await expect(page.locator('[data-testid="ag-grid-wrapper"]').first()).toBeAttached({ timeout: 20000 });
  });
});

test.describe('Admin — Client Management (admin role only)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('admin nav drawer is rendered', async ({ page }) => {
    await expect(page.locator('.v-navigation-drawer').first()).toBeVisible({ timeout: 10000 });
  });
});
