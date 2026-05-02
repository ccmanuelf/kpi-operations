/**
 * Composable for StandardsGrid script logic — column definitions and
 * store-bound CRUD wrappers for the production-standards worksheet.
 *
 * Backend alignment: column field names match
 * backend/routes/capacity/_models.py StandardCreate (style_model,
 * operation_code, operation_name, department, sam_minutes,
 * setup_time_minutes, machine_time_minutes, manual_time_minutes, notes).
 * Persistence is centralised via
 * `useCapacityPlanningStore.saveWorksheet('productionStandards')`.
 */
import { computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

export interface StandardRow {
  _id?: number | string
  _isNew?: boolean
  style_model?: string
  operation_code?: string
  operation_name?: string
  department?: string
  sam_minutes?: number
  setup_time_minutes?: number
  machine_time_minutes?: number
  manual_time_minutes?: number
  notes?: string
  [key: string]: unknown
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: { min?: number; precision?: number }
  cellRenderer?: (params: { data: StandardRow; rowIndex: number }) => HTMLElement
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

interface UseStandardsGridDataReturn {
  standards: ComputedRef<StandardRow[]>
  hasChanges: ComputedRef<boolean>
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeRow: (index: number) => void
  duplicateRow: (index: number) => void
  onCellValueChanged: () => void
}

export default function useStandardsGridData(): UseStandardsGridDataReturn {
  const { t } = useI18n()
  const store = useCapacityPlanningStore()

  const standards = computed<StandardRow[]>(
    () => (store.worksheets.productionStandards.data as StandardRow[]) || [],
  )

  const hasChanges = computed<boolean>(
    () => Boolean(store.worksheets.productionStandards.dirty),
  )

  const addRow = (): void => {
    store.addRow('productionStandards')
  }

  const removeRow = (index: number): void => {
    store.removeRow('productionStandards', index)
  }

  const duplicateRow = (index: number): void => {
    store.duplicateRow('productionStandards', index)
  }

  const onCellValueChanged = (): void => {
    store.worksheets.productionStandards.dirty = true
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('capacityPlanningGrids.standards.style'),
      field: 'style_model',
      editable: true,
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 110,
    },
    {
      headerName: t('capacityPlanningGrids.standards.opCode'),
      field: 'operation_code',
      editable: true,
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 110,
    },
    {
      headerName: t('capacityPlanningGrids.standards.operation'),
      field: 'operation_name',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 200,
    },
    {
      headerName: t('capacityPlanningGrids.standards.department'),
      field: 'department',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 140,
    },
    {
      headerName: t('capacityPlanningGrids.standards.samMin'),
      field: 'sam_minutes',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      width: 110,
    },
    {
      headerName: t('capacityPlanningGrids.standards.setupMin'),
      field: 'setup_time_minutes',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      width: 110,
    },
    {
      headerName: t('capacityPlanningGrids.standards.machineMin'),
      field: 'machine_time_minutes',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      width: 110,
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
    standards,
    hasChanges,
    columnDefs,
    addRow,
    removeRow,
    duplicateRow,
    onCellValueChanged,
  }
}

const renderActions = (
  params: { data: StandardRow; rowIndex: number },
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
