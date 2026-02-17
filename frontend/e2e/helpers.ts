import { Page } from '@playwright/test';

/**
 * E2E Test Helper Functions
 * Shared utilities for Playwright tests across the KPI Operations Platform
 */

/**
 * Wait for backend health check to confirm API is ready
 * @param page - Playwright Page object
 * @param timeout - Maximum wait time in milliseconds
 * @returns true if backend is ready, false otherwise
 */
export async function waitForBackend(page: Page, timeout = 10000): Promise<boolean> {
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

/**
 * Login with retry logic for stability
 * Handles common login failures and rate limiting with exponential backoff
 *
 * @param page - Playwright Page object
 * @param role - User role ('admin', 'operator', or 'leader')
 * @param maxRetries - Maximum number of login attempts
 * @throws Error if login fails after all retries
 */
export async function login(
  page: Page,
  role: 'admin' | 'operator' | 'leader' = 'admin',
  maxRetries = 3
): Promise<void> {
  // Ensure backend is ready before attempting login
  const backendReady = await waitForBackend(page);
  if (!backendReady) {
    throw new Error('Backend is not responding');
  }

  const credentials = {
    admin: { user: 'admin', pass: 'admin123' },
    operator: { user: 'operator1', pass: 'password123' },
    leader: { user: 'leader1', pass: 'password123' }
  };

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    // Add delay between login attempts with exponential backoff
    if (attempt > 1) {
      await page.waitForTimeout(3000 * attempt);
    }

    // Clear cookies/storage to start fresh
    await page.context().clearCookies();
    await page.goto('/', { waitUntil: 'networkidle' });

    // Wait for the login form to be ready
    await page.waitForSelector('input[type="text"]', { state: 'visible', timeout: 20000 });

    // Dismiss any existing error alerts before filling form
    const existingAlert = page.locator('.v-alert button:has-text("Close")');
    if (await existingAlert.isVisible({ timeout: 500 }).catch(() => false)) {
      await existingAlert.click();
      await page.waitForTimeout(500);
    }

    // Clear any existing values and fill credentials
    await page.locator('input[type="text"]').clear();
    await page.locator('input[type="password"]').clear();
    await page.waitForTimeout(300);
    await page.fill('input[type="text"]', credentials[role].user);
    await page.fill('input[type="password"]', credentials[role].pass);
    await page.waitForTimeout(300);

    await page.click('button:has-text("Sign In")');

    // Wait for response
    await page.waitForLoadState('networkidle', { timeout: 30000 });

    // Check if login failed
    const loginFailed = page.locator('text=Login failed');
    const isLoginFailed = await loginFailed.isVisible({ timeout: 3000 }).catch(() => false);

    if (isLoginFailed) {
      if (attempt < maxRetries) {
        // Dismiss the error alert and retry
        const closeButton = page.locator('.v-alert button:has-text("Close")');
        if (await closeButton.isVisible({ timeout: 1000 }).catch(() => false)) {
          await closeButton.click();
        }
        continue;
      } else {
        throw new Error(`Login failed after ${maxRetries} attempts`);
      }
    }

    // Wait for navigation drawer to confirm successful login
    try {
      await page.waitForSelector('.v-navigation-drawer', { state: 'visible', timeout: 25000 });
      return; // Success
    } catch {
      // Fallback: wait for any indication of successful login
      try {
        await page.waitForSelector('text=Dashboard', { state: 'visible', timeout: 15000 });
        return; // Success
      } catch {
        if (attempt < maxRetries) {
          continue;
        }
        throw new Error('Login succeeded but navigation not visible');
      }
    }
  }
}
