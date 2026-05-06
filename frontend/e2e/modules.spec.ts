import { test, expect } from '@playwright/test';
import { login } from './helpers';

/**
 * KPI Operations Platform - Quality & Reports E2E Tests
 */

// Increase timeout for stability
test.setTimeout(60000);

// The entry-interface audit (memory/entry-interface-audit.md, Phase 3
// closed 2026-05-02) migrated Quality, Attendance, and Downtime entries
// from form-based UI (spinbutton fields like "Defect", "Inspected",
// "Submit" button) to AG Grid surfaces. The selectors below — and the
// `page.click('text=Quality')` ambiguous-click pattern — target UI that
// no longer exists.
//
// New grid surfaces are covered by per-grid component tests; full E2E
// rewrite against AGGridBase row-edit flows is tracked as Phase B.7
// in memory/ci-hygiene-tracker.md.
test.describe.skip('Quality Management [SKIPPED — old form UI replaced by AG Grid; see Phase B.7]', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('text=Quality');
    await page.waitForTimeout(1000);
  });

  test('should display quality metrics', async ({ page }) => {
    await expect(page.locator('text=Quality').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show defect quantity field', async ({ page }) => {
    // Quality Entry is a form with defect-related fields
    const defectField = page.getByRole('spinbutton', { name: /Defect/i }).first();
    await expect(defectField).toBeVisible({ timeout: 10000 });
  });

  test('should show inspected quantity field', async ({ page }) => {
    // Quality Entry form has inspected quantity field
    const inspectedField = page.getByRole('spinbutton', { name: /Inspected/i }).first();
    await expect(inspectedField).toBeVisible({ timeout: 10000 });
  });

  test('should display quality entry form', async ({ page }) => {
    // Quality Entry is form-based, not grid-based - look for form elements
    const submitButton = page.getByRole('button', { name: /Submit/i });
    await expect(submitButton).toBeVisible({ timeout: 10000 });
  });

  test('should add quality inspection', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add")').first();
    if (await addButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await addButton.click({ force: true });
      await expect(page.locator('.v-dialog')).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe.skip('Attendance Tracking [SKIPPED — old form UI replaced by AG Grid; see Phase B.7]', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('text=Attendance');
    await page.waitForTimeout(1000);
  });

  test('should display attendance page', async ({ page }) => {
    await page.waitForLoadState('networkidle');
    // Verify attendance page content loaded (not just nav text)
    const pageContent = page.locator('.v-card').or(page.locator('.v-form'));
    await expect(pageContent.first()).toBeVisible({ timeout: 10000 });
  });

  test('should show attendance form fields', async ({ page }) => {
    await page.waitForLoadState('networkidle');
    // Attendance page may have form fields or grid - check for content
    const pageContent = page.locator('.v-card').or(page.locator('.v-form')).or(page.locator('[data-testid="attendance-form"]'));
    await expect(pageContent.first()).toBeVisible({ timeout: 15000 });
  });

  test('should display attendance entry content', async ({ page }) => {
    // Look for common attendance entry elements
    const formOrGrid = page.locator('.v-card').or(page.locator('.v-form'));
    await expect(formOrGrid.first()).toBeVisible({ timeout: 10000 });
  });

  test('should add attendance record', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add")').first();
    if (await addButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await addButton.click({ force: true });
      await expect(page.locator('.v-dialog')).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe.skip('Downtime Analysis [SKIPPED — old form UI replaced by AG Grid; see Phase B.7]', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('text=Downtime');
    await page.waitForTimeout(1000);
  });

  test('should display downtime page', async ({ page }) => {
    await expect(page.locator('text=Downtime').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show availability metrics', async ({ page }) => {
    const availCard = page.locator('text=Availability').or(page.locator('[data-testid="availability"]'));
    await expect(availCard.first()).toBeVisible({ timeout: 10000 });
  });

  test('should display downtime entry content', async ({ page }) => {
    // Downtime Entry page - look for form or content elements
    const formOrGrid = page.locator('.v-card').or(page.locator('.v-form'));
    await expect(formOrGrid.first()).toBeVisible({ timeout: 10000 });
  });

  test('should log downtime event', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add")').or(page.locator('button:has-text("Log")'));
    if (await addButton.first().isVisible({ timeout: 5000 }).catch(() => false)) {
      await addButton.first().click();
      await expect(page.locator('.v-dialog')).toBeVisible({ timeout: 5000 });
    }
  });
});

// `page.click('text=Reports')` clicks any element with "Reports" text.
// In the current build the Reports view itself has been removed/renamed
// (no `/reports` route); the test still passes for `should display
// reports page` because the *nav-bar* link text matches, but the
// `should show report generation options` test depends on PDF/Excel
// buttons that don't exist in the current UI. Skipping the whole block
// until a real reports surface ships and this can be rewritten.
test.describe.skip('Reports [SKIPPED — Reports view removed/replaced; see Phase B.7]', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('text=Reports');
    await page.waitForTimeout(1000);
  });

  test('should display reports page', async ({ page }) => {
    await expect(page.locator('text=Reports').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show report generation options', async ({ page }) => {
    const pdfButton = page.locator('button:has-text("PDF")').or(page.locator('[data-testid="export-pdf"]'));
    const excelButton = page.locator('button:has-text("Excel")').or(page.locator('[data-testid="export-excel"]'));

    // At least one export option should be visible
    const hasPdf = await pdfButton.first().isVisible({ timeout: 5000 }).catch(() => false);
    const hasExcel = await excelButton.first().isVisible({ timeout: 5000 }).catch(() => false);

    expect(hasPdf || hasExcel).toBeTruthy();
  });

  test('should select date range', async ({ page }) => {
    const dateInput = page.locator('input[type="date"]').or(page.locator('.v-date-picker'));
    if (await dateInput.first().isVisible({ timeout: 5000 }).catch(() => false)) {
      await dateInput.first().click();
    }
  });
});

test.describe('Client Management (Admin)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should access client management', async ({ page }) => {
    const clientsLink = page.locator('text=Clients').first();
    if (await clientsLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await clientsLink.click({ force: true });
      await page.waitForLoadState('networkidle');
      // Verify client page content loaded
      const clientContent = page.locator('.v-card').or(page.locator('.ag-root')).or(page.locator('.v-data-table'));
      await expect(clientContent.first()).toBeVisible({ timeout: 10000 });
    } else {
      // Client management may require different nav path — verify admin is logged in
      await expect(page.locator('.v-navigation-drawer')).toBeVisible();
    }
  });

  test('should display client list', async ({ page }) => {
    const clientsLink = page.locator('text=Clients').first();
    if (await clientsLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await clientsLink.click({ force: true });
      const grid = page.locator('.ag-root').or(page.locator('.v-data-table'));
      await expect(grid.first()).toBeVisible({ timeout: 10000 });
    }
  });
});

test.describe('User Management (Admin)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should access user management', async ({ page }) => {
    const usersLink = page.locator('text=Users').first();
    if (await usersLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await usersLink.click({ force: true });
      await expect(page.locator('text=User').first()).toBeVisible({ timeout: 10000 });
    }
  });
});
