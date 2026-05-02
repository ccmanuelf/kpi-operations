/**
 * @vitest-environment happy-dom
 *
 * Unit tests for useFloatingPoolGridData composable —
 * Group H Surface #21 (FloatingPoolManagement).
 *
 * Verifies: column shape, status valueGetter ASSIGNED/AVAILABLE,
 * assignedTo cell-editor wired to client list, onCellValueChanged
 * routing rules (assignment set → /assign, cleared → /unassign,
 * date/notes change while assigned → re-fire /assign, date/notes
 * change while unassigned → no-op), unassignRow API call, error
 * fallback refreshes data.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    post: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/services/api', () => ({ default: mockApi }))

import useFloatingPoolGridData, {
  type FloatingPoolGridRow,
  type ClientOption,
} from '../useFloatingPoolGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean | ((params: { data: FloatingPoolGridRow }) => boolean)
  cellEditor?: string
  cellEditorParams?: { values?: unknown[]; formatValue?: (v: unknown) => string }
  valueGetter?: (params: { data: FloatingPoolGridRow }) => unknown
  valueFormatter?: (params: { value?: unknown; data?: FloatingPoolGridRow }) => string
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

const buildHarness = () => {
  const entries = ref<FloatingPoolGridRow[]>([])
  const clientOptions = ref<ClientOption[]>([
    { client_id: 'CLIENT001', name: 'Client One' },
    { client_id: 'CLIENT002', name: 'Client Two' },
  ])
  const fetchData = vi.fn().mockResolvedValue(undefined)
  const notify = { showSuccess: vi.fn(), showError: vi.fn() }
  const grid = useFloatingPoolGridData({
    entries,
    clientOptions,
    fetchData,
    notify,
  })
  return { ...grid, entries, clientOptions, fetchData, notify }
}

beforeEach(() => {
  mockApi.post.mockReset()
  mockApi.post.mockResolvedValue({ data: {} })
})

describe('column definitions', () => {
  it('employee_id and employee_name are read-only and pinned left', () => {
    const { columnDefs } = buildHarness()
    const id = findCol(columnDefs.value, 'employee_id')!
    const name = findCol(columnDefs.value, 'employee_name')!
    expect(id.editable).toBe(false)
    expect(id.pinned).toBe('left')
    expect(name.editable).toBe(false)
    expect(name.pinned).toBe('left')
  })

  it('status valueGetter returns ASSIGNED when current_assignment is set', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, '_status')!
    expect(
      col.valueGetter!({ data: { current_assignment: 'CLIENT001' } as FloatingPoolGridRow }),
    ).toBe('ASSIGNED')
    expect(
      col.valueGetter!({ data: { current_assignment: null } as FloatingPoolGridRow }),
    ).toBe('AVAILABLE')
  })

  it('current_assignment uses agSelectCellEditor including a null option', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'current_assignment')!
    expect(col.cellEditor).toBe('agSelectCellEditor')
    const values = col.cellEditorParams!.values!
    expect(values[0]).toBeNull()
    expect(values).toContain('CLIENT001')
    expect(values).toContain('CLIENT002')
  })

  it('current_assignment formatValue resolves client name', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'current_assignment')!
    const fv = col.cellEditorParams!.formatValue!
    expect(fv('CLIENT001')).toBe('Client One')
    expect(fv('CLIENT999')).toBe('CLIENT999')
    expect(fv(null)).toBe('admin.floatingPool.notAssigned')
  })

  it('current_assignment valueFormatter renders display label', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'current_assignment')!
    expect(col.valueFormatter!({ value: 'CLIENT002' })).toBe('Client Two')
    expect(col.valueFormatter!({ value: null })).toBe('admin.floatingPool.notAssigned')
  })

  it('available_from / available_to use date string editors', () => {
    const { columnDefs } = buildHarness()
    expect(findCol(columnDefs.value, 'available_from')!.cellEditor).toBe(
      'agDateStringCellEditor',
    )
    expect(findCol(columnDefs.value, 'available_to')!.cellEditor).toBe(
      'agDateStringCellEditor',
    )
  })

  it('notes uses popup large-text editor', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'notes') as
      | { cellEditor?: string; cellEditorPopup?: boolean }
      | undefined
    expect(col!.cellEditor).toBe('agLargeTextCellEditor')
    expect(col!.cellEditorPopup).toBe(true)
  })

  it('actions column is pinned right and non-editable', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, '_actions')!
    expect(col.pinned).toBe('right')
    expect(col.editable).toBe(false)
  })
})

describe('onCellValueChanged — current_assignment', () => {
  it('sends /assign when current_assignment changes from null to a client', async () => {
    const harness = buildHarness()
    const row: FloatingPoolGridRow = {
      pool_id: 1,
      employee_id: 100,
      current_assignment: 'CLIENT001',
      available_from: '2026-05-01T08:00',
      available_to: '2026-05-15T17:00',
      notes: 'cover for Maria',
    }
    await harness.onCellValueChanged({
      data: row,
      colDef: { field: 'current_assignment' },
      oldValue: null,
      newValue: 'CLIENT001',
    })
    expect(mockApi.post).toHaveBeenCalledWith('/floating-pool/assign', {
      employee_id: 100,
      client_id: 'CLIENT001',
      available_from: '2026-05-01T08:00',
      available_to: '2026-05-15T17:00',
      notes: 'cover for Maria',
    })
    expect(harness.fetchData).toHaveBeenCalled()
    expect(harness.notify.showSuccess).toHaveBeenCalled()
  })

  it('sends /unassign when current_assignment is cleared', async () => {
    const harness = buildHarness()
    const row: FloatingPoolGridRow = {
      pool_id: 7,
      employee_id: 200,
      current_assignment: null,
    }
    await harness.onCellValueChanged({
      data: row,
      colDef: { field: 'current_assignment' },
      oldValue: 'CLIENT001',
      newValue: null,
    })
    expect(mockApi.post).toHaveBeenCalledWith('/floating-pool/unassign', { pool_id: 7 })
    expect(harness.fetchData).toHaveBeenCalled()
  })

  it('does nothing when both old and new values are falsy', async () => {
    const harness = buildHarness()
    const row: FloatingPoolGridRow = { pool_id: 1, employee_id: 100, current_assignment: null }
    await harness.onCellValueChanged({
      data: row,
      colDef: { field: 'current_assignment' },
      oldValue: null,
      newValue: null,
    })
    expect(mockApi.post).not.toHaveBeenCalled()
  })

  it('refreshes data and shows error when /assign fails', async () => {
    const harness = buildHarness()
    mockApi.post.mockRejectedValueOnce({
      response: { data: { detail: 'already assigned' } },
    })
    const row: FloatingPoolGridRow = {
      pool_id: 1,
      employee_id: 100,
      current_assignment: 'CLIENT001',
    }
    await harness.onCellValueChanged({
      data: row,
      colDef: { field: 'current_assignment' },
      oldValue: null,
      newValue: 'CLIENT001',
    })
    expect(harness.notify.showError).toHaveBeenCalledWith('already assigned')
    expect(harness.fetchData).toHaveBeenCalled()
  })

  it('errors out when employee_id is missing', async () => {
    const harness = buildHarness()
    const row: FloatingPoolGridRow = { pool_id: 1, current_assignment: 'CLIENT001' }
    await harness.onCellValueChanged({
      data: row,
      colDef: { field: 'current_assignment' },
      oldValue: null,
      newValue: 'CLIENT001',
    })
    expect(mockApi.post).not.toHaveBeenCalled()
    expect(harness.notify.showError).toHaveBeenCalled()
  })
})

describe('onCellValueChanged — date / notes edits', () => {
  it('re-fires /assign when notes change on an assigned row', async () => {
    const harness = buildHarness()
    const row: FloatingPoolGridRow = {
      pool_id: 1,
      employee_id: 100,
      current_assignment: 'CLIENT001',
      available_from: '2026-05-01T08:00',
      notes: 'updated note',
    }
    await harness.onCellValueChanged({
      data: row,
      colDef: { field: 'notes' },
      oldValue: 'old note',
      newValue: 'updated note',
    })
    expect(mockApi.post).toHaveBeenCalledWith(
      '/floating-pool/assign',
      expect.objectContaining({
        client_id: 'CLIENT001',
        notes: 'updated note',
      }),
    )
  })

  it('re-fires /assign when available_from changes on an assigned row', async () => {
    const harness = buildHarness()
    const row: FloatingPoolGridRow = {
      pool_id: 1,
      employee_id: 100,
      current_assignment: 'CLIENT001',
      available_from: '2026-06-01T08:00',
    }
    await harness.onCellValueChanged({
      data: row,
      colDef: { field: 'available_from' },
      oldValue: '2026-05-01T08:00',
      newValue: '2026-06-01T08:00',
    })
    expect(mockApi.post).toHaveBeenCalledWith(
      '/floating-pool/assign',
      expect.objectContaining({ available_from: '2026-06-01T08:00' }),
    )
  })

  it('does NOT call any endpoint when date or notes change on an unassigned row', async () => {
    const harness = buildHarness()
    const row: FloatingPoolGridRow = {
      pool_id: 1,
      employee_id: 100,
      current_assignment: null,
      notes: 'unrelated',
    }
    await harness.onCellValueChanged({
      data: row,
      colDef: { field: 'notes' },
      oldValue: '',
      newValue: 'unrelated',
    })
    expect(mockApi.post).not.toHaveBeenCalled()
  })
})

describe('unassignRow', () => {
  it('POSTs /unassign with pool_id and refreshes', async () => {
    const harness = buildHarness()
    const row: FloatingPoolGridRow = {
      pool_id: 42,
      employee_id: 100,
      current_assignment: 'CLIENT001',
    }
    await harness.unassignRow(row)
    expect(mockApi.post).toHaveBeenCalledWith('/floating-pool/unassign', { pool_id: 42 })
    expect(harness.fetchData).toHaveBeenCalled()
    expect(harness.notify.showSuccess).toHaveBeenCalled()
  })

  it('errors when pool_id is missing', async () => {
    const harness = buildHarness()
    const row: FloatingPoolGridRow = { employee_id: 100 }
    await harness.unassignRow(row)
    expect(mockApi.post).not.toHaveBeenCalled()
    expect(harness.notify.showError).toHaveBeenCalled()
  })

  it('shows error and refreshes when /unassign fails', async () => {
    const harness = buildHarness()
    mockApi.post.mockRejectedValueOnce({ message: 'network down' })
    const row: FloatingPoolGridRow = { pool_id: 1, employee_id: 100 }
    await harness.unassignRow(row)
    expect(harness.notify.showError).toHaveBeenCalledWith('network down')
    expect(harness.fetchData).toHaveBeenCalled()
  })
})

describe('actions cell renderer', () => {
  const renderActions = (
    row: FloatingPoolGridRow,
    harness: ReturnType<typeof buildHarness>,
  ): HTMLElement => {
    const col = findCol(harness.columnDefs.value, '_actions') as
      | { cellRenderer?: (p: { data: FloatingPoolGridRow; rowIndex: number }) => HTMLElement }
      | undefined
    return col!.cellRenderer!({ data: row, rowIndex: 0 })
  }

  it('renders an em-dash placeholder when row is not assigned', () => {
    const harness = buildHarness()
    const el = renderActions(
      { pool_id: 1, employee_id: 100, current_assignment: null },
      harness,
    )
    expect(el.querySelector('.ag-grid-unassign-btn')).toBeNull()
    expect(el.textContent).toContain('—')
  })

  it('renders an Unassign button when assigned and wires to unassign', async () => {
    const harness = buildHarness()
    const row: FloatingPoolGridRow = {
      pool_id: 1,
      employee_id: 100,
      current_assignment: 'CLIENT001',
    }
    const el = renderActions(row, harness)
    const btn = el.querySelector('.ag-grid-unassign-btn') as HTMLButtonElement
    expect(btn).not.toBeNull()
    btn.click()
    await Promise.resolve()
    expect(mockApi.post).toHaveBeenCalledWith('/floating-pool/unassign', { pool_id: 1 })
  })
})
