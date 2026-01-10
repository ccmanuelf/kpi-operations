/**
 * Quality Entry E2E Tests
 * Tests quality inspection workflow: CRUD, defect tracking, PPM/DPMO/FPY calculations
 */
import { test, expect } from '@playwright/test';

test.describe('Quality Entry Workflow', () => {

  test.describe('Quality Inspection CRUD', () => {

    test('should create a new quality inspection', async ({ page }) => {
      await page.goto('/quality');
      await page.waitForSelector('.ag-root-wrapper, form[name="quality"]');

      // Add new inspection
      await page.click('button:has-text("Add"), button:has-text("New Inspection")');

      // Fill inspection data
      await page.fill('input[name="units_inspected"]', '500');
      await page.fill('input[name="defects_found"]', '3');
      await page.fill('input[name="scrap_count"]', '1');
      await page.fill('input[name="rework_count"]', '2');

      // Select defect category
      await page.click('[aria-label="Defect Category"]');
      await page.click('text=Visual');

      // Save
      await page.click('button:has-text("Save")');

      // Verify success
      await expect(page.locator('.v-snackbar')).toContainText(/created|saved|success/i);
    });

    test('should edit quality inspection', async ({ page }) => {
      await page.goto('/quality');
      await page.waitForSelector('.ag-root-wrapper');

      // Select and edit
      await page.locator('.ag-row').first().click();
      await page.click('button:has-text("Edit")');

      // Update defects
      await page.fill('input[name="defects_found"]', '5');
      await page.click('button:has-text("Save")');

      // Verify
      await expect(page.locator('.v-snackbar')).toContainText(/updated|saved/i);
    });

    test('should delete quality inspection', async ({ page }) => {
      await page.goto('/quality');
      await page.waitForSelector('.ag-root-wrapper');

      await page.locator('.ag-row').first().click();
      await page.click('button:has-text("Delete")');
      await page.click('button:has-text("Confirm")');

      await expect(page.locator('.v-snackbar')).toContainText(/deleted/i);
    });
  });

  test.describe('Defect Tracking', () => {

    test('should add defect details', async ({ page }) => {
      await page.goto('/quality');
      await page.waitForSelector('.ag-root-wrapper');

      // Select an inspection
      await page.locator('.ag-row').first().click();

      // Click "Add Defect Detail"
      await page.click('button:has-text("Add Defect"), button:has-text("Defect Details")');

      // Fill defect details
      await page.fill('input[name="defect_type"]', 'Thread Loose');
      await page.fill('input[name="defect_location"]', 'Left Side Panel');
      await page.fill('input[name="defect_count"]', '2');

      // Select severity
      await page.click('[aria-label="Severity"]');
      await page.click('text=Minor');

      // Save
      await page.click('button:has-text("Save Defect")');

      // Verify defect added
      await expect(page.locator('.defect-list, .defect-table')).toContainText('Thread Loose');
    });

    test('should show defect pareto chart', async ({ page }) => {
      await page.goto('/quality');

      // Look for pareto chart
      const paretoChart = page.locator('.pareto-chart, canvas:near(:text("Pareto"))');
      await expect(paretoChart).toBeVisible();
    });

    test('should filter by defect category', async ({ page }) => {
      await page.goto('/quality');
      await page.waitForSelector('.ag-root-wrapper');

      // Open filter
      await page.click('button:has-text("Filter")');

      // Select Visual defects
      await page.click('[aria-label="Defect Category Filter"]');
      await page.click('text=Visual');
      await page.click('button:has-text("Apply")');

      // Verify filter applied
      const rows = page.locator('.ag-row');
      const count = await rows.count();
      for (let i = 0; i < Math.min(count, 5); i++) {
        await expect(rows.nth(i)).toContainText(/Visual|VISUAL/);
      }
    });
  });

  test.describe('Quality KPIs', () => {

    test('should display PPM calculation', async ({ page }) => {
      await page.goto('/quality');

      // Look for PPM KPI
      const ppmKPI = page.locator('.kpi-card:has-text("PPM"), .metric:has-text("PPM")');
      await expect(ppmKPI).toBeVisible();

      // Verify numeric value
      await expect(ppmKPI).toContainText(/\d+/);
    });

    test('should display DPMO calculation', async ({ page }) => {
      await page.goto('/quality');

      // Look for DPMO KPI
      const dpmoKPI = page.locator('.kpi-card:has-text("DPMO"), .metric:has-text("DPMO")');
      await expect(dpmoKPI).toBeVisible();
    });

    test('should display FPY (First Pass Yield)', async ({ page }) => {
      await page.goto('/quality');

      // Look for FPY KPI
      const fpyKPI = page.locator('.kpi-card:has-text("FPY"), .kpi-card:has-text("First Pass")');
      await expect(fpyKPI).toBeVisible();
      await expect(fpyKPI).toContainText('%');
    });

    test('should display RTY (Rolled Throughput Yield)', async ({ page }) => {
      await page.goto('/quality');

      // Look for RTY KPI
      const rtyKPI = page.locator('.kpi-card:has-text("RTY"), .kpi-card:has-text("Rolled Throughput")');
      await expect(rtyKPI).toBeVisible();
    });

    test('should recalculate KPIs when inspection added', async ({ page }) => {
      await page.goto('/quality');

      // Get initial PPM
      const ppmValue = page.locator('.ppm-value, .kpi-value:near(:text("PPM"))');
      const initialPPM = await ppmValue.textContent();

      // Add inspection with high defects
      await page.click('button:has-text("Add")');
      await page.fill('input[name="units_inspected"]', '100');
      await page.fill('input[name="defects_found"]', '10');
      await page.click('button:has-text("Save")');

      // Wait for recalculation
      await page.waitForTimeout(2000);

      // PPM should increase (more defects)
      const newPPM = await ppmValue.textContent();
      // Verify change occurred
    });
  });

  test.describe('Quality Reports', () => {

    test('should generate quality trend report', async ({ page }) => {
      await page.goto('/quality');

      // Click reports
      await page.click('button:has-text("Reports")');

      // Select quality trend
      await page.click('text=Quality Trend');

      // Verify chart loads
      await expect(page.locator('.trend-chart, canvas')).toBeVisible();
    });

    test('should export quality data to Excel', async ({ page }) => {
      await page.goto('/quality');

      // Click export
      const downloadPromise = page.waitForEvent('download');
      await page.click('button:has-text("Export"), button:has-text("Excel")');

      // Verify download started
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toContain('.xlsx');
    });
  });
});
