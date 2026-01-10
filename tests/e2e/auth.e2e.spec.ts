/**
 * Authentication and Authorization E2E Tests
 * Tests login, logout, role-based access, session management
 */
import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {

  test.describe('Login Flow', () => {

    test('should show login page when not authenticated', async ({ page }) => {
      // Clear any existing auth state
      await page.context().clearCookies();

      // Navigate to protected route
      await page.goto('/dashboard');

      // Should redirect to login
      await expect(page).toHaveURL(/login/);

      // Verify login form visible
      await expect(page.locator('input[name="username"], input[type="email"]')).toBeVisible();
      await expect(page.locator('input[type="password"]')).toBeVisible();
    });

    test('should login successfully with valid credentials', async ({ page }) => {
      await page.goto('/login');

      // Fill credentials
      await page.fill('input[name="username"]', 'testuser');
      await page.fill('input[type="password"]', 'TestPass123!');

      // Submit
      await page.click('button[type="submit"]');

      // Wait for navigation
      await page.waitForURL('**/dashboard**', { timeout: 10000 });

      // Verify logged in
      await expect(page.locator('h1')).toContainText(/Dashboard|KPI/i);
    });

    test('should show error for invalid credentials', async ({ page }) => {
      await page.goto('/login');

      // Fill invalid credentials
      await page.fill('input[name="username"]', 'wronguser');
      await page.fill('input[type="password"]', 'wrongpass');

      // Submit
      await page.click('button[type="submit"]');

      // Verify error message
      await expect(page.locator('.v-alert, .error-message')).toContainText(/invalid|incorrect|failed/i);

      // Should stay on login page
      await expect(page).toHaveURL(/login/);
    });

    test('should validate required fields', async ({ page }) => {
      await page.goto('/login');

      // Click submit without filling
      await page.click('button[type="submit"]');

      // Verify validation messages
      await expect(page.locator('.v-messages__message, .field-error')).toContainText(/required/i);
    });

    test('should show password toggle', async ({ page }) => {
      await page.goto('/login');

      // Fill password
      await page.fill('input[type="password"]', 'secretpassword');

      // Verify password is hidden
      const passwordInput = page.locator('input[type="password"]');
      await expect(passwordInput).toHaveAttribute('type', 'password');

      // Click toggle button
      const toggleButton = page.locator('button:near(input[type="password"]), .password-toggle');
      if (await toggleButton.isVisible()) {
        await toggleButton.click();

        // Verify password is visible
        await expect(page.locator('input[name="password"], input:has([value="secretpassword"])')).toHaveAttribute('type', 'text');
      }
    });
  });

  test.describe('Logout Flow', () => {

    test('should logout successfully', async ({ page }) => {
      // First login
      await page.goto('/login');
      await page.fill('input[name="username"]', 'testuser');
      await page.fill('input[type="password"]', 'TestPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Click user menu
      await page.click('[aria-label="User Menu"], .user-menu, .avatar');

      // Click logout
      await page.click('text=Logout, text=Sign Out');

      // Verify redirected to login
      await expect(page).toHaveURL(/login/);
    });

    test('should clear session on logout', async ({ page }) => {
      // Login
      await page.goto('/login');
      await page.fill('input[name="username"]', 'testuser');
      await page.fill('input[type="password"]', 'TestPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Logout
      await page.click('[aria-label="User Menu"], .user-menu');
      await page.click('text=Logout');

      // Try to access protected route
      await page.goto('/dashboard');

      // Should redirect to login
      await expect(page).toHaveURL(/login/);
    });
  });

  test.describe('Session Management', () => {

    test('should persist session across page reload', async ({ page }) => {
      // Login
      await page.goto('/login');
      await page.fill('input[name="username"]', 'testuser');
      await page.fill('input[type="password"]', 'TestPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Reload page
      await page.reload();

      // Should still be logged in
      await expect(page).toHaveURL(/dashboard/);
      await expect(page.locator('h1')).toContainText(/Dashboard|KPI/i);
    });

    test('should handle expired session', async ({ page }) => {
      // Login
      await page.goto('/login');
      await page.fill('input[name="username"]', 'testuser');
      await page.fill('input[type="password"]', 'TestPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Manually clear auth token to simulate expiration
      await page.evaluate(() => {
        localStorage.removeItem('token');
        localStorage.removeItem('auth_token');
        sessionStorage.removeItem('token');
      });

      // Try to fetch data (triggers API call)
      await page.reload();

      // Should redirect to login
      await expect(page).toHaveURL(/login/);
    });
  });
});

test.describe('Authorization', () => {

  test.describe('Role-Based Access Control', () => {

    test('operator should have limited access', async ({ page }) => {
      // Login as operator
      await page.goto('/login');
      await page.fill('input[name="username"]', 'operator');
      await page.fill('input[type="password"]', 'OperatorPass123!');
      await page.click('button[type="submit"]');

      // Try to access admin route
      await page.goto('/admin');

      // Should be redirected or show access denied
      await expect(page.locator('text=Access Denied, text=Unauthorized')).toBeVisible().or(
        expect(page).toHaveURL(/dashboard|403/)
      );
    });

    test('supervisor should have extended access', async ({ page }) => {
      // Login as supervisor
      await page.goto('/login');
      await page.fill('input[name="username"]', 'supervisor');
      await page.fill('input[type="password"]', 'SupervisorPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Should be able to access reports
      await page.goto('/reports');
      await expect(page.locator('h1, h2')).toContainText(/Report/i);
    });

    test('admin should have full access', async ({ page }) => {
      // Login as admin
      await page.goto('/login');
      await page.fill('input[name="username"]', 'admin');
      await page.fill('input[type="password"]', 'AdminPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Should be able to access admin
      await page.goto('/admin');
      await expect(page.locator('h1, h2')).toContainText(/Admin|Settings/i);
    });
  });

  test.describe('Feature Permissions', () => {

    test('should hide unauthorized actions', async ({ page }) => {
      // Login as operator
      await page.goto('/login');
      await page.fill('input[name="username"]', 'operator');
      await page.fill('input[type="password"]', 'OperatorPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Navigate to production
      await page.goto('/production');

      // Delete button should not be visible for operator
      const deleteButton = page.locator('button:has-text("Delete")');
      // Either not visible or disabled
      if (await deleteButton.isVisible()) {
        await expect(deleteButton).toBeDisabled();
      }
    });

    test('should show authorized actions', async ({ page }) => {
      // Login as supervisor
      await page.goto('/login');
      await page.fill('input[name="username"]', 'supervisor');
      await page.fill('input[type="password"]', 'SupervisorPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Navigate to production
      await page.goto('/production');

      // Should see Add and Edit buttons
      await expect(page.locator('button:has-text("Add")')).toBeVisible();
    });
  });

  test.describe('API Authorization', () => {

    test('should return 401 for unauthenticated API calls', async ({ request }) => {
      // Call API without token
      const response = await request.get('/api/production');

      expect(response.status()).toBe(401);
    });

    test('should return 403 for unauthorized API calls', async ({ request }) => {
      // Login as operator
      const loginResponse = await request.post('/api/auth/login', {
        data: {
          username: 'operator',
          password: 'OperatorPass123!'
        }
      });

      if (loginResponse.ok()) {
        const { access_token } = await loginResponse.json();

        // Try to access admin-only endpoint
        const adminResponse = await request.delete('/api/production/1', {
          headers: {
            'Authorization': `Bearer ${access_token}`
          }
        });

        expect(adminResponse.status()).toBe(403);
      }
    });
  });
});

test.describe('Password Security', () => {

  test('should enforce password requirements', async ({ page }) => {
    // Navigate to registration or password change
    await page.goto('/register');

    // Fill weak password
    await page.fill('input[name="password"]', 'weak');

    // Submit
    await page.click('button[type="submit"]');

    // Verify validation error
    await expect(page.locator('.v-messages__message, .field-error')).toContainText(/minimum|characters|strong/i);
  });

  test('should require password confirmation', async ({ page }) => {
    await page.goto('/register');

    // Fill mismatched passwords
    await page.fill('input[name="password"]', 'StrongPass123!');
    await page.fill('input[name="confirm_password"]', 'DifferentPass123!');

    // Submit
    await page.click('button[type="submit"]');

    // Verify error
    await expect(page.locator('.v-messages__message, .field-error')).toContainText(/match|same/i);
  });
});
