/**
 * Unit tests for useStandardsGridData composable —
 * Group D Surface #11 (Production Standards worksheet).
 *
 * Verifies column-shape conformance to backend StandardCreate schema and
 * store-bound CRUD wrappers using 'productionStandards' worksheet name.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { storeApi } = vi.hoisted(() => ({
  storeApi: {
    addRow: vi.fn(),
    removeRow: vi.fn(),
    duplicateRow: vi.fn(),
    worksheets: {
      productionStandards: { data: [] as unknown[], dirty: false },
    },
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/stores/capacityPlanningStore', () => ({
  useCapacityPlanningStore: () => storeApi,
}))

import useStandardsGridData, { type StandardRow } from '../useStandardsGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { min?: number; precision?: number }
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

describe('useStandardsGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeApi.worksheets.productionStandards = { data: [], dirty: false }
    vi.clearAllMocks()
  })

  describe('column definitions match backend schema', () => {
    it('exposes style_model as text editor (pinned left)', () => {
      const { columnDefs } = useStandardsGridData()
      const col = findCol(columnDefs.value, 'style_model')!
      expect(col.cellEditor).toBe('agTextCellEditor')
      expect(col.pinned).toBe('left')
    })

    it('exposes operation_code as text editor (pinned left)', () => {
      const { columnDefs } = useStandardsGridData()
      const col = findCol(columnDefs.value, 'operation_code')!
      expect(col.cellEditor).toBe('agTextCellEditor')
      expect(col.pinned).toBe('left')
    })

    it('exposes operation_name as text editor', () => {
      const { columnDefs } = useStandardsGridData()
      const col = findCol(columnDefs.value, 'operation_name')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('exposes department as text editor', () => {
      const { columnDefs } = useStandardsGridData()
      const col = findCol(columnDefs.value, 'department')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('exposes sam_minutes as numeric (min:0, precision:2)', () => {
      const { columnDefs } = useStandardsGridData()
      const col = findCol(columnDefs.value, 'sam_minutes')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, precision: 2 })
    })

    it('exposes setup_time_minutes as numeric', () => {
      const { columnDefs } = useStandardsGridData()
      const col = findCol(columnDefs.value, 'setup_time_minutes')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
    })

    it('exposes machine_time_minutes as numeric', () => {
      const { columnDefs } = useStandardsGridData()
      const col = findCol(columnDefs.value, 'machine_time_minutes')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
    })

    it('exposes _actions column pinned right', () => {
      const { columnDefs } = useStandardsGridData()
      const col = findCol(columnDefs.value, '_actions')!
      expect(col.pinned).toBe('right')
    })

    it('does NOT expose manual_time_minutes or notes (not in current UI)', () => {
      const { columnDefs } = useStandardsGridData()
      expect(findCol(columnDefs.value, 'manual_time_minutes')).toBeUndefined()
      expect(findCol(columnDefs.value, 'notes')).toBeUndefined()
    })
  })

  describe('store-bound CRUD wrappers', () => {
    it("addRow delegates to store.addRow('productionStandards')", () => {
      const { addRow } = useStandardsGridData()
      addRow()
      expect(storeApi.addRow).toHaveBeenCalledWith('productionStandards')
    })

    it("removeRow delegates to store.removeRow('productionStandards', index)", () => {
      const { removeRow } = useStandardsGridData()
      removeRow(2)
      expect(storeApi.removeRow).toHaveBeenCalledWith('productionStandards', 2)
    })

    it("duplicateRow delegates to store.duplicateRow('productionStandards', index)", () => {
      const { duplicateRow } = useStandardsGridData()
      duplicateRow(1)
      expect(storeApi.duplicateRow).toHaveBeenCalledWith('productionStandards', 1)
    })

    it('onCellValueChanged marks the worksheet dirty', () => {
      const { onCellValueChanged } = useStandardsGridData()
      expect(storeApi.worksheets.productionStandards.dirty).toBe(false)
      onCellValueChanged()
      expect(storeApi.worksheets.productionStandards.dirty).toBe(true)
    })
  })

  describe('reactive store binding', () => {
    it('standards mirrors store.worksheets.productionStandards.data', () => {
      const seed: StandardRow[] = [
        { style_model: 'STYLE-A', operation_code: 'OP-1', sam_minutes: 0.5 },
        { style_model: 'STYLE-A', operation_code: 'OP-2', sam_minutes: 0.75 },
      ]
      storeApi.worksheets.productionStandards.data = seed
      const { standards } = useStandardsGridData()
      expect(standards.value).toBe(seed)
    })

    it('hasChanges returns true when worksheet dirty=true', () => {
      storeApi.worksheets.productionStandards.dirty = true
      const { hasChanges } = useStandardsGridData()
      expect(hasChanges.value).toBe(true)
    })
  })
})
