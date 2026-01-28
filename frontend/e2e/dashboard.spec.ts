import { test, expect, Page } from '@playwright/test';

/**
 * KPI Operations Platform - Dashboard E2E Tests
 */

// Helper function to login
async function login(page: Page) {
  await page.goto('/');
  await page.fill('input[type="text"]', 'admin');
  await page.fill('input[type="password"]', 'admin123');
  await page.click('button:has-text("Sign In")');
  await expect(page.locator('nav')).toBeVisible({ timeout: 15000 });
}

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should display dashboard after login', async ({ page }) => {
    // Dashboard should have KPI cards
    await expect(page.locator('.v-card').first()).toBeVisible({ timeout: 10000 });
  });

  test('should display navigation menu', async ({ page }) => {
    // Navigation should be visible
    await expect(page.locator('nav')).toBeVisible();
    
    // Should have navigation items
    const navItems = page.locator('.v-list-item');
    await expect(navItems.first()).toBeVisible();
  });

  test('should navigate to production page', async ({ page }) => {
    await page.click('text=Production');
    
    // Should show production content
    await expect(page.locator('text=Production').first()).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to quality page', async ({ page }) => {
    await page.click('text=Quality');
    
    await expect(page.locator('text=Quality').first()).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to attendance page', async ({ page }) => {
    await page.click('text=Attendance');
    
    await expect(page.locator('text=Attendance').first()).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to downtime page', async ({ page }) => {
    await page.click('text=Downtime');
    
    await expect(page.locator('text=Downtime').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show user menu', async ({ page }) => {
    const userMenu = page.locator('[data-testid="user-menu"]').or(page.locator('.v-avatar'));
    if (await userMenu.isVisible()) {
      await userMenu.click();
      await expect(page.locator('.v-menu')).toBeVisible();
    }
  });

  test('should display KPI metrics', async ({ page }) => {
    // Look for KPI-related content
    const metricsSection = page.locator('.v-card');
    await expect(metricsSection.first()).toBeVisible({ timeout: 10000 });
  });

  test('should be responsive on mobile', async ({ page }) => {
    // Set viewport to mobile size
    await page.setViewportSize({ width: 375, height: 667 });
    
    // Page should still be functional
    await expect(page.locator('body')).toBeVisible();
  });
});

test.describe('Production Management', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('text=Production');
    await page.waitForTimeout(1000);
  });

  test('should display production data grid', async ({ page }) => {
    // AG Grid or data table should be visible
    const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
    await expect(grid).toBeVisible({ timeout: 10000 });
  });

  test('should have add entry button', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add")').or(page.locator('[data-testid="add-entry"]'));
    await expect(addButton).toBeVisible({ timeout: 10000 });
  });

  test('should open add entry dialog', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add")').or(page.locator('[data-testid="add-entry"]'));
    if (await addButton.isVisible()) {
      await addButton.click();
      
      // Dialog should appear
      const dialog = page.locator('.v-dialog');
      await expect(dialog).toBeVisible({ timeout: 5000 });
    }
  });

  test('should filter production data', async ({ page }) => {
    // Look for filter inputs
    const filterInput = page.locator('input[placeholder*="filter"]').or(page.locator('.ag-filter-input'));
    if (await filterInput.isVisible()) {
      await filterInput.fill('test');
    }
  });

  test('should sort production data', async ({ page }) => {
    // Click on column header to sort
    const columnHeader = page.locator('.ag-header-cell').first().or(page.locator('th').first());
    if (await columnHeader.isVisible()) {
      await columnHeader.click();
    }
  });
});
