/**
 * Inline-grid editing for one hold catalog (statuses OR reasons).
 *
 * Instantiated twice by the admin view — once per `kind` — because the two
 * catalogs are identical in shape apart from the code field's name
 * (`status_code` vs `reason_code`).
 *
 * Backend alignment (`backend/routes/hold_catalogs.py`):
 *  - POST accepts client_id, <kind>_code, display_name, sort_order. It does
 *    NOT accept is_active, so the code and active columns are editable only
 *    where the API can honour them — a new row is created active, and its
 *    code is fixed once saved.
 *  - PUT accepts display_name, is_active, sort_order only.
 *
 * Existing rows autosave via PUT on each cell change (Excel-style); new rows
 * accumulate locally until the operator clicks Save, then POST.
 *
 * The row-action renderer below mirrors the one in useDefectTypesGridData /
 * usePartOpportunitiesGridData / useScenariosGridData / useWorkOrderGridData;
 * that duplication predates this file and is left alone deliberately.
 */
import { computed, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  createHoldStatus,
  createHoldReason,
  updateHoldStatus,
  updateHoldReason,
} from '@/services/api/holdCatalogs'
import type { CatalogKind, HoldCatalogRow } from './useHoldCatalogAdmin'

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean | ((_params: { data: HoldCatalogRow }) => boolean)
  cellEditor?: string
  cellEditorParams?: { min?: number; precision?: number }
  cellRenderer?: (_params: { data: HoldCatalogRow; value?: unknown }) => HTMLElement
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

interface SnackbarLike {
  showSuccess: (_m: string) => void
  showError: (_m: string) => void
}

interface UseHoldCatalogGridDataOptions {
  kind: CatalogKind
  selectedClient: Ref<string | number | null>
  rows: Ref<HoldCatalogRow[]>
  loadCatalogs: () => Promise<void>
  notify: SnackbarLike
  onConfirmDelete: (_kind: CatalogKind, _row: HoldCatalogRow) => void
}

/** The code field's name differs between the two catalogs; nothing else does. */
export const codeField = (kind: CatalogKind): 'status_code' | 'reason_code' =>
  kind === 'status' ? 'status_code' : 'reason_code'

export default function useHoldCatalogGridData(
  options: UseHoldCatalogGridDataOptions,
): {
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeNewRow: (_row: HoldCatalogRow) => void
  saveNewRow: (_row: HoldCatalogRow) => Promise<void>
  onCellValueChanged: (_event: { data: HoldCatalogRow }) => Promise<void>
} {
  const { t } = useI18n()
  const { kind, selectedClient, rows, loadCatalogs, notify, onConfirmDelete } = options
  const field = codeField(kind)

  const errorDetail = (e: unknown, fallback: string): string => {
    const ax = e as { response?: { data?: { detail?: string } }; message?: string }
    return ax?.response?.data?.detail || ax?.message || fallback
  }

  const addRow = (): void => {
    if (!selectedClient.value) {
      notify.showError(t('admin.holdCatalogs.selectClientFirst'))
      return
    }
    const newRow: HoldCatalogRow = {
      _isNew: true,
      [field]: '',
      display_name: '',
      sort_order: rows.value.length + 1,
      is_active: true,
      is_default: false,
    }
    rows.value = [newRow, ...rows.value]
  }

  const removeNewRow = (row: HoldCatalogRow): void => {
    rows.value = rows.value.filter((r) => r !== row)
  }

  const saveNewRow = async (row: HoldCatalogRow): Promise<void> => {
    if (!selectedClient.value) return
    const code = row[field]
    if (!code || !row.display_name) {
      notify.showError(t('admin.holdCatalogs.fillRequiredFields'))
      return
    }
    row._isSaving = true
    try {
      const payload = {
        client_id: String(selectedClient.value),
        display_name: row.display_name,
        sort_order: row.sort_order ?? 0,
      }
      if (kind === 'status') {
        await createHoldStatus({ ...payload, status_code: code })
      } else {
        await createHoldReason({ ...payload, reason_code: code })
      }
      notify.showSuccess(t('admin.holdCatalogs.entryCreated'))
      await loadCatalogs()
    } catch (error) {
      notify.showError(errorDetail(error, t('errors.general')))
    } finally {
      row._isSaving = false
    }
  }

  const onCellValueChanged = async (event: { data: HoldCatalogRow }): Promise<void> => {
    // New rows: do NOT autosave; the operator clicks Save explicitly.
    if (event.data._isNew) return
    if (!event.data.catalog_id) return

    event.data._isSaving = true
    try {
      const patch = {
        display_name: event.data.display_name,
        is_active: event.data.is_active !== false,
        sort_order: event.data.sort_order ?? 0,
      }
      if (kind === 'status') {
        await updateHoldStatus(event.data.catalog_id, patch)
      } else {
        await updateHoldReason(event.data.catalog_id, patch)
      }
      notify.showSuccess(t('admin.holdCatalogs.entryUpdated'))
    } catch (error) {
      notify.showError(errorDetail(error, t('errors.general')))
      // Roll the cell back by re-reading the server's version.
      await loadCatalogs()
    } finally {
      event.data._isSaving = false
    }
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName:
        kind === 'status'
          ? t('admin.holdCatalogs.statusCode')
          : t('admin.holdCatalogs.reasonCode'),
      field,
      // The API has no way to rename a code, so it is fixed once saved.
      editable: (params) => Boolean(params.data._isNew),
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 190,
    },
    {
      headerName: t('admin.holdCatalogs.displayName'),
      field: 'display_name',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 220,
    },
    {
      headerName: t('admin.holdCatalogs.sortOrder'),
      field: 'sort_order',
      editable: true,
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      width: 110,
    },
    {
      headerName: t('common.active'),
      field: 'is_active',
      // POST cannot set this, so it stays read-only until the row exists.
      editable: (params) => !params.data._isNew,
      cellEditor: 'agCheckboxCellEditor',
      cellRenderer: (params) => renderCheckmark(params.data.is_active !== false),
      width: 90,
    },
    {
      headerName: t('admin.holdCatalogs.seeded'),
      field: 'is_default',
      editable: false,
      cellRenderer: (params) => renderCheckmark(params.data.is_default === true),
      width: 100,
    },
    {
      headerName: t('common.actions'),
      field: '_actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params) =>
        renderActions(params, kind, { saveNewRow, removeNewRow, onConfirmDelete }),
      width: 130,
      pinned: 'right',
    },
  ])

  return { columnDefs, addRow, removeNewRow, saveNewRow, onCellValueChanged }
}

const renderCheckmark = (value: boolean): HTMLElement => {
  const span = document.createElement('span')
  span.textContent = value ? '✓' : ''
  span.style.color = value ? 'var(--cds-support-success, #198038)' : 'inherit'
  return span
}

const renderActions = (
  params: { data: HoldCatalogRow },
  kind: CatalogKind,
  handlers: {
    saveNewRow: (_row: HoldCatalogRow) => Promise<void>
    removeNewRow: (_row: HoldCatalogRow) => void
    onConfirmDelete: (_kind: CatalogKind, _row: HoldCatalogRow) => void
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
      ?.addEventListener('click', () => handlers.onConfirmDelete(kind, params.data))
  }
  return div
}
