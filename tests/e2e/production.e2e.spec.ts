/**
 * Production Entry E2E Tests
 * Tests complete production workflow: CRUD operations, CSV upload, KPI calculations
 */
import { test, expect, Page } from '@playwright/test';

test.describe('Production Entry Workflow', () => {

  test.describe('Manual Data Entry', () => {

    test('should create a new production entry via grid', async ({ page }) => {
      await page.goto('/production');

      // Wait for AG Grid to load
      await page.waitForSelector('.ag-root-wrapper');

      // Click "Add Row" button
      await page.click('button:has-text("Add Row"), button:has-text("Add Entry")');

      // Fill in the new row using AG Grid cell editing
      const gridRow = page.locator('.ag-row:last-child');

      // Double-click to edit cell
      await gridRow.locator('.ag-cell[col-id="work_order_number"]').dblclick();
      await page.keyboard.type('WO-E2E-TEST-001');
      await page.keyboard.press('Tab');

      // Fill units produced
      await page.keyboard.type('250');
      await page.keyboard.press('Tab');

      // Fill run time hours
      await page.keyboard.type('8.5');
      await page.keyboard.press('Tab');

      // Fill employees assigned
      await page.keyboard.type('5');
      await page.keyboard.press('Enter');

      // Save the entry
      await page.click('button:has-text("Save"), button:has-text("Submit")');

      // Verify success notification
      await expect(page.locator('.v-snackbar, .notification')).toContainText(/saved|created|success/i);

      // Verify entry appears in grid
      await expect(page.locator('.ag-cell:has-text("WO-E2E-TEST-001")')).toBeVisible();
    });

    test('should edit existing production entry', async ({ page }) => {
      await page.goto('/production');

      // Wait for grid to load
      await page.waitForSelector('.ag-root-wrapper');

      // Find an existing row and double-click to edit
      const firstRow = page.locator('.ag-row').first();
      const unitsCell = firstRow.locator('.ag-cell[col-id="units_produced"]');

      await unitsCell.dblclick();

      // Clear and enter new value
      await page.keyboard.press('Control+a');
      await page.keyboard.type('999');
      await page.keyboard.press('Enter');

      // Save changes
      await page.click('button:has-text("Save")');

      // Verify save success
      await expect(page.locator('.v-snackbar, .notification')).toContainText(/saved|updated|success/i);
    });

    test('should delete production entry with confirmation', async ({ page }) => {
      await page.goto('/production');
      await page.waitForSelector('.ag-root-wrapper');

      // Select a row
      const firstRow = page.locator('.ag-row').first();
      await firstRow.click();

      // Click delete button
      await page.click('button:has-text("Delete")');

      // Confirm deletion in dialog
      await page.click('button:has-text("Confirm"), button:has-text("Yes")');

      // Verify deletion notification
      await expect(page.locator('.v-snackbar, .notification')).toContainText(/deleted|removed/i);
    });

    test('should validate required fields', async ({ page }) => {
      await page.goto('/production');
      await page.waitForSelector('.ag-root-wrapper');

      // Click Add Row
      await page.click('button:has-text("Add Row")');

      // Try to save without filling required fields
      await page.click('button:has-text("Save")');

      // Verify validation errors
      await expect(page.locator('.v-messages__message, .error-text')).toContainText(/required/i);
    });
  });

  test.describe('CSV Upload', () => {

    test('should upload valid CSV file successfully', async ({ page }) => {
      await page.goto('/production');

      // Open CSV upload dialog
      await page.click('button:has-text("Upload CSV"), button:has-text("Import")');

      // Wait for upload dialog
      await page.waitForSelector('[role="dialog"]');

      // Upload file
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'production_test.csv',
        mimeType: 'text/csv',
        buffer: Buffer.from(
          'work_order_number,production_date,units_produced,run_time_hours,employees_assigned\n' +
          'WO-CSV-001,2025-01-01,100,8.0,3\n' +
          'WO-CSV-002,2025-01-02,150,8.5,4\n' +
          'WO-CSV-003,2025-01-03,200,7.5,5\n'
        )
      });

      // Wait for validation
      await page.waitForSelector('.validation-results, .preview-table');

      // Verify preview shows correct counts
      await expect(page.locator('text=3 valid rows, text=Valid: 3')).toBeVisible();

      // Click import button
      await page.click('button:has-text("Import"), button:has-text("Confirm")');

      // Verify success
      await expect(page.locator('.v-snackbar, .notification')).toContainText(/imported|success/i);
    });

    test('should show validation errors for invalid CSV', async ({ page }) => {
      await page.goto('/production');
      await page.click('button:has-text("Upload CSV")');
      await page.waitForSelector('[role="dialog"]');

      // Upload CSV with errors
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'production_errors.csv',
        mimeType: 'text/csv',
        buffer: Buffer.from(
          'work_order_number,production_date,units_produced,run_time_hours,employees_assigned\n' +
          'WO-VALID-001,2025-01-01,100,8.0,3\n' +
          'WO-INVALID-001,invalid-date,abc,8.0,3\n' +  // Invalid date and units
          'WO-INVALID-002,2025-01-02,-50,8.0,3\n'      // Negative units
        )
      });

      // Wait for validation
      await page.waitForSelector('.validation-results');

      // Verify error messages shown
      await expect(page.locator('.error-row, .validation-error')).toHaveCount(2);
      await expect(page.locator('text=/invalid.*date|date.*error/i')).toBeVisible();
    });

    test('should allow partial import with valid rows', async ({ page }) => {
      await page.goto('/production');
      await page.click('button:has-text("Upload CSV")');
      await page.waitForSelector('[role="dialog"]');

      // Upload CSV with mixed valid/invalid rows
      const fileInput = page.locator('input[type="file"]');
      await fileInput.setInputFiles({
        name: 'production_mixed.csv',
        mimeType: 'text/csv',
        buffer: Buffer.from(
          'work_order_number,production_date,units_produced,run_time_hours,employees_assigned\n' +
          'WO-VALID-001,2025-01-01,100,8.0,3\n' +
          'WO-VALID-002,2025-01-02,150,8.5,4\n' +
          'WO-INVALID-001,bad-date,xyz,8.0,3\n'
        )
      });

      // Wait for validation
      await page.waitForSelector('.validation-results');

      // Check partial import checkbox if available
      const partialCheckbox = page.locator('input[type="checkbox"]:near(:text("Import valid rows"))');
      if (await partialCheckbox.isVisible()) {
        await partialCheckbox.check();
      }

      // Click import
      await page.click('button:has-text("Import Valid"), button:has-text("Import")');

      // Verify success with partial import message
      await expect(page.locator('.v-snackbar, .notification')).toContainText(/2.*imported|imported.*2/i);
    });
  });

  test.describe('KPI Calculation', () => {

    test('should display efficiency KPI after data entry', async ({ page }) => {
      await page.goto('/production');
      await page.waitForSelector('.ag-root-wrapper');

      // Look for efficiency column in grid
      const efficiencyHeader = page.locator('.ag-header-cell:has-text("Efficiency")');
      await expect(efficiencyHeader).toBeVisible();

      // Verify efficiency values are calculated (not N/A or empty)
      const efficiencyCells = page.locator('.ag-cell[col-id="efficiency_percent"]');
      const firstCell = efficiencyCells.first();
      await expect(firstCell).not.toContainText('N/A');
    });

    test('should display performance KPI', async ({ page }) => {
      await page.goto('/production');
      await page.waitForSelector('.ag-root-wrapper');

      // Look for performance column
      const performanceHeader = page.locator('.ag-header-cell:has-text("Performance")');
      await expect(performanceHeader).toBeVisible();

      // Verify performance values exist
      const performanceCells = page.locator('.ag-cell[col-id="performance_percent"]');
      const firstCell = performanceCells.first();
      await expect(firstCell).not.toBeEmpty();
    });

    test('should recalculate KPIs when data changes', async ({ page }) => {
      await page.goto('/production');
      await page.waitForSelector('.ag-root-wrapper');

      // Get initial efficiency value
      const efficiencyCell = page.locator('.ag-cell[col-id="efficiency_percent"]').first();
      const initialValue = await efficiencyCell.textContent();

      // Edit units produced to a higher value
      const unitsCell = page.locator('.ag-cell[col-id="units_produced"]').first();
      await unitsCell.dblclick();
      await page.keyboard.press('Control+a');
      await page.keyboard.type('9999');
      await page.keyboard.press('Enter');

      // Wait for recalculation
      await page.waitForTimeout(1000);

      // Verify efficiency changed
      const newValue = await efficiencyCell.textContent();
      expect(newValue).not.toBe(initialValue);
    });
  });

  test.describe('Read-back Confirmation', () => {

    test('should show read-back dialog before final save', async ({ page }) => {
      await page.goto('/production');
      await page.waitForSelector('.ag-root-wrapper');

      // Make some changes
      await page.click('button:has-text("Add Row")');
      const gridRow = page.locator('.ag-row:last-child');
      await gridRow.locator('.ag-cell').first().dblclick();
      await page.keyboard.type('WO-READBACK-TEST');
      await page.keyboard.press('Enter');

      // Click submit batch
      await page.click('button:has-text("Submit Batch"), button:has-text("Save All")');

      // Verify read-back dialog appears
      await expect(page.locator('[role="dialog"]:has-text("Confirm"), [role="dialog"]:has-text("Review")')).toBeVisible();

      // Verify the changes are listed
      await expect(page.locator('[role="dialog"]')).toContainText('WO-READBACK-TEST');

      // Confirm
      await page.click('button:has-text("Confirm"), button:has-text("Save")');

      // Verify success
      await expect(page.locator('.v-snackbar')).toContainText(/success|saved/i);
    });
  });
});
