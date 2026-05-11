import { test, expect, Page } from '@playwright/test';
import { login } from './helpers';

/**
 * KPI Operations Platform - Floating Pool Management E2E Tests
 *
 * Surface: /admin/floating-pool — admin-only inline AG-Grid (Group H Surface
 * #21 of the entry-interface audit). Pool membership is set elsewhere
 * (employee admin); this surface assigns / unassigns existing pool entries
 * via inline grid edits and a per-row Unassign button.
 *
 * Re-enabled in Phase B.7. Original suite was skipped for "flaky nav
 * selectors" + "tautological asserts"; both addressed here:
 *   - Direct goto('/admin/floating-pool', { waitUntil: 'domcontentloaded' })
 *     replaces the 3-fallback locator helper.
 *   - data-testid attributes added on summary cards for stable assertions.
 *   - Tests for legacy v-data-table / "Assign" dialog UI (removed in the
 *     2026-05-01 entry-interface migration) are deleted, not skipped — they
 *     test a feature shape that no longer exists.
 */

test.setTimeout(60000);

async function navigateToFloatingPool(page: Page) {
  // Direct goto with domcontentloaded fires deterministically vs. networkidle
  // which is held open by Vite HMR + in-flight store fetches.
  await page.goto('/admin/floating-pool', { waitUntil: 'domcontentloaded' });
  // Wait for the page-specific content marker (added in Phase B.7).
  await page.waitForSelector('[data-testid="floating-pool-content"]', {
    state: 'visible',
    timeout: 30000,
  });
}

test.describe('Floating Pool Management — Pool Overview', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin');
    await navigateToFloatingPool(page);
  });

  test('should display floating pool page', async ({ page }) => {
    // The 4 summary cards are the page's "above the fold" content.
    await expect(page.locator('[data-testid="floating-pool-total-card"]')).toBeVisible({
      timeout: 15000,
    });
  });

  test('should show employee grid', async ({ page }) => {
    // AG-Grid root must mount — replaces the legacy v-data-table check.
    await expect(page.locator('.ag-root').first()).toBeVisible({ timeout: 15000 });
  });

  test('should display current-assignment summary card', async ({ page }) => {
    // The "Currently Assigned" card shows summary.assigned. Use
    // toHaveText (which polls) instead of textContent() (which grabs the
    // current DOM snapshot — empty during the data fetch on Render's
    // free-tier cold-load).
    const assignedCard = page.locator('[data-testid="floating-pool-assigned-card"]');
    await expect(assignedCard).toBeVisible({ timeout: 15000 });
    await expect(assignedCard.locator('.text-h4')).toHaveText(/^\d+$/, { timeout: 15000 });
  });

  test('should show employee availability summary card', async ({ page }) => {
    const availableCard = page.locator('[data-testid="floating-pool-available-card"]');
    await expect(availableCard).toBeVisible({ timeout: 15000 });
    await expect(availableCard.locator('.text-h4')).toHaveText(/^\d+$/, { timeout: 15000 });
  });
});

test.describe('Floating Pool Management — Utilization Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin');
    await navigateToFloatingPool(page);
  });

  test('should show utilization metric card', async ({ page }) => {
    const utilCard = page.locator('[data-testid="floating-pool-utilization-card"]');
    await expect(utilCard).toBeVisible({ timeout: 15000 });
    // Utilization renders as "{N}%" — assert the format, not just visibility.
    await expect(utilCard.locator('.text-h4')).toHaveText(/^\d+%$/, { timeout: 15000 });
  });

  test('should display total-employees card alongside available count', async ({ page }) => {
    // Both cards render and totals are sensible (available <= total). Use
    // toHaveText to wait for the data fetch to populate the counts.
    const totalLoc = page.locator('[data-testid="floating-pool-total-card"] .text-h4');
    const availLoc = page.locator('[data-testid="floating-pool-available-card"] .text-h4');
    await expect(totalLoc).toHaveText(/^\d+$/, { timeout: 15000 });
    await expect(availLoc).toHaveText(/^\d+$/, { timeout: 15000 });

    const total = await totalLoc.textContent();
    const available = await availLoc.textContent();
    expect(Number(available)).toBeLessThanOrEqual(Number(total));
  });

  test('should expose simulation-insights expansion panel', async ({ page }) => {
    // The Simulation Insights panel exists in the page (collapsed by default).
    // Real assertion replaces the deleted-UI client-allocation test.
    const panel = page.locator('.v-expansion-panel-title').filter({
      hasText: /insights|recomendaciones|recommendations/i,
    });
    await expect(panel.first()).toBeVisible({ timeout: 15000 });
  });
});

test.describe('Floating Pool Management — Filters', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin');
    await navigateToFloatingPool(page);
  });

  test('should expose status filter select', async ({ page }) => {
    // The first .v-select on the page is the status filter (filterByStatus).
    const statusSelect = page.locator('.v-select').first();
    await expect(statusSelect).toBeVisible({ timeout: 15000 });
  });

  test('should expose client filter select', async ({ page }) => {
    // Two .v-select components on the page; the second is filterByClient.
    const clientSelect = page.locator('.v-select').nth(1);
    await expect(clientSelect).toBeVisible({ timeout: 15000 });
  });

  test('should expose refresh button', async ({ page }) => {
    // The page-level refresh button (mdi-refresh icon + Refresh label).
    const refreshBtn = page.locator('button').filter({ hasText: /refresh|actualizar/i }).first();
    await expect(refreshBtn).toBeVisible({ timeout: 15000 });
  });
});
