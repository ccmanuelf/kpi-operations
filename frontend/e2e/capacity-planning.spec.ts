import { test, expect, Page } from '@playwright/test';
import { login } from './helpers';

/**
 * KPI Operations Platform - Capacity Planning E2E Tests
 *
 * Tests the Capacity Planning Module with Component Check (Mini-MRP Layer):
 * - Navigation and page load
 * - Tab navigation through all 11 worksheets
 * - Action buttons functionality
 * - Basic UI elements verification
 *
 * Note: These tests run serially to avoid login rate limiting issues.
 */

// Increase default timeout for all tests
test.setTimeout(120000);

// Helper to navigate to Capacity Planning page
async function navigateToCapacityPlanning(page: Page) {
  // Scroll nav item into view and click — it's near the bottom of a long drawer
  const navItem = page.locator('.v-navigation-drawer a[href="/capacity-planning"]');
  await navItem.scrollIntoViewIfNeeded();
  await navItem.click();

  // Wait for URL to confirm Vue Router navigation completed
  await page.waitForURL('**/capacity-planning', { timeout: 15000 });

  // Wait for the page-specific header (not the nav item text)
  await page.waitForSelector('.v-card-title:has-text("Capacity Planning")', { state: 'visible', timeout: 30000 });
}

// Helper to wait for tab content to load
async function waitForTabContent(page: Page, timeout = 5000) {
  await page.waitForLoadState('networkidle', { timeout });
  await page.waitForTimeout(500); // Buffer for Vue reactivity
}

// Helper to click a tab by name
async function clickTab(page: Page, tabName: string) {
  const tabsContainer = page.locator('.v-tabs');
  const tab = tabsContainer.locator('.v-tab', { hasText: tabName });
  await tab.click();
  await waitForTabContent(page);
}

// =============================================================================
// Navigation Tests
// =============================================================================

test.describe('Capacity Planning - Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should display Capacity Planning in navigation menu', async ({ page }) => {
    const navItem = page.locator('.v-navigation-drawer').locator('text=Capacity Planning');
    await expect(navItem).toBeVisible({ timeout: 15000 });
  });

  test('should navigate to Capacity Planning page', async ({ page }) => {
    await navigateToCapacityPlanning(page);

    // Check page header - should contain "Capacity Planning"
    await expect(page.locator('.v-card-title:has-text("Capacity Planning")')).toBeVisible({ timeout: 30000 });
  });

  test('should display all worksheet tabs', async ({ page }) => {
    await navigateToCapacityPlanning(page);
    await waitForTabContent(page);

    // Check all 11 tabs are visible
    const tabsContainer = page.locator('.v-tabs');

    await expect(tabsContainer.locator('.v-tab:has-text("Orders")')).toBeVisible({ timeout: 15000 });
    await expect(tabsContainer.locator('.v-tab:has-text("Calendar")')).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('.v-tab:has-text("Lines")')).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('.v-tab:has-text("Standards")')).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('.v-tab:has-text("BOM")')).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('.v-tab:has-text("Stock")')).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('.v-tab:has-text("Component Check")')).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('.v-tab:has-text("Analysis")')).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('.v-tab:has-text("Schedule")')).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('.v-tab:has-text("Scenarios")')).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('.v-tab:has-text("KPI Tracking")')).toBeVisible({ timeout: 5000 });
  });

  test('should display action buttons', async ({ page }) => {
    await navigateToCapacityPlanning(page);
    await waitForTabContent(page);

    // Check action buttons
    await expect(page.locator('button:has-text("Run Component Check")')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('button:has-text("Run Capacity Analysis")')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('button:has-text("Generate Schedule")')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('button:has-text("Export")').first()).toBeVisible({ timeout: 5000 });
  });

  test('should display summary stats bar', async ({ page }) => {
    await navigateToCapacityPlanning(page);
    await waitForTabContent(page);

    // Check summary stats - use more relaxed matching
    const statsBar = page.locator('.v-card');
    await expect(statsBar.locator('text=Orders').first()).toBeVisible({ timeout: 10000 });
    await expect(statsBar.locator('text=Lines').first()).toBeVisible({ timeout: 5000 });
  });
});

// =============================================================================
// Tab Navigation Tests
// =============================================================================

test.describe('Capacity Planning - Tab Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToCapacityPlanning(page);
    await waitForTabContent(page);
  });

  test('should navigate through all tabs', async ({ page }) => {
    const tabs = ['Orders', 'Calendar', 'Lines', 'Standards', 'BOM', 'Stock',
                  'Component Check', 'Analysis', 'Schedule', 'Scenarios', 'KPI Tracking'];

    for (const tabName of tabs) {
      await clickTab(page, tabName);
      // Verify tab is selected (has selected styling)
      const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
      await expect(selectedTab.filter({ hasText: tabName })).toBeVisible({ timeout: 5000 });
    }
  });

  test('should display Orders tab by default', async ({ page }) => {
    // Orders should be the first/default tab
    const ordersTab = page.locator('.v-tabs .v-tab').first();
    await expect(ordersTab).toContainText('Orders');
  });

  test('should switch to Calendar tab', async ({ page }) => {
    await clickTab(page, 'Calendar');
    const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
    await expect(selectedTab.filter({ hasText: 'Calendar' })).toBeVisible({ timeout: 5000 });
  });

  test('should switch to Lines tab', async ({ page }) => {
    await clickTab(page, 'Lines');
    const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
    await expect(selectedTab.filter({ hasText: 'Lines' })).toBeVisible({ timeout: 5000 });
  });

  test('should switch to Standards tab', async ({ page }) => {
    await clickTab(page, 'Standards');
    const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
    await expect(selectedTab.filter({ hasText: 'Standards' })).toBeVisible({ timeout: 5000 });
  });

  test('should switch to BOM tab', async ({ page }) => {
    await clickTab(page, 'BOM');
    const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
    await expect(selectedTab.filter({ hasText: 'BOM' })).toBeVisible({ timeout: 5000 });
  });

  test('should switch to Stock tab', async ({ page }) => {
    await clickTab(page, 'Stock');
    const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
    await expect(selectedTab.filter({ hasText: 'Stock' })).toBeVisible({ timeout: 5000 });
  });

  test('should switch to Component Check tab', async ({ page }) => {
    await clickTab(page, 'Component Check');
    const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
    await expect(selectedTab.filter({ hasText: 'Component Check' })).toBeVisible({ timeout: 5000 });
  });

  test('should switch to Analysis tab', async ({ page }) => {
    await clickTab(page, 'Analysis');
    const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
    await expect(selectedTab.filter({ hasText: 'Analysis' })).toBeVisible({ timeout: 5000 });
  });

  test('should switch to Schedule tab', async ({ page }) => {
    await clickTab(page, 'Schedule');
    const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
    await expect(selectedTab.filter({ hasText: 'Schedule' })).toBeVisible({ timeout: 5000 });
  });

  test('should switch to Scenarios tab', async ({ page }) => {
    await clickTab(page, 'Scenarios');
    const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
    await expect(selectedTab.filter({ hasText: 'Scenarios' })).toBeVisible({ timeout: 5000 });
  });

  test('should switch to KPI Tracking tab', async ({ page }) => {
    await clickTab(page, 'KPI Tracking');
    const selectedTab = page.locator('.v-tabs .v-tab--selected, .v-tabs .v-btn--active');
    await expect(selectedTab.filter({ hasText: 'KPI Tracking' })).toBeVisible({ timeout: 5000 });
  });
});

// =============================================================================
// Action Button Tests
// =============================================================================

test.describe('Capacity Planning - Action Buttons', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToCapacityPlanning(page);
    await waitForTabContent(page);
  });

  test('should open Analysis dialog when clicking Run Capacity Analysis', async ({ page }) => {
    await page.click('button:has-text("Run Capacity Analysis")');
    await expect(page.locator('.v-dialog:has-text("Run Capacity Analysis")')).toBeVisible({ timeout: 5000 });
  });

  test('should open Schedule dialog when clicking Generate Schedule', async ({ page }) => {
    await page.click('button:has-text("Generate Schedule")');
    await expect(page.locator('.v-dialog:has-text("Generate Production Schedule")')).toBeVisible({ timeout: 5000 });
  });

  test('should have Save All Changes button', async ({ page }) => {
    await expect(page.locator('button:has-text("Save All Changes")')).toBeVisible({ timeout: 10000 });
  });

  test('should have Reset button', async ({ page }) => {
    await expect(page.locator('button:has-text("Reset")')).toBeVisible({ timeout: 10000 });
  });
});

// =============================================================================
// Dialog Tests
// =============================================================================

test.describe('Capacity Planning - Dialogs', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToCapacityPlanning(page);
    await waitForTabContent(page);
  });

  test('Analysis dialog should have date inputs', async ({ page }) => {
    await page.click('button:has-text("Run Capacity Analysis")');
    await page.waitForSelector('.v-dialog', { state: 'visible' });

    // Check for date inputs in the dialog
    await expect(page.locator('.v-dialog input[type="date"]').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.v-dialog:has-text("Start Date")')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.v-dialog:has-text("End Date")')).toBeVisible({ timeout: 5000 });
  });

  test('Analysis dialog can be closed', async ({ page }) => {
    await page.click('button:has-text("Run Capacity Analysis")');
    await page.waitForSelector('.v-dialog', { state: 'visible' });

    // Click cancel button
    await page.click('.v-dialog button:has-text("Cancel")');
    await expect(page.locator('.v-dialog:has-text("Run Capacity Analysis")')).toBeHidden({ timeout: 5000 });
  });

  test('Schedule dialog should have name input', async ({ page }) => {
    await page.click('button:has-text("Generate Schedule")');
    await page.waitForSelector('.v-dialog', { state: 'visible' });

    // Check for schedule name input
    await expect(page.locator('.v-dialog:has-text("Schedule Name")')).toBeVisible({ timeout: 5000 });
  });

  test('Schedule dialog can be closed', async ({ page }) => {
    await page.click('button:has-text("Generate Schedule")');
    await page.waitForSelector('.v-dialog', { state: 'visible' });

    // Click cancel button
    await page.click('.v-dialog button:has-text("Cancel")');
    await expect(page.locator('.v-dialog:has-text("Generate Production Schedule")')).toBeHidden({ timeout: 5000 });
  });
});

// =============================================================================
// Performance Tests
// =============================================================================

test.describe('Capacity Planning - Performance', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should load page within acceptable time', async ({ page }) => {
    const startTime = Date.now();
    await navigateToCapacityPlanning(page);
    const loadTime = Date.now() - startTime;

    // Page should load within 15 seconds
    expect(loadTime).toBeLessThan(15000);
  });

  test('should render tabs without significant lag', async ({ page }) => {
    await navigateToCapacityPlanning(page);

    const startTime = Date.now();
    await page.waitForSelector('.v-tabs', { state: 'visible' });
    const renderTime = Date.now() - startTime;

    // Tabs should render within 5 seconds
    expect(renderTime).toBeLessThan(5000);
  });
});

// =============================================================================
// Error Handling Tests
// =============================================================================

test.describe('Capacity Planning - Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToCapacityPlanning(page);
    await waitForTabContent(page);
  });

  test('should handle tab switching gracefully', async ({ page }) => {
    // Rapidly switch between tabs
    await clickTab(page, 'BOM');
    await clickTab(page, 'Orders');
    await clickTab(page, 'Analysis');
    await clickTab(page, 'Schedule');

    // UI should still be responsive
    await expect(page.locator('.v-tabs')).toBeVisible({ timeout: 5000 });
  });

  test('should remain functional after dialog close', async ({ page }) => {
    // Open and close dialog
    await page.click('button:has-text("Run Capacity Analysis")');
    await page.waitForSelector('.v-dialog', { state: 'visible' });
    await page.click('.v-dialog button:has-text("Cancel")');

    // UI should still be functional
    await expect(page.locator('button:has-text("Run Capacity Analysis")')).toBeEnabled({ timeout: 5000 });
  });
});
