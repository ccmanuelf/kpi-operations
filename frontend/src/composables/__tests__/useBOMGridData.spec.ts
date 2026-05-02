/**
 * Unit tests for useBOMGridData composable —
 * Group F Surface #16 (BOM master-detail).
 *
 * Verifies parent/child grid composition: parent grid columns aligned
 * to BOM header schema, child grid columns aligned to component
 * schema, selection drives the detail rowData, and store-bound CRUD
 * delegates to the right worksheet/component actions.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { storeApi } = vi.hoisted(() => ({
  storeApi: {
    addRow: vi.fn(),
    removeRow: vi.fn(),
    addBOMComponent: vi.fn(),
    removeBOMComponent: vi.fn(),
    worksheets: {
      bom: { data: [] as unknown[], dirty: false },
    },
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/stores/capacityPlanningStore', () => ({
  useCapacityPlanningStore: () => storeApi,
}))

import useBOMGridData, {
  BOM_UOM_OPTIONS,
  type BOMHeaderRow,
  type BOMComponentRow,
} from '../useBOMGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { values?: unknown[]; min?: number; max?: number }
  pinned?: 'left' | 'right'
  valueGetter?: (params: { data: BOMHeaderRow }) => unknown
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

describe('useBOMGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeApi.worksheets.bom = { data: [], dirty: false }
    vi.clearAllMocks()
  })

  describe('BOM_UOM_OPTIONS', () => {
    it('shares the canonical UOM set with stock', () => {
      expect(BOM_UOM_OPTIONS).toEqual(['EA', 'M', 'YD', 'KG', 'LB', 'PC', 'SET'])
    })
  })

  describe('parent grid column definitions', () => {
    it('exposes parent_item_code as text editor (pinned left)', () => {
      const { bomColumnDefs } = useBOMGridData()
      const col = findCol(bomColumnDefs.value, 'parent_item_code')!
      expect(col.cellEditor).toBe('agTextCellEditor')
      expect(col.pinned).toBe('left')
    })

    it('exposes parent_item_description as text editor', () => {
      const { bomColumnDefs } = useBOMGridData()
      const col = findCol(bomColumnDefs.value, 'parent_item_description')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('exposes style_model as text editor', () => {
      const { bomColumnDefs } = useBOMGridData()
      const col = findCol(bomColumnDefs.value, 'style_model')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('exposes revision as text editor', () => {
      const { bomColumnDefs } = useBOMGridData()
      const col = findCol(bomColumnDefs.value, 'revision')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('exposes _components_count as read-only column derived via valueGetter', () => {
      const { bomColumnDefs } = useBOMGridData()
      const col = findCol(bomColumnDefs.value, '_components_count')!
      expect(col.editable).toBe(false)
      expect(typeof col.valueGetter).toBe('function')
      expect(col.valueGetter!({ data: { components: [{}, {}] } as BOMHeaderRow })).toBe(2)
      expect(col.valueGetter!({ data: {} as BOMHeaderRow })).toBe(0)
    })

    it('exposes is_active as checkbox editor', () => {
      const { bomColumnDefs } = useBOMGridData()
      const col = findCol(bomColumnDefs.value, 'is_active')!
      expect(col.cellEditor).toBe('agCheckboxCellEditor')
    })

    it('exposes _actions column pinned right', () => {
      const { bomColumnDefs } = useBOMGridData()
      const col = findCol(bomColumnDefs.value, '_actions')!
      expect(col.pinned).toBe('right')
    })
  })

  describe('child grid column definitions', () => {
    it('exposes component_item_code as text editor (pinned left)', () => {
      const { componentColumnDefs } = useBOMGridData()
      const col = findCol(componentColumnDefs.value, 'component_item_code')!
      expect(col.cellEditor).toBe('agTextCellEditor')
      expect(col.pinned).toBe('left')
    })

    it('exposes quantity_per as numeric (min:0, precision:4)', () => {
      const { componentColumnDefs } = useBOMGridData()
      const col = findCol(componentColumnDefs.value, 'quantity_per')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, precision: 4 })
    })

    it('exposes unit_of_measure as select editor over BOM_UOM_OPTIONS', () => {
      const { componentColumnDefs } = useBOMGridData()
      const col = findCol(componentColumnDefs.value, 'unit_of_measure')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toEqual(BOM_UOM_OPTIONS)
    })

    it('exposes waste_percentage as numeric (0..100)', () => {
      const { componentColumnDefs } = useBOMGridData()
      const col = findCol(componentColumnDefs.value, 'waste_percentage')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, max: 100, precision: 2 })
    })
  })

  describe('selection state', () => {
    it('selectedBOM returns null when no row selected', () => {
      const { selectedBOM, selectedBOMIndex } = useBOMGridData()
      selectedBOMIndex.value = null
      expect(selectedBOM.value).toBeNull()
    })

    it('selectedBOM returns the selected BOM by index', () => {
      const seed: BOMHeaderRow[] = [
        { parent_item_code: 'A' },
        { parent_item_code: 'B' },
      ]
      storeApi.worksheets.bom.data = seed
      const { selectedBOM, selectedBOMIndex } = useBOMGridData()
      selectedBOMIndex.value = 1
      expect(selectedBOM.value).toMatchObject({ parent_item_code: 'B' })
    })

    it('selectedComponents reflects the selected BOMs components array', () => {
      const components: BOMComponentRow[] = [{ component_item_code: 'C-1' }]
      storeApi.worksheets.bom.data = [{ parent_item_code: 'A', components }]
      const { selectedComponents, selectedBOMIndex } = useBOMGridData()
      selectedBOMIndex.value = 0
      expect(selectedComponents.value).toEqual(components)
    })

    it('selectedComponents returns empty array when nothing selected', () => {
      const { selectedComponents } = useBOMGridData()
      expect(selectedComponents.value).toEqual([])
    })

    it('onBOMRowClicked updates selectedBOMIndex from event.rowIndex', () => {
      const { selectedBOMIndex, onBOMRowClicked } = useBOMGridData()
      onBOMRowClicked({ data: {} as BOMHeaderRow, rowIndex: 3 })
      expect(selectedBOMIndex.value).toBe(3)
    })
  })

  describe('CRUD delegation', () => {
    it("addBOM delegates to store.addRow('bom') and selects the new row", () => {
      storeApi.worksheets.bom.data = [{ parent_item_code: 'A' }]
      // Simulate the store appending a row when addRow is called.
      storeApi.addRow.mockImplementation((name: string) => {
        if (name === 'bom') {
          ;(storeApi.worksheets.bom.data as unknown[]).push({ parent_item_code: 'NEW' })
        }
      })
      const { addBOM, selectedBOMIndex } = useBOMGridData()
      addBOM()
      expect(storeApi.addRow).toHaveBeenCalledWith('bom')
      expect(selectedBOMIndex.value).toBe(1)
    })

    it("removeBOM delegates to store.removeRow('bom', index)", () => {
      const { removeBOM } = useBOMGridData()
      removeBOM(2)
      expect(storeApi.removeRow).toHaveBeenCalledWith('bom', 2)
    })

    it('removeBOM clears selection when the removed row was selected', () => {
      const { removeBOM, selectedBOMIndex } = useBOMGridData()
      selectedBOMIndex.value = 2
      removeBOM(2)
      expect(selectedBOMIndex.value).toBeNull()
    })

    it('removeBOM shifts selection down when a row above is removed', () => {
      const { removeBOM, selectedBOMIndex } = useBOMGridData()
      selectedBOMIndex.value = 4
      removeBOM(1)
      expect(selectedBOMIndex.value).toBe(3)
    })

    it("addComponent delegates to store.addBOMComponent with the selected index", () => {
      const { addComponent, selectedBOMIndex } = useBOMGridData()
      selectedBOMIndex.value = 2
      addComponent()
      expect(storeApi.addBOMComponent).toHaveBeenCalledWith(2)
    })

    it('addComponent does nothing when no BOM is selected', () => {
      const { addComponent } = useBOMGridData()
      addComponent()
      expect(storeApi.addBOMComponent).not.toHaveBeenCalled()
    })

    it("removeComponent delegates to store.removeBOMComponent with selected BOM index + component index", () => {
      const { removeComponent, selectedBOMIndex } = useBOMGridData()
      selectedBOMIndex.value = 1
      removeComponent(3)
      expect(storeApi.removeBOMComponent).toHaveBeenCalledWith(1, 3)
    })

    it('onBOMCellValueChanged marks worksheet dirty', () => {
      const { onBOMCellValueChanged } = useBOMGridData()
      expect(storeApi.worksheets.bom.dirty).toBe(false)
      onBOMCellValueChanged()
      expect(storeApi.worksheets.bom.dirty).toBe(true)
    })

    it('onComponentCellValueChanged also marks worksheet dirty', () => {
      const { onComponentCellValueChanged } = useBOMGridData()
      onComponentCellValueChanged()
      expect(storeApi.worksheets.bom.dirty).toBe(true)
    })
  })
})
