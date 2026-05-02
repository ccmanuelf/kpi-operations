/**
 * Unit tests for useStockGridData composable —
 * Group D Surface #10 (Stock worksheet).
 *
 * Verifies the migration from v-data-table + v-text-field slots to
 * AGGridBase + AG Grid native cell editors. Asserts:
 *   - Column defs aligned to backend StockSnapshotCreate schema.
 *   - available_quantity auto-recomputes (on_hand - allocated) when those
 *     columns change.
 *   - searchTerm filters by item_code / item_description (case-insensitive).
 *   - Aggregations (totalOnHand, totalAllocated, totalAvailable) sum across
 *     all rows.
 *   - Staleness warning fires when most-recent snapshot date exceeds
 *     dashboardInputs.shortage_alert_days.
 *   - Store-bound CRUD wrappers call useCapacityPlanningStore methods with
 *     'stockSnapshot' worksheet name.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { storeApi } = vi.hoisted(() => ({
  storeApi: {
    addRow: vi.fn(),
    removeRow: vi.fn(),
    importData: vi.fn(),
    worksheets: {
      stockSnapshot: { data: [] as unknown[], dirty: false },
      dashboardInputs: { data: { shortage_alert_days: 7 } },
    },
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}))

vi.mock('@/stores/capacityPlanningStore', () => ({
  useCapacityPlanningStore: () => storeApi,
}))

import useStockGridData, {
  STOCK_UOM_OPTIONS,
  type StockRow,
} from '../useStockGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { values?: unknown[]; min?: number; precision?: number }
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

describe('useStockGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeApi.worksheets.stockSnapshot = { data: [], dirty: false }
    storeApi.worksheets.dashboardInputs = { data: { shortage_alert_days: 7 } }
    vi.clearAllMocks()
  })

  describe('column definitions match backend schema', () => {
    it('exposes snapshot_date as date editor (pinned left)', () => {
      const { columnDefs } = useStockGridData()
      const col = findCol(columnDefs.value, 'snapshot_date')!
      expect(col.cellEditor).toBe('agDateStringCellEditor')
      expect(col.pinned).toBe('left')
    })

    it('exposes item_code as text editor (pinned left)', () => {
      const { columnDefs } = useStockGridData()
      const col = findCol(columnDefs.value, 'item_code')!
      expect(col.cellEditor).toBe('agTextCellEditor')
      expect(col.pinned).toBe('left')
    })

    it('exposes on_hand_quantity as numeric (min:0, precision:2)', () => {
      const { columnDefs } = useStockGridData()
      const col = findCol(columnDefs.value, 'on_hand_quantity')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, precision: 2 })
    })

    it('exposes allocated_quantity as numeric', () => {
      const { columnDefs } = useStockGridData()
      const col = findCol(columnDefs.value, 'allocated_quantity')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
    })

    it('exposes on_order_quantity as numeric', () => {
      const { columnDefs } = useStockGridData()
      const col = findCol(columnDefs.value, 'on_order_quantity')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
    })

    it('exposes available_quantity as read-only column', () => {
      const { columnDefs } = useStockGridData()
      const col = findCol(columnDefs.value, 'available_quantity')!
      expect(col.editable).toBe(false)
    })

    it('exposes unit_of_measure as select editor with STOCK_UOM_OPTIONS', () => {
      const { columnDefs } = useStockGridData()
      const col = findCol(columnDefs.value, 'unit_of_measure')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toEqual(STOCK_UOM_OPTIONS)
    })

    it('exposes _actions column pinned right', () => {
      const { columnDefs } = useStockGridData()
      const col = findCol(columnDefs.value, '_actions')!
      expect(col.pinned).toBe('right')
    })
  })

  describe('available_quantity auto-recompute', () => {
    it('recomputes when on_hand_quantity column changes', () => {
      const { onCellValueChanged } = useStockGridData()
      const row: StockRow = {
        on_hand_quantity: 100,
        allocated_quantity: 30,
        available_quantity: 0,
      }
      onCellValueChanged({ data: row, column: { colId: 'on_hand_quantity' } })
      expect(row.available_quantity).toBe(70)
    })

    it('recomputes when allocated_quantity column changes', () => {
      const { onCellValueChanged } = useStockGridData()
      const row: StockRow = {
        on_hand_quantity: 100,
        allocated_quantity: 60,
        available_quantity: 0,
      }
      onCellValueChanged({ data: row, column: { colId: 'allocated_quantity' } })
      expect(row.available_quantity).toBe(40)
    })

    it('does NOT recompute when other columns change (e.g. notes)', () => {
      const { onCellValueChanged } = useStockGridData()
      const row: StockRow = {
        on_hand_quantity: 100,
        allocated_quantity: 30,
        available_quantity: 999, // sentinel
      }
      onCellValueChanged({ data: row, column: { colId: 'notes' } })
      expect(row.available_quantity).toBe(999)
    })

    it('marks worksheet dirty on any cell change', () => {
      const { onCellValueChanged } = useStockGridData()
      expect(storeApi.worksheets.stockSnapshot.dirty).toBe(false)
      onCellValueChanged({ data: {}, column: { colId: 'item_code' } })
      expect(storeApi.worksheets.stockSnapshot.dirty).toBe(true)
    })
  })

  describe('searchTerm filtering', () => {
    it('filters by item_code (case-insensitive)', () => {
      storeApi.worksheets.stockSnapshot.data = [
        { item_code: 'WIDGET-A' },
        { item_code: 'WIDGET-B' },
        { item_code: 'GADGET-X' },
      ]
      const { searchTerm, filteredStock } = useStockGridData()
      searchTerm.value = 'widget'
      expect(filteredStock.value).toHaveLength(2)
    })

    it('filters by item_description', () => {
      storeApi.worksheets.stockSnapshot.data = [
        { item_code: 'A', item_description: 'Steel rod' },
        { item_code: 'B', item_description: 'Aluminium plate' },
      ]
      const { searchTerm, filteredStock } = useStockGridData()
      searchTerm.value = 'steel'
      expect(filteredStock.value).toHaveLength(1)
    })

    it('returns all rows when searchTerm is empty', () => {
      storeApi.worksheets.stockSnapshot.data = [{ item_code: 'A' }, { item_code: 'B' }]
      const { filteredStock } = useStockGridData()
      expect(filteredStock.value).toHaveLength(2)
    })
  })

  describe('aggregations', () => {
    it('totalOnHand sums on_hand_quantity', () => {
      storeApi.worksheets.stockSnapshot.data = [
        { on_hand_quantity: 100 },
        { on_hand_quantity: 50 },
        { on_hand_quantity: 25 },
      ]
      const { totalOnHand } = useStockGridData()
      expect(totalOnHand.value).toBe(175)
    })

    it('totalAllocated sums allocated_quantity', () => {
      storeApi.worksheets.stockSnapshot.data = [
        { allocated_quantity: 10 },
        { allocated_quantity: 20 },
      ]
      const { totalAllocated } = useStockGridData()
      expect(totalAllocated.value).toBe(30)
    })

    it('totalAvailable sums available_quantity', () => {
      storeApi.worksheets.stockSnapshot.data = [
        { available_quantity: 90 },
        { available_quantity: 30 },
      ]
      const { totalAvailable } = useStockGridData()
      expect(totalAvailable.value).toBe(120)
    })
  })

  describe('staleness warning', () => {
    it('returns null when no rows', () => {
      const { stalenessWarning } = useStockGridData()
      expect(stalenessWarning.value).toBeNull()
    })

    it('returns null when most-recent snapshot is within alert window', () => {
      const today = new Date().toISOString().slice(0, 10)
      storeApi.worksheets.stockSnapshot.data = [{ snapshot_date: today }]
      const { stalenessWarning } = useStockGridData()
      expect(stalenessWarning.value).toBeNull()
    })

    it('returns warning when most-recent snapshot exceeds shortage_alert_days', () => {
      const old = new Date()
      old.setDate(old.getDate() - 30)
      storeApi.worksheets.stockSnapshot.data = [
        { snapshot_date: old.toISOString().slice(0, 10) },
      ]
      const { stalenessWarning } = useStockGridData()
      expect(stalenessWarning.value).toContain('capacityPlanning.stock.stalenessWarning')
    })
  })

  describe('store-bound CRUD wrappers', () => {
    it("addRow delegates to store.addRow('stockSnapshot')", () => {
      const { addRow } = useStockGridData()
      addRow()
      expect(storeApi.addRow).toHaveBeenCalledWith('stockSnapshot')
    })

    it("removeRow delegates to store.removeRow('stockSnapshot', index)", () => {
      const { removeRow } = useStockGridData()
      removeRow(3)
      expect(storeApi.removeRow).toHaveBeenCalledWith('stockSnapshot', 3)
    })

    it("importData delegates to store.importData('stockSnapshot', rows)", () => {
      const { importData } = useStockGridData()
      const rows = [{ item_code: 'X', on_hand_quantity: 10 }]
      importData(rows)
      expect(storeApi.importData).toHaveBeenCalledWith('stockSnapshot', rows)
    })
  })
})
