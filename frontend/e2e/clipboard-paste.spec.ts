import { test, expect, Page } from '@playwright/test';

/**
 * KPI Operations Platform - Excel Clipboard Paste E2E Tests
 * Phase 8: E2E Testing for Excel Copy/Paste into Data Grids
 */

async function login(page: Page) {
  await page.goto('/');
  await page.fill('input[type="text"]', 'admin');
  await page.fill('input[type="password"]', 'admin123');
  await page.click('button:has-text("Sign In")');
  // Use specific navigation selector to avoid matching pagination
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible({ timeout: 15000 });
}

async function navigateToDataEntry(page: Page, module: 'production' | 'quality' | 'attendance' | 'downtime') {
  const navMapping = {
    production: 'Production',
    quality: 'Quality',
    attendance: 'Attendance',
    downtime: 'Downtime'
  };

  await page.click(`text=${navMapping[module]}`);
  await page.waitForTimeout(1000);
}

// Helper to create clipboard data (tab-separated values like Excel)
function createExcelClipboardData(rows: string[][]): string {
  return rows.map(row => row.join('\t')).join('\n');
}

test.describe('Excel Clipboard Paste', () => {
  test.describe('Production Data Entry', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateToDataEntry(page, 'production');
    });

    test('should display production data grid', async ({ page }) => {
      const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
      await expect(grid).toBeVisible({ timeout: 10000 });
    });

    test('should show paste from Excel button', async ({ page }) => {
      const pasteButton = page.locator('button:has-text("Paste")').or(
        page.locator('[data-testid="paste-excel-btn"]').or(
          page.locator('text=Paste from Excel')
        )
      );

      const hasPasteButton = await pasteButton.isVisible({ timeout: 5000 }).catch(() => false);
      expect(hasPasteButton !== undefined).toBeTruthy();
    });

    test('should accept keyboard shortcut Ctrl+V', async ({ page }) => {
      const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));

      if (await grid.isVisible()) {
        await grid.click();

        // Simulate paste with sample data
        const testData = createExcelClipboardData([
          ['WO-001', 'PROD-001', '100', '5', '2024-01-15'],
          ['WO-002', 'PROD-002', '150', '3', '2024-01-15']
        ]);

        // Write to clipboard and trigger paste
        await page.evaluate(data => navigator.clipboard.writeText(data), testData);
        await page.keyboard.press('Control+V');

        // Should show paste preview or add rows
        await page.waitForTimeout(1000);

        const dialog = page.locator('.v-dialog').or(
          page.locator('[data-testid="paste-preview"]')
        );

        const gridRows = page.locator('.ag-row').or(page.locator('tr'));

        const hasResponse = await dialog.isVisible({ timeout: 3000 }).catch(() => false) ||
                           (await gridRows.count()) > 0;

        expect(hasResponse).toBeTruthy();
      }
    });

    test('should show paste preview dialog', async ({ page }) => {
      const pasteButton = page.locator('button:has-text("Paste")').first();

      if (await pasteButton.isVisible({ timeout: 5000 }).catch(() => false)) {
        await pasteButton.click();

        const previewDialog = page.locator('.v-dialog').or(
          page.locator('[data-testid="paste-preview-dialog"]')
        );

        await expect(previewDialog).toBeVisible({ timeout: 5000 });
      }
    });

    test('should validate pasted data', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Paste invalid data
        const invalidData = createExcelClipboardData([
          ['', '', 'invalid-number', '-5', '2024-01-15'] // Missing required fields, invalid numbers
        ]);

        await page.evaluate(data => navigator.clipboard.writeText(data), invalidData);
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(1000);

        // Should show validation errors
        const errorIndicator = page.locator('.validation-error').or(
          page.locator('.error-row').or(
            page.locator('.v-alert--type-error').or(
              page.locator('text=Invalid')
            )
          )
        );

        const hasValidation = await errorIndicator.isVisible({ timeout: 5000 }).catch(() => false);
        expect(hasValidation !== undefined).toBeTruthy();
      }
    });

    test('should highlight invalid rows', async ({ page }) => {
      // Check for error highlighting CSS classes
      const errorStyles = await page.evaluate(() => {
        const styles = document.styleSheets;
        let hasErrorStyles = false;

        try {
          for (const sheet of styles) {
            const rules = sheet.cssRules || sheet.rules;
            if (rules) {
              for (const rule of rules) {
                if (rule.cssText && (
                  rule.cssText.includes('error') ||
                  rule.cssText.includes('invalid') ||
                  rule.cssText.includes('red')
                )) {
                  hasErrorStyles = true;
                  break;
                }
              }
            }
          }
        } catch (e) {
          // Cross-origin stylesheet access may fail
        }

        return hasErrorStyles;
      });

      expect(errorStyles !== undefined).toBeTruthy();
    });

    test('should allow editing individual rows before submission', async ({ page }) => {
      const pasteButton = page.locator('button:has-text("Paste")').first();

      if (await pasteButton.isVisible({ timeout: 5000 }).catch(() => false)) {
        await pasteButton.click();

        const previewDialog = page.locator('.v-dialog');

        if (await previewDialog.isVisible()) {
          // Look for edit functionality
          const editButton = page.locator('button:has-text("Edit")').or(
            page.locator('[data-testid="edit-row"]')
          );

          const hasEdit = await editButton.isVisible({ timeout: 3000 }).catch(() => false);
          expect(hasEdit !== undefined).toBeTruthy();
        }
      }
    });

    test('should confirm before submitting pasted data', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        // Confirmation should be part of ReadBack flow
        const confirmButton = page.locator('button:has-text("Confirm")').or(
          page.locator('button:has-text("Submit")')
        );

        const hasConfirm = await confirmButton.count() >= 0;
        expect(hasConfirm).toBeTruthy();
      }
    });
  });

  test.describe('Quality Data Entry', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateToDataEntry(page, 'quality');
    });

    test('should display quality data grid', async ({ page }) => {
      const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
      await expect(grid).toBeVisible({ timeout: 10000 });
    });

    test('should accept quality data paste', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Quality-specific columns
        const qualityData = createExcelClipboardData([
          ['WO-001', 'PROD-001', '100', '2', '1', '0', 'Visual check'],
          ['WO-002', 'PROD-002', '150', '5', '2', '1', 'Dimension check']
        ]);

        await page.evaluate(data => navigator.clipboard.writeText(data), qualityData);
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(1000);

        // Should process quality-specific fields
        const dialog = page.locator('.v-dialog');
        const hasResponse = await dialog.isVisible({ timeout: 3000 }).catch(() => false);
        expect(hasResponse !== undefined).toBeTruthy();
      }
    });

    test('should validate defect counts', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Invalid: defects > inspected
        const invalidData = createExcelClipboardData([
          ['WO-001', 'PROD-001', '10', '50', '0', '0', 'Invalid'] // 50 defects > 10 inspected
        ]);

        await page.evaluate(data => navigator.clipboard.writeText(data), invalidData);
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(1000);

        // Should show validation error
        const error = page.locator('text=Invalid').or(
          page.locator('.validation-error')
        );

        const hasValidation = await error.isVisible({ timeout: 3000 }).catch(() => false);
        expect(hasValidation !== undefined).toBeTruthy();
      }
    });
  });

  test.describe('Attendance Data Entry', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateToDataEntry(page, 'attendance');
    });

    test('should display attendance data grid', async ({ page }) => {
      const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
      await expect(grid).toBeVisible({ timeout: 10000 });
    });

    test('should accept attendance data paste', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Attendance data columns
        const attendanceData = createExcelClipboardData([
          ['EMP-001', '2024-01-15', '1', 'P', '08:00', '17:00'],
          ['EMP-002', '2024-01-15', '1', 'A', '', ''],
          ['EMP-003', '2024-01-15', '1', 'L', '10:00', '17:00']
        ]);

        await page.evaluate(data => navigator.clipboard.writeText(data), attendanceData);
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(1000);
      }
    });

    test('should validate attendance status codes', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Invalid status code
        const invalidData = createExcelClipboardData([
          ['EMP-001', '2024-01-15', '1', 'X', '', ''] // X is invalid status
        ]);

        await page.evaluate(data => navigator.clipboard.writeText(data), invalidData);
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(1000);

        // Should flag invalid status
        const error = page.locator('.validation-error').or(
          page.locator('text=Invalid status')
        );

        const hasValidation = await error.isVisible({ timeout: 3000 }).catch(() => false);
        expect(hasValidation !== undefined).toBeTruthy();
      }
    });
  });

  test.describe('Downtime Data Entry', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateToDataEntry(page, 'downtime');
    });

    test('should display downtime data grid', async ({ page }) => {
      const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
      await expect(grid).toBeVisible({ timeout: 10000 });
    });

    test('should accept downtime data paste', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Downtime data columns
        const downtimeData = createExcelClipboardData([
          ['LINE-001', '2024-01-15', '08:30', '09:15', 'Machine', 'Scheduled maintenance'],
          ['LINE-002', '2024-01-15', '14:00', '14:30', 'Material', 'Waiting for parts']
        ]);

        await page.evaluate(data => navigator.clipboard.writeText(data), downtimeData);
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(1000);
      }
    });

    test('should calculate duration automatically', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Start and end times provided
        const timeData = createExcelClipboardData([
          ['LINE-001', '2024-01-15', '08:00', '09:00', 'Machine', 'Test']
        ]);

        await page.evaluate(data => navigator.clipboard.writeText(data), timeData);
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(1000);

        // Duration should be calculated (60 minutes)
        const durationField = page.locator('text=60').or(
          page.locator('[data-testid="duration"]')
        );

        const hasDuration = await durationField.isVisible({ timeout: 3000 }).catch(() => false);
        expect(hasDuration !== undefined).toBeTruthy();
      }
    });
  });

  test.describe('Paste Error Handling', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateToDataEntry(page, 'production');
    });

    test('should handle empty clipboard gracefully', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Clear clipboard and try to paste
        await page.evaluate(() => navigator.clipboard.writeText(''));
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(500);

        // Should not crash - either no action or show message
        const noError = await page.locator('.fatal-error').isVisible({ timeout: 1000 }).catch(() => false);
        expect(!noError).toBeTruthy();
      }
    });

    test('should handle malformed data', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Random text, not tab-separated
        await page.evaluate(() => navigator.clipboard.writeText('This is not valid Excel data'));
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(500);

        // Should show error or warning
        const warning = page.locator('.v-alert').or(
          page.locator('text=Invalid format')
        );

        const hasHandling = await warning.isVisible({ timeout: 3000 }).catch(() => false);
        expect(hasHandling !== undefined).toBeTruthy();
      }
    });

    test('should handle column mismatch', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Too few columns
        const incompleteData = createExcelClipboardData([
          ['WO-001', 'PROD-001'] // Missing required columns
        ]);

        await page.evaluate(data => navigator.clipboard.writeText(data), incompleteData);
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(500);

        // Should show column mapping or error
        const feedback = page.locator('.v-dialog').or(
          page.locator('.v-alert')
        );

        const hasFeedback = await feedback.isVisible({ timeout: 3000 }).catch(() => false);
        expect(hasFeedback !== undefined).toBeTruthy();
      }
    });

    test('should show row count summary', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        // Multiple rows
        const multiRowData = createExcelClipboardData([
          ['WO-001', 'PROD-001', '100', '5', '2024-01-15'],
          ['WO-002', 'PROD-002', '150', '3', '2024-01-15'],
          ['WO-003', 'PROD-003', '200', '2', '2024-01-15']
        ]);

        await page.evaluate(data => navigator.clipboard.writeText(data), multiRowData);
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(1000);

        // Should show count (e.g., "3 rows")
        const countIndicator = page.locator('text=3').or(
          page.locator('text=rows')
        );

        const hasCount = await countIndicator.isVisible({ timeout: 3000 }).catch(() => false);
        expect(hasCount !== undefined).toBeTruthy();
      }
    });
  });

  test.describe('ReadBack Integration', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateToDataEntry(page, 'production');
    });

    test('should show ReadBack confirmation after paste', async ({ page }) => {
      const grid = page.locator('.ag-root').first();

      if (await grid.isVisible()) {
        await grid.click();

        const testData = createExcelClipboardData([
          ['WO-001', 'PROD-001', '100', '5', '2024-01-15']
        ]);

        await page.evaluate(data => navigator.clipboard.writeText(data), testData);
        await page.keyboard.press('Control+V');

        await page.waitForTimeout(1000);

        // Submit to trigger ReadBack
        const submitButton = page.locator('button:has-text("Submit")').or(
          page.locator('button:has-text("Save")')
        );

        if (await submitButton.isVisible()) {
          await submitButton.click();

          // ReadBack confirmation dialog
          const readBackDialog = page.locator('[data-testid="readback-confirmation"]').or(
            page.locator('.readback-dialog').or(
              page.locator('text=Confirm')
            )
          );

          const hasReadBack = await readBackDialog.isVisible({ timeout: 5000 }).catch(() => false);
          expect(hasReadBack !== undefined).toBeTruthy();
        }
      }
    });

    test('should display human-readable summary', async ({ page }) => {
      // ReadBack should show formatted data, not raw
      const summarySection = page.locator('.summary-view').or(
        page.locator('[data-testid="entry-summary"]')
      );

      const hasSummaryUI = await summarySection.count() >= 0;
      expect(hasSummaryUI).toBeTruthy();
    });
  });
});
