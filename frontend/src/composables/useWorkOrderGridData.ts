/**
 * Composable for WorkOrderManagement inline-grid editing — column
 * defs, autosave on cell change for existing rows, explicit save for
 * new rows.
 *
 * Same Excel-style inline-edit pattern as the Group E admin catalogs
 * (Defect Types, Part Opportunities): existing rows PUT immediately
 * on every cell-value change; new rows accumulate locally until the
 * operator clicks the green Save button in the row's actions column,
 * then POST.
 *
 * Backend alignment: payload shape matches backend/schemas/work_order.py
 * WorkOrderCreate / WorkOrderUpdate. client_id derived from authStore /
 * kpiStore (Group A pattern) — fixes the legacy hardcoded 'CLIENT001'.
 */
import { computed, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { useAuthStore } from '@/stores/authStore'
import { useKPIStore } from '@/stores/kpi'

export interface WorkOrderRow {
  work_order_id?: string
  client_id?: string
  style_model?: string
  planned_quantity?: number | null
  actual_quantity?: number
  status?: string
  priority?: string | null
  planned_start_date?: string
  planned_ship_date?: string
  customer_po_number?: string
  ideal_cycle_time?: number | null
  notes?: string
  _isNew?: boolean
  _isSaving?: boolean
  [key: string]: unknown
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean | ((params: { data: WorkOrderRow }) => boolean)
  cellEditor?: string
  cellEditorParams?: { values?: string[]; min?: number; max?: number; precision?: number }
  cellRenderer?: (params: {
    data: WorkOrderRow
    rowIndex: number
    value?: unknown
  }) => HTMLElement
  valueGetter?: (params: { data: WorkOrderRow }) => unknown
  valueFormatter?: (params: { value?: unknown; data?: WorkOrderRow }) => string
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

// Backend WorkOrderStatusEnum values (backend/schemas/work_order.py:13-26).
export const WORK_ORDER_STATUS_OPTIONS: string[] = [
  'RECEIVED',
  'RELEASED',
  'DEMOTED',
  'ACTIVE',
  'IN_PROGRESS',
  'ON_HOLD',
  'COMPLETED',
  'SHIPPED',
  'CLOSED',
  'REJECTED',
  'CANCELLED',
]

// Backend priority pattern (backend/schemas/work_order.py:68).
export const WORK_ORDER_PRIORITY_OPTIONS: string[] = ['HIGH', 'MEDIUM', 'LOW']

const STATUS_COLORS: Record<string, string> = {
  RECEIVED: '#1976d2',
  RELEASED: '#1976d2',
  ACTIVE: '#1976d2',
  IN_PROGRESS: '#1976d2',
  ON_HOLD: '#ed6c02',
  COMPLETED: '#2e7d32',
  SHIPPED: '#2e7d32',
  CLOSED: '#757575',
  DEMOTED: '#757575',
  REJECTED: '#c62828',
  CANCELLED: '#c62828',
}

const PRIORITY_COLORS: Record<string, string> = {
  HIGH: '#c62828',
  MEDIUM: '#ed6c02',
  LOW: '#1976d2',
}

interface SnackbarLike {
  showSuccess: (m: string) => void
  showError: (m: string) => void
}

interface UseWorkOrderGridDataOptions {
  workOrders: Ref<WorkOrderRow[]>
  loadWorkOrders: () => Promise<void>
  notify: SnackbarLike
  onConfirmDelete: (row: WorkOrderRow) => void
  onOpenDetail: (row: WorkOrderRow) => void
}

interface UseWorkOrderGridDataReturn {
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeNewRow: (row: WorkOrderRow) => void
  saveNewRow: (row: WorkOrderRow) => Promise<void>
  onCellValueChanged: (event: {
    data: WorkOrderRow
    column?: { colId?: string }
  }) => Promise<void>
}

const errorDetail = (e: unknown, fallback: string): string => {
  const ax = e as { response?: { data?: { detail?: string } }; message?: string }
  return ax?.response?.data?.detail || ax?.message || fallback
}

const requiredFieldsPresent = (row: WorkOrderRow): boolean => {
  return Boolean(
    row.work_order_id &&
      row.style_model &&
      typeof row.planned_quantity === 'number' &&
      row.planned_quantity > 0,
  )
}

const buildPayload = (row: WorkOrderRow, clientId: string | number) => ({
  work_order_id: row.work_order_id,
  client_id: String(clientId),
  style_model: row.style_model,
  planned_quantity: row.planned_quantity,
  actual_quantity: row.actual_quantity ?? 0,
  status: row.status || 'RECEIVED',
  priority: row.priority || undefined,
  planned_start_date: row.planned_start_date || undefined,
  planned_ship_date: row.planned_ship_date || undefined,
  customer_po_number: row.customer_po_number || undefined,
  ideal_cycle_time: row.ideal_cycle_time ?? undefined,
  notes: row.notes || undefined,
})

const buildUpdatePayload = (row: WorkOrderRow) => ({
  style_model: row.style_model,
  planned_quantity: row.planned_quantity,
  actual_quantity: row.actual_quantity,
  status: row.status,
  priority: row.priority || undefined,
  planned_start_date: row.planned_start_date || undefined,
  planned_ship_date: row.planned_ship_date || undefined,
  customer_po_number: row.customer_po_number || undefined,
  ideal_cycle_time: row.ideal_cycle_time ?? undefined,
  notes: row.notes || undefined,
})

export default function useWorkOrderGridData(
  options: UseWorkOrderGridDataOptions,
): UseWorkOrderGridDataReturn {
  const { t } = useI18n()
  const { workOrders, loadWorkOrders, notify, onConfirmDelete, onOpenDetail } = options
  const authStore = useAuthStore()
  const kpiStore = useKPIStore()

  const activeClientId = (): string | number | null => {
    return authStore.user?.client_id_assigned ?? kpiStore.selectedClient ?? null
  }

  const addRow = (): void => {
    const clientId = activeClientId()
    if (!clientId) {
      notify.showError(t('workOrders.errors.noClient') || 'No client selected')
      return
    }
    const newRow: WorkOrderRow = {
      _isNew: true,
      work_order_id: '',
      client_id: String(clientId),
      style_model: '',
      planned_quantity: null,
      actual_quantity: 0,
      status: 'RECEIVED',
      priority: null,
      planned_start_date: '',
      planned_ship_date: '',
      customer_po_number: '',
      ideal_cycle_time: null,
      notes: '',
    }
    workOrders.value = [newRow, ...workOrders.value]
  }

  const removeNewRow = (row: WorkOrderRow): void => {
    workOrders.value = workOrders.value.filter((r) => r !== row)
  }

  const saveNewRow = async (row: WorkOrderRow): Promise<void> => {
    if (!requiredFieldsPresent(row)) {
      notify.showError(t('workOrders.errors.fillRequired') || 'Fill required fields first')
      return
    }
    const clientId = activeClientId()
    if (!clientId) {
      notify.showError(t('workOrders.errors.noClient') || 'No client selected')
      return
    }
    row._isSaving = true
    try {
      await api.post('/work-orders', buildPayload(row, clientId))
      notify.showSuccess(t('workOrders.created') || 'Work order created')
      await loadWorkOrders()
    } catch (error) {
      notify.showError(errorDetail(error, t('errors.general')))
    } finally {
      row._isSaving = false
    }
  }

  const onCellValueChanged = async (event: {
    data: WorkOrderRow
    column?: { colId?: string }
  }): Promise<void> => {
    if (event.data._isNew) return
    if (!event.data.work_order_id) return

    event.data._isSaving = true
    try {
      await api.put(`/work-orders/${event.data.work_order_id}`, buildUpdatePayload(event.data))
      notify.showSuccess(t('workOrders.updated') || 'Work order updated')
    } catch (error) {
      notify.showError(errorDetail(error, t('errors.general')))
      await loadWorkOrders()
    } finally {
      event.data._isSaving = false
    }
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('workOrders.workOrderId'),
      field: 'work_order_id',
      // Natural key — editable only on new rows.
      editable: (params) => Boolean(params.data._isNew),
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 150,
    },
    {
      headerName: t('production.style'),
      field: 'style_model',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 160,
    },
    {
      headerName: t('workOrders.quantityOrdered'),
      field: 'planned_quantity',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 1, precision: 0 },
      width: 130,
    },
    {
      headerName: t('workOrders.quantityCompleted'),
      field: 'actual_quantity',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      width: 130,
    },
    {
      headerName: t('workOrders.progress'),
      field: '_progress',
      editable: false,
      sortable: false,
      filter: false,
      valueGetter: (params) => calculateProgress(params.data),
      cellRenderer: (params) => renderProgressBar(calculateProgress(params.data)),
      width: 140,
    },
    {
      headerName: t('common.status'),
      field: 'status',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: WORK_ORDER_STATUS_OPTIONS },
      cellRenderer: (params) => renderStatusChip(String(params.data.status || '')),
      width: 140,
    },
    {
      headerName: t('workOrders.priority'),
      field: 'priority',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: WORK_ORDER_PRIORITY_OPTIONS },
      cellRenderer: (params) => renderPriorityChip(params.data.priority),
      width: 110,
    },
    {
      headerName: t('workOrders.plannedStart'),
      field: 'planned_start_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      width: 140,
    },
    {
      headerName: t('workOrders.plannedEnd'),
      field: 'planned_ship_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      cellRenderer: (params) =>
        renderDateWithOverdueFlag(params.data.planned_ship_date),
      width: 150,
    },
    {
      headerName: t('production.cycleTime'),
      field: 'ideal_cycle_time',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 4 },
      width: 130,
    },
    {
      headerName: t('production.notes'),
      field: 'notes',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      width: 200,
    },
    {
      headerName: t('common.actions'),
      field: '_actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params) =>
        renderActions(params, {
          saveNewRow,
          removeNewRow,
          onConfirmDelete,
          onOpenDetail,
        }),
      width: 140,
      pinned: 'right',
    },
  ])

  return {
    columnDefs,
    addRow,
    removeNewRow,
    saveNewRow,
    onCellValueChanged,
  }
}

export const calculateProgress = (row: WorkOrderRow): number => {
  const planned = Number(row.planned_quantity) || 0
  const actual = Number(row.actual_quantity) || 0
  if (planned <= 0) return 0
  return Math.min(100, Math.round((actual / planned) * 100))
}

export const isOverdue = (planned_ship_date: string | undefined | null): boolean => {
  if (!planned_ship_date) return false
  const date = new Date(planned_ship_date)
  return !Number.isNaN(date.getTime()) && date < new Date()
}

const renderProgressBar = (pct: number): HTMLElement => {
  const wrap = document.createElement('div')
  wrap.style.cssText =
    'display:flex;align-items:center;gap:6px;width:100%;line-height:1.2;'
  const bar = document.createElement('div')
  bar.style.cssText =
    'flex:1;height:8px;background:#e0e0e0;border-radius:4px;overflow:hidden;'
  const fill = document.createElement('div')
  const color =
    pct >= 80 ? '#2e7d32' : pct >= 50 ? '#1976d2' : pct >= 25 ? '#ed6c02' : '#c62828'
  fill.style.cssText = `width:${pct}%;height:100%;background:${color};`
  bar.appendChild(fill)
  const label = document.createElement('span')
  label.textContent = `${pct}%`
  label.style.cssText = 'font-size:11px;font-weight:600;'
  wrap.appendChild(bar)
  wrap.appendChild(label)
  return wrap
}

const renderStatusChip = (status: string): HTMLElement => {
  const span = document.createElement('span')
  if (!status) {
    span.textContent = '--'
    span.style.color = '#9e9e9e'
    return span
  }
  const color = STATUS_COLORS[status] || STATUS_COLORS.RECEIVED
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

const renderPriorityChip = (priority: string | null | undefined): HTMLElement => {
  const span = document.createElement('span')
  if (!priority) {
    span.textContent = '-'
    span.style.color = '#9e9e9e'
    return span
  }
  const color = PRIORITY_COLORS[priority] || '#757575'
  span.textContent = priority
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

const renderDateWithOverdueFlag = (
  planned_ship_date: string | undefined | null,
): HTMLElement => {
  const span = document.createElement('span')
  if (!planned_ship_date) {
    span.textContent = '-'
    span.style.color = '#9e9e9e'
    return span
  }
  const date = new Date(planned_ship_date)
  const formatted = Number.isNaN(date.getTime())
    ? planned_ship_date
    : date.toLocaleDateString()
  span.textContent = formatted
  if (isOverdue(planned_ship_date)) {
    span.style.color = '#c62828'
    span.style.fontWeight = '600'
    span.textContent = `⚠ ${formatted}`
  }
  return span
}

const renderActions = (
  params: { data: WorkOrderRow; rowIndex: number },
  handlers: {
    saveNewRow: (row: WorkOrderRow) => Promise<void>
    removeNewRow: (row: WorkOrderRow) => void
    onConfirmDelete: (row: WorkOrderRow) => void
    onOpenDetail: (row: WorkOrderRow) => void
  },
): HTMLElement => {
  const div = document.createElement('div')
  div.style.cssText = 'display: flex; gap: 4px;'
  if (params.data._isNew) {
    div.innerHTML = `
      <button class="ag-grid-save-btn" title="Save new work order" style="
        background: #2e7d32;
        color: white;
        border: none;
        padding: 2px 6px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      ">✓</button>
      <button class="ag-grid-cancel-btn" title="Discard new row" style="
        background: transparent;
        color: #c62828;
        border: 1px solid #c62828;
        padding: 2px 6px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      ">✕</button>
    `
    div
      .querySelector('.ag-grid-save-btn')
      ?.addEventListener('click', () => handlers.saveNewRow(params.data))
    div
      .querySelector('.ag-grid-cancel-btn')
      ?.addEventListener('click', () => handlers.removeNewRow(params.data))
  } else {
    div.innerHTML = `
      <button class="ag-grid-detail-btn" title="View details" style="
        background: transparent;
        color: #1976d2;
        border: 1px solid #1976d2;
        padding: 2px 6px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      ">👁</button>
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
      .querySelector('.ag-grid-detail-btn')
      ?.addEventListener('click', () => handlers.onOpenDetail(params.data))
    div
      .querySelector('.ag-grid-delete-btn')
      ?.addEventListener('click', () => handlers.onConfirmDelete(params.data))
  }
  return div
}
