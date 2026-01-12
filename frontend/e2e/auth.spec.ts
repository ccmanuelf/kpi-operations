import { test, expect, Page } from '@playwright/test';

/**
 * KPI Operations Platform - Authentication E2E Tests
 */

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display login page', async ({ page }) => {
    await expect(page.locator('text=Manufacturing KPI Platform')).toBeVisible();
    await expect(page.locator('input[type="text"]').first()).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button:has-text("Login")')).toBeVisible();
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.fill('input[type="text"]', 'invaliduser');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button:has-text("Login")');
    
    await expect(page.locator('.v-alert')).toBeVisible({ timeout: 10000 });
  });

  test('should login successfully with valid credentials', async ({ page }) => {
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button:has-text("Login")');
    
    // Should redirect to dashboard
    await expect(page).toHaveURL('/', { timeout: 10000 });
    // Dashboard content should be visible
    await expect(page.locator('nav')).toBeVisible({ timeout: 10000 });
  });

  test('should show forgot password dialog', async ({ page }) => {
    await page.click('text=Forgot Password?');
    
    await expect(page.locator('text=Reset Password')).toBeVisible();
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });

  test('should show registration dialog', async ({ page }) => {
    await page.click('text=Create Account');
    
    await expect(page.locator('text=Create Account').last()).toBeVisible();
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });

  test('should validate registration form', async ({ page }) => {
    await page.click('text=Create Account');
    
    // Try to submit empty form
    await page.click('button:has-text("Create Account")');
    
    // Should show validation errors
    await expect(page.locator('.v-messages__message')).toBeVisible({ timeout: 5000 });
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.fill('input[type="text"]', 'admin');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button:has-text("Login")');
    
    await expect(page.locator('nav')).toBeVisible({ timeout: 10000 });
    
    // Find and click logout button
    const logoutButton = page.locator('[data-testid="logout-btn"]').or(page.locator('text=Logout'));
    if (await logoutButton.isVisible()) {
      await logoutButton.click();
      await expect(page.locator('text=Manufacturing KPI Platform')).toBeVisible({ timeout: 10000 });
    }
  });
});
