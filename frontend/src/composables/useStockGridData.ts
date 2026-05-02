/**
 * Composable for StockGrid script logic — column definitions,
 * search filter, summary stats, staleness warning, store-bound CRUD.
 *
 * Backend alignment: column field names match
 * backend/routes/capacity/_models.py StockSnapshotCreate
 * (snapshot_date, item_code, item_description, on_hand_quantity,
 * allocated_quantity, on_order_quantity, unit_of_measure, location,
 * notes). Persistence is centralised in
 * `useCapacityPlanningStore.saveWorksheet('stockSnapshot')`. The UI
 * computes available_quantity as `on_hand - allocated`; the backend's
 * canonical formula (`on_hand - allocated + on_order`) takes over once
 * the worksheet round-trips.
 */
import { ref, computed, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

export interface StockRow {
  _id?: number | string
  _isNew?: boolean
  snapshot_date?: string
  item_code?: string
  item_description?: string
  on_hand_quantity?: number
  allocated_quantity?: number
  on_order_quantity?: number
  available_quantity?: number
  unit_of_measure?: string
  location?: string
  notes?: string
  [key: string]: unknown
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { values?: string[]; min?: number; precision?: number }
  cellRenderer?: (params: { data: StockRow; rowIndex: number }) => HTMLElement
  valueFormatter?: (params: { value?: unknown }) => string
  cellClass?: (params: { data: StockRow }) => string
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

export const STOCK_UOM_OPTIONS: string[] = ['EA', 'M', 'YD', 'KG', 'LB', 'PC', 'SET']

interface UseStockGridDataReturn {
  stock: ComputedRef<StockRow[]>
  filteredStock: ComputedRef<StockRow[]>
  searchTerm: Ref<string>
  hasChanges: ComputedRef<boolean>
  totalOnHand: ComputedRef<number>
  totalAllocated: ComputedRef<number>
  totalAvailable: ComputedRef<number>
  stalenessWarning: ComputedRef<string | null>
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeRow: (index: number) => void
  onCellValueChanged: (event: {
    data: StockRow
    column?: { colId?: string }
  }) => void
  importData: (rows: Partial<StockRow>[]) => void
}

export default function useStockGridData(): UseStockGridDataReturn {
  const { t } = useI18n()
  const store = useCapacityPlanningStore()

  const searchTerm = ref('')

  const stock = computed<StockRow[]>(
    () => (store.worksheets.stockSnapshot.data as StockRow[]) || [],
  )

  const filteredStock = computed<StockRow[]>(() => {
    if (!searchTerm.value) return stock.value
    const q = searchTerm.value.toLowerCase()
    return stock.value.filter(
      (r) =>
        (r.item_code || '').toLowerCase().includes(q) ||
        (r.item_description || '').toLowerCase().includes(q),
    )
  })

  const hasChanges = computed<boolean>(
    () => Boolean(store.worksheets.stockSnapshot.dirty),
  )

  const totalOnHand = computed<number>(() =>
    stock.value.reduce(
      (sum, r) => sum + (Number(r.on_hand_quantity) || 0),
      0,
    ),
  )

  const totalAllocated = computed<number>(() =>
    stock.value.reduce(
      (sum, r) => sum + (Number(r.allocated_quantity) || 0),
      0,
    ),
  )

  const totalAvailable = computed<number>(() =>
    stock.value.reduce(
      (sum, r) => sum + (Number(r.available_quantity) || 0),
      0,
    ),
  )

  const stalenessWarning = computed<string | null>(() => {
    if (!stock.value.length) return null
    const dashboard = store.worksheets.dashboardInputs?.data as
      | { shortage_alert_days?: number }
      | undefined
    const alertDays = dashboard?.shortage_alert_days ?? 7
    const dates = stock.value
      .map((r) => r.snapshot_date)
      .filter((d): d is string => Boolean(d))
      .map((d) => new Date(d))
    if (!dates.length) return null
    const mostRecent = new Date(Math.max(...dates.map((d) => d.getTime())))
    const daysSince = Math.floor(
      (Date.now() - mostRecent.getTime()) / (1000 * 60 * 60 * 24),
    )
    if (daysSince > alertDays) {
      return t('capacityPlanning.stock.stalenessWarning', {
        days: daysSince,
        date: mostRecent.toISOString().slice(0, 10),
      })
    }
    return null
  })

  const addRow = (): void => {
    store.addRow('stockSnapshot')
  }

  const removeRow = (index: number): void => {
    store.removeRow('stockSnapshot', index)
  }

  const importData = (rows: Partial<StockRow>[]): void => {
    store.importData('stockSnapshot', rows)
  }

  // Auto-recompute available_quantity = on_hand - allocated when those columns change.
  // Backend's canonical formula adds on_order; we use the lighter UI formula
  // and let the backend overwrite on round-trip.
  const onCellValueChanged = (event: {
    data: StockRow
    column?: { colId?: string }
  }): void => {
    const colId = event.column?.colId
    if (colId === 'on_hand_quantity' || colId === 'allocated_quantity') {
      const onHand = Number(event.data.on_hand_quantity) || 0
      const allocated = Number(event.data.allocated_quantity) || 0
      event.data.available_quantity = onHand - allocated
    }
    store.worksheets.stockSnapshot.dirty = true
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('capacityPlanning.stock.headers.date'),
      field: 'snapshot_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      pinned: 'left',
      width: 130,
    },
    {
      headerName: t('capacityPlanning.stock.headers.itemCode'),
      field: 'item_code',
      editable: true,
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 120,
    },
    {
      headerName: t('capacityPlanning.stock.headers.description'),
      field: 'item_description',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 220,
    },
    {
      headerName: t('capacityPlanning.stock.headers.onHand'),
      field: 'on_hand_quantity',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      width: 110,
    },
    {
      headerName: t('capacityPlanning.stock.headers.allocated'),
      field: 'allocated_quantity',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      width: 110,
    },
    {
      headerName: t('capacityPlanning.stock.headers.onOrder'),
      field: 'on_order_quantity',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      width: 110,
    },
    {
      headerName: t('capacityPlanning.stock.headers.available'),
      field: 'available_quantity',
      editable: false,
      cellClass: (params) =>
        Number(params.data.available_quantity ?? 0) < 0
          ? 'ag-cell-error ag-cell-bold'
          : 'ag-cell-success',
      width: 110,
    },
    {
      headerName: t('capacityPlanning.stock.headers.uom'),
      field: 'unit_of_measure',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: STOCK_UOM_OPTIONS },
      width: 90,
    },
    {
      headerName: t('common.actions'),
      field: '_actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params) => renderDeleteAction(params, removeRow),
      width: 90,
      pinned: 'right',
    },
  ])

  return {
    stock,
    filteredStock,
    searchTerm,
    hasChanges,
    totalOnHand,
    totalAllocated,
    totalAvailable,
    stalenessWarning,
    columnDefs,
    addRow,
    removeRow,
    onCellValueChanged,
    importData,
  }
}

const renderDeleteAction = (
  params: { data: StockRow; rowIndex: number },
  remove: (i: number) => void,
): HTMLElement => {
  const div = document.createElement('div')
  div.style.cssText = 'display: flex; gap: 4px;'
  div.innerHTML = `
    <button class="ag-grid-delete-btn" title="Delete" style="
      background: #c62828;
      color: white;
      border: none;
      padding: 2px 6px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    ">✕</button>
  `
  div
    .querySelector('.ag-grid-delete-btn')
    ?.addEventListener('click', () => remove(params.rowIndex))
  return div
}
