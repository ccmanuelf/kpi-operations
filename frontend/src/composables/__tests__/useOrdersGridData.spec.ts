/**
 * Unit tests for useOrdersGridData composable —
 * Group D Surface #13 (Capacity Orders worksheet, final Group D surface).
 *
 * Verifies column-shape conformance to backend OrderCreate schema,
 * canonical OrderPriority/OrderStatus enums (legacy 'CRITICAL' UI bug
 * fixed → URGENT), CSV parser, and store-bound CRUD wrappers.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { storeApi } = vi.hoisted(() => ({
  storeApi: {
    addRow: vi.fn(),
    removeRow: vi.fn(),
    duplicateRow: vi.fn(),
    importData: vi.fn(),
    worksheets: {
      orders: { data: [] as unknown[], dirty: false },
    },
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/stores/capacityPlanningStore', () => ({
  useCapacityPlanningStore: () => storeApi,
}))

import useOrdersGridData, {
  ORDER_PRIORITY_OPTIONS,
  ORDER_STATUS_OPTIONS,
  type OrderRow,
} from '../useOrdersGridData'

interface ColumnDefShape {
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { values?: unknown[]; min?: number; precision?: number }
  pinned?: 'left' | 'right'
}

const findCol = (cols: unknown[], field: string): ColumnDefShape | undefined =>
  (cols as ColumnDefShape[]).find((c) => c.field === field)

describe('ORDER_PRIORITY_OPTIONS catalog', () => {
  it('matches the backend OrderPriority enum (no CRITICAL)', () => {
    expect(ORDER_PRIORITY_OPTIONS).toEqual(['LOW', 'NORMAL', 'HIGH', 'URGENT'])
  })

  it('does NOT contain legacy "CRITICAL" (UI bug)', () => {
    expect(ORDER_PRIORITY_OPTIONS).not.toContain('CRITICAL')
  })
})

describe('ORDER_STATUS_OPTIONS catalog', () => {
  it('matches the backend OrderStatus enum lifecycle', () => {
    expect(ORDER_STATUS_OPTIONS).toEqual([
      'DRAFT',
      'CONFIRMED',
      'SCHEDULED',
      'IN_PROGRESS',
      'COMPLETED',
      'CANCELLED',
    ])
  })
})

describe('useOrdersGridData', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeApi.worksheets.orders = { data: [], dirty: false }
    vi.clearAllMocks()
  })

  describe('column definitions match backend schema', () => {
    it('exposes order_number as text editor (pinned left)', () => {
      const { columnDefs } = useOrdersGridData()
      const col = findCol(columnDefs.value, 'order_number')!
      expect(col.cellEditor).toBe('agTextCellEditor')
      expect(col.pinned).toBe('left')
    })

    it('exposes customer_name as text editor', () => {
      const { columnDefs } = useOrdersGridData()
      const col = findCol(columnDefs.value, 'customer_name')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('exposes style_model as text editor', () => {
      const { columnDefs } = useOrdersGridData()
      const col = findCol(columnDefs.value, 'style_model')!
      expect(col.cellEditor).toBe('agTextCellEditor')
    })

    it('exposes order_quantity as numeric integer (min:0)', () => {
      const { columnDefs } = useOrdersGridData()
      const col = findCol(columnDefs.value, 'order_quantity')!
      expect(col.cellEditor).toBe('agNumberCellEditor')
      expect(col.cellEditorParams).toEqual({ min: 0, precision: 0 })
    })

    it('exposes required_date as date editor', () => {
      const { columnDefs } = useOrdersGridData()
      const col = findCol(columnDefs.value, 'required_date')!
      expect(col.cellEditor).toBe('agDateStringCellEditor')
    })

    it('exposes priority as select editor over canonical OrderPriority enum', () => {
      const { columnDefs } = useOrdersGridData()
      const col = findCol(columnDefs.value, 'priority')!
      expect(col.cellEditor).toBe('agSelectCellEditor')
      expect(col.cellEditorParams!.values).toEqual(ORDER_PRIORITY_OPTIONS)
    })

    it('exposes status as read-only with chip renderer', () => {
      const { columnDefs } = useOrdersGridData()
      const col = findCol(columnDefs.value, 'status')!
      expect(col.editable).toBe(false)
    })

    it('exposes _actions column pinned right', () => {
      const { columnDefs } = useOrdersGridData()
      const col = findCol(columnDefs.value, '_actions')!
      expect(col.pinned).toBe('right')
    })
  })

  describe('parseCsv helper', () => {
    it('parses CSV with header into row objects', () => {
      const { parseCsv } = useOrdersGridData()
      const csv = `order_number,customer_name,order_quantity\nORD-1,Acme,100\nORD-2,Beta,250`
      const rows = parseCsv(csv)
      expect(rows).toHaveLength(2)
      expect(rows[0]).toMatchObject({
        order_number: 'ORD-1',
        customer_name: 'Acme',
        order_quantity: 100,
      })
    })

    it('coerces order_quantity to integer', () => {
      const { parseCsv } = useOrdersGridData()
      const csv = `order_number,order_quantity\nORD-1,42`
      const rows = parseCsv(csv)
      expect(rows[0].order_quantity).toBe(42)
    })

    it('defaults missing priority to NORMAL', () => {
      const { parseCsv } = useOrdersGridData()
      const csv = `order_number\nORD-1`
      const rows = parseCsv(csv)
      expect(rows[0].priority).toBe('NORMAL')
    })

    it('defaults missing status to DRAFT', () => {
      const { parseCsv } = useOrdersGridData()
      const csv = `order_number\nORD-1`
      const rows = parseCsv(csv)
      expect(rows[0].status).toBe('DRAFT')
    })

    it('replaces non-canonical priority values (e.g. legacy CRITICAL) with NORMAL', () => {
      const { parseCsv } = useOrdersGridData()
      const csv = `order_number,priority\nORD-1,CRITICAL`
      const rows = parseCsv(csv)
      expect(rows[0].priority).toBe('NORMAL')
    })

    it('preserves valid priority values', () => {
      const { parseCsv } = useOrdersGridData()
      const csv = `order_number,priority\nORD-1,URGENT`
      const rows = parseCsv(csv)
      expect(rows[0].priority).toBe('URGENT')
    })
  })

  describe('importCsv integration', () => {
    it("delegates to store.importData with 'orders' worksheet name", () => {
      const { importCsv } = useOrdersGridData()
      importCsv(`order_number\nORD-1`)
      expect(storeApi.importData).toHaveBeenCalledWith(
        'orders',
        expect.arrayContaining([
          expect.objectContaining({ order_number: 'ORD-1' }),
        ]),
      )
    })

    it('does NOT call store when csv is empty', () => {
      const { importCsv } = useOrdersGridData()
      importCsv('   ')
      expect(storeApi.importData).not.toHaveBeenCalled()
    })
  })

  describe('store-bound CRUD wrappers', () => {
    it("addRow delegates to store.addRow('orders')", () => {
      const { addRow } = useOrdersGridData()
      addRow()
      expect(storeApi.addRow).toHaveBeenCalledWith('orders')
    })

    it("removeRow delegates to store.removeRow('orders', index)", () => {
      const { removeRow } = useOrdersGridData()
      removeRow(2)
      expect(storeApi.removeRow).toHaveBeenCalledWith('orders', 2)
    })

    it("duplicateRow delegates to store.duplicateRow('orders', index)", () => {
      const { duplicateRow } = useOrdersGridData()
      duplicateRow(1)
      expect(storeApi.duplicateRow).toHaveBeenCalledWith('orders', 1)
    })

    it('onCellValueChanged marks the worksheet dirty', () => {
      const { onCellValueChanged } = useOrdersGridData()
      expect(storeApi.worksheets.orders.dirty).toBe(false)
      onCellValueChanged()
      expect(storeApi.worksheets.orders.dirty).toBe(true)
    })
  })

  describe('reactive store binding', () => {
    it('orders mirrors store.worksheets.orders.data', () => {
      const seed: OrderRow[] = [
        { order_number: 'ORD-1', priority: 'NORMAL', status: 'DRAFT' },
      ]
      storeApi.worksheets.orders.data = seed
      const { orders } = useOrdersGridData()
      expect(orders.value).toBe(seed)
    })

    it('hasChanges reflects worksheet.dirty', () => {
      storeApi.worksheets.orders.dirty = true
      const { hasChanges } = useOrdersGridData()
      expect(hasChanges.value).toBe(true)
    })
  })
})
