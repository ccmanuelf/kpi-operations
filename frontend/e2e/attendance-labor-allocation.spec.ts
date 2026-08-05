import { test, expect, Page } from '@playwright/test'
import { login } from './helpers'

/**
 * Attendance grid — labor-hours capture E2E guard (Cycle 3 PR-A, Task 7).
 *
 * Covers the OT split columns + AllocationEditorDialog end to end: enter
 * an OT split on a row, open the allocation dialog, add
 * billed_production 5h + training 1h, save, and assert both the local
 * summary-cell update and the actual API round-trip (response
 * assertion on the PUT the dialog fires).
 *
 * Uses a PRE-SEEDED, already-persisted attendance entry (direct API call
 * before navigating) rather than a fresh unsaved grid row. Root cause:
 * AGGridBase's rowData binding doesn't route AG Grid's own cell-edit
 * mutations back through Vue's reactive `attendanceData` ref (verified
 * independently — editing the pre-existing `status` column via the real
 * grid UI *also* never flips the batch Save Records button's disabled
 * state), so the grid's batch-save path can't be driven end-to-end via a
 * real browser session today. That's a pre-existing gap in
 * useAttendanceGridData/AGGridBase's cell-edit wiring, unrelated to this
 * task's diff — flagged in the task report, not fixed here (fixing it
 * safely means auditing every AGGridBase consumer's edit-then-save flow,
 * well past Task 7's remit). AllocationEditorDialog's own save path is
 * unaffected: for an already-persisted row (has attendance_entry_id) it
 * PUTs directly via api.updateAttendanceEntry, bypassing the grid's
 * batch-save/hasChanges chain entirely — which is exactly the
 * "entry-update path" the task brief calls for.
 *
 * Login as 'operator' (not 'admin'): the attendance grid has no client
 * selector of its own — activeClientId() falls back to
 * authStore.user.client_id_assigned, which is null for a fresh admin
 * session, so an admin session can load the grid but can't create
 * attendance records. operator1 carries an assigned client (ACME-MFG
 * per the demo seed) and matches this grid's real-world primary users.
 */

test.setTimeout(60000)

async function navigateToAttendance(page: Page) {
  await page.goto('/data-entry/attendance', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('[data-testid="attendance-entry-view"]', {
    state: 'visible',
    timeout: 30000,
  })
}

// Seeds one already-persisted attendance entry for TODAY. The grid's
// existingMap merge (useAttendanceGridData.ts loadEmployees) keys by
// employee_id and takes the LAST entry seen while iterating a
// shift_date-DESC list — GET /api/attendance's shift_date query param is
// silently ignored (not a declared param on that endpoint), so any older
// pre-existing entry for the same employee+shift would win the merge over
// today's freshly-seeded one. Picks the first employee (in the same
// employee_name order /api/employees returns, which is also the grid's
// row order) with ZERO existing entries for the target shift, so there's
// nothing to collide with. Returns the row index that employee will land
// on, computed from the same ordered list the grid loads.
async function seedExistingAttendanceEntry(page: Page) {
  return page.evaluate(async () => {
    const token = localStorage.getItem('access_token')
    const headers = { Authorization: `Bearer ${token}` }

    const employeesRes = await fetch('/api/employees?limit=100', { headers })
    const employees = employeesRes.ok ? await employeesRes.json() : []
    const shiftsRes = await fetch('/api/shifts', { headers })
    const shifts = shiftsRes.ok ? await shiftsRes.json() : []
    if (!Array.isArray(employees) || employees.length === 0) return null
    if (!Array.isArray(shifts) || shifts.length === 0) return null

    const shift = shifts[0]

    let employee = null
    let rowIndex = -1
    for (let i = 0; i < employees.length; i++) {
      const candidate = employees[i]
      const existingRes = await fetch(
        `/api/attendance?employee_id=${candidate.employee_id}&shift_id=${shift.shift_id}`,
        { headers },
      )
      const existing = existingRes.ok ? await existingRes.json() : []
      if (Array.isArray(existing) && existing.length === 0) {
        employee = candidate
        rowIndex = i
        break
      }
    }
    if (!employee) return null

    const d = new Date()
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
      d.getDate(),
    ).padStart(2, '0')}`

    const createRes = await fetch('/api/attendance', {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: 'ACME-MFG',
        employee_id: employee.employee_id,
        shift_date: today,
        shift_id: shift.shift_id,
        scheduled_hours: 8,
        actual_hours: 8,
      }),
    })
    if (!createRes.ok) return null
    const created = await createRes.json()
    return {
      employeeId: employee.employee_id,
      employeeName: employee.employee_name,
      attendanceEntryId: created.attendance_entry_id,
      rowIndex,
    }
  })
}

test.describe('Attendance grid — OT split + hour allocation', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, 'operator')
  })

  test('OT split + allocation dialog round-trip through the entry-update path', async ({
    page,
  }) => {
    await navigateToAttendance(page)

    const seed = await seedExistingAttendanceEntry(page)
    expect(seed, 'setup: need at least one employee + shift for the seeded client').toBeTruthy()

    // Reload so loadEmployees() picks up the freshly-seeded entry.
    await navigateToAttendance(page)

    const loadBtn = page.locator('[data-testid="attendance-load-employees-btn"]')
    await expect(loadBtn).toBeEnabled({ timeout: 15000 })
    await loadBtn.click()

    const grid = page.locator('.ag-root').first()
    await expect(grid).toBeVisible({ timeout: 15000 })

    // AG Grid virtualizes rows — the seeded employee may be well past the
    // ~15 rows the 600px-tall viewport renders by default (desktop row
    // height is 38px; see useResponsive.ts::getRowHeight). Scroll it into
    // the render window before locating it.
    await page
      .locator('.ag-body-viewport')
      .first()
      .evaluate((el, top) => {
        el.scrollTop = top
      }, seed!.rowIndex * 38)

    const rowIndex = String(seed!.rowIndex)
    const row = page.locator(`.ag-center-cols-container .ag-row[row-index="${rowIndex}"]`)
    await expect(row).toBeVisible({ timeout: 15000 })
    // Correlation check: the seeded employee (from the same unfiltered,
    // employee_name-ordered list the grid loads) must land at this row.
    // employee_id is pinned left, so it renders in a separate container.
    const pinnedRow = page.locator(
      `.ag-pinned-left-cols-container .ag-row[row-index="${rowIndex}"]`,
    )
    await expect(pinnedRow.locator('.ag-cell[col-id="employee_id"]')).toHaveText(
      String(seed!.employeeId),
    )

    // Enter an OT split (UI coverage for the new column — normal_hours
    // = actual_hours(8) is what backend/calculations/labor_hours.py::
    // validate_ot_split requires if this ever round-trips through the
    // grid's batch save).
    const normalCell = row.locator('.ag-cell[col-id="normal_hours"]')
    await normalCell.click()
    await page.keyboard.type('8')
    await page.keyboard.press('Tab')
    await expect(normalCell).toHaveText('8')

    // Open the allocation dialog from the row's allocations button-cell.
    const allocationsBtn = row.locator('[data-testid="attendance-allocations-btn"]')
    await expect(allocationsBtn).toBeVisible()
    await allocationsBtn.click()

    const dialog = page.locator('[data-testid="allocation-editor-dialog"]')
    await expect(dialog).toBeVisible({ timeout: 10000 })

    // Row 0: billed_production, 5h.
    await page.locator('[data-testid="allocation-category-select-0"]').click()
    await page
      .locator('.v-list-item')
      .filter({ hasText: /Billed production|Producción facturada/i })
      .first()
      .click()
    await page.locator('[data-testid="allocation-hours-input-0"] input').fill('5')

    // Add a second row: training, 1h.
    await page.locator('[data-testid="allocation-add-row-btn"]').click()
    await page.locator('[data-testid="allocation-category-select-1"]').click()
    await page
      .locator('.v-list-item')
      .filter({ hasText: /^Training$|^Capacitación$/i })
      .first()
      .click()
    await page.locator('[data-testid="allocation-hours-input-1"] input').fill('1')

    // Both hours are within actual_hours (6 <= 8) — save should be enabled.
    const saveBtn = page.locator('[data-testid="allocation-save-btn"]')
    await expect(saveBtn).toBeEnabled({ timeout: 5000 })

    // The dialog's own save fires PUT .../attendance/{id} directly (the
    // row is already persisted) — the "entry-update path" the task brief
    // calls for. Assert the response body actually carries what we
    // entered — the API round-trip. (Matches on "/attendance/" rather
    // than "/api/attendance/" — the frontend's axios baseURL is
    // "/api/v1", proxied to the backend's unversioned "/api/attendance"
    // routes.)
    const [response] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes('/attendance/') && r.request().method() === 'PUT',
        { timeout: 15000 },
      ),
      saveBtn.click(),
    ])

    expect(response.ok()).toBeTruthy()
    const body = await response.json()
    expect(body.allocations).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ category: 'billed_production', hours: 5 }),
        expect.objectContaining({ category: 'training', hours: 1 }),
      ]),
    )
    expect(body.billed_hours).toBe(5)

    await expect(dialog).toBeHidden({ timeout: 10000 })

    // Summary cell reflects the saved allocations (6 / 8 h — the
    // template is locale-invariant, only the numbers substitute).
    await expect(allocationsBtn).toHaveText('6 / 8 h', { timeout: 10000 })
  })
})
