import { test, expect, Page } from '@playwright/test'
import { login } from './helpers'

/**
 * Attendance grid — labor-hours capture E2E guard (Cycle 3 PR-A, Task 7).
 *
 * Covers the OT split columns + AllocationEditorDialog end to end: enter
 * an OT split on a row, open the allocation dialog, add
 * billed_production 5h + training 1h, save the dialog (local summary-cell
 * update + its own direct PUT round-trip), then drive the grid's real
 * batch Save Records flow for the OT split and assert THAT PUT's response
 * body carries the persisted split — the brief's "API round-trip
 * persisted" requirement for both the allocations and the OT split.
 *
 * Uses a PRE-SEEDED, already-persisted attendance entry (direct API call
 * before navigating) rather than a fresh unsaved grid row, so both the
 * dialog's own save (PUT, requires attendance_entry_id) and the grid's
 * batch save (PUT, not POST) exercise the update path.
 *
 * Fix round 1 note: this guard previously stopped short of driving Save
 * Records for the OT split — useAttendanceGridData's `hasChanges` (and
 * both completeness chips) never reacted to a real AG Grid cell edit,
 * because AG Grid's `cellValueChanged` event.data is not reliably the
 * same object instance Vue tracks inside attendanceData.value (verified
 * empirically — mutating event.data in place left attendanceData.value's
 * own copy of the row untouched). Fixed in useAttendanceGridData.ts by
 * re-resolving to the actual tracked row by employee_id before mutating
 * (markRowAsChanged/onAllocationsSaved/openAllocationDialog), plus an
 * `editTick` dirty-signal read by every affected computed as a
 * belt-and-suspenders re-derive trigger — this spec's
 * `attendance-save-btn` enabled-state assertion below is the end-to-end
 * guard for that fix.
 *
 * Login as 'operator' (not 'admin'): the attendance grid has no client
 * selector of its own — activeClientId() falls back to
 * authStore.user.client_id_assigned, which is null for a fresh admin
 * session, so an admin session can load the grid but can't create
 * attendance records. demo_operator carries an assigned client (DEMO-PIECE
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

// Seeds one already-persisted attendance entry for TODAY, on an employee
// that has no entry for today's shift yet.
//
// Why "today's shift" and not "any date": the grid's existingMap merge
// (useAttendanceGridData.ts loadEmployees) keys by employee_id and takes
// the LAST entry seen, so two entries for the SAME employee on the SAME
// shift_date would make it non-deterministic which one hydrates the row —
// and the dialog's PUT would then target an attendance_entry_id this
// helper never returned. Entries on OTHER dates cannot collide: that same
// loadEmployees call passes `shift_date: selectedDate.value` (today) to
// GET /attendance, and the backend filters it exactly
// (crud/attendance.py::get_attendance_records, `func.date(shift_date) ==
// shift_date`). Measured against a freshly seeded DB: every DEMO-PIECE
// employee has 100+ prior-day entries, and
// GET /attendance?shift_date=<today>&shift_id=1 still returns 0 rows.
//
// This check used to omit shift_date, i.e. it demanded an employee with
// zero entries on ANY date. That is unsatisfiable for a correctly
// tenant-scoped listing — the seeder backfills every one of a client's
// employees across the whole window — so it only ever passed by picking
// an employee belonging to ANOTHER tenant out of a listing that leaked
// them, and then binding that employee to this client via the POST below.
// It was a test that depended on the cross-tenant leak, not a guard
// against it.
//
// What today is free at all rests on: backend/seed/emitters_master.py
// computes activity_days = (as_of - activity_start).days and
// emitters_operations.py iterates range(activity_days), so the last
// seeded day is as_of - 1 and the as_of day itself carries no attendance.
// If the seeder ever emits as_of-day rows, every candidate here collides
// and this helper returns null again — the fix then is to move the grid
// off today (the view's date field), NOT to widen the search back across
// tenants.
//
// client_id comes from the chosen employee's own assignment rather than a
// hardcoded 'DEMO-PIECE': if the listing ever leaks another tenant's
// employee again, the POST is then made against THAT tenant and the
// backend's verify_client_access returns 403, so this helper fails loudly
// instead of silently manufacturing a cross-tenant row.
//
// Picks the first eligible employee in the same employee_name order
// /api/employees returns (which is also the grid's row order — the grid's
// extra shift_id/active params are not declared on the endpoint and are
// ignored, so both calls get the same page). Returns the row index that
// employee will land on, computed from the same ordered list the grid
// loads.
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

    const d = new Date()
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
      d.getDate(),
    ).padStart(2, '0')}`

    let employee = null
    let clientId = ''
    let rowIndex = -1
    for (let i = 0; i < employees.length; i++) {
      const candidate = employees[i]
      // client_id_assigned is a comma-separated token list; NULL marks a
      // floating-pool employee who belongs to no tenant, and attendance
      // needs a client_id, so those are not candidates.
      const assigned = String(candidate.client_id_assigned || '')
        .split(',')
        .map((c: string) => c.trim())
        .filter(Boolean)
      if (assigned.length === 0) continue
      const existingRes = await fetch(
        `/api/attendance?employee_id=${candidate.employee_id}&shift_id=${shift.shift_id}` +
          `&shift_date=${today}`,
        { headers },
      )
      const existing = existingRes.ok ? await existingRes.json() : []
      if (Array.isArray(existing) && existing.length === 0) {
        employee = candidate
        clientId = assigned[0]
        rowIndex = i
        break
      }
    }
    if (!employee) return null

    const createRes = await fetch('/api/attendance', {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: clientId,
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

  test('OT split (via Save Records) + allocation dialog round-trip through the entry-update path', async ({
    page,
  }) => {
    await navigateToAttendance(page)

    const seed = await seedExistingAttendanceEntry(page)
    expect(
      seed,
      "setup: the logged-in user's own client needs a shift and at least one " +
        'employee with no attendance entry for it today (see seedExistingAttendanceEntry)',
    ).toBeTruthy()

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
    // A couple of rows of buffer above the target keeps it comfortably
    // inside AG Grid's virtualized render window even if the exact pixel
    // math (uniform 38px rows, no header/padding offset) is slightly off.
    const scrollTarget = Math.max(0, (seed!.rowIndex - 2) * 38)
    const rowIndex = String(seed!.rowIndex)
    const row = page.locator(`.ag-row[row-index="${rowIndex}"]`)

    await expect(async () => {
      // v36 renamed the scroll container `.ag-body-viewport` ->
      // `.ag-grid-viewport` (verified against the shipped bundle: zero
      // occurrences of the old name, 58 of the new). Throw rather than
      // no-op if it is missing: `scrollTop` on a non-existent or
      // non-scrolling element is silent, which would surface as "row not
      // found" and send the next reader hunting the wrong bug.
      await page.evaluate((top) => {
        const scroller = document.querySelector<HTMLElement>('.ag-grid-viewport')
        if (!scroller) throw new Error('.ag-grid-viewport not found - AG Grid DOM changed again')
        scroller.scrollTop = top
      }, scrollTarget)
      await expect(row).toBeVisible({ timeout: 2000 })
    }).toPass({ timeout: 15000 })
    // Correlation check: the seeded employee (from the same unfiltered,
    // employee_name-ordered list the grid loads) must land at this row.
    // employee_id is pinned left, but as of v36 the pinned and centre cell
    // groups live inside the SAME `.ag-row`, so the row locator above already
    // covers it -- no separate container locator is needed.
    await expect(row.locator('.ag-cell[col-id="employee_id"]')).toHaveText(
      String(seed!.employeeId),
    )

    // Save Records starts disabled (nothing changed yet).
    const saveRecordsBtn = page.locator('[data-testid="attendance-save-btn"]')
    await expect(saveRecordsBtn).toBeDisabled()

    // Enter a full OT split via a real grid cell edit: normal_hours = 8 =
    // actual_hours satisfies backend/calculations/labor_hours.py::
    // validate_ot_split's sum-must-equal-actual_hours rule with
    // double/triple left at their unset default (server defaults missing
    // tiers to 0 for the sum check, then normalizes them to 0 in the
    // persisted record).
    const normalCell = row.locator('.ag-cell[col-id="normal_hours"]')
    await normalCell.click()
    await page.keyboard.type('8')
    await page.keyboard.press('Tab')
    await expect(normalCell).toHaveText('8')

    // Fix round 1 guard: a real cell edit must flip hasChanges and
    // enable Save Records (previously stayed stuck disabled — see the
    // file-level doc comment).
    await expect(saveRecordsBtn).toBeEnabled({ timeout: 5000 })

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
    const dialogSaveBtn = page.locator('[data-testid="allocation-save-btn"]')
    await expect(dialogSaveBtn).toBeEnabled({ timeout: 5000 })

    // The dialog's own save fires PUT .../attendance/{id} directly (the
    // row is already persisted) — the "entry-update path" the task brief
    // calls for. Assert the response body actually carries what we
    // entered — the API round-trip. (Matches on "/attendance/" rather
    // than "/api/attendance/" — the frontend's axios baseURL is
    // "/api/v1", proxied to the backend's unversioned "/api/attendance"
    // routes.)
    const [dialogPutResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes('/attendance/') && r.request().method() === 'PUT',
        { timeout: 15000 },
      ),
      dialogSaveBtn.click(),
    ])

    expect(dialogPutResponse.ok()).toBeTruthy()
    const dialogPutBody = await dialogPutResponse.json()
    expect(dialogPutBody.allocations).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ category: 'billed_production', hours: 5 }),
        expect.objectContaining({ category: 'training', hours: 1 }),
      ]),
    )
    expect(dialogPutBody.billed_hours).toBe(5)

    await expect(dialog).toBeHidden({ timeout: 10000 })

    // Summary cell reflects the saved allocations (6 / 8 h — the
    // template is locale-invariant, only the numbers substitute).
    await expect(allocationsBtn).toHaveText('6 / 8 h', { timeout: 10000 })

    // Fix round 1 guard, the real path: Save Records is still enabled
    // (the OT cell edit's _hasChanges survives the dialog round-trip),
    // click it, confirm the read-back dialog, and assert the resulting
    // PUT actually carries the persisted OT split — not just a DOM
    // assertion on the cell text.
    await expect(saveRecordsBtn).toBeEnabled({ timeout: 5000 })
    await saveRecordsBtn.click()

    const confirmBtn = page.locator('[data-testid="readback-confirm-btn"]')
    await expect(confirmBtn).toBeVisible({ timeout: 10000 })

    const [saveRecordsPutResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes('/attendance/') && r.request().method() === 'PUT',
        { timeout: 15000 },
      ),
      confirmBtn.click(),
    ])

    expect(saveRecordsPutResponse.ok()).toBeTruthy()
    const saveRecordsPutBody = await saveRecordsPutResponse.json()
    expect(saveRecordsPutBody.normal_hours).toBe(8)
    expect(saveRecordsPutBody.double_hours).toBe(0)
    expect(saveRecordsPutBody.triple_hours).toBe(0)
    // The allocations set via the dialog earlier ride along on the same
    // buildPayload-driven Save Records request (it always sends the
    // row's current full state, not just the field that changed).
    expect(saveRecordsPutBody.allocations).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ category: 'billed_production', hours: 5 }),
        expect.objectContaining({ category: 'training', hours: 1 }),
      ]),
    )
  })
})
