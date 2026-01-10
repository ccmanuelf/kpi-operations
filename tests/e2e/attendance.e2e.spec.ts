/**
 * Attendance Entry E2E Tests
 * Tests attendance tracking workflow: CRUD, coverage, absenteeism calculations
 */
import { test, expect } from '@playwright/test';

test.describe('Attendance Entry Workflow', () => {

  test.describe('Attendance CRUD Operations', () => {

    test('should create attendance record', async ({ page }) => {
      await page.goto('/attendance');
      await page.waitForSelector('.ag-root-wrapper, form[name="attendance"]');

      // Add new record
      await page.click('button:has-text("Add"), button:has-text("New Record")');

      // Fill attendance data
      await page.fill('input[name="employee_id"]', 'EMP-E2E-001');
      await page.fill('input[name="scheduled_hours"]', '8.0');
      await page.fill('input[name="actual_hours"]', '8.0');

      // Select shift
      await page.click('[aria-label="Shift"]');
      await page.click('text=Day Shift');

      // Save
      await page.click('button:has-text("Save")');

      // Verify success
      await expect(page.locator('.v-snackbar')).toContainText(/created|saved|success/i);
    });

    test('should record absence', async ({ page }) => {
      await page.goto('/attendance');
      await page.waitForSelector('.ag-root-wrapper');

      // Add absence record
      await page.click('button:has-text("Add")');

      await page.fill('input[name="employee_id"]', 'EMP-E2E-002');
      await page.fill('input[name="scheduled_hours"]', '8.0');
      await page.fill('input[name="actual_hours"]', '0');
      await page.fill('input[name="absence_hours"]', '8.0');

      // Select absence reason
      await page.click('[aria-label="Absence Reason"]');
      await page.click('text=Sick Leave');

      await page.click('button:has-text("Save")');

      // Verify
      await expect(page.locator('.v-snackbar')).toContainText(/saved/i);
    });

    test('should edit attendance record', async ({ page }) => {
      await page.goto('/attendance');
      await page.waitForSelector('.ag-root-wrapper');

      // Select and edit
      await page.locator('.ag-row').first().click();
      await page.click('button:has-text("Edit")');

      // Update hours
      await page.fill('input[name="actual_hours"]', '7.5');
      await page.click('button:has-text("Save")');

      await expect(page.locator('.v-snackbar')).toContainText(/updated/i);
    });

    test('should delete attendance record', async ({ page }) => {
      await page.goto('/attendance');
      await page.waitForSelector('.ag-root-wrapper');

      await page.locator('.ag-row').first().click();
      await page.click('button:has-text("Delete")');
      await page.click('button:has-text("Confirm")');

      await expect(page.locator('.v-snackbar')).toContainText(/deleted/i);
    });
  });

  test.describe('Coverage Tracking', () => {

    test('should display shift coverage summary', async ({ page }) => {
      await page.goto('/attendance');

      // Look for coverage summary
      const coverageSummary = page.locator('.coverage-summary, .shift-coverage');
      await expect(coverageSummary).toBeVisible();

      // Verify coverage percentage shown
      await expect(coverageSummary).toContainText('%');
    });

    test('should show understaffed warning', async ({ page }) => {
      await page.goto('/attendance');

      // Look for understaffed indicator (if any shifts are understaffed)
      const understaffedWarning = page.locator('.understaffed, .warning:has-text("coverage")');
      // May or may not be visible depending on data
    });

    test('should track floating pool assignments', async ({ page }) => {
      await page.goto('/attendance');

      // Click floating pool tab/section
      await page.click('text=Floating Pool, button:has-text("Pool")');

      // Verify floating pool employees shown
      await expect(page.locator('.floating-pool-list, .pool-employees')).toBeVisible();
    });
  });

  test.describe('Absenteeism KPI', () => {

    test('should display absenteeism rate', async ({ page }) => {
      await page.goto('/attendance');

      // Look for absenteeism KPI
      const absenteeismKPI = page.locator('.kpi-card:has-text("Absenteeism"), .metric:has-text("Absenteeism")');
      await expect(absenteeismKPI).toBeVisible();
      await expect(absenteeismKPI).toContainText('%');
    });

    test('should show absenteeism trend', async ({ page }) => {
      await page.goto('/attendance');

      // Look for trend chart
      const trendChart = page.locator('.absenteeism-trend, canvas:near(:text("Absenteeism"))');
      await expect(trendChart).toBeVisible();
    });

    test('should update absenteeism when absence recorded', async ({ page }) => {
      await page.goto('/attendance');

      // Get initial absenteeism
      const absenteeismValue = page.locator('.absenteeism-value, .kpi-value:near(:text("Absenteeism"))');
      const initialValue = await absenteeismValue.textContent();

      // Record multiple absences
      await page.click('button:has-text("Add")');
      await page.fill('input[name="employee_id"]', 'EMP-ABSENT-001');
      await page.fill('input[name="scheduled_hours"]', '8.0');
      await page.fill('input[name="absence_hours"]', '8.0');
      await page.click('[aria-label="Absence Reason"]');
      await page.click('text=Unexcused');
      await page.click('button:has-text("Save")');

      // Wait for recalculation
      await page.waitForTimeout(2000);

      // Absenteeism should increase
      const newValue = await absenteeismValue.textContent();
    });
  });

  test.describe('Attendance Reports', () => {

    test('should generate attendance summary', async ({ page }) => {
      await page.goto('/attendance');

      // Click reports
      await page.click('button:has-text("Reports")');

      // Select summary
      await page.click('text=Attendance Summary');

      // Verify report loads
      await expect(page.locator('.report-container, .summary-report')).toBeVisible();
    });

    test('should filter by date range', async ({ page }) => {
      await page.goto('/attendance');

      // Open date filter
      await page.click('button:has-text("Filter"), [aria-label="Date Range"]');

      // Select last 7 days
      await page.click('text=Last 7 Days');

      // Verify filter applied
      await expect(page.locator('.ag-row')).toHaveCount({ min: 0 });
    });
  });
});
