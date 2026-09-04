/**
 * Unit tests for the hold-catalog admin composables.
 *
 * The gates here exist because the catalogs are load-bearing: `routes/holds.py`
 * rejects any status or reason that is not ACTIVE in the client's catalog, so
 * an unseeded tenant cannot record a hold at all. Two invariants protect that:
 *
 *  1. `catalogIsEmpty` must be false when the read FAILED — a network error is
 *     not evidence of an empty catalog, and the empty state offers "Seed
 *     Defaults" as the diagnosis.
 *  2. Columns are editable only where the API can honour the edit. POST has no
 *     `is_active`, and no endpoint can rename a code.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

const { mockService } = vi.hoisted(() => ({
  mockService: {
    listHoldStatuses: vi.fn(),
    listHoldReasons: vi.fn(),
    createHoldStatus: vi.fn(),
    createHoldReason: vi.fn(),
    updateHoldStatus: vi.fn(),
    updateHoldReason: vi.fn(),
    deleteHoldStatus: vi.fn(),
    deleteHoldReason: vi.fn(),
    seedHoldCatalogDefaults: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))
vi.mock('@/services/api/holdCatalogs', () => mockService)
vi.mock('@/services/api', () => ({ default: { getClients: vi.fn(() => Promise.resolve({ data: [] })) } }))

import useHoldCatalogGridData, { codeField } from '../useHoldCatalogGridData'
import { useHoldCatalogAdmin, type HoldCatalogRow } from '../useHoldCatalogAdmin'

interface ColumnDefShape {
  field?: string
  editable?: boolean | ((_params: { data: HoldCatalogRow }) => boolean)
  cellEditor?: string
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

const notify = { showSuccess: vi.fn(), showError: vi.fn() }

const makeGrid = (kind: 'status' | 'reason', rows: HoldCatalogRow[] = []) => {
  const rowsRef = ref<HoldCatalogRow[]>(rows)
  const grid = useHoldCatalogGridData({
    kind,
    selectedClient: ref('DEMO-PIECE'),
    rows: rowsRef,
    loadCatalogs: vi.fn(() => Promise.resolve()),
    notify,
    onConfirmDelete: vi.fn(),
  })
  return { grid, rowsRef }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('codeField', () => {
  it('maps each catalog kind to the field name its API actually uses', () => {
    expect(codeField('status')).toBe('status_code')
    expect(codeField('reason')).toBe('reason_code')
  })
})

describe('useHoldCatalogGridData column editability', () => {
  it.each(['status', 'reason'] as const)(
    'makes the %s code editable on new rows only — no endpoint can rename one',
    (kind) => {
      const { grid } = makeGrid(kind)
      const col = findCol(grid.columnDefs.value, codeField(kind))
      expect(typeof col?.editable).toBe('function')
      const editable = col!.editable as (_p: { data: HoldCatalogRow }) => boolean
      expect(editable({ data: { _isNew: true } })).toBe(true)
      expect(editable({ data: { catalog_id: 1 } })).toBe(false)
    },
  )

  it('makes is_active editable on existing rows only — POST cannot set it', () => {
    const { grid } = makeGrid('status')
    const col = findCol(grid.columnDefs.value, 'is_active')
    const editable = col!.editable as (_p: { data: HoldCatalogRow }) => boolean
    expect(editable({ data: { _isNew: true } })).toBe(false)
    expect(editable({ data: { catalog_id: 1 } })).toBe(true)
  })

  it('never offers is_default for editing — it marks system-seeded rows', () => {
    const { grid } = makeGrid('reason')
    expect(findCol(grid.columnDefs.value, 'is_default')?.editable).toBe(false)
  })
})

describe('useHoldCatalogGridData writes', () => {
  it('posts the kind-correct code field when saving a new row', async () => {
    mockService.createHoldReason.mockResolvedValue({ data: {} })
    const { grid } = makeGrid('reason')
    await grid.saveNewRow({
      _isNew: true,
      reason_code: 'TOOLING',
      display_name: 'Tooling',
      sort_order: 3,
    })
    expect(mockService.createHoldReason).toHaveBeenCalledWith({
      client_id: 'DEMO-PIECE',
      reason_code: 'TOOLING',
      display_name: 'Tooling',
      sort_order: 3,
    })
    expect(mockService.createHoldStatus).not.toHaveBeenCalled()
  })

  it('refuses to save a new row with no code or no display name', async () => {
    const { grid } = makeGrid('status')
    await grid.saveNewRow({ _isNew: true, status_code: '', display_name: 'Named' })
    await grid.saveNewRow({ _isNew: true, status_code: 'CODE', display_name: '' })
    expect(mockService.createHoldStatus).not.toHaveBeenCalled()
    expect(notify.showError).toHaveBeenCalledTimes(2)
  })

  it('autosaves an existing row but never a new one', async () => {
    mockService.updateHoldStatus.mockResolvedValue({ data: {} })
    const { grid } = makeGrid('status')

    await grid.onCellValueChanged({ data: { _isNew: true, status_code: 'X' } })
    expect(mockService.updateHoldStatus).not.toHaveBeenCalled()

    await grid.onCellValueChanged({
      data: { catalog_id: 7, display_name: 'On Hold', is_active: true, sort_order: 2 },
    })
    expect(mockService.updateHoldStatus).toHaveBeenCalledWith(7, {
      display_name: 'On Hold',
      is_active: true,
      sort_order: 2,
    })
  })
})

describe('useHoldCatalogAdmin.catalogIsEmpty', () => {
  it('is false after a FAILED read — a blank screen is not proof of an empty catalog', async () => {
    mockService.listHoldStatuses.mockRejectedValue(new Error('network down'))
    mockService.listHoldReasons.mockRejectedValue(new Error('network down'))
    const admin = useHoldCatalogAdmin()
    admin.selectedClient.value = 'DEMO-PIECE'

    await expect(admin.loadCatalogs()).rejects.toThrow('network down')

    expect(admin.statuses.value).toEqual([])
    expect(admin.reasons.value).toEqual([])
    expect(admin.catalogIsEmpty.value).toBe(false)
  })

  it('is true only once a successful read returns nothing', async () => {
    mockService.listHoldStatuses.mockResolvedValue({ data: [] })
    mockService.listHoldReasons.mockResolvedValue({ data: [] })
    const admin = useHoldCatalogAdmin()
    admin.selectedClient.value = 'DEMO-PIECE'

    expect(admin.catalogIsEmpty.value).toBe(false)
    await admin.loadCatalogs()
    expect(admin.catalogIsEmpty.value).toBe(true)
  })

  it('is false when the client has a catalog', async () => {
    mockService.listHoldStatuses.mockResolvedValue({ data: [{ catalog_id: 1 }] })
    mockService.listHoldReasons.mockResolvedValue({ data: [] })
    const admin = useHoldCatalogAdmin()
    admin.selectedClient.value = 'DEMO-PIECE'
    await admin.loadCatalogs()
    expect(admin.catalogIsEmpty.value).toBe(false)
  })
})

describe('useHoldCatalogAdmin.seedDefaults', () => {
  it('seeds and re-reads, so the empty state clears without a manual refresh', async () => {
    mockService.seedHoldCatalogDefaults.mockResolvedValue({
      data: { statuses_created: 7, reasons_created: 11, skipped: 0 },
    })
    mockService.listHoldStatuses.mockResolvedValue({ data: [{ catalog_id: 1 }] })
    mockService.listHoldReasons.mockResolvedValue({ data: [{ catalog_id: 2 }] })

    const admin = useHoldCatalogAdmin()
    admin.selectedClient.value = 'DEMO-PIECE'
    const result = await admin.seedDefaults()

    expect(mockService.seedHoldCatalogDefaults).toHaveBeenCalledWith('DEMO-PIECE')
    expect(result).toEqual({ statuses_created: 7, reasons_created: 11, skipped: 0 })
    expect(admin.catalogIsEmpty.value).toBe(false)
  })

  it('does nothing without a selected client', async () => {
    const admin = useHoldCatalogAdmin()
    expect(await admin.seedDefaults()).toBeNull()
    expect(mockService.seedHoldCatalogDefaults).not.toHaveBeenCalled()
  })
})
