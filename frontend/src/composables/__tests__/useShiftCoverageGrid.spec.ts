/**
 * Gates for the shift-coverage screen.
 *
 * Two things here are not stylistic and each has a server-side counterpart:
 *
 *  - the write tier SPLITS (POST/PUT contributor, DELETE supervisory), so an
 *    operator may edit and must not be offered a delete;
 *  - `coverage_percentage` is derived and clamped server-side, so an editable
 *    percentage column would take a value the next read throws away.
 *
 * The rest pin the races this repo has already been bitten by on a
 * client-scoped screen: a slower read landing over a newer one, and a
 * committed write whose refresh failed being reported as a failed write.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getShifts: vi.fn(() => Promise.resolve({ data: [] })),
    getShiftCoverage: vi.fn(() => Promise.resolve({ data: [] })),
    createShiftCoverage: vi.fn(() => Promise.resolve({ data: {} })),
    updateShiftCoverage: vi.fn(() => Promise.resolve({ data: {} })),
    deleteShiftCoverage: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('@/services/api', () => ({ default: mockApi }))
import { useShiftCoverageGrid, SHORTFALL_THRESHOLD } from '../useShiftCoverageGrid'
import { useAuthStore } from '@/stores/authStore'

const row = (over: Record<string, unknown> = {}) => ({
  coverage_id: 1,
  client_id: 'C1',
  shift_id: 3,
  coverage_date: '2026-06-11',
  required_employees: 8,
  actual_employees: 6,
  coverage_percentage: 75,
  notes: null,
  ...over,
})

const asRole = (role: string) => {
  const auth = useAuthStore()
  auth.user = { role } as never
}

// authStore reads localStorage in its state initialiser, and it is not on
// `global` under this environment -- authStore.spec.ts stubs it the same way.
beforeEach(() => {
  Object.defineProperty(global, 'localStorage', {
    value: { getItem: vi.fn(() => null), setItem: vi.fn(), removeItem: vi.fn(), clear: vi.fn() },
    writable: true,
    configurable: true,
  })
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('the write tier splits, and the UI must split with it', () => {
  it('lets an operator edit but never offers them a delete', () => {
    // backend/routes/coverage.py: PUT is get_current_contributor, DELETE is
    // get_current_active_supervisor. An operator clears the first and not the
    // second, so one flag for both either hides a legal edit or offers a
    // delete the server answers with 403.
    asRole('operator')
    const c = useShiftCoverageGrid()
    expect(c.canEdit.value).toBe(true)
    expect(c.canDelete.value).toBe(false)
  })

  it('gives a supervisor both', () => {
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    expect(c.canEdit.value).toBe(true)
    expect(c.canDelete.value).toBe(true)
  })

  it('gives a viewer neither', () => {
    asRole('viewer')
    const c = useShiftCoverageGrid()
    expect(c.canEdit.value).toBe(false)
    expect(c.canDelete.value).toBe(false)
  })
})

describe('the derived percentage is never editable', () => {
  it('leaves coverage_percentage read-only even for a supervisor', () => {
    // The server recomputes it from required/actual on every write and clamps
    // it to the column ceiling. An editable column here accepts a number the
    // very next read replaces, which reads to the operator as the app losing
    // their input.
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    const pct = c.columnSpecs.value.find((d) => d.field === 'coverage_percentage')
    expect(pct?.editable).toBe(false)
  })

  it('does make required and actual editable for a contributor', () => {
    // Two-sided: the read-only rule must not have been achieved by making the
    // whole grid read-only.
    asRole('operator')
    const c = useShiftCoverageGrid()
    const req = c.columnSpecs.value.find((d) => d.field === 'required_employees')
    const act = c.columnSpecs.value.find((d) => d.field === 'actual_employees')
    expect(req?.editable).toBe(true)
    expect(act?.editable).toBe(true)
  })

  it('makes them non-editable for a viewer', () => {
    asRole('viewer')
    const c = useShiftCoverageGrid()
    const req = c.columnSpecs.value.find((d) => d.field === 'required_employees')
    expect(req?.editable).toBe(false)
  })
})

describe('updates send only what the API accepts', () => {
  it('never sends client_id, shift_id or coverage_date', async () => {
    // ShiftCoverageUpdate exposes required_employees, actual_employees and
    // notes and nothing else -- that is what stops an edit from moving a row
    // to another tenant and routing around the create-time ownership check.
    // Sending more would either 422 or, worse, quietly appear to work.
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'

    await c.update(row() as never, { actual_employees: 4 } as never)

    expect(mockApi.updateShiftCoverage).toHaveBeenCalledTimes(1)
    const [id, payload] = mockApi.updateShiftCoverage.mock.calls[0]
    expect(id).toBe(1)
    expect(Object.keys(payload as object).sort()).toEqual([
      'actual_employees',
      'notes',
      'required_employees',
    ])
  })
})

describe('a committed write with a failed refresh is not a failed write', () => {
  it('reports success and raises the stale banner', async () => {
    // Telling the operator the write failed sends them back to re-enter a
    // record that already exists, which the server then refuses as a
    // duplicate. The row IS saved; only the list is behind.
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'
    mockApi.getShiftCoverage.mockRejectedValueOnce(new Error('read failed'))

    const ok = await c.create({ shift_id: 3, coverage_date: '2026-06-11', required_employees: 8, actual_employees: 6 } as never)

    expect(ok).toBe(true)
    expect(c.staleAfterWrite.value).toBe(true)
  })

  it('clears the banner once a read succeeds again', async () => {
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'
    c.staleAfterWrite.value = true

    mockApi.getShiftCoverage.mockResolvedValueOnce({ data: [row()] })
    await c.load()

    expect(c.staleAfterWrite.value).toBe(false)
  })
})

describe('a slower read cannot overwrite a newer one', () => {
  it('discards a superseded response', async () => {
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'

    let releaseFirst: (_v: unknown) => void = () => {}
    mockApi.getShiftCoverage
      .mockImplementationOnce(() => new Promise((res) => { releaseFirst = res }))
      .mockImplementationOnce(() => Promise.resolve({ data: [row({ coverage_id: 99 })] }))

    const first = c.load()
    const second = c.load()
    await second
    releaseFirst({ data: [row({ coverage_id: 11 })] })
    await first

    expect(c.rows.value.map((r) => r.coverage_id)).toEqual([99])
  })

  it('clearing the client supersedes a read already in flight', async () => {
    // Without bumping the token on the empty path, the outstanding request
    // still matches and repopulates the table for a client nobody selected.
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'

    let release: (_v: unknown) => void = () => {}
    mockApi.getShiftCoverage.mockImplementationOnce(
      () => new Promise((res) => { release = res }),
    )

    const inflight = c.load()
    c.selectedClient.value = null
    await c.load()
    release({ data: [row()] })
    await inflight

    expect(c.rows.value).toEqual([])
  })
})

describe('errors say something a person can act on', () => {
  it('turns a 409 into the duplicate message', async () => {
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'
    mockApi.createShiftCoverage.mockRejectedValueOnce({ response: { status: 409, data: {} } })

    const ok = await c.create({ shift_id: 3, coverage_date: '2026-06-11', required_employees: 8, actual_employees: 6 } as never)

    expect(ok).toBe(false)
    expect(c.error.value?.key).toBe('coverage.errors.duplicate')
  })

  it('prefers the server detail when there is one', async () => {
    // The backend names WHICH record holds the slot; that is more useful than
    // anything the client can compose.
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'
    mockApi.deleteShiftCoverage.mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'Coverage for shift 3 on 2026-06-11 already exists' } },
    })

    await c.remove(row() as never)

    expect(c.error.value?.detail).toContain('already exists')
  })
})

describe('a rejected edit does not leave the grid showing it', () => {
  it('re-reads after a failed update, not only after a successful one', async () => {
    // This runs from an inline grid edit, and AG Grid has already written the
    // new value into its row model before the request goes out. Without the
    // re-read the cell keeps showing a number the server refused, beside an
    // error message saying it was refused.
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'
    mockApi.updateShiftCoverage.mockRejectedValueOnce({ response: { status: 409, data: {} } })
    mockApi.getShiftCoverage.mockResolvedValueOnce({ data: [row({ actual_employees: 6 })] })

    const ok = await c.update(row() as never, { actual_employees: 999 } as never)

    expect(ok).toBe(false)
    expect(mockApi.getShiftCoverage).toHaveBeenCalled()
    expect(c.rows.value[0].actual_employees).toBe(6)
  })

  it('does not bury a reload failure under the write failure', async () => {
    // If the revert's own re-read also fails it has already emptied the grid
    // and reported why. Overwriting that with the rejected-edit message leaves
    // an empty, stale table explained by the wrong error.
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'
    mockApi.updateShiftCoverage.mockRejectedValueOnce({ response: { status: 409, data: {} } })
    mockApi.getShiftCoverage.mockRejectedValueOnce({ response: { status: 500, data: {} } })

    await c.update(row() as never, { actual_employees: 999 } as never)

    expect(c.staleAfterWrite.value).toBe(true)
    expect(c.error.value?.key).toBe('coverage.errors.generic')
  })

  it('still says WHY, after the revert', async () => {
    // The revert re-reads, and load() clears `error` on entry. Setting the
    // failure before the refresh loses it, so the value snaps back with
    // nothing on screen explaining it -- which reads as the app discarding
    // the edit for no reason.
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'
    mockApi.updateShiftCoverage.mockRejectedValueOnce({ response: { status: 409, data: {} } })
    mockApi.getShiftCoverage.mockResolvedValueOnce({ data: [row()] })

    await c.update(row() as never, { actual_employees: 999 } as never)

    expect(c.error.value?.key).toBe('coverage.errors.duplicate')
  })
})

describe('the default range is the local calendar date', () => {
  // Pinned to a moment where the local and UTC dates genuinely differ.
  // Comparing against `new Date()` proves nothing: for most of the day, and
  // ALWAYS in CI (which runs UTC), the two agree, so the assertion holds
  // whichever implementation is used. It has to be a fixed instant chosen so
  // the two disagree, or it is not a gate.
  const LOCAL_MIDNIGHT_ISH = new Date(2026, 5, 11, 0, 30) // local 2026-06-11 00:30
  const LATE_EVENING = new Date(2026, 5, 11, 23, 30) // local 2026-06-11 23:30

  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('reports the local date, whichever side of UTC the runner sits on', () => {
    for (const instant of [LOCAL_MIDNIGHT_ISH, LATE_EVENING]) {
      vi.setSystemTime(instant)
      asRole('supervisor')
      const c = useShiftCoverageGrid()
      expect(c.endDate.value).toBe('2026-06-11')
    }
  })

  it('never derives a calendar date through toISOString', () => {
    // A SOURCE gate, because the behavioural one above cannot fail in CI: it
    // runs UTC, where the local and UTC dates are always equal, so both
    // implementations satisfy it. Setting process.env.TZ to force the
    // difference is not an option either -- it is process-wide and leaks into
    // every other spec sharing the worker, which was measured doing exactly
    // that. Reading the source is the only check that holds in any zone.
    const src = readFileSync(resolve(__dirname, '../useShiftCoverageGrid.ts'), 'utf8')
    expect(src).not.toMatch(/toISOString\(\)\.slice/)
  })

  it('the range start is the local date N days back', () => {
    vi.setSystemTime(LATE_EVENING)
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.applyRange(30)
    expect(c.endDate.value).toBe('2026-06-11')
    expect(c.startDate.value).toBe('2026-05-12')
  })
})

describe('the row is filed under the client the form was opened for', () => {
  it('uses the pinned client, not whatever is selected when the POST fires', async () => {
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'

    // The operator opened the dialog against C1; the selection moved to C2
    // before the request went out.
    c.selectedClient.value = 'C2'
    await c.create(
      { shift_id: 3, coverage_date: '2026-06-11', required_employees: 8, actual_employees: 6 } as never,
      'C1',
    )

    expect(mockApi.createShiftCoverage.mock.calls[0][0]).toMatchObject({ client_id: 'C1' })
  })
})

describe('only the selected client\'s shifts are offered', () => {
  it('excludes another tenant\'s shifts', async () => {
    // getShifts() returns everything the caller can see; for an admin that is
    // every client. A shift belonging to another tenant produces a row the
    // server refuses with 400, so offering it is the same "action that fails"
    // defect the screen exists to remove.
    asRole('admin')
    const c = useShiftCoverageGrid()
    mockApi.getShifts.mockResolvedValueOnce({
      data: [
        { shift_id: 1, client_id: 'C1', shift_name: 'C1 Day' },
        { shift_id: 2, client_id: 'C2', shift_name: 'C2 Day' },
      ],
    })
    await c.loadShifts()
    c.selectedClient.value = 'C1'

    expect(c.shiftsForClient.value.map((s) => s.shift_id)).toEqual([1])
  })

  it('the dialog lists shifts for the client it was PINNED to', async () => {
    // The add dialog pins the client it was opened for so the row cannot be
    // filed under another tenant. The shift list has to be pinned with it --
    // otherwise the operator picks from client B's shifts while the row is
    // written for client A, and the server refuses it as cross-tenant.
    asRole('admin')
    const c = useShiftCoverageGrid()
    mockApi.getShifts.mockResolvedValueOnce({
      data: [
        { shift_id: 1, client_id: 'C1', shift_name: 'C1 Day' },
        { shift_id: 2, client_id: 'C2', shift_name: 'C2 Day' },
      ],
    })
    await c.loadShifts()
    c.selectedClient.value = 'C2'

    expect(c.shiftsFor('C1').map((s) => s.shift_id)).toEqual([1])
  })

  it('points the list at the client the row was written for', async () => {
    // Otherwise the record is filed correctly and is then invisible, because
    // the post-write refresh reads whatever client is selected.
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C2'

    await c.create(
      { shift_id: 3, coverage_date: '2026-06-11', required_employees: 8, actual_employees: 6 } as never,
      'C1',
    )

    expect(c.selectedClient.value).toBe('C1')
    expect(mockApi.getShiftCoverage).toHaveBeenCalledWith(
      expect.objectContaining({ client_id: 'C1' }),
    )
  })

  it('does NOT move the operator when the create fails', async () => {
    // Re-pointing before the POST would leave them looking at another
    // client's rows beside an error about a row they tried to add to theirs.
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C2'
    mockApi.createShiftCoverage.mockRejectedValueOnce({ response: { status: 409, data: {} } })

    const ok = await c.create(
      { shift_id: 3, coverage_date: '2026-06-11', required_employees: 8, actual_employees: 6 } as never,
      'C1',
    )

    expect(ok).toBe(false)
    expect(c.selectedClient.value).toBe('C2')
  })

  it('offers nothing until a client is chosen', async () => {
    asRole('admin')
    const c = useShiftCoverageGrid()
    mockApi.getShifts.mockResolvedValueOnce({
      data: [{ shift_id: 1, client_id: 'C1', shift_name: 'C1 Day' }],
    })
    await c.loadShifts()

    expect(c.shiftsForClient.value).toEqual([])
  })
})

describe('the summary reflects the data', () => {
  it('counts shifts that ran below the shortfall threshold', async () => {
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    c.selectedClient.value = 'C1'
    mockApi.getShiftCoverage.mockResolvedValueOnce({
      data: [
        row({ coverage_id: 1, coverage_percentage: 100 }),
        row({ coverage_id: 2, coverage_percentage: SHORTFALL_THRESHOLD - 0.1 }),
        row({ coverage_id: 3, coverage_percentage: 62.5 }),
      ],
    })
    await c.load()

    expect(c.shortfalls.value.map((r) => r.coverage_id)).toEqual([2, 3])
    expect(c.averageCoverage.value).toBeCloseTo(84.1, 1)
  })

  it('reports no average when there is nothing loaded', () => {
    asRole('supervisor')
    const c = useShiftCoverageGrid()
    expect(c.averageCoverage.value).toBeNull()
  })
})
