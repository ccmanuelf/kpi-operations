/**
 * Gates for shift master-data admin.
 *
 * Three things here are the point, not incidental:
 *
 *  1. Writes must invalidate the cached shift reference data. `reference.ts`
 *     serves the shift dropdown on every data-entry grid from a 30-minute TTL
 *     cache, so a shift created here would otherwise be invisible where
 *     operators need it until the cache aged out.
 *  2. POST /shifts/check-overlap must run BEFORE the create. The endpoint was
 *     built for exactly this and never called; overlaps are permitted by the
 *     backend, so the user is asked rather than blocked, and answering "no"
 *     must actually cancel the save.
 *  3. Times must be normalised to HH:MM:SS. A plain text editor will happily
 *     send "25:00" or "half six" to Pydantic.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

const { mockShifts, mockReference } = vi.hoisted(() => ({
  mockShifts: {
    listShifts: vi.fn(() => Promise.resolve({ data: [] })),
    createShift: vi.fn(() => Promise.resolve({ data: { data: {}, warnings: [] } })),
    updateShift: vi.fn(() => Promise.resolve({ data: { data: {}, warnings: [] } })),
    deleteShift: vi.fn(() => Promise.resolve({ data: {} })),
    checkShiftOverlap: vi.fn(() =>
      Promise.resolve({ data: { has_overlaps: false, overlaps: [] } }),
    ),
  },
  mockReference: { invalidateReferenceType: vi.fn() },
}))

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (k: string) => k }) }))
vi.mock('@/services/api/shifts', () => mockShifts)
vi.mock('@/services/api/reference', () => mockReference)
vi.mock('@/services/api', () => ({
  default: { getClients: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import useShiftAdminGridData, { normalizeTime } from '../useShiftAdminGridData'
import { useShiftAdmin, type ShiftRow } from '../useShiftAdmin'

const notify = {
  showSuccess: vi.fn(),
  showError: vi.fn(),
  showWarning: vi.fn(),
}

const makeGrid = (confirmOverlap = vi.fn(() => Promise.resolve(true))) => {
  const shifts = ref<ShiftRow[]>([])
  const grid = useShiftAdminGridData({
    selectedClient: ref('DEMO-PIECE'),
    shifts,
    loadShifts: vi.fn(() => Promise.resolve()),
    notify,
    onConfirmDelete: vi.fn(),
    confirmOverlap,
    showAllClients: ref(false),
  })
  return { grid, shifts, confirmOverlap }
}

const validRow = (): ShiftRow => ({
  _isNew: true,
  shift_name: 'First',
  start_time: '06:00',
  end_time: '14:00',
})

beforeEach(() => {
  vi.clearAllMocks()
  mockShifts.checkShiftOverlap.mockResolvedValue({
    data: { has_overlaps: false, overlaps: [] },
  })
  mockShifts.createShift.mockResolvedValue({ data: { data: {}, warnings: [] } })
  mockShifts.updateShift.mockResolvedValue({ data: { data: {}, warnings: [] } })
})

describe('normalizeTime', () => {
  it.each([
    ['06:00', '06:00:00'],
    ['6:00', '06:00:00'],
    ['06:00:00', '06:00:00'],
    ['23:59:59', '23:59:59'],
    ['00:00', '00:00:00'],
  ])('normalises %s to %s', (input, expected) => {
    expect(normalizeTime(input)).toBe(expected)
  })

  it.each(['25:00', '06:60', '06:00:60', 'half six', '', '0600', '6', null, 14])(
    'rejects %s rather than passing it to the API',
    (input) => {
      expect(normalizeTime(input)).toBeNull()
    },
  )
})

describe('overlap pre-check', () => {
  it('checks for overlaps before creating, not after', async () => {
    const { grid } = makeGrid()
    await grid.saveNewRow(validRow())

    expect(mockShifts.checkShiftOverlap).toHaveBeenCalledWith({
      client_id: 'DEMO-PIECE',
      start_time: '06:00:00',
      end_time: '14:00:00',
    })
    const checkOrder = mockShifts.checkShiftOverlap.mock.invocationCallOrder[0]
    const createOrder = mockShifts.createShift.mock.invocationCallOrder[0]
    expect(checkOrder).toBeLessThan(createOrder)
  })

  it('asks the user when there are overlaps, and cancelling does NOT create', async () => {
    mockShifts.checkShiftOverlap.mockResolvedValue({
      data: {
        has_overlaps: true,
        overlaps: [
          { shift_id: 1, shift_name: 'Night', start_time: '22:00:00', end_time: '06:30:00' },
        ],
      },
    })
    const decline = vi.fn(() => Promise.resolve(false))
    const { grid } = makeGrid(decline)

    await grid.saveNewRow(validRow())

    expect(decline).toHaveBeenCalledWith([
      { shift_id: 1, shift_name: 'Night', start_time: '22:00:00', end_time: '06:30:00' },
    ])
    expect(mockShifts.createShift).not.toHaveBeenCalled()
  })

  it('creates anyway when the user accepts — the backend permits overlaps', async () => {
    mockShifts.checkShiftOverlap.mockResolvedValue({
      data: { has_overlaps: true, overlaps: [] },
    })
    const { grid } = makeGrid(vi.fn(() => Promise.resolve(true)))
    await grid.saveNewRow(validRow())
    expect(mockShifts.createShift).toHaveBeenCalled()
  })
})

describe('soft-validation warnings', () => {
  it('surfaces the warnings the create response carries instead of dropping them', async () => {
    mockShifts.createShift.mockResolvedValue({
      data: { data: {}, warnings: ['Overlaps with Night (22:00-06:30)'] },
    })
    const { grid } = makeGrid()
    await grid.saveNewRow(validRow())
    expect(notify.showWarning).toHaveBeenCalledWith('Overlaps with Night (22:00-06:30)')
  })

  it('surfaces update warnings too', async () => {
    mockShifts.updateShift.mockResolvedValue({
      data: { data: {}, warnings: ['Overlaps with Second'] },
    })
    const { grid } = makeGrid()
    await grid.onCellValueChanged({
      data: { shift_id: 3, shift_name: 'First', start_time: '06:00', end_time: '14:00' },
    })
    expect(notify.showWarning).toHaveBeenCalledWith('Overlaps with Second')
  })
})

describe('reference-cache invalidation', () => {
  it('invalidates cached shifts after a create, or every dropdown stays stale', async () => {
    const { grid } = makeGrid()
    await grid.saveNewRow(validRow())
    expect(mockReference.invalidateReferenceType).toHaveBeenCalledWith('shifts')
  })

  it('invalidates cached shifts after an update', async () => {
    const { grid } = makeGrid()
    await grid.onCellValueChanged({
      data: { shift_id: 3, shift_name: 'First', start_time: '06:00', end_time: '14:00' },
    })
    expect(mockReference.invalidateReferenceType).toHaveBeenCalledWith('shifts')
  })

  it('invalidates cached shifts after a delete', async () => {
    const admin = useShiftAdmin()
    await admin.removeShift(3)
    expect(mockShifts.deleteShift).toHaveBeenCalledWith(3)
    expect(mockReference.invalidateReferenceType).toHaveBeenCalledWith('shifts')
  })
})

describe('write guards', () => {
  it('refuses to create a row with an unparseable time', async () => {
    const { grid } = makeGrid()
    await grid.saveNewRow({ _isNew: true, shift_name: 'X', start_time: '25:00', end_time: '14:00' })
    expect(mockShifts.checkShiftOverlap).not.toHaveBeenCalled()
    expect(mockShifts.createShift).not.toHaveBeenCalled()
    expect(notify.showError).toHaveBeenCalled()
  })

  it('never autosaves a new row', async () => {
    const { grid } = makeGrid()
    await grid.onCellValueChanged({ data: { _isNew: true, shift_name: 'X' } })
    expect(mockShifts.updateShift).not.toHaveBeenCalled()
  })
})

// Found by the adversarial cross-model review of this branch.
describe('concurrent-edit safety', () => {
  it('ignores a second Save while the first is still in flight', async () => {
    const { grid } = makeGrid()
    await grid.saveNewRow({ ...validRow(), _isSaving: true })
    expect(mockShifts.checkShiftOverlap).not.toHaveBeenCalled()
    expect(mockShifts.createShift).not.toHaveBeenCalled()
  })

  it('ignores a cell change while that row is already saving', async () => {
    const { grid } = makeGrid()
    await grid.onCellValueChanged({
      data: { shift_id: 1, shift_name: 'A', start_time: '06:00', end_time: '14:00', _isSaving: true },
    })
    expect(mockShifts.updateShift).not.toHaveBeenCalled()
  })

  it('refuses to PUT an emptied shift_name — the column is min_length=1', async () => {
    const { grid } = makeGrid()
    await grid.onCellValueChanged({
      data: { shift_id: 1, shift_name: '', start_time: '06:00', end_time: '14:00' },
    })
    expect(mockShifts.updateShift).not.toHaveBeenCalled()
    expect(notify.showError).toHaveBeenCalled()
  })
})

describe('unsaved drafts survive the reload a write triggers', () => {
  it('keeps other draft rows when the server list is re-read', async () => {
    mockShifts.listShifts.mockResolvedValue({ data: [{ shift_id: 1, shift_name: 'SAVED' }] })
    const admin = useShiftAdmin()
    // addRow always stamps the draft with the selected client, so a realistic
    // draft carries one; the scoping filter below relies on it.
    admin.selectedClient.value = 'DEMO-PIECE'
    admin.shifts.value = [
      { _isNew: true, shift_name: 'STILL_TYPING', client_id: 'DEMO-PIECE' },
    ]

    await admin.loadShifts()

    expect(admin.shifts.value.map((r) => r.shift_name)).toEqual(['STILL_TYPING', 'SAVED'])
  })

  // Found by the adversarial review: the draft-preservation fix above kept
  // EVERY draft, so one started under client A survived a switch to client B
  // and would then be saved against B.
  it('does not carry a draft across a client switch', async () => {
    mockShifts.listShifts.mockResolvedValue({ data: [] })
    const admin = useShiftAdmin()
    admin.selectedClient.value = 'CLIENT-A'
    admin.shifts.value = [{ _isNew: true, shift_name: 'FOR-A', client_id: 'CLIENT-A' }]

    admin.selectedClient.value = 'CLIENT-B'
    await admin.loadShifts()

    expect(admin.shifts.value).toEqual([])
  })

  it('keeps a draft that belongs to the client still selected', async () => {
    mockShifts.listShifts.mockResolvedValue({ data: [] })
    const admin = useShiftAdmin()
    admin.selectedClient.value = 'CLIENT-A'
    admin.shifts.value = [{ _isNew: true, shift_name: 'FOR-A', client_id: 'CLIENT-A' }]

    await admin.loadShifts()

    expect(admin.shifts.value.map((r) => r.shift_name)).toEqual(['FOR-A'])
  })

  it('drops the just-saved draft so it is not duplicated by its server copy', async () => {
    const { grid, shifts } = makeGrid()
    const row = validRow()
    shifts.value = [row]
    await grid.saveNewRow(row)
    expect(shifts.value).not.toContain(row)
  })
})

describe('useShiftAdmin.noShiftsConfigured', () => {
  it('is false after a FAILED read — the onboarding step reports on this state', async () => {
    mockShifts.listShifts.mockRejectedValue(new Error('network down'))
    const admin = useShiftAdmin()
    await expect(admin.loadShifts()).rejects.toThrow('network down')
    expect(admin.noShiftsConfigured.value).toBe(false)
  })

  it('is true once a successful read returns nothing', async () => {
    mockShifts.listShifts.mockResolvedValue({ data: [] })
    const admin = useShiftAdmin()
    await admin.loadShifts()
    expect(admin.noShiftsConfigured.value).toBe(true)
  })
})

describe('reactivating a deactivated shift', () => {
  it('asks the server for inactive rows when the toggle is on', async () => {
    mockShifts.listShifts.mockResolvedValue({ data: [] })
    const admin = useShiftAdmin()
    admin.selectedClient.value = 'DEMO-PIECE'

    await admin.loadShifts()
    expect(mockShifts.listShifts).toHaveBeenLastCalledWith('DEMO-PIECE', false)

    // Without this, DELETE (a soft delete) hides the row for good and the
    // editable is_active column is a one-way switch that looks reversible.
    admin.includeInactive.value = true
    await admin.loadShifts()
    expect(mockShifts.listShifts).toHaveBeenLastCalledWith('DEMO-PIECE', true)
  })
})
