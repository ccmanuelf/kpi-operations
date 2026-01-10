/**
 * Authentication Setup for E2E Tests
 * Creates authenticated state for test users
 */
import { test as setup, expect } from '@playwright/test';
import path from 'path';

const authFile = path.join(__dirname, '.auth/user.json');

setup('authenticate', async ({ page }) => {
  // Navigate to login page
  await page.goto('/login');

  // Wait for login form to be visible
  await expect(page.locator('input[type="email"], input[name="username"]')).toBeVisible();

  // Fill in credentials
  await page.fill('input[name="username"]', process.env.E2E_TEST_USER || 'testuser');
  await page.fill('input[type="password"]', process.env.E2E_TEST_PASSWORD || 'TestPass123!');

  // Click login button
  await page.click('button[type="submit"]');

  // Wait for navigation to dashboard
  await page.waitForURL('**/dashboard**', { timeout: 10000 });

  // Verify successful login
  await expect(page.locator('h1')).toContainText(/Dashboard|KPI/i);

  // Save the storage state
  await page.context().storageState({ path: authFile });
});

// Alternative: API-based authentication setup (faster)
setup('authenticate via API', async ({ request }) => {
  // Login via API
  const response = await request.post('/api/auth/login', {
    data: {
      username: process.env.E2E_TEST_USER || 'testuser',
      password: process.env.E2E_TEST_PASSWORD || 'TestPass123!'
    }
  });

  // Check if login was successful
  if (response.ok()) {
    const body = await response.json();

    // Store the token for later use
    process.env.E2E_AUTH_TOKEN = body.access_token;
  }
});
