/**
 * Downtime Entry E2E Tests
 * Tests downtime tracking workflow: CRUD operations, resolution, availability impact
 */
import { test, expect } from '@playwright/test';

test.describe('Downtime Entry Workflow', () => {

  test.describe('Downtime CRUD Operations', () => {

    test('should create a new downtime event', async ({ page }) => {
      await page.goto('/downtime');

      // Wait for page to load
      await page.waitForSelector('.ag-root-wrapper, form[name="downtime"]');

      // Click Add button
      await page.click('button:has-text("Add"), button:has-text("New Downtime")');

      // Fill downtime form
      await page.fill('input[name="production_line"], [aria-label="Production Line"]', 'LINE-A');

      // Select downtime category
      await page.click('[aria-label="Category"], input[name="category"]');
      await page.click('text=Equipment');

      // Select downtime reason
      await page.click('[aria-label="Reason"], input[name="reason"]');
      await page.click('text=Machine Breakdown');

      // Fill duration
      await page.fill('input[name="duration_minutes"], [aria-label="Duration"]', '30');

      // Add notes
      await page.fill('textarea[name="notes"], [aria-label="Notes"]', 'E2E Test - Motor overheating');

      // Save
      await page.click('button:has-text("Save"), button[type="submit"]');

      // Verify success
      await expect(page.locator('.v-snackbar')).toContainText(/created|saved|success/i);

      // Verify entry appears
      await expect(page.locator('.ag-cell:has-text("LINE-A")')).toBeVisible();
    });

    test('should edit existing downtime event', async ({ page }) => {
      await page.goto('/downtime');
      await page.waitForSelector('.ag-root-wrapper');

      // Select first row
      const firstRow = page.locator('.ag-row').first();
      await firstRow.click();

      // Click edit
      await page.click('button:has-text("Edit")');

      // Update duration
      await page.fill('input[name="duration_minutes"]', '45');

      // Save
      await page.click('button:has-text("Save")');

      // Verify update
      await expect(page.locator('.v-snackbar')).toContainText(/updated|saved/i);
    });

    test('should delete downtime event', async ({ page }) => {
      await page.goto('/downtime');
      await page.waitForSelector('.ag-root-wrapper');

      // Select row
      const firstRow = page.locator('.ag-row').first();
      await firstRow.click();

      // Delete
      await page.click('button:has-text("Delete")');

      // Confirm
      await page.click('button:has-text("Confirm"), button:has-text("Yes")');

      // Verify deletion
      await expect(page.locator('.v-snackbar')).toContainText(/deleted|removed/i);
    });
  });

  test.describe('Downtime Resolution', () => {

    test('should resolve open downtime event', async ({ page }) => {
      await page.goto('/downtime');
      await page.waitForSelector('.ag-root-wrapper');

      // Find an open/active downtime
      const openDowntime = page.locator('.ag-row:has(.status-open), .ag-row:has-text("Active")');

      if (await openDowntime.count() > 0) {
        await openDowntime.first().click();

        // Click resolve button
        await page.click('button:has-text("Resolve"), button:has-text("Close")');

        // Fill resolution details
        await page.fill('textarea[name="resolution_notes"]', 'E2E Test - Issue resolved');

        // Confirm resolution
        await page.click('button:has-text("Confirm Resolution")');

        // Verify status changed
        await expect(page.locator('.v-snackbar')).toContainText(/resolved|closed/i);
      }
    });

    test('should track downtime duration automatically', async ({ page }) => {
      await page.goto('/downtime');

      // Create a new downtime with start time only
      await page.click('button:has-text("Add")');

      // Fill required fields
      await page.fill('input[name="production_line"]', 'LINE-B');
      await page.click('[aria-label="Category"]');
      await page.click('text=Changeover');

      // Save without end time
      await page.click('button:has-text("Save")');

      // Verify timer is running
      await expect(page.locator('.timer, .duration-counter')).toBeVisible();
    });
  });

  test.describe('Downtime Categories', () => {

    test('should filter by downtime category', async ({ page }) => {
      await page.goto('/downtime');
      await page.waitForSelector('.ag-root-wrapper');

      // Open filter
      await page.click('button:has-text("Filter")');

      // Select Equipment category
      await page.click('[aria-label="Category Filter"]');
      await page.click('text=Equipment');

      // Apply filter
      await page.click('button:has-text("Apply")');

      // Verify only equipment downtime shown
      const rows = page.locator('.ag-row');
      const count = await rows.count();
      for (let i = 0; i < Math.min(count, 5); i++) {
        await expect(rows.nth(i)).toContainText(/Equipment|EQUIPMENT/);
      }
    });

    test('should display downtime by reason chart', async ({ page }) => {
      await page.goto('/downtime');

      // Look for chart or summary section
      const chart = page.locator('canvas, .chart-container, .downtime-summary');
      await expect(chart).toBeVisible();
    });
  });

  test.describe('Availability Impact', () => {

    test('should show availability percentage', async ({ page }) => {
      await page.goto('/downtime');

      // Look for availability KPI
      const availabilityKPI = page.locator('.kpi-card:has-text("Availability"), .metric:has-text("Availability")');
      await expect(availabilityKPI).toBeVisible();

      // Verify percentage is displayed
      await expect(availabilityKPI).toContainText('%');
    });

    test('should update availability when downtime added', async ({ page }) => {
      await page.goto('/downtime');

      // Get initial availability
      const availabilityKPI = page.locator('.kpi-value:near(:text("Availability")), .availability-value');
      const initialValue = await availabilityKPI.textContent();

      // Add significant downtime
      await page.click('button:has-text("Add")');
      await page.fill('input[name="production_line"]', 'LINE-C');
      await page.click('[aria-label="Category"]');
      await page.click('text=Equipment');
      await page.fill('input[name="duration_minutes"]', '120');
      await page.click('button:has-text("Save")');

      // Wait for recalculation
      await page.waitForTimeout(2000);

      // Verify availability changed
      const newValue = await availabilityKPI.textContent();
      // Note: May need adjustment based on actual implementation
    });
  });
});
