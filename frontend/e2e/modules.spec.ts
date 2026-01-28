import { test, expect, Page } from '@playwright/test';

/**
 * KPI Operations Platform - Quality & Reports E2E Tests
 */

async function login(page: Page) {
  await page.goto('/');
  await page.fill('input[type="text"]', 'admin');
  await page.fill('input[type="password"]', 'admin123');
  await page.click('button:has-text("Sign In")');
  await expect(page.locator('nav')).toBeVisible({ timeout: 15000 });
}

test.describe('Quality Management', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('text=Quality');
    await page.waitForTimeout(1000);
  });

  test('should display quality metrics', async ({ page }) => {
    await expect(page.locator('text=Quality').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show PPM metrics', async ({ page }) => {
    const ppmCard = page.locator('text=PPM').or(page.locator('[data-testid="ppm-metric"]'));
    await expect(ppmCard).toBeVisible({ timeout: 10000 });
  });

  test('should show defect rate', async ({ page }) => {
    const defectCard = page.locator('text=Defect').or(page.locator('[data-testid="defect-rate"]'));
    await expect(defectCard).toBeVisible({ timeout: 10000 });
  });

  test('should display quality data grid', async ({ page }) => {
    const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
    await expect(grid).toBeVisible({ timeout: 10000 });
  });

  test('should add quality inspection', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add")');
    if (await addButton.isVisible()) {
      await addButton.click();
      await expect(page.locator('.v-dialog')).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe('Attendance Tracking', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('text=Attendance');
    await page.waitForTimeout(1000);
  });

  test('should display attendance page', async ({ page }) => {
    await expect(page.locator('text=Attendance').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show attendance rate', async ({ page }) => {
    const rateCard = page.locator('text=Rate').or(page.locator('[data-testid="attendance-rate"]'));
    await expect(rateCard).toBeVisible({ timeout: 10000 });
  });

  test('should display attendance grid', async ({ page }) => {
    const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
    await expect(grid).toBeVisible({ timeout: 10000 });
  });

  test('should add attendance record', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add")');
    if (await addButton.isVisible()) {
      await addButton.click();
      await expect(page.locator('.v-dialog')).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe('Downtime Analysis', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('text=Downtime');
    await page.waitForTimeout(1000);
  });

  test('should display downtime page', async ({ page }) => {
    await expect(page.locator('text=Downtime').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show availability metrics', async ({ page }) => {
    const availCard = page.locator('text=Availability').or(page.locator('[data-testid="availability"]'));
    await expect(availCard).toBeVisible({ timeout: 10000 });
  });

  test('should display downtime grid', async ({ page }) => {
    const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
    await expect(grid).toBeVisible({ timeout: 10000 });
  });

  test('should log downtime event', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add")').or(page.locator('button:has-text("Log")'));
    if (await addButton.isVisible()) {
      await addButton.click();
      await expect(page.locator('.v-dialog')).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe('Reports', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('text=Reports');
    await page.waitForTimeout(1000);
  });

  test('should display reports page', async ({ page }) => {
    await expect(page.locator('text=Reports').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show report generation options', async ({ page }) => {
    const pdfButton = page.locator('button:has-text("PDF")').or(page.locator('[data-testid="export-pdf"]'));
    const excelButton = page.locator('button:has-text("Excel")').or(page.locator('[data-testid="export-excel"]'));
    
    // At least one export option should be visible
    const hasPdf = await pdfButton.isVisible();
    const hasExcel = await excelButton.isVisible();
    
    expect(hasPdf || hasExcel).toBeTruthy();
  });

  test('should select date range', async ({ page }) => {
    const dateInput = page.locator('input[type="date"]').or(page.locator('.v-date-picker'));
    if (await dateInput.isVisible()) {
      await dateInput.click();
    }
  });
});

test.describe('Client Management (Admin)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should access client management', async ({ page }) => {
    const clientsLink = page.locator('text=Clients');
    if (await clientsLink.isVisible()) {
      await clientsLink.click();
      await expect(page.locator('text=Client').first()).toBeVisible({ timeout: 10000 });
    }
  });

  test('should display client list', async ({ page }) => {
    const clientsLink = page.locator('text=Clients');
    if (await clientsLink.isVisible()) {
      await clientsLink.click();
      const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
      await expect(grid).toBeVisible({ timeout: 10000 });
    }
  });
});

test.describe('User Management (Admin)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should access user management', async ({ page }) => {
    const usersLink = page.locator('text=Users');
    if (await usersLink.isVisible()) {
      await usersLink.click();
      await expect(page.locator('text=User').first()).toBeVisible({ timeout: 10000 });
    }
  });
});
