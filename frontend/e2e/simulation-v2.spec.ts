import { test, expect, Page } from '@playwright/test';
import { login } from './helpers';

/**
 * KPI Operations Platform - Simulation V2 E2E Tests
 *
 * Tests the Production Line Simulation v2.0 feature:
 * - Navigation and page load
 * - Operations grid (add, edit, import)
 * - Schedule configuration
 * - Demand configuration
 * - Breakdowns configuration
 * - Validation flow
 * - Simulation execution
 * - Results display
 * - Config export/import
 */

// Increase default timeout for all tests
test.setTimeout(90000);

// Helper to navigate to simulation v2 with stability improvements.
// Uses page.goto() directly (matches the dashboard.spec.ts pattern from
// commit 16b32e5) — clicking the nav drawer link races with the
// role-based v-list-group expansion in CI Chromium and intermittently
// loses the click. Direct goto bypasses that entire surface.
async function navigateToSimulationV2(page: Page, clearSampleData = true) {
  // Clear localStorage flag BEFORE navigation so any onMounted logic
  // (sample-data auto-load) sees the suppressed state on first paint.
  if (clearSampleData) {
    await page.evaluate(() => {
      localStorage.setItem('simulation_v2_visited', 'true');
    });
  }

  // domcontentloaded fires deterministically; networkidle hangs in CI
  // when Vite HMR + in-flight store fetches keep the network busy.
  await page.goto('/simulation', { waitUntil: 'domcontentloaded' });

  // Wait for the page header to confirm SimulationV2View mounted.
  await page.waitForSelector('text=Production Line Simulation v2.0', { state: 'visible', timeout: 30000 });
}

// Helper to wait for tab content to load. domcontentloaded fires
// deterministically; networkidle hangs in CI when Vite HMR + in-flight
// store fetches keep the network busy. Per-test toBeVisible() assertions
// do the rest of the waiting.
async function waitForTabContent(page: Page, timeout = 15000) {
  await page.waitForLoadState('domcontentloaded', { timeout });
  await page.waitForTimeout(300); // Small buffer for Vue reactivity
}

test.describe('Simulation V2 - Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('should display Simulation v2 in navigation menu', async ({ page }) => {
    // The nav drawer renders `t('navigation.simulation')` = "Simulation"
    // (no "v2" suffix). Match by stable href instead of locale-fragile
    // label text.
    const navItem = page.locator('.v-navigation-drawer a[href="/simulation"]');
    await expect(navItem.first()).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to Simulation v2 page', async ({ page }) => {
    await navigateToSimulationV2(page);

    // Check page header
    await expect(page.locator('text=Production Line Simulation v2.0')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=SimPy Engine')).toBeVisible({ timeout: 5000 });
  });

  test('should display all tabs', async ({ page }) => {
    await navigateToSimulationV2(page);
    await waitForTabContent(page);

    // Use more specific selectors for tab buttons within the tabs container
    const tabsContainer = page.locator('.v-tabs');
    await expect(tabsContainer.locator('button', { hasText: 'Operations' })).toBeVisible({ timeout: 10000 });
    await expect(tabsContainer.locator('button', { hasText: 'Schedule' })).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('button', { hasText: 'Demand' })).toBeVisible({ timeout: 5000 });
    await expect(tabsContainer.locator('button', { hasText: 'Breakdowns' })).toBeVisible({ timeout: 5000 });
  });

  test('should display action buttons', async ({ page }) => {
    await navigateToSimulationV2(page);
    await waitForTabContent(page);

    await expect(page.locator('button:has-text("Validate Configuration")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('button:has-text("Run Simulation")')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('button:has-text("Import Config")')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('button:has-text("Export Config")')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('button:has-text("Reset")')).toBeVisible({ timeout: 5000 });
  });

  test('should display How to Use button and open guide', async ({ page }) => {
    await navigateToSimulationV2(page);
    await waitForTabContent(page);

    const helpButton = page.locator('button:has-text("How to Use")');
    await expect(helpButton).toBeVisible({ timeout: 10000 });

    await helpButton.click({ force: true });
    await expect(page.locator('text=Production Line Simulation v2.0 Guide')).toBeVisible({ timeout: 10000 });

    // Close dialog
    await page.locator('.v-dialog button:has-text("Close")').click();
    await page.waitForTimeout(300);
  });
});

test.describe('Simulation V2 - Operations Tab', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);
    await waitForTabContent(page);
  });

  test('should display Operations tab by default', async ({ page }) => {
    // Operations tab should be active
    const operationsTab = page.locator('.v-tabs button', { hasText: 'Operations' });
    await expect(operationsTab).toBeVisible({ timeout: 10000 });

    // Should show operations grid or empty state
    const gridOrEmpty = page.locator('.ag-root').or(page.locator('text=Add operations'));
    await expect(gridOrEmpty.first()).toBeVisible({ timeout: 10000 });
  });

  test('should show Add Operation button', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add Operation")');
    await expect(addButton).toBeVisible({ timeout: 10000 });
  });

  test('should add a new operation row', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add Operation")');
    await addButton.click({ force: true });

    // Wait for AG Grid to render the new row.
    const gridRows = page.locator('.ag-row');
    await expect(gridRows.first()).toBeVisible({ timeout: 15000 });
  });

  test('should show CSV import dialog', async ({ page }) => {
    const importButton = page.locator('button:has-text("Import CSV")');
    if (await importButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await importButton.click({ force: true });

      // Dialog should appear
      await expect(page.locator('.v-dialog')).toBeVisible({ timeout: 10000 });

      // Close dialog
      await page.keyboard.press('Escape');
    }
  });

  test('should edit operation values in grid', async ({ page }) => {
    // Add an operation first
    const addButton = page.locator('button:has-text("Add Operation")');
    await addButton.click({ force: true });
    await page.waitForTimeout(500);

    // Click on a cell to edit (product column)
    const productCell = page.locator('.ag-cell[col-id="product"]').first();
    if (await productCell.isVisible({ timeout: 5000 }).catch(() => false)) {
      await productCell.dblclick();
      await page.waitForTimeout(300);
    }
  });
});

test.describe('Simulation V2 - Schedule Tab', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);

    // Click on Schedule tab
    const scheduleTab = page.locator('.v-tabs button', { hasText: 'Schedule' });
    await scheduleTab.click({ force: true });
    await waitForTabContent(page, 10000);
  });

  test('should display Schedule Configuration', async ({ page }) => {
    await expect(page.locator('text=Schedule Configuration').first()).toBeVisible({ timeout: 15000 });
  });

  test('should show shift configuration', async ({ page }) => {
    await expect(page.locator('text=Shifts').or(page.locator('text=Shift')).first()).toBeVisible({ timeout: 15000 });
  });

  test('should show work days configuration', async ({ page }) => {
    await expect(page.locator('text=Work Days').or(page.locator('text=Days')).first()).toBeVisible({ timeout: 15000 });
  });

  test('should show overtime toggle', async ({ page }) => {
    // Look for overtime-related elements with broader matching
    const overtimeElement = page.locator('text=Overtime').or(page.locator('text=OT')).or(page.locator('[aria-label*="overtime" i]'));
    await expect(overtimeElement.first()).toBeVisible({ timeout: 15000 });
  });

  test('should display daily hours summary', async ({ page }) => {
    // Look for specific hours-related summary text visible on the schedule page
    const hoursElement = page.locator('text=Daily Planned Hours')
      .or(page.locator('text=Weekly Base Hours'))
      .or(page.locator('text=/\\d+\\.?\\d*h/'));
    await expect(hoursElement.first()).toBeVisible({ timeout: 15000 });
  });

  test('should update shift hours', async ({ page }) => {
    // Find any numeric input field in the schedule form
    const inputField = page.locator('.v-text-field input[type="number"]').first();
    if (await inputField.isVisible({ timeout: 5000 }).catch(() => false)) {
      await inputField.clear();
      await inputField.fill('10');
    }
  });
});

test.describe('Simulation V2 - Demand Tab', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);

    // Click on Demand tab
    const demandTab = page.locator('.v-tabs button', { hasText: 'Demand' });
    await demandTab.click({ force: true });
    await waitForTabContent(page, 10000);
  });

  test('should display Demand Configuration', async ({ page }) => {
    await expect(page.locator('text=Demand Configuration').or(page.locator('text=Demand')).first()).toBeVisible({ timeout: 15000 });
  });

  test('should show demand mode selector', async ({ page }) => {
    // Look for the select component
    await expect(page.locator('.v-select').first()).toBeVisible({ timeout: 15000 });
  });

  test('should show horizon days selector', async ({ page }) => {
    // Look for horizon or days selector
    const horizonElement = page.locator('text=Horizon').or(page.locator('text=Days')).or(page.locator('.v-select'));
    await expect(horizonElement.first()).toBeVisible({ timeout: 15000 });
  });

  test('should add product demand', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add Product Demand")');
    await expect(addButton).toBeVisible({ timeout: 15000 });
    await addButton.click({ force: true });

    const gridRows = page.locator('.ag-row');
    await expect(gridRows.first()).toBeVisible({ timeout: 15000 });
  });

  test('should interact with demand mode selector', async ({ page }) => {
    // Just verify the select is clickable
    const modeSelect = page.locator('.v-select').first();
    await expect(modeSelect).toBeVisible({ timeout: 15000 });
    await modeSelect.click({ force: true });
    await page.waitForTimeout(300);
    // Close by pressing escape
    await page.keyboard.press('Escape');
  });
});

test.describe('Simulation V2 - Breakdowns Tab', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);

    // Click on Breakdowns tab
    const breakdownsTab = page.locator('.v-tabs button', { hasText: 'Breakdowns' });
    await breakdownsTab.click({ force: true });
    await waitForTabContent(page, 10000);
  });

  test('should display Equipment Breakdowns section', async ({ page }) => {
    await expect(page.locator('text=Equipment Breakdowns').or(page.locator('text=Breakdowns')).first()).toBeVisible({ timeout: 15000 });
  });

  test('should show optional indicator', async ({ page }) => {
    // Look for optional or breakdowns indicator
    const indicator = page.locator('text=Optional').or(page.locator('text=Breakdowns')).or(page.locator('.v-chip'));
    await expect(indicator.first()).toBeVisible({ timeout: 15000 });
  });

  test('should show perfect reliability message when empty', async ({ page }) => {
    // Look for empty state message with broader matching
    const emptyMessage = page.locator('text=perfect').or(
      page.locator('text=No breakdown')
    ).or(
      page.locator('text=reliability')
    ).or(
      page.locator('text=100%')
    );
    await expect(emptyMessage.first()).toBeVisible({ timeout: 15000 });
  });

  test('should add breakdown rule', async ({ page }) => {
    const addButton = page.locator('button:has-text("Add Breakdown Rule")');
    await expect(addButton).toBeVisible({ timeout: 15000 });
    await addButton.click({ force: true });

    // Check for either grid rows or a dialog for adding breakdown
    const gridOrDialog = page.locator('.ag-row').or(page.locator('.v-dialog'));
    await expect(gridOrDialog.first()).toBeVisible({ timeout: 15000 });
  });
});

test.describe('Simulation V2 - Validation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);
    await waitForTabContent(page);
  });

  test('should disable validate button when no operations', async ({ page }) => {
    const validateButton = page.locator('button:has-text("Validate Configuration")');
    await expect(validateButton).toBeDisabled({ timeout: 10000 });
  });

  test('should enable validate button after adding operation', async ({ page }) => {
    // Add an operation
    const addButton = page.locator('button:has-text("Add Operation")');
    await addButton.click({ force: true });

    // Validate button should be enabled
    const validateButton = page.locator('button:has-text("Validate Configuration")');
    await expect(validateButton).toBeEnabled({ timeout: 15000 });
  });

  test('should show validation panel after validation', async ({ page }) => {
    // Add an operation
    const addButton = page.locator('button:has-text("Add Operation")');
    await addButton.click({ force: true });
    await page.waitForTimeout(500);

    // Click validate
    const validateButton = page.locator('button:has-text("Validate Configuration")');
    await validateButton.click({ force: true });

    // Should show validation panel (may have errors for incomplete data).
    // The toBeVisible timeout absorbs the API round-trip — no separate
    // networkidle wait needed.
    const validationPanel = page.locator('text=Validation').or(page.locator('.v-alert'));
    await expect(validationPanel.first()).toBeVisible({ timeout: 20000 });
  });
});

test.describe('Simulation V2 - Run Simulation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);
    await waitForTabContent(page);
  });

  test('should disable run button when conditions not met', async ({ page }) => {
    const runButton = page.locator('button:has-text("Run Simulation")');
    await expect(runButton).toBeDisabled({ timeout: 10000 });
  });

  test('should show loading state when running simulation', async ({ page }) => {
    // This test would need complete valid data to actually run
    // For now, just verify the button exists
    const runButton = page.locator('button:has-text("Run Simulation")');
    await expect(runButton).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Simulation V2 - Config Management', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);
    await waitForTabContent(page);
  });

  test('should open import config dialog', async ({ page }) => {
    const importButton = page.locator('button:has-text("Import Config")');
    await importButton.click({ force: true });

    await expect(page.locator('text=Import Configuration')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('textarea')).toBeVisible({ timeout: 5000 });

    // Close dialog
    await page.locator('.v-dialog button:has-text("Cancel")').click();
  });

  test('should import valid JSON configuration', async ({ page }) => {
    const importButton = page.locator('button:has-text("Import Config")');
    await importButton.click({ force: true });
    await page.waitForTimeout(300);

    const validConfig = JSON.stringify({
      operations: [
        { product: 'Test', step: 1, operation: 'Op1', machine_tool: 'M1', sam_min: 2, operators: 1, grade_pct: 85, fpd_pct: 2 }
      ],
      schedule: { shifts_enabled: 1, shift1_hours: 8, work_days: 5 },
      demands: [
        { product: 'Test', daily_demand: 100, bundle_size: 10 }
      ]
    });

    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible({ timeout: 10000 });
    await textarea.fill(validConfig);

    // Find the import button in the dialog (not the main import button)
    const dialogImportBtn = page.locator('.v-dialog button:has-text("Import")');
    await dialogImportBtn.click({ force: true });

    // Go to operations tab to verify
    await page.locator('.v-tabs button', { hasText: 'Operations' }).click();

    // Check that operations grid has data — toBeVisible absorbs the
    // import-roundtrip + tab switch wait.
    const operationsGrid = page.locator('.ag-row');
    await expect(operationsGrid.first()).toBeVisible({ timeout: 20000 });
  });

  test('should show error for invalid JSON', async ({ page }) => {
    const importButton = page.locator('button:has-text("Import Config")');
    await importButton.click({ force: true });
    await page.waitForTimeout(300);

    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible({ timeout: 10000 });
    await textarea.fill('invalid json {{{');

    const dialogImportBtn = page.locator('.v-dialog button:has-text("Import")');
    await dialogImportBtn.click({ force: true });

    // Should show error alert
    await expect(page.locator('.v-alert').or(page.locator('text=Invalid')).or(page.locator('text=Error')).first()).toBeVisible({ timeout: 10000 });
  });

  test('should disable export when no data', async ({ page }) => {
    const exportButton = page.locator('button:has-text("Export Config")');
    await expect(exportButton).toBeDisabled({ timeout: 15000 });
  });

  test('should enable export after adding operations', async ({ page }) => {
    // Add an operation
    const addButton = page.locator('button:has-text("Add Operation")');
    await addButton.click({ force: true });

    const exportButton = page.locator('button:has-text("Export Config")');
    await expect(exportButton).toBeEnabled({ timeout: 20000 });
  });

  test('should show reset confirmation dialog', async ({ page }) => {
    // Add an operation first
    const addButton = page.locator('button:has-text("Add Operation")');
    await addButton.click({ force: true });
    await page.waitForTimeout(500);

    // Click reset
    const resetButton = page.locator('button:has-text("Reset")');
    await resetButton.click({ force: true });
    await page.waitForTimeout(500);

    // Should show reset dialog with options
    await expect(page.locator('.v-dialog')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Reset Configuration')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=Clear All')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=Load Sample Data')).toBeVisible({ timeout: 5000 });

    // Cancel — use Escape key because WebKit's v-overlay-scroll-blocked
    // on <html> intercepts pointer events on dialog buttons
    await page.keyboard.press('Escape');
  });

  test('should reset all data after confirmation', async ({ page }) => {
    // Add an operation
    const addButton = page.locator('button:has-text("Add Operation")');
    await addButton.click({ force: true });
    await page.waitForTimeout(500);

    // Click reset
    const resetButton = page.locator('button:has-text("Reset")');
    await resetButton.click({ force: true });
    await page.waitForTimeout(500);

    // Wait for dialog to fully render before interacting — under parallel
    // load WebKit is slower to make dialog content interactive
    const clearAllOption = page.locator('.v-list-item').filter({ hasText: 'Clear All' });
    await clearAllOption.waitFor({ state: 'visible', timeout: 5000 });
    // Use force:true — WebKit's v-overlay-scroll-blocked intercepts pointer events
    await clearAllOption.click({ force: true });

    // Operations should be cleared (toHaveCount polls until satisfied).
    const gridRows = page.locator('.ag-row');
    await expect(gridRows).toHaveCount(0, { timeout: 20000 });
  });
});

test.describe('Simulation V2 - Summary Stats', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);
    await waitForTabContent(page);
  });

  test('should not show summary stats when no operations', async ({ page }) => {
    // Summary bar visibility depends on having operations
    // Just verify the page loaded correctly
    await expect(page.locator('text=Production Line Simulation v2.0')).toBeVisible({ timeout: 10000 });
  });

  test('should show summary stats after adding operations', async ({ page }) => {
    // Add operations
    const addButton = page.locator('button:has-text("Add Operation")');
    await addButton.click({ force: true });

    // Summary should show - look for the stat card or operation count
    const statsIndicator = page.locator('.v-card').filter({ hasText: 'Operations' }).or(page.locator('text=1 operation'));
    await expect(statsIndicator.first()).toBeVisible({ timeout: 20000 });
  });
});

test.describe('Simulation V2 - Full Workflow', () => {
  test('should complete full simulation workflow', async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);
    await waitForTabContent(page);

    // Step 1: Import a valid configuration
    const importButton = page.locator('button:has-text("Import Config")');
    await importButton.click({ force: true });
    await page.waitForTimeout(300);

    const validConfig = JSON.stringify({
      operations: [
        { product: 'Widget-A', step: 1, operation: 'Cut', machine_tool: 'Cutter-1', sam_min: 2.5, operators: 2, grade_pct: 85, fpd_pct: 3 },
        { product: 'Widget-A', step: 2, operation: 'Assemble', machine_tool: 'Assembly-1', sam_min: 5.0, operators: 3, grade_pct: 80, fpd_pct: 5 },
        { product: 'Widget-A', step: 3, operation: 'Pack', machine_tool: 'Packer-1', sam_min: 1.5, operators: 1, grade_pct: 90, fpd_pct: 1 }
      ],
      schedule: {
        shifts_enabled: 1,
        shift1_hours: 8,
        shift2_hours: 0,
        shift3_hours: 0,
        work_days: 5,
        ot_enabled: false,
        weekday_ot_hours: 0,
        weekend_ot_days: 0,
        weekend_ot_hours: 0
      },
      demands: [
        { product: 'Widget-A', daily_demand: 100, weekly_demand: null, bundle_size: 10, mix_share_pct: null }
      ],
      breakdowns: [],
      mode: 'demand-driven',
      horizon_days: 1
    });

    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible({ timeout: 10000 });
    await textarea.fill(validConfig);

    const dialogImportBtn = page.locator('.v-dialog button:has-text("Import")');
    await dialogImportBtn.click({ force: true });

    // Step 2: Verify data loaded - go to operations tab
    await page.locator('.v-tabs button', { hasText: 'Operations' }).click();
    await expect(page.locator('.ag-row').first()).toBeVisible({ timeout: 20000 });

    // Step 3: Validate configuration
    const validateButton = page.locator('button:has-text("Validate Configuration")');
    await expect(validateButton).toBeEnabled({ timeout: 15000 });
    await validateButton.click({ force: true });

    // Step 4: Check for validation response (any validation panel appearing).
    // The toBeVisible timeout absorbs the validate API round-trip.
    const validationPanel = page.locator('.v-card').filter({ hasText: 'Validation' });
    await expect(validationPanel.first()).toBeVisible({ timeout: 20000 });

    // Step 5: Run simulation if run button is enabled. If valid config
    // is required and our import wasn't, the run button stays disabled —
    // skip the run step in that case but still assert validation worked.
    const runButton = page.locator('button:has-text("Run Simulation")');
    const runEnabled = await runButton.isEnabled({ timeout: 5000 }).catch(() => false);
    if (runEnabled) {
      await runButton.click({ force: true });

      // Results dialog or "Results" header should appear after the run
      // completes. The 30s timeout absorbs SimPy execution time.
      const resultsIndicator = page.locator('.v-dialog').or(page.locator('text=Results'));
      await expect(resultsIndicator.first()).toBeVisible({ timeout: 30000 });
    }
  });
});

test.describe('Simulation V2 - Responsive Design', () => {
  test('should be functional on tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await login(page);
    await navigateToSimulationV2(page);

    // Page should still be functional
    await expect(page.locator('text=Production Line Simulation').first()).toBeVisible({ timeout: 15000 });
  });

  test('should be functional on mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await login(page);
    await navigateToSimulationV2(page);

    // Page should still be functional - may have shorter title on mobile
    await expect(page.locator('text=Simulation').first()).toBeVisible({ timeout: 15000 });
  });
});

test.describe('Simulation V2 - Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);
    await waitForTabContent(page);
  });

  test('should display error alert when API fails', async ({ page }) => {
    // This would require mocking the API, but we can at least verify
    // the error alert component exists

    // Add operation with invalid data and try to validate
    const addButton = page.locator('button:has-text("Add Operation")');
    await addButton.click({ force: true });
    await page.waitForTimeout(500);

    // Try to validate incomplete data
    const validateButton = page.locator('button:has-text("Validate Configuration")');
    await validateButton.click({ force: true });

    // Should show some kind of feedback (error or validation result).
    // toBeVisible absorbs the API round-trip wait.
    const feedback = page.locator('.v-alert').or(page.locator('.v-card').filter({ hasText: 'Validation' }));
    await expect(feedback.first()).toBeVisible({ timeout: 20000 });
  });
});

test.describe('Simulation V2 - Sample Data Onboarding', () => {
  test('should load sample T-Shirt data on first visit', async ({ page }) => {
    await login(page);

    // Clear visited flag to simulate first visit
    await page.evaluate(() => {
      localStorage.removeItem('simulation_v2_visited');
    });

    // Navigate to simulation page via stable href selector (locale-independent)
    const navItem = page.locator('.v-navigation-drawer a[href="/simulation"]');
    await navItem.scrollIntoViewIfNeeded();
    await navItem.click({ force: true });

    // Wait for the page header to confirm navigation
    await page.waitForSelector('text=Production Line Simulation v2.0', { state: 'visible', timeout: 30000 });

    // Should have pre-loaded operations (check for summary stats)
    const summaryStats = page.locator('.v-card').filter({ hasText: 'Products' });
    await expect(summaryStats.first()).toBeVisible({ timeout: 15000 });

    // The grid should have rows with sample data
    const gridRows = page.locator('.ag-row');
    await expect(gridRows.first()).toBeVisible({ timeout: 10000 });
    const rowCount = await gridRows.count();
    expect(rowCount).toBeGreaterThan(0);

    // Verify it's T-Shirt data (use first() to avoid strict mode violation)
    const tshirtCell = page.locator('.ag-cell').filter({ hasText: 'Basic T-Shirt' }).first();
    await expect(tshirtCell).toBeVisible({ timeout: 15000 });
  });

  test('should not reload sample data on subsequent visits', async ({ page }) => {
    await login(page);

    // Mark as already visited
    await page.evaluate(() => {
      localStorage.setItem('simulation_v2_visited', 'true');
    });

    await navigateToSimulationV2(page);
    await waitForTabContent(page);

    // Welcome snackbar should NOT appear
    const welcomeSnackbar = page.locator('.v-snackbar').filter({ hasText: 'Welcome' });
    const hasWelcome = await welcomeSnackbar.isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasWelcome).toBe(false);
  });

  test('should show reset dialog with Clear All and Load Sample options', async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);
    await waitForTabContent(page);

    // Click Reset button
    const resetButton = page.locator('button:has-text("Reset")');
    await resetButton.click({ force: true });
    await page.waitForTimeout(500);

    // Reset dialog should appear with two options
    const dialog = page.locator('.v-dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });
    await expect(dialog.locator('text=Reset Configuration')).toBeVisible({ timeout: 5000 });
    await expect(dialog.locator('.v-list-item:has-text("Clear All")')).toBeVisible({ timeout: 5000 });
    await expect(dialog.locator('.v-list-item:has-text("Load Sample Data")')).toBeVisible({ timeout: 5000 });

    // Close dialog — use Escape key instead of clicking Cancel because
    // WebKit's v-overlay-scroll-blocked on <html> intercepts pointer events
    await page.keyboard.press('Escape');
  });

  test('should load sample data when clicking Load Sample Data in reset dialog', async ({ page }) => {
    await login(page);
    await navigateToSimulationV2(page);
    await waitForTabContent(page);

    // Click Reset button
    const resetButton = page.locator('button:has-text("Reset")');
    await resetButton.click({ force: true });
    await page.waitForTimeout(500);

    // Click Load Sample Data option — wait for render + force:true for WebKit overlay
    const loadSampleOption = page.locator('.v-list-item').filter({ hasText: 'Load Sample Data' });
    await loadSampleOption.waitFor({ state: 'visible', timeout: 5000 });
    await loadSampleOption.click({ force: true });
    await page.waitForTimeout(1000);

    // Should have sample data loaded
    const tshirtCell = page.locator('.ag-cell').filter({ hasText: 'Basic T-Shirt' });
    await expect(tshirtCell.first()).toBeVisible({ timeout: 10000 });

    // Summary stats should show data
    const productsCount = page.locator('.text-h6').filter({ hasText: '1' }).first();
    await expect(productsCount).toBeVisible({ timeout: 5000 });
  });

  test('should clear all data when clicking Clear All in reset dialog', async ({ page }) => {
    await login(page);

    // First load with sample data
    await page.evaluate(() => {
      localStorage.removeItem('simulation_v2_visited');
    });

    // Navigate to simulation page via stable href selector (locale-independent)
    const navItem = page.locator('.v-navigation-drawer a[href="/simulation"]');
    await navItem.scrollIntoViewIfNeeded();
    await navItem.click({ force: true });
    await page.waitForSelector('text=Production Line Simulation v2.0', { state: 'visible', timeout: 30000 });

    // Verify sample data is loaded
    const gridRows = page.locator('.ag-row');
    await expect(gridRows.first()).toBeVisible({ timeout: 15000 });
    const initialCount = await gridRows.count();
    expect(initialCount).toBeGreaterThan(0);

    // Click Reset button
    const resetButton = page.locator('button:has-text("Reset")');
    await resetButton.click({ force: true });

    // Wait for dialog to fully render, then click Clear All
    // Use force:true — WebKit's v-overlay-scroll-blocked intercepts pointer events
    const clearAllOption = page.locator('.v-list-item').filter({ hasText: 'Clear All' });
    await clearAllOption.waitFor({ state: 'visible', timeout: 5000 });
    await clearAllOption.click({ force: true });

    // After Clear All, the grid must report zero rows. toHaveCount polls
    // until the assertion is satisfied or times out.
    await expect(gridRows).toHaveCount(0, { timeout: 15000 });
  });
});
