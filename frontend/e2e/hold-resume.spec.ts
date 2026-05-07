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
 * Why `page.goto()` instead of nav-drawer click: the role-based
 * menu expansion (memory/dark-mode-and-nav.md) runs CSS transitions
 * on v-list-group children that fail Playwright's stability check at
 * `scrollIntoViewIfNeeded()` on cold-start CI runners. `goto()`
 * bypasses the drawer entirely; auth state is preserved by login()'s
 * cookie/localStorage state.
 *
 * Stable selectors used (per docs/CONTRIBUTING.md "E2E Parity"):
 *   - `data-testid="ag-grid-wrapper"` (AGGridBase)
 *   - `data-testid="holds-grid-header"`, `holds-add-row-btn`,
 *     `holds-save-btn` (HoldEntryGrid)
 */

test.setTimeout(60000);

test.describe('Hold / Resume Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.goto('/data-entry/hold-resume');
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  });

  test('view + grid surface render', async ({ page }) => {
    await expect(page.locator('[data-testid="hold-resume-entry-view"]')).toBeVisible({ timeout: 20000 });
    await expect(page.locator('[data-testid="ag-grid-wrapper"]').first()).toBeAttached({ timeout: 20000 });
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
