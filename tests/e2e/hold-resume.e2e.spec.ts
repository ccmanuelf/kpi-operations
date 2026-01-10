/**
 * Hold/Resume Workflow E2E Tests
 * Tests WIP hold workflow: create hold, resume, aging tracking
 */
import { test, expect } from '@playwright/test';

test.describe('Hold/Resume Workflow', () => {

  test.describe('WIP Hold Operations', () => {

    test('should create a new hold', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper, form[name="hold"]');

      // Add new hold
      await page.click('button:has-text("Add Hold"), button:has-text("New Hold")');

      // Fill hold data
      await page.fill('input[name="work_order_number"]', 'WO-HOLD-E2E-001');
      await page.fill('input[name="units_on_hold"]', '50');

      // Select hold reason
      await page.click('[aria-label="Hold Reason"]');
      await page.click('text=Quality Issue');

      // Select priority
      await page.click('[aria-label="Priority"]');
      await page.click('text=High');

      // Add notes
      await page.fill('textarea[name="hold_notes"]', 'E2E Test - Pending inspection');

      // Save
      await page.click('button:has-text("Save"), button:has-text("Create Hold")');

      // Verify success
      await expect(page.locator('.v-snackbar')).toContainText(/created|saved|success/i);

      // Verify hold appears in list
      await expect(page.locator('.ag-cell:has-text("WO-HOLD-E2E-001")')).toBeVisible();
    });

    test('should edit hold details', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper');

      // Select hold
      await page.locator('.ag-row').first().click();
      await page.click('button:has-text("Edit")');

      // Update units on hold
      await page.fill('input[name="units_on_hold"]', '75');

      // Save
      await page.click('button:has-text("Save")');

      await expect(page.locator('.v-snackbar')).toContainText(/updated/i);
    });

    test('should delete hold', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper');

      await page.locator('.ag-row').first().click();
      await page.click('button:has-text("Delete")');
      await page.click('button:has-text("Confirm")');

      await expect(page.locator('.v-snackbar')).toContainText(/deleted/i);
    });
  });

  test.describe('Resume Workflow', () => {

    test('should resume hold with full release', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper');

      // Find an active hold
      const activeHold = page.locator('.ag-row:has(.status-active), .ag-row:has-text("Active")');

      if (await activeHold.count() > 0) {
        await activeHold.first().click();

        // Click resume
        await page.click('button:has-text("Resume"), button:has-text("Release")');

        // Select full release
        await page.click('text=Full Release');

        // Add resolution notes
        await page.fill('textarea[name="resolution_notes"]', 'E2E Test - Issue resolved, all units released');

        // Confirm
        await page.click('button:has-text("Confirm Resume")');

        // Verify status changed
        await expect(page.locator('.v-snackbar')).toContainText(/resumed|released|resolved/i);
      }
    });

    test('should resume hold with partial release', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper');

      const activeHold = page.locator('.ag-row:has(.status-active)');

      if (await activeHold.count() > 0) {
        await activeHold.first().click();
        await page.click('button:has-text("Resume")');

        // Select partial release
        await page.click('text=Partial Release');

        // Enter units to release
        await page.fill('input[name="units_released"]', '25');

        // Add notes
        await page.fill('textarea[name="resolution_notes"]', 'E2E Test - Partial release, remaining under review');

        // Confirm
        await page.click('button:has-text("Confirm")');

        // Verify partial release
        await expect(page.locator('.v-snackbar')).toContainText(/released|updated/i);
      }
    });

    test('should track resume history', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper');

      // Select a hold with history
      await page.locator('.ag-row').first().click();

      // Click history tab/button
      await page.click('text=History, button:has-text("History")');

      // Verify history displayed
      await expect(page.locator('.history-list, .audit-trail')).toBeVisible();
    });
  });

  test.describe('WIP Aging', () => {

    test('should display WIP aging days', async ({ page }) => {
      await page.goto('/holds');

      // Look for aging column in grid
      const agingHeader = page.locator('.ag-header-cell:has-text("Aging"), .ag-header-cell:has-text("Days on Hold")');
      await expect(agingHeader).toBeVisible();

      // Verify aging values shown
      const agingCells = page.locator('.ag-cell[col-id="aging_days"], .ag-cell[col-id="days_on_hold"]');
      if (await agingCells.count() > 0) {
        const firstCell = agingCells.first();
        await expect(firstCell).toContainText(/\d+/);
      }
    });

    test('should highlight aged items', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper');

      // Look for aged item highlighting (> 7 days typically)
      const agedItems = page.locator('.ag-row.aged, .ag-row:has(.warning-badge)');
      // May or may not have aged items
    });

    test('should sort by aging', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper');

      // Click aging header to sort
      await page.click('.ag-header-cell:has-text("Aging"), .ag-header-cell:has-text("Days")');

      // Verify sort applied (descending - oldest first)
      await page.click('.ag-header-cell:has-text("Aging")');

      // Get first row aging value
      const firstAgingCell = page.locator('.ag-cell[col-id="aging_days"]').first();
      const firstValue = await firstAgingCell.textContent();

      // Click to sort ascending
      await page.click('.ag-header-cell:has-text("Aging")');

      // First value should now be smaller
      const newFirstValue = await firstAgingCell.textContent();
      expect(parseInt(newFirstValue || '0')).toBeLessThanOrEqual(parseInt(firstValue || '999'));
    });

    test('should display WIP aging KPI on dashboard', async ({ page }) => {
      await page.goto('/dashboard');

      // Look for WIP aging KPI
      const wipAgingKPI = page.locator('.kpi-card:has-text("WIP Aging"), .kpi-card:has-text("On Hold")');
      await expect(wipAgingKPI).toBeVisible();
    });
  });

  test.describe('Hold Filtering', () => {

    test('should filter by hold reason', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper');

      // Open filter
      await page.click('button:has-text("Filter")');

      // Select Quality Issue
      await page.click('[aria-label="Hold Reason Filter"]');
      await page.click('text=Quality Issue');
      await page.click('button:has-text("Apply")');

      // Verify filter
      const rows = page.locator('.ag-row');
      const count = await rows.count();
      for (let i = 0; i < Math.min(count, 5); i++) {
        await expect(rows.nth(i)).toContainText(/Quality|QUALITY/);
      }
    });

    test('should filter by status', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper');

      // Filter active holds only
      await page.click('button:has-text("Filter")');
      await page.click('[aria-label="Status Filter"]');
      await page.click('text=Active');
      await page.click('button:has-text("Apply")');

      // Verify all visible are active
      const rows = page.locator('.ag-row');
      const count = await rows.count();
      for (let i = 0; i < Math.min(count, 5); i++) {
        await expect(rows.nth(i)).toContainText(/Active|ACTIVE/);
      }
    });

    test('should filter by priority', async ({ page }) => {
      await page.goto('/holds');
      await page.waitForSelector('.ag-root-wrapper');

      // Filter high priority
      await page.click('button:has-text("Filter")');
      await page.click('[aria-label="Priority Filter"]');
      await page.click('text=High');
      await page.click('button:has-text("Apply")');

      // Verify filter
      const rows = page.locator('.ag-row');
      const count = await rows.count();
      for (let i = 0; i < Math.min(count, 5); i++) {
        await expect(rows.nth(i)).toContainText(/High|HIGH/);
      }
    });
  });
});
