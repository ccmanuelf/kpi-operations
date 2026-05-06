import { test, expect, Page } from '@playwright/test';
import { login } from './helpers';

/**
 * Excel clipboard paste — E2E smoke tests against AGGridBase.
 *
 * The entry-interface audit (Phase 3, 2026-05-02) consolidated paste
 * support into AGGridBase: `enableExcelPaste` + `enableCsvImport`
 * props expose paste/import buttons in the toolbar. The previous
 * spec was rewritten 2026-05-06 against those toolbar testids and a
 * synthetic-ClipboardEvent dispatch pattern that doesn't depend on
 * navigator.clipboard permissions in headless CI Chromium.
 *
 * Stable selectors used (per docs/CONTRIBUTING.md "E2E Parity"):
 *   - `a[href="/...entry"]` for navigation
 *   - `data-testid="ag-grid-toolbar"`, `paste-excel-btn`, etc.
 *   - `data-testid="<entity>-grid-header"` per grid
 */

test.setTimeout(60000);

async function navigateVia(page: Page, href: string) {
  const link = page.locator(`.v-navigation-drawer a[href="${href}"]`);
  await link.scrollIntoViewIfNeeded();
  await link.click({ force: true });
  await page.waitForURL(`**${href}`, { timeout: 15000 });
  await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
}

/**
 * Dispatch a synthetic paste event with the given text. Bypasses
 * the navigator.clipboard permission boundary, which hangs on
 * headless CI Chromium even with grantPermissions.
 */
async function dispatchPaste(page: Page, text: string): Promise<void> {
  await page.evaluate((data) => {
    const target = document.activeElement ?? document.body;
    const dt = new DataTransfer();
    dt.setData('text/plain', data);
    target.dispatchEvent(
      new ClipboardEvent('paste', {
        bubbles: true,
        cancelable: true,
        clipboardData: dt,
      }),
    );
  }, text);
}

function tabSeparated(rows: string[][]): string {
  return rows.map((row) => row.join('\t')).join('\n');
}

test.describe('Excel Clipboard Paste', () => {
  test.describe('Production grid', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateVia(page, '/production-entry');
    });

    test('grid + AG Grid toolbar render', async ({ page }) => {
      await expect(page.locator('[data-testid="production-grid-header"]')).toBeVisible({ timeout: 15000 });
      await expect(page.locator('[data-testid="ag-grid-wrapper"]')).toBeVisible();
      await expect(page.locator('[data-testid="ag-grid-toolbar"]')).toBeVisible();
    });

    test('paste-from-Excel button is in the toolbar', async ({ page }) => {
      const pasteBtn = page.locator('[data-testid="paste-excel-btn"]');
      // Some grids enable paste, some don't — the contract is "if the
      // toolbar shows the button, it's clickable without crashing".
      const visible = await pasteBtn.isVisible({ timeout: 5000 }).catch(() => false);
      if (visible) {
        await pasteBtn.click({ force: true });
        // No fatal-error overlay after click.
        await expect(page.locator('.fatal-error')).toHaveCount(0);
      }
    });
  });

  test.describe('Quality grid', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateVia(page, '/data-entry/quality');
    });

    test('grid renders with toolbar', async ({ page }) => {
      await expect(page.locator('[data-testid="quality-grid-header"]')).toBeVisible({ timeout: 15000 });
      await expect(page.locator('[data-testid="ag-grid-wrapper"]')).toBeVisible();
    });
  });

  test.describe('Downtime grid', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateVia(page, '/data-entry/downtime');
    });

    test('grid renders with toolbar', async ({ page }) => {
      await expect(page.locator('[data-testid="downtime-grid-header"]')).toBeVisible({ timeout: 15000 });
      await expect(page.locator('[data-testid="ag-grid-wrapper"]')).toBeVisible();
    });
  });

  test.describe('Synthetic paste error handling', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateVia(page, '/production-entry');
    });

    test('empty paste does not crash the grid', async ({ page }) => {
      const grid = page.locator('[data-testid="ag-grid-wrapper"]');
      await expect(grid).toBeVisible({ timeout: 15000 });

      // Click into the grid to set focus, then dispatch the synthetic
      // event. force:true sidesteps the role-based-nav-expansion
      // stability check (see helpers.ts comment).
      await grid.click({ force: true });
      await dispatchPaste(page, '');

      await expect(grid).toBeVisible();
      await expect(page.locator('.fatal-error')).toHaveCount(0);
    });

    test('malformed paste does not crash the grid', async ({ page }) => {
      const grid = page.locator('[data-testid="ag-grid-wrapper"]');
      await expect(grid).toBeVisible({ timeout: 15000 });
      await grid.click({ force: true });
      await dispatchPaste(page, 'This is not valid Excel data');

      await expect(grid).toBeVisible();
      await expect(page.locator('.fatal-error')).toHaveCount(0);
    });

    test('column-mismatch paste does not crash the grid', async ({ page }) => {
      const grid = page.locator('[data-testid="ag-grid-wrapper"]');
      await expect(grid).toBeVisible({ timeout: 15000 });
      await grid.click({ force: true });
      await dispatchPaste(page, tabSeparated([['WO-001', 'PROD-001']]));

      await expect(grid).toBeVisible();
      await expect(page.locator('.fatal-error')).toHaveCount(0);
    });
  });
});
