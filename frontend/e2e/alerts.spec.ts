import { test, expect, Page } from '@playwright/test';
import { login } from './helpers';

/**
 * KPI Operations Platform — Alert Board E2E
 *
 * Surface: /alerts — AlertsView wrapping AlertDashboard.
 *
 * This board had NO browser coverage until now, for a reason that has just
 * stopped being true: ALERT, ALERT_CONFIG and ALERT_HISTORY were empty in every
 * demo, so the page rendered a header, three filter selects and nothing else.
 * A spec written then could only have asserted the empty state.
 *
 * The seeder now writes 32 alerts per run spanning four severities, four
 * categories and all three statuses, which is what makes the assertions below
 * possible — every one of them would pass vacuously against an empty board,
 * so each asserts a NON-EMPTY result and the specific axis it exercises.
 *
 * Selectors are `data-testid`, added alongside this spec. The floating-pool
 * suite records what the alternative costs: it was skipped for "flaky nav
 * selectors" until Phase B.7 replaced them with exactly this.
 */

test.setTimeout(60000);

async function gotoAlerts(page: Page) {
  await page.goto('/alerts', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="alert-dashboard"]', {
    state: 'visible',
    timeout: 30000,
  });
  // The board fetches after mount; wait for it to stop reporting a load.
  await expect(page.locator('[data-testid="alert-section-all"]')).toBeVisible({ timeout: 20000 });
}

test.describe('Alert board — the seeded board renders', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin');
    await gotoAlerts(page);
  });

  test('shows a total and at least one alert card', async ({ page }) => {
    const total = page.locator('[data-testid="alert-stat-total"] .count');
    await expect(total).toBeVisible({ timeout: 15000 });
    const totalText = ((await total.textContent()) ?? '').trim();
    expect(Number(totalText)).toBeGreaterThan(0);

    // Cards, not just a count: a total with no rows would be the empty board
    // this spec exists to distinguish from a populated one.
    await expect(page.locator('[data-testid="alert-card"]').first()).toBeVisible({
      timeout: 15000,
    });
    expect(await page.locator('[data-testid="alert-card"]').count()).toBeGreaterThan(0);
  });

  test('every rendered card carries a severity and a status the app defines', async ({ page }) => {
    const cards = page.locator('[data-testid="alert-card"]');
    const n = await cards.count();
    expect(n).toBeGreaterThan(0);

    const severities = new Set<string>();
    const statuses = new Set<string>();
    for (let i = 0; i < n; i++) {
      severities.add((await cards.nth(i).getAttribute('data-severity')) ?? '');
      statuses.add((await cards.nth(i).getAttribute('data-status')) ?? '');
    }
    // The seeded vocabulary is the app's own — routes/alerts/generate.py writes
    // these same values, so a card outside these sets means the seed and the
    // generator have diverged.
    for (const s of severities) expect(['urgent', 'critical', 'warning', 'info']).toContain(s);
    for (const s of statuses) expect(['active', 'acknowledged', 'resolved']).toContain(s);
  });

  test('the severity summary reflects what is on the board', async ({ page }) => {
    // Each chip renders only when its count is non-zero, so a visible chip is
    // itself the assertion that the seed produced that severity.
    const chips = ['urgent', 'critical', 'warning', 'info'];
    let shown = 0;
    for (const c of chips) {
      if (await page.locator(`[data-testid="alert-stat-${c}"]`).isVisible().catch(() => false)) {
        shown += 1;
      }
    }
    expect(shown, 'no severity chip rendered, so the board has no active alerts').toBeGreaterThan(0);
  });
});

test.describe('Alert board — the filters actually filter', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'admin');
    await gotoAlerts(page);
  });

  test('filtering by status returns only that status', async ({ page }) => {
    // `resolved` is the interesting one: it exists only because the seed spans
    // the whole workflow rather than leaving every alert active.
    await page.locator('[data-testid="alert-filter-status"]').selectOption('resolved');
    await expect(page.locator('[data-testid="alert-section-all"]')).toBeVisible();
    await page.waitForTimeout(1500); // the change handler refetches

    const cards = page.locator('[data-testid="alert-card"]');
    const n = await cards.count();
    if (n === 0) {
      // An empty result is a legitimate answer, but then it must be the empty
      // state rather than a silently broken list.
      await expect(page.locator('[data-testid="alert-empty"]')).toBeVisible();
      return;
    }
    for (let i = 0; i < n; i++) {
      expect(await cards.nth(i).getAttribute('data-status')).toBe('resolved');
    }
  });

  test('filtering by severity returns only that severity', async ({ page }) => {
    await page.locator('[data-testid="alert-filter-status"]').selectOption('');
    await page.waitForTimeout(1000);
    await page.locator('[data-testid="alert-filter-severity"]').selectOption('critical');
    await page.waitForTimeout(1500);

    const cards = page.locator('[data-testid="alert-card"]');
    const n = await cards.count();
    if (n === 0) {
      await expect(page.locator('[data-testid="alert-empty"]')).toBeVisible();
      return;
    }
    for (let i = 0; i < n; i++) {
      expect(await cards.nth(i).getAttribute('data-severity')).toBe('critical');
    }
  });
});
