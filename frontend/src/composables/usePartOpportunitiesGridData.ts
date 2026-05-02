/**
 * Composable for AdminPartOpportunities inline-grid editing — column
 * defs, autosave on cell change for existing rows, and explicit save
 * for new rows.
 *
 * Same Excel-style inline-edit pattern as useDefectTypesGridData
 * (Group E #14): existing rows PUT immediately on cell change; new
 * rows accumulate locally until the operator clicks the green Save
 * button in the row's actions column, then POST.
 */
import { computed, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

export const COMPLEXITY_OPTIONS: string[] = ['Simple', 'Standard', 'Complex', 'Very Complex']

export interface PartOpportunityGridRow {
  part_opportunities_id?: string | number
  part_number?: string
  opportunities_per_unit?: number
  part_description?: string
  complexity?: string
  client_id?: string | number | null
  notes?: string
  is_active?: boolean
  _isNew?: boolean
  _isSaving?: boolean
  [key: string]: unknown
}

export interface ClientOption {
  client_id: string | number
  client_name: string
  [key: string]: unknown
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean | ((params: { data: PartOpportunityGridRow }) => boolean)
  cellEditor?: string
  cellEditorParams?:
    | { values?: unknown[]; min?: number; max?: number; precision?: number }
    | (() => { values?: unknown[] })
  valueFormatter?: (params: { value?: unknown; data?: PartOpportunityGridRow }) => string
  cellRenderer?: (params: {
    data: PartOpportunityGridRow
    rowIndex: number
    value?: unknown
  }) => HTMLElement
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

interface SnackbarLike {
  showSuccess: (m: string) => void
  showError: (m: string) => void
}

interface UsePartOpportunitiesGridDataOptions {
  selectedClient: Ref<string | number | null>
  partOpportunities: Ref<PartOpportunityGridRow[]>
  clientOptions: Ref<ClientOption[]> | ComputedRef<ClientOption[]>
  loadPartOpportunities: () => Promise<void>
  notify: SnackbarLike
  onConfirmDelete: (row: PartOpportunityGridRow) => void
}

interface UsePartOpportunitiesGridDataReturn {
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeNewRow: (row: PartOpportunityGridRow) => void
  saveNewRow: (row: PartOpportunityGridRow) => Promise<void>
  onCellValueChanged: (event: {
    data: PartOpportunityGridRow
    column?: { colId?: string }
  }) => Promise<void>
}

const errorDetail = (e: unknown, fallback: string): string => {
  const ax = e as { response?: { data?: { detail?: string } }; message?: string }
  return ax?.response?.data?.detail || ax?.message || fallback
}

const requiredFieldsPresent = (row: PartOpportunityGridRow): boolean => {
  return Boolean(
    row.part_number &&
      row.client_id &&
      typeof row.opportunities_per_unit === 'number' &&
      row.opportunities_per_unit > 0,
  )
}

const buildPayload = (row: PartOpportunityGridRow) => ({
  part_number: row.part_number,
  opportunities_per_unit: row.opportunities_per_unit,
  part_description: row.part_description ?? '',
  complexity: row.complexity ?? '',
  client_id: row.client_id,
  notes: row.notes ?? '',
  is_active: row.is_active !== false,
})

export default function usePartOpportunitiesGridData(
  options: UsePartOpportunitiesGridDataOptions,
): UsePartOpportunitiesGridDataReturn {
  const { t } = useI18n()
  const {
    selectedClient,
    partOpportunities,
    clientOptions,
    loadPartOpportunities,
    notify,
    onConfirmDelete,
  } = options

  const addRow = (): void => {
    const newRow: PartOpportunityGridRow = {
      _isNew: true,
      part_number: '',
      opportunities_per_unit: 10,
      part_description: '',
      complexity: 'Standard',
      client_id: selectedClient.value ?? null,
      notes: '',
      is_active: true,
    }
    partOpportunities.value = [newRow, ...partOpportunities.value]
  }

  const removeNewRow = (row: PartOpportunityGridRow): void => {
    partOpportunities.value = partOpportunities.value.filter((r) => r !== row)
  }

  const saveNewRow = async (row: PartOpportunityGridRow): Promise<void> => {
    if (!requiredFieldsPresent(row)) {
      notify.showError(
        t('admin.fillRequiredFields') || 'Fill required fields first',
      )
      return
    }
    row._isSaving = true
    try {
      await api.post('/part-opportunities', buildPayload(row))
      notify.showSuccess(t('success.saved'))
      await loadPartOpportunities()
    } catch (error) {
      notify.showError(errorDetail(error, t('errors.general')))
    } finally {
      row._isSaving = false
    }
  }

  const onCellValueChanged = async (event: {
    data: PartOpportunityGridRow
    column?: { colId?: string }
  }): Promise<void> => {
    if (event.data._isNew) return
    if (!event.data.part_opportunities_id) return

    event.data._isSaving = true
    try {
      await api.put(
        `/part-opportunities/${event.data.part_opportunities_id}`,
        buildPayload(event.data),
      )
      notify.showSuccess(t('success.updated'))
    } catch (error) {
      notify.showError(errorDetail(error, t('errors.general')))
      // Roll back the cell value by reloading from server.
      await loadPartOpportunities()
    } finally {
      event.data._isSaving = false
    }
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('jobs.partNumber'),
      field: 'part_number',
      // Part number is editable only on new rows (matches legacy
      // `:disabled="isEditing"`).
      editable: (params) => Boolean(params.data._isNew),
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 140,
    },
    {
      headerName: t('admin.opportunitiesPerUnit'),
      field: 'opportunities_per_unit',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 1, precision: 0 },
      width: 150,
    },
    {
      headerName: t('admin.partDescription'),
      field: 'part_description',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 220,
    },
    {
      headerName: t('admin.complexity'),
      field: 'complexity',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: COMPLEXITY_OPTIONS },
      width: 130,
    },
    {
      headerName: t('filters.client'),
      field: 'client_id',
      // client_id is editable only on new rows (matches legacy
      // `:disabled="isEditing"`).
      editable: (params) => Boolean(params.data._isNew),
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: clientOptions.value.map((c) => c.client_id),
      }),
      valueFormatter: (params) => {
        const c = clientOptions.value.find((o) => o.client_id === params.value)
        return c?.client_name || String(params.value || '')
      },
      width: 160,
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

const renderCheckmark = (value: boolean): HTMLElement => {
  const span = document.createElement('span')
  span.textContent = value ? '\u2713' : ''
  span.style.color = value ? 'var(--cds-support-success, #198038)' : 'inherit'
  return span
}

const renderActions = (
  params: { data: PartOpportunityGridRow; rowIndex: number },
  handlers: {
    saveNewRow: (row: PartOpportunityGridRow) => Promise<void>
    removeNewRow: (row: PartOpportunityGridRow) => void
    onConfirmDelete: (row: PartOpportunityGridRow) => void
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
