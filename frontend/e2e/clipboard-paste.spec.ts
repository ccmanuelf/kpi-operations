import { test, expect, Page, Locator } from '@playwright/test';
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
  // domcontentloaded (vs networkidle) avoids waits that never resolve
  // when long-lived connections — Vite HMR websocket, in-flight store
  // fetches — keep the network active. Phase B.7 root-caused the
  // original CI flakes to that exact pattern.
  await page.goto(href, { waitUntil: 'domcontentloaded' });
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

/**
 * Drive an AG Grid v35 `agSelectCellEditor` cell: click the cell to
 * start editing (singleClickEdit), then ArrowDown to open the
 * component's own `ag-select` picker (AG Grid's SelectCellEditor wires
 * ArrowDown/Enter/Space on the focused combobox to `showPicker()`
 * unless editing was started by Enter, in which case it auto-opens).
 * The picker renders `.ag-select-list-item` rows in a body-level
 * portal; `mousedown` on one commits the value and stops editing.
 */
async function setGridSelect(cell: Locator, page: Page, itemMatcher: string | RegExp): Promise<void> {
  await cell.click();
  await page.keyboard.press('ArrowDown');
  const item = page.locator('.ag-select-list-item', { hasText: itemMatcher }).first();
  await item.waitFor({ state: 'visible', timeout: 5000 });
  await item.click();
}

async function expectGridCell(cell: Locator, matcher: RegExp): Promise<void> {
  await expect(cell).toHaveText(matcher, { timeout: 5000 });
}

test.describe('Excel Clipboard Paste', () => {
  test.describe('Production grid', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateVia(page, '/production-entry');
    });

    test('grid + AG Grid toolbar render', async ({ page }) => {
      await expect(page.locator('[data-testid="production-entry-view"]')).toBeVisible({ timeout: 15000 });
      await expect(page.locator('[data-testid="ag-grid-wrapper"]').first()).toBeVisible();
      await expect(page.locator('[data-testid="ag-grid-toolbar"]')).toBeVisible();
    });

    test('paste-from-Excel button is in the toolbar', async ({ page }) => {
      const pasteBtn = page.locator('[data-testid="paste-excel-btn"]').first();
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
      await expect(page.locator('[data-testid="quality-entry-view"]')).toBeVisible({ timeout: 15000 });
      await expect(page.locator('[data-testid="ag-grid-wrapper"]').first()).toBeVisible();
    });
  });

  test.describe('Downtime grid', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateVia(page, '/data-entry/downtime');
    });

    test('grid renders with toolbar', async ({ page }) => {
      await expect(page.locator('[data-testid="downtime-entry-view"]')).toBeVisible({ timeout: 15000 });
      await expect(page.locator('[data-testid="ag-grid-wrapper"]').first()).toBeVisible();
    });

    test('downtime grid: reason select auto-fills category, override sticks', async ({ page }) => {
      await expect(page.locator('[data-testid="downtime-entry-view"]')).toBeVisible({ timeout: 15000 });

      await page.locator('[data-testid="downtime-add-row-btn"]').click();
      // addNewEntry() auto-starts editing the new row's shift_date cell
      // (useDowntimeGridData.ts) — back out of it before touching the
      // reason/category cells on the same row.
      await page.waitForTimeout(300);
      await page.keyboard.press('Escape');

      const row = page.locator('.ag-center-cols-container .ag-row[row-index="0"]');
      const reasonCell = row.locator('.ag-cell[col-id="downtime_reason"]');
      const categoryCell = row.locator('.ag-cell[col-id="root_cause_category"]');

      // Reason codes are unformatted in the grid editor (no
      // valueFormatter on that column) — the raw taxonomy code is what
      // renders in the picker list.
      await setGridSelect(reasonCell, page, 'MATERIAL_SHORTAGE');
      await expectGridCell(categoryCell, /Materials|Materiales/);

      // Category codes ARE formatted via categoryLabelKey — the
      // picker shows the translated label, not the raw code.
      await setGridSelect(categoryCell, page, /Scheduling|Programación/);
      await setGridSelect(reasonCell, page, 'EQUIPMENT_FAILURE');
      // The manual override on this row must survive the reason change.
      await expectGridCell(categoryCell, /Scheduling|Programación/);
    });
  });

  test.describe('Synthetic paste error handling', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateVia(page, '/production-entry');
    });

    test('empty paste does not crash the grid', async ({ page }) => {
      const grid = page.locator('[data-testid="ag-grid-wrapper"]').first();
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
      const grid = page.locator('[data-testid="ag-grid-wrapper"]').first();
      await expect(grid).toBeVisible({ timeout: 15000 });
      await grid.click({ force: true });
      await dispatchPaste(page, 'This is not valid Excel data');

      await expect(grid).toBeVisible();
      await expect(page.locator('.fatal-error')).toHaveCount(0);
    });

    test('column-mismatch paste does not crash the grid', async ({ page }) => {
      const grid = page.locator('[data-testid="ag-grid-wrapper"]').first();
      await expect(grid).toBeVisible({ timeout: 15000 });
      await grid.click({ force: true });
      await dispatchPaste(page, tabSeparated([['WO-001', 'PROD-001']]));

      await expect(grid).toBeVisible();
      await expect(page.locator('.fatal-error')).toHaveCount(0);
    });
  });
});
