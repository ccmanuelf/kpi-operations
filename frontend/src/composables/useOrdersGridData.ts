/**
 * Composable for OrdersGrid script logic — column definitions,
 * priority/status enums, CSV import helper, and store-bound CRUD wrappers.
 *
 * Backend alignment: column field names match
 * backend/routes/capacity/_models.py OrderCreate (order_number, customer_name,
 * style_model, order_quantity, required_date, priority, status, ...).
 * Priority/status values mirror the canonical OrderPriority and OrderStatus
 * enums from backend/orm/capacity/orders.py:18,27.
 *
 * Persistence is centralised via
 * `useCapacityPlanningStore.saveWorksheet('orders')`.
 */
import { computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

export interface OrderRow {
  _id?: number | string
  _isNew?: boolean
  order_number?: string
  customer_name?: string
  style_model?: string
  style_description?: string
  order_quantity?: number
  order_date?: string
  required_date?: string
  planned_start_date?: string
  planned_end_date?: string
  priority?: string
  status?: string
  order_sam_minutes?: number
  notes?: string
  [key: string]: unknown
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { values?: string[]; min?: number; precision?: number }
  cellRenderer?: (params: { data: OrderRow; rowIndex: number; value?: unknown }) => HTMLElement
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

// Canonical OrderPriority enum (backend/orm/capacity/orders.py:18).
export const ORDER_PRIORITY_OPTIONS: string[] = ['LOW', 'NORMAL', 'HIGH', 'URGENT']

// Canonical OrderStatus enum (backend/orm/capacity/orders.py:27).
export const ORDER_STATUS_OPTIONS: string[] = [
  'DRAFT',
  'CONFIRMED',
  'SCHEDULED',
  'IN_PROGRESS',
  'COMPLETED',
  'CANCELLED',
]

const STATUS_COLORS: Record<string, string> = {
  DRAFT: '#9e9e9e',
  CONFIRMED: '#1976d2',
  SCHEDULED: '#7b1fa2',
  IN_PROGRESS: '#ed6c02',
  COMPLETED: '#2e7d32',
  CANCELLED: '#c62828',
}

interface UseOrdersGridDataReturn {
  orders: ComputedRef<OrderRow[]>
  hasChanges: ComputedRef<boolean>
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeRow: (index: number) => void
  duplicateRow: (index: number) => void
  onCellValueChanged: () => void
  parseCsv: (csvText: string) => Partial<OrderRow>[]
  importCsv: (csvText: string) => void
  onRowsPasted: (pasteData: { convertedRows?: Partial<OrderRow>[] }) => void
}

export default function useOrdersGridData(): UseOrdersGridDataReturn {
  const { t } = useI18n()
  const store = useCapacityPlanningStore()

  const orders = computed<OrderRow[]>(
    () => (store.worksheets.orders.data as OrderRow[]) || [],
  )

  const hasChanges = computed<boolean>(
    () => Boolean(store.worksheets.orders.dirty),
  )

  const addRow = (): void => {
    store.addRow('orders')
  }

  const removeRow = (index: number): void => {
    store.removeRow('orders', index)
  }

  const duplicateRow = (index: number): void => {
    store.duplicateRow('orders', index)
  }

  const onCellValueChanged = (): void => {
    store.worksheets.orders.dirty = true
  }

  const parseCsv = (csvText: string): Partial<OrderRow>[] => {
    const lines = csvText.trim().split('\n')
    if (lines.length === 0) return []
    const headerLine = lines[0].split(',').map((h) => h.trim())
    return lines.slice(1).map((line) => {
      const values = line.split(',').map((v) => v.trim())
      const row: Partial<OrderRow> = {}
      headerLine.forEach((h, i) => {
        ;(row as Record<string, unknown>)[h] = values[i] || ''
      })
      if (row.order_quantity !== undefined && row.order_quantity !== '') {
        row.order_quantity = parseInt(String(row.order_quantity)) || 0
      }
      // Default missing required-by-backend fields to canonical enum values.
      if (!row.priority || !ORDER_PRIORITY_OPTIONS.includes(row.priority)) {
        row.priority = 'NORMAL'
      }
      if (!row.status || !ORDER_STATUS_OPTIONS.includes(row.status)) {
        row.status = 'DRAFT'
      }
      return row
    })
  }

  const importCsv = (csvText: string): void => {
    if (!csvText.trim()) return
    const rows = parseCsv(csvText)
    store.importData('orders', rows)
  }

  // AGGridBase emits `rows-pasted` with a Papaparse-validated payload
  // when the operator clicks the toolbar Import-CSV button or pastes
  // from Excel. Route the parsed rows through the same `store.importData`
  // path that the legacy textarea-paste dialog used.
  const onRowsPasted = (pasteData: { convertedRows?: Partial<OrderRow>[] }): void => {
    const rows = pasteData?.convertedRows
    if (!rows || rows.length === 0) return
    store.importData('orders', rows)
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('capacityPlanning.orders.headers.orderNumber'),
      field: 'order_number',
      editable: true,
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 130,
    },
    {
      headerName: t('capacityPlanning.orders.headers.customer'),
      field: 'customer_name',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 160,
    },
    {
      headerName: t('capacityPlanning.orders.headers.style'),
      field: 'style_model',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 110,
    },
    {
      headerName: t('capacityPlanning.orders.headers.quantity'),
      field: 'order_quantity',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      width: 110,
    },
    {
      headerName: t('capacityPlanning.orders.headers.requiredDate'),
      field: 'required_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      width: 140,
    },
    {
      headerName: t('capacityPlanning.orders.headers.priority'),
      field: 'priority',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: ORDER_PRIORITY_OPTIONS },
      width: 120,
    },
    {
      headerName: t('capacityPlanning.orders.headers.status'),
      field: 'status',
      editable: false,
      cellRenderer: renderStatusChip,
      width: 130,
    },
    {
      headerName: t('common.actions'),
      field: '_actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params) => renderActions(params, { duplicateRow, removeRow }),
      width: 110,
      pinned: 'right',
    },
  ])

  return {
    orders,
    hasChanges,
    columnDefs,
    addRow,
    removeRow,
    duplicateRow,
    onCellValueChanged,
    parseCsv,
    importCsv,
    onRowsPasted,
  }
}

const renderStatusChip = (params: { value?: unknown }): HTMLElement => {
  const status = String(params.value || 'DRAFT')
  const color = STATUS_COLORS[status] || STATUS_COLORS.DRAFT
  const span = document.createElement('span')
  span.textContent = status
  span.style.cssText = `
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    color: white;
    background: ${color};
  `
  return span
}

const renderActions = (
  params: { data: OrderRow; rowIndex: number },
  handlers: { duplicateRow: (i: number) => void; removeRow: (i: number) => void },
): HTMLElement => {
  const div = document.createElement('div')
  div.style.cssText = 'display: flex; gap: 4px;'
  div.innerHTML = `
    <button class="ag-grid-duplicate-btn" title="Duplicate" style="
      background: transparent;
      color: #1976d2;
      border: 1px solid #1976d2;
      padding: 2px 6px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 12px;
    ">⎘</button>
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
    .querySelector('.ag-grid-duplicate-btn')
    ?.addEventListener('click', () => handlers.duplicateRow(params.rowIndex))
  div
    .querySelector('.ag-grid-delete-btn')
    ?.addEventListener('click', () => handlers.removeRow(params.rowIndex))
  return div
}
