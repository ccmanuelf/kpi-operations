/**
 * Composable for KPITrackingPanel script logic — column definitions
 * and store-bound CRUD wrappers.
 *
 * Workbook-style worksheet (Group D pattern): edits accumulate in
 * memory; persistence is centralised via
 * `useCapacityPlanningStore.saveWorksheet('kpiTracking')`. Most fields
 * (actual_value, variance_percent, status, period) are read-only —
 * they're populated by `store.loadKPIActuals()` against backend
 * actuals data. Only kpi_name and target_value are operator-editable.
 */
import { computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

export interface KPITrackingRow {
  _id?: number | string
  _isNew?: boolean
  kpi_name?: string
  target_value?: number
  actual_value?: number | null
  variance_percent?: number | null
  status?: string
  period_start?: string | null
  period_end?: string | null
  [key: string]: unknown
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { values?: string[]; min?: number; max?: number; precision?: number }
  cellRenderer?: (params: {
    data: KPITrackingRow
    rowIndex: number
    value?: unknown
  }) => HTMLElement
  valueGetter?: (params: { data: KPITrackingRow }) => unknown
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

const VARIANCE_COLORS = {
  ON_TARGET: '#2e7d32', // |variance| <= 5%
  OFF_TARGET: '#ed6c02', // 5% < |variance| <= 10%
  CRITICAL: '#c62828', // |variance| > 10%
}

const STATUS_COLORS: Record<string, string> = {
  PENDING: '#757575',
  ON_TRACK: '#2e7d32',
  AT_RISK: '#ed6c02',
  OFF_TARGET: '#c62828',
  ACHIEVED: '#2e7d32',
}

interface UseKPITrackingGridDataReturn {
  kpiData: ComputedRef<KPITrackingRow[]>
  hasChanges: ComputedRef<boolean>
  onTargetCount: ComputedRef<number>
  offTargetCount: ComputedRef<number>
  criticalCount: ComputedRef<number>
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeRow: (index: number) => void
  onCellValueChanged: () => void
}

const formatDate = (value: unknown): string => {
  if (!value) return ''
  const d = new Date(value as string)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString()
}

export const classifyVariance = (
  variance: number | null | undefined,
): 'ON_TARGET' | 'OFF_TARGET' | 'CRITICAL' | null => {
  if (variance === null || variance === undefined) return null
  const abs = Math.abs(variance)
  if (abs <= 5) return 'ON_TARGET'
  if (abs <= 10) return 'OFF_TARGET'
  return 'CRITICAL'
}

export default function useKPITrackingGridData(): UseKPITrackingGridDataReturn {
  const { t } = useI18n()
  const store = useCapacityPlanningStore()

  const kpiData = computed<KPITrackingRow[]>(
    () => (store.worksheets.kpiTracking.data as KPITrackingRow[]) || [],
  )

  const hasChanges = computed<boolean>(
    () => Boolean(store.worksheets.kpiTracking.dirty),
  )

  const onTargetCount = computed<number>(
    () => kpiData.value.filter((k) => classifyVariance(k.variance_percent) === 'ON_TARGET').length,
  )

  const offTargetCount = computed<number>(
    () => kpiData.value.filter((k) => classifyVariance(k.variance_percent) === 'OFF_TARGET').length,
  )

  const criticalCount = computed<number>(
    () => kpiData.value.filter((k) => classifyVariance(k.variance_percent) === 'CRITICAL').length,
  )

  const addRow = (): void => {
    store.addRow('kpiTracking')
  }

  const removeRow = (index: number): void => {
    store.removeRow('kpiTracking', index)
  }

  const onCellValueChanged = (): void => {
    store.worksheets.kpiTracking.dirty = true
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('capacityPlanning.kpiTracking.headers.kpiName'),
      field: 'kpi_name',
      editable: true,
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 220,
    },
    {
      headerName: t('capacityPlanning.kpiTracking.headers.target'),
      field: 'target_value',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { precision: 2 },
      width: 120,
    },
    {
      headerName: t('capacityPlanning.kpiTracking.headers.actual'),
      field: 'actual_value',
      editable: false,
      cellRenderer: (params) =>
        renderActualValue(params.data.actual_value),
      width: 120,
    },
    {
      headerName: t('capacityPlanning.kpiTracking.headers.variance'),
      field: 'variance_percent',
      editable: false,
      cellRenderer: (params) =>
        renderVarianceChip(params.data.variance_percent),
      width: 130,
    },
    {
      headerName: t('capacityPlanning.kpiTracking.headers.status'),
      field: 'status',
      editable: false,
      cellRenderer: (params) =>
        renderStatusChip(String(params.data.status || '')),
      width: 130,
    },
    {
      headerName: t('capacityPlanning.kpiTracking.headers.period'),
      field: '_period',
      editable: false,
      sortable: false,
      filter: false,
      valueGetter: (params) => {
        const start = params.data.period_start
        const end = params.data.period_end
        if (!start || !end) return ''
        return `${formatDate(start)} - ${formatDate(end)}`
      },
      width: 200,
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
    kpiData,
    hasChanges,
    onTargetCount,
    offTargetCount,
    criticalCount,
    columnDefs,
    addRow,
    removeRow,
    onCellValueChanged,
  }
}

const renderActualValue = (value: number | null | undefined): HTMLElement => {
  const span = document.createElement('span')
  if (value === null || value === undefined) {
    span.textContent = '--'
    span.style.color = '#9e9e9e'
  } else {
    span.textContent = String(value)
  }
  return span
}

const renderVarianceChip = (variance: number | null | undefined): HTMLElement => {
  const span = document.createElement('span')
  if (variance === null || variance === undefined) {
    span.textContent = '--'
    span.style.color = '#9e9e9e'
    return span
  }
  const tier = classifyVariance(variance)!
  const color = VARIANCE_COLORS[tier]
  const sign = variance > 0 ? '+' : ''
  span.textContent = `${sign}${variance}%`
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

const renderStatusChip = (status: string): HTMLElement => {
  const span = document.createElement('span')
  if (!status) {
    span.textContent = '--'
    span.style.color = '#9e9e9e'
    return span
  }
  const color = STATUS_COLORS[status] || STATUS_COLORS.PENDING
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

const renderDeleteAction = (
  params: { data: KPITrackingRow; rowIndex: number },
  remove: (i: number) => void,
): HTMLElement => {
  const div = document.createElement('div')
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
