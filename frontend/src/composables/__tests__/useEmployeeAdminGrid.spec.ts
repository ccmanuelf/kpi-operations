/**
 * Unit tests for useEmployeeAdminGrid composable — the Employees admin
 * surface (Cycle 3 PR-A, Task 7). Verifies: column shape (roster fields
 * read-only, labor_class editable), labor_class select values/format,
 * empty-cell resting display for null, onCellValueChanged routing
 * (labor_class field only), PUT payload + error fallback refresh.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    put: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/services/api', () => ({ default: mockApi }))

import useEmployeeAdminGrid, { type EmployeeGridRow } from '../useEmployeeAdminGrid'

interface ColumnDefShape {
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { values?: unknown[]; formatValue?: (_v: unknown) => string }
  valueFormatter?: (_params: { value?: unknown }) => string
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

const buildHarness = () => {
  const fetchData = vi.fn().mockResolvedValue(undefined)
  const notify = { showSuccess: vi.fn(), showError: vi.fn() }
  const grid = useEmployeeAdminGrid({ fetchData, notify })
  return { ...grid, fetchData, notify }
}

beforeEach(() => {
  mockApi.put.mockReset()
  mockApi.put.mockResolvedValue({ data: {} })
})

describe('column definitions', () => {
  it('roster fields (id/code/name/department) are read-only', () => {
    const { columnDefs } = buildHarness()
    for (const field of ['employee_id', 'employee_code', 'employee_name', 'department']) {
      expect(findCol(columnDefs.value, field)!.editable).toBe(false)
    }
  })

  it('employee_id and employee_code are pinned left', () => {
    const { columnDefs } = buildHarness()
    expect(findCol(columnDefs.value, 'employee_id')!.pinned).toBe('left')
    expect(findCol(columnDefs.value, 'employee_code')!.pinned).toBe('left')
  })

  it('labor_class is editable with a null + direct/indirect select', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'labor_class')!
    expect(col.editable).toBe(true)
    expect(col.cellEditor).toBe('agSelectCellEditor')
    expect(col.cellEditorParams!.values).toEqual([null, 'direct', 'indirect'])
  })

  it('labor_class formatValue resolves null to the unclassified i18n key', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'labor_class')!
    expect(col.cellEditorParams!.formatValue!(null)).toBe('labor.unclassified')
    expect(col.cellEditorParams!.formatValue!('direct')).toBe('labor.classes.direct')
  })

  it('labor_class resting valueFormatter renders EMPTY for null (no placeholder text)', () => {
    const { columnDefs } = buildHarness()
    const col = findCol(columnDefs.value, 'labor_class')!
    expect(col.valueFormatter!({ value: null })).toBe('')
    expect(col.valueFormatter!({ value: undefined })).toBe('')
    expect(col.valueFormatter!({ value: 'indirect' })).toBe('labor.classes.indirect')
  })
})

describe('onCellValueChanged routing', () => {
  it('labor_class edit fires the update PUT', async () => {
    const { onCellValueChanged, fetchData } = buildHarness()
    const row: EmployeeGridRow = { employee_id: 42, labor_class: 'direct' }
    await onCellValueChanged({ data: row, colDef: { field: 'labor_class' }, newValue: 'direct' })
    expect(mockApi.put).toHaveBeenCalledWith('/employees/42', { labor_class: 'direct' })
    expect(fetchData).toHaveBeenCalled()
  })

  it('clearing labor_class sends an explicit null', async () => {
    const { onCellValueChanged } = buildHarness()
    const row: EmployeeGridRow = { employee_id: 42 }
    await onCellValueChanged({ data: row, colDef: { field: 'labor_class' }, newValue: null })
    expect(mockApi.put).toHaveBeenCalledWith('/employees/42', { labor_class: null })
  })

  it('edits on other fields are ignored (no PUT)', async () => {
    const { onCellValueChanged } = buildHarness()
    const row: EmployeeGridRow = { employee_id: 42 }
    await onCellValueChanged({ data: row, colDef: { field: 'employee_name' }, newValue: 'x' })
    expect(mockApi.put).not.toHaveBeenCalled()
  })

  it('missing employee_id is a no-op (defensive — read-only id column)', async () => {
    const { updateLaborClass } = buildHarness()
    await updateLaborClass({}, 'direct')
    expect(mockApi.put).not.toHaveBeenCalled()
  })
})

describe('error fallback', () => {
  it('a failed PUT still refreshes data and notifies error', async () => {
    mockApi.put.mockRejectedValueOnce({ response: { data: { detail: 'boom' } } })
    const { updateLaborClass, fetchData, notify } = buildHarness()
    await updateLaborClass({ employee_id: 1 }, 'direct')
    expect(fetchData).toHaveBeenCalled()
    expect(notify.showError).toHaveBeenCalledWith('boom')
  })
})
