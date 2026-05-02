/**
 * Unit tests for useProductionLinesGridData composable —
 * Group D Surface #9 (Production Lines worksheet).
 *
 * Verifies the migration from v-data-table + v-text-field slots to
 * AGGridBase + AG Grid native cell editors. Asserts:
 *   - Column defs use AG Grid native editor types matching the backend
 *     ProductionLineCreate schema (line_code/line_name/department text;
 *     standard_capacity_units_per_hour/max_operators/efficiency_factor
 *     numeric with bounds; is_active checkbox).
 *   - Store-bound CRUD wrappers call useCapacityPlanningStore methods
 *     with the correct worksheet name 'productionLines'.
 *   - onCellValueChanged marks the worksheet dirty (so the workbook-level
 *     saveWorksheet action picks it up).
 *   - lines / hasChanges reactively read from the store.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { storeApi } = vi.hoisted(() => ({
  storeApi: {
    addRow: vi.fn(),
    removeRow: vi.fn(),
    duplicateRow: vi.fn(),
    worksheets: {
      productionLines: { data: [] as unknown[], dirty: false },
    },
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/stores/capacityPlanningStore', () => ({
  useCapacityPlanningStore: () => storeApi,
}))

import useProductionLinesGridData, {
  type ProductionLineRow,
} from '../useProductionLinesGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { min?: number; max?: number; precision?: number }
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

describe('useProductionLinesGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeApi.worksheets.productionLines = { data: [], dirty: false }
    vi.clearAllMocks()
  })

  describe('column definitions match backend schema', () => {
    it('exposes line_code as text editor (pinned left)', () => {
      const { columnDefs } = useProductionLinesGridData()
      const col = findCol(columnDefs.value, 'line_code')!
      expect(col.cellEditor).toBe('agTextCellEditor')
      expect(col.editable).toBe(true)
      expect(col.pinned).toBe('left')
    })

    it('exposes line_name as text editor', () => {
      const { columnDefs } = useProductionLinesGridData()
      const col = findCol(columnDefs.value, 'line_name')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('exposes department as text editor', () => {
      const { columnDefs } = useProductionLinesGridData()
      const col = findCol(columnDefs.value, 'department')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('exposes standard_capacity_units_per_hour as numeric with min:0 precision:2', () => {
      const { columnDefs } = useProductionLinesGridData()
      const col = findCol(columnDefs.value, 'standard_capacity_units_per_hour')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, precision: 2 })
    })

    it('exposes max_operators as numeric integer with min:0', () => {
      const { columnDefs } = useProductionLinesGridData()
      const col = findCol(columnDefs.value, 'max_operators')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, precision: 0 })
    })

    it('exposes efficiency_factor as numeric (0-1, precision 2)', () => {
      const { columnDefs } = useProductionLinesGridData()
      const col = findCol(columnDefs.value, 'efficiency_factor')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, max: 1, precision: 2 })
    })

    it('exposes is_active as checkbox editor', () => {
      const { columnDefs } = useProductionLinesGridData()
      const col = findCol(columnDefs.value, 'is_active')!
      expect(col.cellEditor).toBe('agCheckboxCellEditor')
    })

    it('exposes _actions column pinned right (non-sortable, non-filterable)', () => {
      const { columnDefs } = useProductionLinesGridData()
      const col = findCol(columnDefs.value, '_actions') as ColumnDefShape & {
        sortable?: boolean
        filter?: boolean
      }
      expect(col.pinned).toBe('right')
      expect(col.sortable).toBe(false)
      expect(col.filter).toBe(false)
    })

    it('does NOT expose absenteeism_factor or notes columns (not in current UI)', () => {
      const { columnDefs } = useProductionLinesGridData()
      expect(findCol(columnDefs.value, 'absenteeism_factor')).toBeUndefined()
      expect(findCol(columnDefs.value, 'notes')).toBeUndefined()
    })
  })

  describe('store-bound CRUD wrappers', () => {
    it("addRow delegates to store.addRow('productionLines')", () => {
      const { addRow } = useProductionLinesGridData()
      addRow()
      expect(storeApi.addRow).toHaveBeenCalledWith('productionLines')
    })

    it("removeRow delegates to store.removeRow('productionLines', index)", () => {
      const { removeRow } = useProductionLinesGridData()
      removeRow(2)
      expect(storeApi.removeRow).toHaveBeenCalledWith('productionLines', 2)
    })

    it("duplicateRow delegates to store.duplicateRow('productionLines', index)", () => {
      const { duplicateRow } = useProductionLinesGridData()
      duplicateRow(1)
      expect(storeApi.duplicateRow).toHaveBeenCalledWith('productionLines', 1)
    })

    it('onCellValueChanged marks the worksheet dirty', () => {
      const { onCellValueChanged } = useProductionLinesGridData()
      expect(storeApi.worksheets.productionLines.dirty).toBe(false)
      onCellValueChanged()
      expect(storeApi.worksheets.productionLines.dirty).toBe(true)
    })
  })

  describe('reactive store binding', () => {
    it('lines mirrors store.worksheets.productionLines.data', () => {
      const seed: ProductionLineRow[] = [
        { line_code: 'L1', line_name: 'Line 1', is_active: true },
        { line_code: 'L2', line_name: 'Line 2', is_active: false },
      ]
      storeApi.worksheets.productionLines.data = seed
      const { lines } = useProductionLinesGridData()
      expect(lines.value).toBe(seed)
    })

    it('hasChanges returns true when worksheet dirty=true', () => {
      storeApi.worksheets.productionLines.dirty = true
      const { hasChanges } = useProductionLinesGridData()
      expect(hasChanges.value).toBe(true)
    })

    it('hasChanges returns false when worksheet dirty=false', () => {
      storeApi.worksheets.productionLines.dirty = false
      const { hasChanges } = useProductionLinesGridData()
      expect(hasChanges.value).toBe(false)
    })
  })
})
