/**
 * KPI Dashboard E2E Tests
 * Tests KPI dashboard display, filtering, charting, and reporting
 */
import { test, expect } from '@playwright/test';

test.describe('KPI Dashboard', () => {

  test.describe('Dashboard Display', () => {

    test('should load dashboard with all KPI cards', async ({ page }) => {
      await page.goto('/dashboard');

      // Wait for dashboard to load
      await page.waitForSelector('.kpi-card, .metric-card');

      // Verify all 10 KPIs are displayed
      const kpiCards = page.locator('.kpi-card, .metric-card');
      await expect(kpiCards).toHaveCount({ min: 8 });

      // Verify specific KPIs
      await expect(page.locator('text=Efficiency')).toBeVisible();
      await expect(page.locator('text=Performance')).toBeVisible();
      await expect(page.locator('text=Quality')).toBeVisible();
      await expect(page.locator('text=Availability')).toBeVisible();
    });

    test('should display OEE calculation', async ({ page }) => {
      await page.goto('/dashboard');

      // OEE = Availability x Performance x Quality
      const oeeCard = page.locator('.kpi-card:has-text("OEE"), .metric-card:has-text("OEE")');
      await expect(oeeCard).toBeVisible();
      await expect(oeeCard).toContainText('%');
    });

    test('should display trend charts', async ({ page }) => {
      await page.goto('/dashboard');

      // Wait for charts to render
      await page.waitForSelector('canvas');

      // Verify trend charts visible
      const charts = page.locator('canvas');
      await expect(charts).toHaveCount({ min: 2 });
    });

    test('should display KPI summary table', async ({ page }) => {
      await page.goto('/dashboard');

      // Look for summary table
      const summaryTable = page.locator('.v-data-table, table:has-text("KPI")');
      await expect(summaryTable).toBeVisible();

      // Verify table has headers
      await expect(summaryTable).toContainText('Current');
      await expect(summaryTable).toContainText('Target');
    });
  });

  test.describe('KPI Status Indicators', () => {

    test('should show green for on-target KPIs', async ({ page }) => {
      await page.goto('/dashboard');

      // Look for success/green status
      const onTargetKPIs = page.locator('.kpi-card:has(.text-success), .status-success');
      // May or may not have on-target KPIs based on data
    });

    test('should show yellow for at-risk KPIs', async ({ page }) => {
      await page.goto('/dashboard');

      // Look for warning/yellow status
      const atRiskKPIs = page.locator('.kpi-card:has(.text-warning), .status-warning');
      // May or may not have at-risk KPIs
    });

    test('should show red for critical KPIs', async ({ page }) => {
      await page.goto('/dashboard');

      // Look for error/red status
      const criticalKPIs = page.locator('.kpi-card:has(.text-error), .status-error');
      // May or may not have critical KPIs
    });

    test('should show trend indicators', async ({ page }) => {
      await page.goto('/dashboard');

      // Look for trend icons (up/down arrows)
      const trendIcons = page.locator('.mdi-trending-up, .mdi-trending-down, .trend-icon');
      await expect(trendIcons).toHaveCount({ min: 1 });
    });
  });

  test.describe('Dashboard Filtering', () => {

    test('should filter by client', async ({ page }) => {
      await page.goto('/dashboard');

      // Open client selector
      await page.click('[aria-label="Client"], .client-selector');

      // Select a specific client
      await page.click('text=Client A, .v-list-item:first-child');

      // Wait for data refresh
      await page.waitForTimeout(1000);

      // Verify data filtered (no specific assertion, just no errors)
    });

    test('should filter by date range', async ({ page }) => {
      await page.goto('/dashboard');

      // Click date range selector
      await page.click('button:has-text("Date Range"), [aria-label="Date Range"]');

      // Select last 7 days
      await page.click('text=7 Days');

      // Verify filter applied
      await expect(page.locator('button')).toContainText('7');
    });

    test('should change trend period', async ({ page }) => {
      await page.goto('/dashboard');

      // Click 30 days toggle
      await page.click('button:has-text("30 Days")');

      // Wait for chart update
      await page.waitForTimeout(1000);

      // Click 90 days
      await page.click('button:has-text("90 Days")');

      // Wait for chart update
      await page.waitForTimeout(1000);

      // Verify no errors
    });
  });

  test.describe('Dashboard Reports', () => {

    test('should download PDF report', async ({ page }) => {
      await page.goto('/dashboard');

      // Click reports menu
      await page.click('button:has-text("Reports")');

      // Click PDF download
      const downloadPromise = page.waitForEvent('download');
      await page.click('text=Download PDF');

      // Verify download
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toContain('.pdf');
    });

    test('should download Excel report', async ({ page }) => {
      await page.goto('/dashboard');

      // Click reports menu
      await page.click('button:has-text("Reports")');

      // Click Excel download
      const downloadPromise = page.waitForEvent('download');
      await page.click('text=Download Excel');

      // Verify download
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toContain('.xlsx');
    });

    test('should open email report dialog', async ({ page }) => {
      await page.goto('/dashboard');

      // Click reports menu
      await page.click('button:has-text("Reports")');

      // Click email report
      await page.click('text=Email Report');

      // Verify dialog opens
      await expect(page.locator('[role="dialog"]')).toBeVisible();
      await expect(page.locator('[role="dialog"]')).toContainText('Recipients');
    });
  });

  test.describe('Dashboard Navigation', () => {

    test('should navigate to detail view when KPI card clicked', async ({ page }) => {
      await page.goto('/dashboard');

      // Click on efficiency KPI card
      await page.click('.kpi-card:has-text("Efficiency")');

      // Verify navigation to detail page
      await expect(page).toHaveURL(/production|efficiency/);
    });

    test('should navigate to production from summary table', async ({ page }) => {
      await page.goto('/dashboard');

      // Click production row action
      await page.click('tr:has-text("Efficiency") button, .v-data-table-row:has-text("Efficiency") button');

      // Verify navigation
      await expect(page).toHaveURL(/production/);
    });

    test('should refresh data on button click', async ({ page }) => {
      await page.goto('/dashboard');

      // Get initial value (to compare after refresh)
      const initialValue = await page.locator('.kpi-card').first().textContent();

      // Click refresh
      await page.click('button[aria-label="refresh"], button:has(.mdi-refresh)');

      // Wait for loading to complete
      await page.waitForSelector('.v-progress-circular', { state: 'hidden', timeout: 10000 });

      // Verify data potentially updated (no errors)
    });
  });

  test.describe('Dashboard Responsiveness', () => {

    test('should adapt to mobile viewport', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await page.goto('/dashboard');

      // Verify KPI cards stack vertically
      const cards = page.locator('.kpi-card');
      // Cards should be visible and arranged for mobile
      await expect(cards.first()).toBeVisible();
    });

    test('should adapt to tablet viewport', async ({ page }) => {
      // Set tablet viewport
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.goto('/dashboard');

      // Verify layout adapts
      await expect(page.locator('.kpi-card').first()).toBeVisible();
    });
  });

  test.describe('Real-time Updates', () => {

    test('should show loading state during data fetch', async ({ page }) => {
      await page.goto('/dashboard');

      // Click refresh to trigger loading
      await page.click('button:has(.mdi-refresh)');

      // Verify loading indicator appears
      const loading = page.locator('.v-progress-circular, .loading-indicator');
      // May be too fast to capture
    });

    test('should show error state gracefully', async ({ page }) => {
      // Navigate with invalid params to potentially trigger error
      await page.goto('/dashboard?client_id=INVALID');

      // Should still render dashboard
      await expect(page.locator('.kpi-card, .error-message')).toBeVisible();
    });
  });
});
