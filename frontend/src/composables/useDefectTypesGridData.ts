/**
 * Composable for AdminDefectTypes inline-grid editing — column defs,
 * autosave on cell change for existing rows, and explicit save for new
 * rows.
 *
 * Backend alignment: payload shape matches the existing
 * api.createDefectType / api.updateDefectType endpoints (defect_code,
 * defect_name, description, category, severity_default,
 * industry_standard_code, sort_order, is_active). Existing rows autosave
 * via PUT on each cell change; new rows accumulate locally until the
 * operator clicks "Save" in the row's actions column, then POST.
 */
import { computed, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import type { DefectType, Severity } from './useDefectTypesData'

export const SEVERITY_OPTIONS: Severity[] = ['CRITICAL', 'MAJOR', 'MINOR']

export const CATEGORY_OPTIONS: string[] = [
  'Assembly',
  'Material',
  'Process',
  'Electrical',
  'Finish',
  'Measurement',
  'Sewing',
  'Packaging',
  'Labeling',
  'Cleanliness',
  'Testing',
  'Documentation',
  'Handling',
  'Environment',
  'General',
]

export interface DefectTypeGridRow extends DefectType {
  defect_type_id?: string | number
  description?: string
  _isNew?: boolean
  _isSaving?: boolean
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean | ((params: { data: DefectTypeGridRow }) => boolean)
  cellEditor?: string
  cellEditorParams?: { values?: string[]; min?: number; precision?: number }
  cellRenderer?: (params: {
    data: DefectTypeGridRow
    rowIndex: number
    value?: unknown
  }) => HTMLElement
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#c62828',
  MAJOR: '#ed6c02',
  MINOR: '#1976d2',
}

interface SnackbarLike {
  showSuccess: (m: string) => void
  showError: (m: string) => void
}

interface UseDefectTypesGridDataOptions {
  selectedClient: Ref<string | number | null>
  defectTypes: Ref<DefectTypeGridRow[]>
  loadDefectTypes: () => Promise<void>
  notify: SnackbarLike
  onConfirmDelete: (row: DefectTypeGridRow) => void
}

interface UseDefectTypesGridDataReturn {
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeNewRow: (row: DefectTypeGridRow) => void
  saveNewRow: (row: DefectTypeGridRow) => Promise<void>
  onCellValueChanged: (event: {
    data: DefectTypeGridRow
    oldValue?: unknown
    column?: { colId?: string }
  }) => Promise<void>
}

export default function useDefectTypesGridData(
  options: UseDefectTypesGridDataOptions,
): UseDefectTypesGridDataReturn {
  const { t } = useI18n()
  const { selectedClient, defectTypes, loadDefectTypes, notify, onConfirmDelete } =
    options

  const errorDetail = (e: unknown, fallback: string): string => {
    const ax = e as { response?: { data?: { detail?: string } }; message?: string }
    return ax?.response?.data?.detail || ax?.message || fallback
  }

  const requiredFieldsPresent = (row: DefectTypeGridRow): boolean => {
    return Boolean(
      row.defect_code &&
        row.defect_name &&
        row.severity_default,
    )
  }

  const buildPayload = (row: DefectTypeGridRow) => ({
    defect_code: row.defect_code,
    defect_name: row.defect_name,
    description: row.description ?? '',
    category: row.category ?? '',
    severity_default: row.severity_default,
    industry_standard_code: row.industry_standard_code ?? '',
    sort_order: row.sort_order ?? 0,
    is_active: row.is_active !== false,
  })

  const addRow = (): void => {
    if (!selectedClient.value) {
      notify.showError(t('admin.defectTypes.selectClientFirst') || 'Select a client first')
      return
    }
    const newRow: DefectTypeGridRow = {
      _isNew: true,
      defect_code: '',
      defect_name: '',
      description: '',
      category: '',
      severity_default: 'MAJOR',
      industry_standard_code: '',
      sort_order: defectTypes.value.length + 1,
      is_active: true,
    }
    defectTypes.value = [newRow, ...defectTypes.value]
  }

  const removeNewRow = (row: DefectTypeGridRow): void => {
    defectTypes.value = defectTypes.value.filter((r) => r !== row)
  }

  const saveNewRow = async (row: DefectTypeGridRow): Promise<void> => {
    if (!selectedClient.value) return
    if (!requiredFieldsPresent(row)) {
      notify.showError(t('admin.defectTypes.fillRequiredFields') || 'Fill required fields first')
      return
    }
    row._isSaving = true
    try {
      await api.createDefectType({
        ...buildPayload(row),
        client_id: selectedClient.value,
      })
      notify.showSuccess(t('admin.defectTypes.defectTypeCreated'))
      await loadDefectTypes()
    } catch (error) {
      notify.showError(errorDetail(error, t('errors.general')))
    } finally {
      row._isSaving = false
    }
  }

  const onCellValueChanged = async (event: {
    data: DefectTypeGridRow
    oldValue?: unknown
    column?: { colId?: string }
  }): Promise<void> => {
    // New rows: do NOT autosave; operator clicks Save explicitly.
    if (event.data._isNew) return
    if (!event.data.defect_type_id) return

    event.data._isSaving = true
    try {
      await api.updateDefectType(event.data.defect_type_id, buildPayload(event.data))
      notify.showSuccess(t('admin.defectTypes.defectTypeUpdated'))
    } catch (error) {
      notify.showError(errorDetail(error, t('errors.general')))
      // Roll back the cell value by reloading from server.
      await loadDefectTypes()
    } finally {
      event.data._isSaving = false
    }
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('admin.defectTypes.defectCode'),
      field: 'defect_code',
      // Code is editable only on new rows (matches legacy `:disabled="isEditing"`).
      editable: (params) => Boolean(params.data._isNew),
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 130,
    },
    {
      headerName: t('admin.defectTypes.defectName'),
      field: 'defect_name',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 200,
    },
    {
      headerName: t('admin.defectTypes.description'),
      field: 'description',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      width: 220,
    },
    {
      headerName: t('admin.defectTypes.category'),
      field: 'category',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: CATEGORY_OPTIONS },
      width: 140,
    },
    {
      headerName: t('admin.defectTypes.defaultSeverity'),
      field: 'severity_default',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: SEVERITY_OPTIONS as unknown as string[] },
      cellRenderer: renderSeverityChip,
      width: 130,
    },
    {
      headerName: t('admin.defectTypes.industryStandardCode'),
      field: 'industry_standard_code',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 150,
    },
    {
      headerName: t('admin.defectTypes.sortOrder'),
      field: 'sort_order',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      width: 110,
    },
    {
      headerName: t('common.active'),
      field: 'is_active',
      editable: true,
      cellEditor: 'agCheckboxCellEditor',
      cellRenderer: (params) =>
        renderCheckmark(params.data.is_active !== false),
      width: 90,
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
        }),
      width: 130,
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

const renderSeverityChip = (params: { value?: unknown }): HTMLElement => {
  const value = String(params.value || 'MAJOR')
  const color = SEVERITY_COLORS[value] || SEVERITY_COLORS.MAJOR
  const span = document.createElement('span')
  span.textContent = value
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

const renderCheckmark = (value: boolean): HTMLElement => {
  const span = document.createElement('span')
  span.textContent = value ? '\u2713' : ''
  span.style.color = value ? 'var(--cds-support-success, #198038)' : 'inherit'
  return span
}

const renderActions = (
  params: { data: DefectTypeGridRow; rowIndex: number },
  handlers: {
    saveNewRow: (row: DefectTypeGridRow) => Promise<void>
    removeNewRow: (row: DefectTypeGridRow) => void
    onConfirmDelete: (row: DefectTypeGridRow) => void
  },
): HTMLElement => {
  const div = document.createElement('div')
  div.style.cssText = 'display: flex; gap: 4px;'
  if (params.data._isNew) {
    div.innerHTML = `
      <button class="ag-grid-save-btn" title="Save new row" style="
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
      ?.addEventListener('click', () => handlers.onConfirmDelete(params.data))
  }
  return div
}
