/**
 * Composable for ProductionLinesGrid script logic — column
 * definitions and store-bound CRUD wrappers.
 *
 * Backend alignment: column field names match
 * backend/routes/capacity/_models.py ProductionLineCreate
 * (line_code, line_name, department, standard_capacity_units_per_hour,
 * max_operators, efficiency_factor, is_active). Persistence is centralised
 * in `useCapacityPlanningStore.saveWorksheet('productionLines')` — this
 * composable manages in-memory editing only.
 */
import { computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

export interface ProductionLineRow {
  _id?: number | string
  _isNew?: boolean
  line_code?: string
  line_name?: string
  department?: string
  standard_capacity_units_per_hour?: number
  max_operators?: number
  efficiency_factor?: number
  is_active?: boolean
  notes?: string
  [key: string]: unknown
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { min?: number; max?: number; precision?: number }
  cellRenderer?: (params: { data: ProductionLineRow; rowIndex: number }) => HTMLElement
  valueFormatter?: (params: { value?: unknown }) => string
  cellStyle?: Record<string, string>
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

interface UseProductionLinesGridDataReturn {
  lines: ComputedRef<ProductionLineRow[]>
  hasChanges: ComputedRef<boolean>
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeRow: (index: number) => void
  duplicateRow: (index: number) => void
  onCellValueChanged: () => void
}

export default function useProductionLinesGridData(): UseProductionLinesGridDataReturn {
  const { t } = useI18n()
  const store = useCapacityPlanningStore()

  const lines = computed<ProductionLineRow[]>(
    () => (store.worksheets.productionLines.data as ProductionLineRow[]) || [],
  )

  const hasChanges = computed<boolean>(
    () => Boolean(store.worksheets.productionLines.dirty),
  )

  const addRow = (): void => {
    store.addRow('productionLines')
  }

  const removeRow = (index: number): void => {
    store.removeRow('productionLines', index)
  }

  const duplicateRow = (index: number): void => {
    store.duplicateRow('productionLines', index)
  }

  const onCellValueChanged = (): void => {
    store.worksheets.productionLines.dirty = true
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('capacityPlanningGrids.productionLines.code'),
      field: 'line_code',
      editable: true,
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 110,
    },
    {
      headerName: t('capacityPlanningGrids.productionLines.name'),
      field: 'line_name',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 180,
    },
    {
      headerName: t('capacityPlanningGrids.productionLines.department'),
      field: 'department',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 140,
    },
    {
      headerName: t('capacityPlanningGrids.productionLines.capacityUnitsPerHr'),
      field: 'standard_capacity_units_per_hour',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      valueFormatter: (params) =>
        params.value !== undefined && params.value !== null
          ? Number(params.value).toFixed(2)
          : '0.00',
      width: 150,
    },
    {
      headerName: t('capacityPlanningGrids.productionLines.maxOperators'),
      field: 'max_operators',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      width: 130,
    },
    {
      headerName: t('capacityPlanningGrids.productionLines.efficiency'),
      field: 'efficiency_factor',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 1, precision: 2 },
      valueFormatter: (params) =>
        params.value !== undefined && params.value !== null
          ? Number(params.value).toFixed(2)
          : '0.85',
      width: 120,
    },
    {
      headerName: t('capacityPlanningGrids.productionLines.active'),
      field: 'is_active',
      editable: true,
      cellEditor: 'agCheckboxCellEditor',
      cellRenderer: (params) =>
        renderCheckmark(Boolean((params.data as ProductionLineRow).is_active)),
      cellStyle: { textAlign: 'center' },
      width: 90,
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
    lines,
    hasChanges,
    columnDefs,
    addRow,
    removeRow,
    duplicateRow,
    onCellValueChanged,
  }
}

const renderCheckmark = (value: boolean): HTMLElement => {
  const span = document.createElement('span')
  span.textContent = value ? '\u2713' : ''
  span.style.color = value ? 'var(--cds-support-success, #198038)' : 'inherit'
  return span
}

const renderActions = (
  params: { data: ProductionLineRow; rowIndex: number },
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
