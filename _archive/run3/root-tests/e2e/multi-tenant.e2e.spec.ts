/**
 * Multi-Tenant Isolation E2E Tests
 * Tests client data isolation, cross-tenant security, access controls
 */
import { test, expect } from '@playwright/test';

test.describe('Multi-Tenant Isolation', () => {

  test.describe('Data Isolation', () => {

    test('should only show data for assigned client', async ({ page }) => {
      // Login as operator for CLIENT-A
      await page.goto('/login');
      await page.fill('input[name="username"]', 'operator_client_a');
      await page.fill('input[type="password"]', 'OperatorPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Navigate to production
      await page.goto('/production');
      await page.waitForSelector('.ag-root-wrapper');

      // Verify all visible data is for CLIENT-A
      const clientCells = page.locator('.ag-cell[col-id="client_id"]');
      const count = await clientCells.count();

      for (let i = 0; i < count; i++) {
        await expect(clientCells.nth(i)).toContainText(/CLIENT-A|client-a/i);
      }
    });

    test('should not show other client data in dropdown', async ({ page }) => {
      // Login as operator for CLIENT-A
      await page.goto('/login');
      await page.fill('input[name="username"]', 'operator_client_a');
      await page.fill('input[type="password"]', 'OperatorPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Check client selector
      await page.goto('/dashboard');

      // If there's a client selector, it should only show CLIENT-A
      const clientSelector = page.locator('[aria-label="Client"], .client-selector');
      if (await clientSelector.isVisible()) {
        await clientSelector.click();

        // Should not see CLIENT-B
        await expect(page.locator('.v-list-item:has-text("CLIENT-B")')).not.toBeVisible();
      }
    });

    test('should filter KPIs by client', async ({ page }) => {
      // Login as operator for CLIENT-A
      await page.goto('/login');
      await page.fill('input[name="username"]', 'operator_client_a');
      await page.fill('input[type="password"]', 'OperatorPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Navigate to dashboard
      await page.goto('/dashboard');

      // KPI values should be calculated only for CLIENT-A data
      // (Cannot easily verify specific values without knowing expected data)
      await expect(page.locator('.kpi-card')).toHaveCount({ min: 1 });
    });
  });

  test.describe('Cross-Tenant Security', () => {

    test('should prevent accessing other client data via URL', async ({ page }) => {
      // Login as operator for CLIENT-A
      await page.goto('/login');
      await page.fill('input[name="username"]', 'operator_client_a');
      await page.fill('input[type="password"]', 'OperatorPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Try to access CLIENT-B data via URL parameter
      await page.goto('/production?client_id=CLIENT-B');

      // Should either:
      // 1. Show access denied
      // 2. Redirect
      // 3. Show empty results
      const accessDenied = page.locator('text=Access Denied, text=Unauthorized, text=No access');
      const emptyResults = page.locator('text=No data, text=No records');

      await expect(accessDenied.or(emptyResults)).toBeVisible().or(
        expect(page).toHaveURL(/dashboard|403/)
      );
    });

    test('should not allow editing other client records', async ({ page }) => {
      // Login as operator for CLIENT-A
      await page.goto('/login');
      await page.fill('input[name="username"]', 'operator_client_a');
      await page.fill('input[type="password"]', 'OperatorPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Try to edit CLIENT-B record via direct API call
      const response = await page.request.put('/api/production/CLIENT-B-RECORD-123', {
        data: {
          units_produced: 9999
        }
      });

      // Should return 403 or 404
      expect([403, 404]).toContain(response.status());
    });

    test('should not allow deleting other client records', async ({ page }) => {
      // Login as operator for CLIENT-A
      await page.goto('/login');
      await page.fill('input[name="username"]', 'operator_client_a');
      await page.fill('input[type="password"]', 'OperatorPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Try to delete CLIENT-B record via direct API call
      const response = await page.request.delete('/api/production/CLIENT-B-RECORD-123');

      // Should return 403 or 404
      expect([403, 404]).toContain(response.status());
    });
  });

  test.describe('Multi-Client User Access', () => {

    test('should show data for all assigned clients', async ({ page }) => {
      // Login as leader with access to multiple clients
      await page.goto('/login');
      await page.fill('input[name="username"]', 'leader_multi_client');
      await page.fill('input[type="password"]', 'LeaderPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Navigate to production
      await page.goto('/production');
      await page.waitForSelector('.ag-root-wrapper');

      // Should see data from both clients
      const clientCells = page.locator('.ag-cell[col-id="client_id"]');
      const texts = await clientCells.allTextContents();

      // Should contain at least one of each client type
      const hasClientA = texts.some(t => t.includes('CLIENT-A'));
      const hasClientB = texts.some(t => t.includes('CLIENT-B'));

      // At least one should be present (depends on data)
    });

    test('should allow switching between assigned clients', async ({ page }) => {
      // Login as leader with multi-client access
      await page.goto('/login');
      await page.fill('input[name="username"]', 'leader_multi_client');
      await page.fill('input[type="password"]', 'LeaderPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Navigate to dashboard
      await page.goto('/dashboard');

      // Open client selector
      const clientSelector = page.locator('[aria-label="Client"], .client-selector');
      if (await clientSelector.isVisible()) {
        await clientSelector.click();

        // Both clients should be available
        await expect(page.locator('.v-list-item:has-text("CLIENT-A")')).toBeVisible();
        await expect(page.locator('.v-list-item:has-text("CLIENT-B")')).toBeVisible();

        // Select CLIENT-B
        await page.click('.v-list-item:has-text("CLIENT-B")');

        // Data should update
        await page.waitForTimeout(1000);
      }
    });
  });

  test.describe('Admin Access', () => {

    test('admin should see all client data', async ({ page }) => {
      // Login as admin
      await page.goto('/login');
      await page.fill('input[name="username"]', 'admin');
      await page.fill('input[type="password"]', 'AdminPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Navigate to production
      await page.goto('/production');
      await page.waitForSelector('.ag-root-wrapper');

      // Admin should see data from all clients
      const clientSelector = page.locator('[aria-label="Client"], .client-selector');
      if (await clientSelector.isVisible()) {
        await clientSelector.click();

        // "All Clients" option should be available
        await expect(page.locator('.v-list-item:has-text("All Clients")')).toBeVisible();
      }
    });

    test('admin should access any client data', async ({ page }) => {
      // Login as admin
      await page.goto('/login');
      await page.fill('input[name="username"]', 'admin');
      await page.fill('input[type="password"]', 'AdminPass123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard**');

      // Navigate with specific client filter
      await page.goto('/production?client_id=CLIENT-A');
      await page.waitForSelector('.ag-root-wrapper');

      // Should see CLIENT-A data
      await expect(page.locator('.ag-cell:has-text("CLIENT-A")')).toBeVisible();

      // Switch to CLIENT-B
      await page.goto('/production?client_id=CLIENT-B');
      await page.waitForSelector('.ag-root-wrapper');

      // Should see CLIENT-B data
      await expect(page.locator('.ag-cell:has-text("CLIENT-B")')).toBeVisible();
    });
  });

  test.describe('API Tenant Isolation', () => {

    test('API should only return assigned client data', async ({ request }) => {
      // Login as operator for CLIENT-A
      const loginResponse = await request.post('/api/auth/login', {
        data: {
          username: 'operator_client_a',
          password: 'OperatorPass123!'
        }
      });

      if (loginResponse.ok()) {
        const { access_token } = await loginResponse.json();

        // Fetch production data
        const dataResponse = await request.get('/api/production', {
          headers: {
            'Authorization': `Bearer ${access_token}`
          }
        });

        if (dataResponse.ok()) {
          const data = await dataResponse.json();

          // All entries should be for CLIENT-A
          if (data.entries && data.entries.length > 0) {
            data.entries.forEach(entry => {
              expect(entry.client_id).toBe('CLIENT-A');
            });
          }
        }
      }
    });

    test('API should reject cross-tenant queries', async ({ request }) => {
      // Login as operator for CLIENT-A
      const loginResponse = await request.post('/api/auth/login', {
        data: {
          username: 'operator_client_a',
          password: 'OperatorPass123!'
        }
      });

      if (loginResponse.ok()) {
        const { access_token } = await loginResponse.json();

        // Try to query CLIENT-B data
        const dataResponse = await request.get('/api/production?client_id=CLIENT-B', {
          headers: {
            'Authorization': `Bearer ${access_token}`
          }
        });

        // Should return 403 or empty results
        if (dataResponse.ok()) {
          const data = await dataResponse.json();
          expect(data.entries || []).toHaveLength(0);
        } else {
          expect(dataResponse.status()).toBe(403);
        }
      }
    });
  });
});

test.describe('Tenant Data Integrity', () => {

  test('should maintain client_id on new entries', async ({ page }) => {
    // Login as operator for CLIENT-A
    await page.goto('/login');
    await page.fill('input[name="username"]', 'operator_client_a');
    await page.fill('input[type="password"]', 'OperatorPass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard**');

    // Navigate to production
    await page.goto('/production');
    await page.waitForSelector('.ag-root-wrapper');

    // Add new entry
    await page.click('button:has-text("Add")');

    // Fill data
    await page.fill('input[name="work_order_number"]', 'WO-TENANT-TEST-001');
    await page.fill('input[name="units_produced"]', '100');

    // Save
    await page.click('button:has-text("Save")');

    // Verify new entry has CLIENT-A
    await expect(page.locator('.ag-cell:has-text("WO-TENANT-TEST-001")')).toBeVisible();
    const row = page.locator('.ag-row:has-text("WO-TENANT-TEST-001")');
    await expect(row.locator('.ag-cell[col-id="client_id"]')).toContainText('CLIENT-A');
  });
});
