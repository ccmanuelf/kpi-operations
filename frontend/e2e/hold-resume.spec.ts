import { test, expect, Page } from '@playwright/test';
import { login } from './helpers';

/**
 * Hold / Resume Workflow E2E.
 *
 * Surface: `/data-entry/hold-resume` (HoldResumeEntry view +
 * HoldEntryGrid component).
 *
 * The view was migrated to AGGridBase as part of the entry-interface
 * audit (2026-05-02). This spec was rewritten 2026-05-06 against the
 * AG Grid surface; the previous form-based selectors (Add Holds tab,
 * Resumed tab, Work Order combobox, Quantity spinbutton, Submit button)
 * were obsoleted by that migration.
 *
 * Stable selectors used (per docs/CONTRIBUTING.md "E2E Parity"):
 *   - `a[href="/data-entry/hold-resume"]` for navigation
 *   - `data-testid="ag-grid-wrapper"` (AGGridBase)
 *   - `data-testid="holds-grid-header"`, `holds-add-row-btn`,
 *     `holds-save-btn` (HoldEntryGrid)
 */

test.setTimeout(60000);

async function navigateToHoldResume(page: Page) {
  const navLink = page.locator('.v-navigation-drawer a[href="/data-entry/hold-resume"]');
  await navLink.scrollIntoViewIfNeeded();
  await navLink.click({ force: true });
  await page.waitForURL('**/data-entry/hold-resume', { timeout: 15000 });
  await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
}

test.describe('Hold / Resume Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToHoldResume(page);
  });

  test('grid renders with header and Add Row button', async ({ page }) => {
    await expect(page.locator('[data-testid="holds-grid-header"]')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-testid="holds-add-row-btn"]')).toBeVisible();
    await expect(page.locator('[data-testid="ag-grid-wrapper"]')).toBeVisible();
  });

  test('Save button is disabled before any unsaved changes', async ({ page }) => {
    const save = page.locator('[data-testid="holds-save-btn"]');
    await expect(save).toBeVisible({ timeout: 15000 });
    await expect(save).toBeDisabled();
  });

  test('Add Row enables the Save button', async ({ page }) => {
    const addBtn = page.locator('[data-testid="holds-add-row-btn"]');
    await expect(addBtn).toBeVisible({ timeout: 15000 });
    await addBtn.click({ force: true });

    const save = page.locator('[data-testid="holds-save-btn"]');
    await expect(save).toBeEnabled({ timeout: 5000 });
  });

  test('AG Grid toolbar exposes paste / import / export controls', async ({ page }) => {
    await expect(page.locator('[data-testid="ag-grid-toolbar"]')).toBeVisible({ timeout: 15000 });

    const toolbarButtons = page.locator(
      '[data-testid="paste-excel-btn"], [data-testid="csv-import-btn"], [data-testid="csv-export-btn"]'
    );
    expect(await toolbarButtons.count()).toBeGreaterThan(0);
  });

  test('page does not 5xx on load', async ({ page }) => {
    const errors = page.locator('.v-alert--type-error, .fatal-error');
    await expect(errors).toHaveCount(0);
  });
});
