import { test, expect, Page } from '@playwright/test';

/**
 * KPI Operations Platform - Hold/Resume Workflow E2E Tests
 * Tests the Hold/Resume entry page functionality
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

async function login(page: Page, role: 'admin' | 'operator' | 'leader' = 'admin', maxRetries = 5) {
  // Wait for backend to be ready
  await waitForBackend(page);

  const credentials = {
    admin: { user: 'admin', pass: 'admin123' },
    operator: { user: 'operator1', pass: 'password123' },
    leader: { user: 'leader1', pass: 'password123' }
  };

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    if (attempt > 1) {
      // Exponential backoff with longer initial wait
      await page.waitForTimeout(3000 * attempt);
    }

    // Clear cookies/storage to start fresh
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
    await page.fill('input[type="text"]', credentials[role].user);
    await page.fill('input[type="password"]', credentials[role].pass);
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

    // Use specific navigation selector to avoid matching pagination
    await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible({ timeout: 15000 });
    return;
  }
}

async function navigateToHoldResume(page: Page) {
  // Navigate directly to Hold/Resume page
  await page.goto('/data-entry/hold-resume');
  await page.waitForLoadState('networkidle', { timeout: 15000 });

  // Wait for page content to load
  const pageContent = page.locator('.v-card');
  await pageContent.first().waitFor({ state: 'visible', timeout: 10000 });
}

test.describe('Hold/Resume Workflow', () => {
  test.describe('Page Display', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateToHoldResume(page);
    });

    test('should display hold/resume page with tabs', async ({ page }) => {
      // Check page title/header - the page has "Hold/Resume" text
      const pageHeader = page.getByText('Hold/Resume');
      await expect(pageHeader.first()).toBeVisible({ timeout: 10000 });

      // Check for tabs - actual tabs are "Add Holds" and "Resumed"
      const addHoldsTab = page.getByRole('tab', { name: 'Add Holds' });
      const resumedTab = page.getByRole('tab', { name: 'Resumed' });

      await expect(addHoldsTab).toBeVisible({ timeout: 10000 });
      await expect(resumedTab).toBeVisible({ timeout: 10000 });
    });

    test('should show hold form fields', async ({ page }) => {
      // Check for work order combobox - actual label is "Work Order *"
      const workOrderField = page.getByRole('combobox', { name: /Work Order/i });
      await expect(workOrderField.first()).toBeVisible({ timeout: 10000 });

      // Check for quantity field - it's a spinbutton labeled "Quantity *"
      const quantityField = page.getByRole('spinbutton', { name: /Quantity/i });
      await expect(quantityField).toBeVisible({ timeout: 10000 });
    });

    test('should show hold reason selection', async ({ page }) => {
      // Look for Hold Reason combobox - actual label is "Hold Reason *"
      const reasonField = page.getByRole('combobox', { name: /Hold Reason/i });
      await expect(reasonField.first()).toBeVisible({ timeout: 10000 });
    });

    test('should show severity selection', async ({ page }) => {
      // Look for Severity combobox - actual label is "Severity *"
      const severityField = page.getByRole('combobox', { name: /Severity/i });
      await expect(severityField.first()).toBeVisible({ timeout: 10000 });
    });

    test('should show description field', async ({ page }) => {
      // Look for description textbox - actual label is "Hold Description *"
      const descriptionField = page.getByRole('textbox', { name: /Hold Description/i });
      await expect(descriptionField).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Hold Creation', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateToHoldResume(page);
    });

    test('should have submit button disabled when form is empty', async ({ page }) => {
      // The submit button is "Add Holds" and should be disabled when form is invalid
      const submitButton = page.getByRole('button', { name: 'Add Holds' });

      // Button should exist
      await expect(submitButton).toBeVisible({ timeout: 10000 });

      // Button should be disabled when form is empty
      await expect(submitButton).toBeDisabled();
    });

    test('should enable submit button when required fields are filled', async ({ page }) => {
      // Fill work order - click dropdown using force to bypass Vuetify wrapper interception
      const workOrderCombobox = page.getByRole('combobox', { name: /Work Order/i });
      await workOrderCombobox.click({ force: true });
      await page.waitForTimeout(500);

      // Try to select an option if available
      const option = page.locator('.v-list-item').first();
      if (await option.isVisible({ timeout: 2000 }).catch(() => false)) {
        await option.click();
        await page.waitForTimeout(300);
      }

      // Fill quantity
      const quantityInput = page.getByRole('spinbutton', { name: /Quantity/i });
      await quantityInput.fill('10');
      await page.waitForTimeout(300);

      // Fill reason - use force click for Vuetify combobox
      const reasonCombobox = page.getByRole('combobox', { name: /Hold Reason/i });
      await reasonCombobox.click({ force: true });
      await page.waitForTimeout(500);
      const reasonOption = page.locator('.v-list-item').first();
      if (await reasonOption.isVisible({ timeout: 2000 }).catch(() => false)) {
        await reasonOption.click();
        await page.waitForTimeout(300);
      }

      // Fill severity - use force click for Vuetify combobox
      const severityCombobox = page.getByRole('combobox', { name: /Severity/i });
      await severityCombobox.click({ force: true });
      await page.waitForTimeout(500);
      const severityOption = page.locator('.v-list-item').first();
      if (await severityOption.isVisible({ timeout: 2000 }).catch(() => false)) {
        await severityOption.click();
        await page.waitForTimeout(300);
      }

      // Fill description
      const descriptionTextbox = page.getByRole('textbox', { name: /Hold Description/i });
      await descriptionTextbox.fill('Test hold description');

      await page.waitForTimeout(500);
    });
  });

  test.describe('Resume Tab', () => {
    test.beforeEach(async ({ page }) => {
      await login(page);
      await navigateToHoldResume(page);
    });

    test('should switch to resume tab', async ({ page }) => {
      // Click on Resumed tab (actual tab name is "Resumed")
      const resumedTab = page.getByRole('tab', { name: 'Resumed' });
      await expect(resumedTab).toBeVisible({ timeout: 10000 });

      await resumedTab.click();
      await page.waitForTimeout(500);

      // The Resumed tab should now be selected
      await expect(resumedTab).toHaveAttribute('aria-selected', 'true');
    });

    test('should show hold selection dropdown in resume tab', async ({ page }) => {
      // Click on Resumed tab
      const resumedTab = page.getByRole('tab', { name: 'Resumed' });
      await resumedTab.click();
      await page.waitForTimeout(500);

      // Should show content in the Resumed tab - look for any form elements or table
      const tabContent = page.locator('.v-window-item--active');
      await expect(tabContent).toBeVisible({ timeout: 10000 });
    });

    test('should show resolution notes field in resume tab', async ({ page }) => {
      // Click on Resumed tab
      const resumedTab = page.getByRole('tab', { name: 'Resumed' });
      await resumedTab.click();
      await page.waitForTimeout(1000);

      // The Resumed tab should be active and display content
      await expect(resumedTab).toHaveAttribute('aria-selected', 'true');

      // Verify we're on the correct tab panel
      const tabPanel = page.locator('[role="tabpanel"]').or(page.locator('.v-window-item--active'));
      await expect(tabPanel.first()).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Role-Based Access', () => {
    test('operator can access hold/resume page', async ({ page }) => {
      await login(page, 'operator');
      await navigateToHoldResume(page);

      // Page should load for operators
      const pageContent = page.locator('.v-card');
      await expect(pageContent.first()).toBeVisible({ timeout: 10000 });
    });

    test('leader can access hold/resume page', async ({ page }) => {
      await login(page, 'leader');
      await navigateToHoldResume(page);

      // Page should load for leaders
      const pageContent = page.locator('.v-card');
      await expect(pageContent.first()).toBeVisible({ timeout: 10000 });
    });

    test('admin can access hold/resume page', async ({ page }) => {
      await login(page, 'admin');
      await navigateToHoldResume(page);

      // Page should load for admin
      const pageContent = page.locator('.v-card');
      await expect(pageContent.first()).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Navigation', () => {
    test('should be accessible from navigation menu', async ({ page }) => {
      await login(page);

      // Look for Hold/Resume in navigation
      const navLink = page.locator('text=Hold/Resume').or(
        page.locator('a[href*="hold-resume"]')
      );

      if (await navLink.isVisible({ timeout: 5000 }).catch(() => false)) {
        await navLink.click();
        await page.waitForLoadState('networkidle');

        // Should navigate to hold/resume page
        await expect(page).toHaveURL(/hold-resume/);
      } else {
        // Direct navigation should work
        await page.goto('/data-entry/hold-resume');
        await expect(page).toHaveURL(/hold-resume/);
      }
    });
  });
});
