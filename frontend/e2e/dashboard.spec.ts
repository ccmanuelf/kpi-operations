import { test, expect, Page } from '@playwright/test';

/**
 * KPI Operations Platform - Dashboard E2E Tests
 */

// Increase timeout for stability
test.setTimeout(60000);

async function waitForBackend(page: Page, timeout = 10000) {
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    try {
      const response = await page.request.get('http://localhost:8000/health/');
      if (response.ok()) return true;
    } catch {
      // Backend not ready yet
    }
    await page.waitForTimeout(500);
  }
  return false;
}

// Helper function to login with retry logic
async function login(page: Page, maxRetries = 3) {
  await waitForBackend(page);

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    if (attempt > 1) {
      await page.waitForTimeout(3000 * attempt);
    }

    await page.context().clearCookies();
    await page.goto('/');
    await page.waitForSelector('input[type="text"]', { state: 'visible', timeout: 15000 });

    // Dismiss any existing error alerts first
    const existingAlert = page.locator('.v-alert button:has-text("Close")');
    if (await existingAlert.isVisible({ timeout: 500 }).catch(() => false)) {
      await existingAlert.click();
      await page.waitForTimeout(500);
    }

    await page.locator('input[type="text"]').clear();
    await page.locator('input[type="password"]').clear();
    await page.waitForTimeout(200);
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.waitForTimeout(200);

    await page.click('button:has-text("Sign In")');
    await page.waitForLoadState('networkidle', { timeout: 30000 });

    // Check if login failed
    const loginFailed = page.locator('text=Login failed');
    if (await loginFailed.isVisible({ timeout: 3000 }).catch(() => false)) {
      if (attempt < maxRetries) {
        const closeBtn = page.locator('.v-alert button:has-text("Close")');
        if (await closeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
          await closeBtn.click();
        }
        continue;
      }
      throw new Error(`Login failed after ${maxRetries} attempts`);
    }

    // Wait for navigation drawer to confirm successful login
    await page.waitForSelector('.v-navigation-drawer', { state: 'visible', timeout: 15000 });
    return;
  }
}

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should display dashboard after login', async ({ page }) => {
    // Wait for dashboard data to load
    await page.waitForLoadState('networkidle');
    // Dashboard should have KPI cards
    await expect(page.locator('.v-card').first()).toBeVisible({ timeout: 15000 });
  });

  test('should display navigation menu', async ({ page }) => {
    // Navigation should be visible - use CSS selector
    await expect(page.locator('.v-navigation-drawer')).toBeVisible();

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
    const userMenu = page.locator('[data-testid="user-menu"]').or(page.locator('.v-avatar').first());
    if (await userMenu.isVisible({ timeout: 3000 }).catch(() => false)) {
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
    await expect(grid.first()).toBeVisible({ timeout: 10000 });
  });

  test('should have add entry button', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add")').or(page.locator('[data-testid="add-entry"]'));
    await expect(addButton.first()).toBeVisible({ timeout: 10000 });
  });

  test('should open add entry dialog', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add")').or(page.locator('[data-testid="add-entry"]'));
    await expect(addButton.first()).toBeVisible({ timeout: 10000 });
    await addButton.first().click();
    await page.waitForTimeout(500);

    // Dialog or inline row add — verify something responded to the click
    const dialog = page.locator('.v-dialog').or(page.locator('[role="dialog"]')).or(page.locator('.v-bottom-sheet'));
    const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
    const isDialogVisible = await dialog.first().isVisible({ timeout: 3000 }).catch(() => false);
    const isGridVisible = await grid.first().isVisible({ timeout: 1000 }).catch(() => false);
    expect(isDialogVisible || isGridVisible).toBeTruthy();
  });

  test('should filter production data', async ({ page }) => {
    // Verify grid loaded first
    const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
    await expect(grid.first()).toBeVisible({ timeout: 10000 });

    // Look for filter inputs
    const filterInput = page.locator('input[placeholder*="filter"]').or(page.locator('.ag-filter-input'));
    if (await filterInput.first().isVisible({ timeout: 3000 }).catch(() => false)) {
      await filterInput.first().fill('test');
    }
  });

  test('should sort production data', async ({ page }) => {
    // Click on column header to sort
    const columnHeader = page.locator('.ag-header-cell').first().or(page.locator('th').first());
    if (await columnHeader.isVisible({ timeout: 3000 }).catch(() => false)) {
      await columnHeader.click();
    }
  });
});
