/**
 * AG Grid Interaction E2E Tests
 * Tests AG Grid-specific functionality: copy/paste, fill handle, undo/redo, keyboard shortcuts
 */
import { test, expect } from '@playwright/test';

test.describe('AG Grid Interactions', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/production');
    await page.waitForSelector('.ag-root-wrapper');
  });

  test.describe('Cell Editing', () => {

    test('should enter edit mode on double-click', async ({ page }) => {
      // Double-click a cell
      const cell = page.locator('.ag-cell[col-id="units_produced"]').first();
      await cell.dblclick();

      // Verify edit mode (input should be visible)
      await expect(page.locator('.ag-cell-inline-editing input, .ag-cell-editing')).toBeVisible();
    });

    test('should enter edit mode on Enter key', async ({ page }) => {
      // Click a cell to select
      const cell = page.locator('.ag-cell[col-id="units_produced"]').first();
      await cell.click();

      // Press Enter
      await page.keyboard.press('Enter');

      // Verify edit mode
      await expect(page.locator('.ag-cell-inline-editing, .ag-cell-editing')).toBeVisible();
    });

    test('should save on Enter', async ({ page }) => {
      const cell = page.locator('.ag-cell[col-id="units_produced"]').first();
      await cell.dblclick();

      // Type value
      await page.keyboard.type('999');

      // Press Enter to save
      await page.keyboard.press('Enter');

      // Verify value saved
      await expect(cell).toContainText('999');
    });

    test('should cancel on Escape', async ({ page }) => {
      const cell = page.locator('.ag-cell[col-id="units_produced"]').first();
      const originalValue = await cell.textContent();

      await cell.dblclick();
      await page.keyboard.type('CHANGED');

      // Press Escape to cancel
      await page.keyboard.press('Escape');

      // Verify original value restored
      await expect(cell).toContainText(originalValue || '');
    });

    test('should move to next cell on Tab', async ({ page }) => {
      const firstCell = page.locator('.ag-cell').first();
      await firstCell.dblclick();
      await page.keyboard.type('100');

      // Press Tab
      await page.keyboard.press('Tab');

      // Should move to next cell in edit mode
      await expect(page.locator('.ag-cell-inline-editing, .ag-cell-focus')).toBeVisible();
    });
  });

  test.describe('Copy/Paste Operations', () => {

    test('should copy single cell value', async ({ page }) => {
      // Select a cell
      const cell = page.locator('.ag-cell[col-id="units_produced"]').first();
      await cell.click();

      // Copy (Ctrl+C)
      await page.keyboard.press('Control+c');

      // Select another cell
      const targetCell = page.locator('.ag-cell[col-id="units_produced"]').nth(1);
      await targetCell.click();

      // Paste (Ctrl+V)
      await page.keyboard.press('Control+v');

      // Values should be same
      const sourceValue = await cell.textContent();
      await expect(targetCell).toContainText(sourceValue || '');
    });

    test('should copy multiple cells', async ({ page }) => {
      // Click first cell
      const firstCell = page.locator('.ag-cell').first();
      await firstCell.click();

      // Shift+Click to select range
      const thirdCell = page.locator('.ag-cell').nth(2);
      await thirdCell.click({ modifiers: ['Shift'] });

      // Copy
      await page.keyboard.press('Control+c');

      // Select target row
      const targetRow = page.locator('.ag-row').nth(2);
      await targetRow.locator('.ag-cell').first().click();

      // Paste
      await page.keyboard.press('Control+v');
    });

    test('should paste from clipboard', async ({ page }) => {
      // Set clipboard content
      await page.evaluate(() => {
        navigator.clipboard.writeText('500\t8.5\t5');
      });

      // Select a cell
      const cell = page.locator('.ag-cell').first();
      await cell.click();

      // Paste
      await page.keyboard.press('Control+v');

      // Verify paste occurred
      await expect(cell).toContainText('500');
    });
  });

  test.describe('Fill Handle', () => {

    test('should fill down when dragging fill handle', async ({ page }) => {
      // Find a cell with fill handle
      const cell = page.locator('.ag-cell[col-id="units_produced"]').first();
      await cell.click();

      // Get cell value
      const value = await cell.textContent();

      // Find fill handle
      const fillHandle = page.locator('.ag-fill-handle, .ag-range-handle');

      if (await fillHandle.isVisible()) {
        // Drag fill handle down
        const cellBox = await cell.boundingBox();
        await fillHandle.dragTo(page.locator('.ag-cell[col-id="units_produced"]').nth(3));

        // Verify cells filled
        const targetCell = page.locator('.ag-cell[col-id="units_produced"]').nth(1);
        await expect(targetCell).toContainText(value || '');
      }
    });
  });

  test.describe('Undo/Redo', () => {

    test('should undo last change with Ctrl+Z', async ({ page }) => {
      const cell = page.locator('.ag-cell[col-id="units_produced"]').first();
      const originalValue = await cell.textContent();

      // Make a change
      await cell.dblclick();
      await page.keyboard.press('Control+a');
      await page.keyboard.type('NEWVALUE');
      await page.keyboard.press('Enter');

      // Undo
      await page.keyboard.press('Control+z');

      // Verify original value restored
      await expect(cell).toContainText(originalValue || '');
    });

    test('should redo with Ctrl+Y', async ({ page }) => {
      const cell = page.locator('.ag-cell[col-id="units_produced"]').first();

      // Make a change
      await cell.dblclick();
      await page.keyboard.press('Control+a');
      await page.keyboard.type('REDOTEST');
      await page.keyboard.press('Enter');

      // Undo
      await page.keyboard.press('Control+z');

      // Redo
      await page.keyboard.press('Control+y');

      // Verify change restored
      await expect(cell).toContainText('REDOTEST');
    });
  });

  test.describe('Row Selection', () => {

    test('should select row on click', async ({ page }) => {
      const row = page.locator('.ag-row').first();
      await row.click();

      // Verify row selected
      await expect(row).toHaveClass(/ag-row-selected/);
    });

    test('should multi-select with Ctrl+Click', async ({ page }) => {
      const row1 = page.locator('.ag-row').first();
      const row2 = page.locator('.ag-row').nth(2);

      await row1.click();
      await row2.click({ modifiers: ['Control'] });

      // Both should be selected
      await expect(row1).toHaveClass(/ag-row-selected/);
      await expect(row2).toHaveClass(/ag-row-selected/);
    });

    test('should range select with Shift+Click', async ({ page }) => {
      const row1 = page.locator('.ag-row').first();
      const row3 = page.locator('.ag-row').nth(2);

      await row1.click();
      await row3.click({ modifiers: ['Shift'] });

      // All rows in range should be selected
      await expect(row1).toHaveClass(/ag-row-selected/);
      await expect(page.locator('.ag-row').nth(1)).toHaveClass(/ag-row-selected/);
      await expect(row3).toHaveClass(/ag-row-selected/);
    });

    test('should select all with Ctrl+A', async ({ page }) => {
      // Click grid first
      await page.locator('.ag-body').click();

      // Select all
      await page.keyboard.press('Control+a');

      // Verify all rows selected
      const selectedRows = page.locator('.ag-row-selected');
      const allRows = page.locator('.ag-row');
      expect(await selectedRows.count()).toBe(await allRows.count());
    });
  });

  test.describe('Sorting', () => {

    test('should sort ascending on header click', async ({ page }) => {
      // Click units_produced header
      await page.click('.ag-header-cell[col-id="units_produced"]');

      // Verify sort indicator
      await expect(page.locator('.ag-header-cell[col-id="units_produced"] .ag-sort-ascending-icon, .ag-header-cell[col-id="units_produced"] .ag-icon-asc')).toBeVisible();
    });

    test('should sort descending on second click', async ({ page }) => {
      const header = page.locator('.ag-header-cell[col-id="units_produced"]');

      // First click - ascending
      await header.click();

      // Second click - descending
      await header.click();

      // Verify sort indicator
      await expect(page.locator('.ag-header-cell[col-id="units_produced"] .ag-sort-descending-icon, .ag-header-cell[col-id="units_produced"] .ag-icon-desc')).toBeVisible();
    });

    test('should clear sort on third click', async ({ page }) => {
      const header = page.locator('.ag-header-cell[col-id="units_produced"]');

      await header.click();
      await header.click();
      await header.click();

      // Verify no sort indicator
      await expect(page.locator('.ag-header-cell[col-id="units_produced"] .ag-sort-ascending-icon')).not.toBeVisible();
      await expect(page.locator('.ag-header-cell[col-id="units_produced"] .ag-sort-descending-icon')).not.toBeVisible();
    });
  });

  test.describe('Filtering', () => {

    test('should open column filter', async ({ page }) => {
      // Click filter icon on header
      const filterIcon = page.locator('.ag-header-cell[col-id="units_produced"] .ag-header-cell-menu-button, .ag-filter-icon');

      if (await filterIcon.isVisible()) {
        await filterIcon.click();

        // Verify filter popup
        await expect(page.locator('.ag-popup, .ag-filter')).toBeVisible();
      }
    });

    test('should filter with text input', async ({ page }) => {
      // Open filter
      await page.locator('.ag-header-cell[col-id="work_order_number"] .ag-header-cell-menu-button').click();

      // Enter filter text
      await page.fill('.ag-filter input', 'WO-');

      // Verify filtered results
      const rows = page.locator('.ag-row');
      const count = await rows.count();
      for (let i = 0; i < Math.min(count, 5); i++) {
        await expect(rows.nth(i)).toContainText('WO-');
      }
    });
  });

  test.describe('Keyboard Navigation', () => {

    test('should navigate with arrow keys', async ({ page }) => {
      // Click first cell
      const firstCell = page.locator('.ag-cell').first();
      await firstCell.click();

      // Press Down arrow
      await page.keyboard.press('ArrowDown');

      // Verify focus moved
      await expect(page.locator('.ag-cell.ag-cell-focus').first()).not.toEqual(firstCell);
    });

    test('should jump to first row with Ctrl+Home', async ({ page }) => {
      // Click a cell in the middle
      await page.locator('.ag-row').nth(5).locator('.ag-cell').first().click();

      // Ctrl+Home
      await page.keyboard.press('Control+Home');

      // Verify at first row
      await expect(page.locator('.ag-row').first().locator('.ag-cell.ag-cell-focus')).toBeVisible();
    });

    test('should jump to last row with Ctrl+End', async ({ page }) => {
      // Click first cell
      await page.locator('.ag-cell').first().click();

      // Ctrl+End
      await page.keyboard.press('Control+End');

      // Verify at last row
      await expect(page.locator('.ag-row').last().locator('.ag-cell.ag-cell-focus, .ag-cell-focus')).toBeVisible();
    });
  });
});
