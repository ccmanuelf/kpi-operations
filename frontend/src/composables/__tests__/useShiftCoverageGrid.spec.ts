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
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

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
