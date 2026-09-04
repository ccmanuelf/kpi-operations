/**
 * Inline-grid editing for the SHIFT master-data table.
 *
 * Backend alignment (`backend/routes/shifts.py`):
 *  - POST /shifts/ takes client_id, shift_name, start_time, end_time and
 *    returns `{ data, warnings }`. Overlapping shifts are ALLOWED; the backend
 *    reports them as soft warnings rather than rejecting.
 *  - PUT /shifts/{id} takes shift_name, start_time, end_time, is_active and
 *    returns the same envelope.
 *  - POST /shifts/check-overlap pre-validates a proposed window. It exists so
 *    the overlap can be raised BEFORE committing, which is what `confirmOverlap`
 *    below is for — the user is told and decides, matching the soft-validation
 *    the backend intends. Answering "no" cancels the save.
 *  - DELETE deactivates. Since reads are active-only, a deactivated shift then
 *    disappears from this screen and cannot be reactivated here.
 */
import { computed, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { invalidateReferenceType } from '@/services/api/reference'
import {
  createShift,
  updateShift,
  checkShiftOverlap,
  type OverlapInfo,
} from '@/services/api/shifts'
import type { ShiftRow } from './useShiftAdmin'

/**
 * Coerce operator input to the `HH:MM:SS` the API expects, or null if it is
 * not a time at all. Accepts `6:00`, `06:00` and `06:00:00`; rejects the
 * out-of-range values a plain text editor would otherwise send to Pydantic.
 */
export const normalizeTime = (value: unknown): string | null => {
  if (typeof value !== 'string') return null
  const match = value.trim().match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/)
  if (!match) return null
  const [h, m, s] = [Number(match[1]), Number(match[2]), Number(match[3] ?? 0)]
  if (h > 23 || m > 59 || s > 59) return null
  return [h, m, s].map((n) => String(n).padStart(2, '0')).join(':')
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean | ((_params: { data: ShiftRow }) => boolean)
  cellEditor?: string
  cellRenderer?: (_params: { data: ShiftRow; value?: unknown }) => HTMLElement
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
  hide?: boolean
}

interface SnackbarLike {
  showSuccess: (_m: string) => void
  showError: (_m: string) => void
  showWarning?: (_m: string) => void
}

interface UseShiftAdminGridDataOptions {
  selectedClient: Ref<string | number | null>
  shifts: Ref<ShiftRow[]>
  loadShifts: () => Promise<void>
  notify: SnackbarLike
  onConfirmDelete: (_row: ShiftRow) => void
  /** Resolves true to save anyway. Wired to a dialog by the view. */
  confirmOverlap: (_overlaps: OverlapInfo[]) => Promise<boolean>
  /** Show every client's shifts; adds a client column and blocks Add. */
  showAllClients: Ref<boolean>
}

export default function useShiftAdminGridData(options: UseShiftAdminGridDataOptions): {
  columnDefs: ComputedRef<ColumnDef[]>
  addRow: () => void
  removeNewRow: (_row: ShiftRow) => void
  saveNewRow: (_row: ShiftRow) => Promise<void>
  onCellValueChanged: (_event: { data: ShiftRow }) => Promise<void>
} {
  const { t } = useI18n()
  const {
    selectedClient,
    shifts,
    loadShifts,
    notify,
    onConfirmDelete,
    confirmOverlap,
    showAllClients,
  } = options

  const errorDetail = (e: unknown, fallback: string): string => {
    const ax = e as { response?: { data?: { detail?: string } }; message?: string }
    return ax?.response?.data?.detail || ax?.message || fallback
  }

  /** Surface the backend's soft-validation instead of swallowing it. */
  const reportWarnings = (warnings: string[] | undefined): void => {
    if (!warnings?.length) return
    const show = notify.showWarning ?? notify.showError
    show(warnings.join(' '))
  }

  const addRow = (): void => {
    if (!selectedClient.value) {
      notify.showError(t('admin.shifts.selectClientFirst'))
      return
    }
    shifts.value = [
      {
        _isNew: true,
        shift_name: '',
        start_time: '',
        end_time: '',
        is_active: true,
        client_id: String(selectedClient.value),
      },
      ...shifts.value,
    ]
  }

  const removeNewRow = (row: ShiftRow): void => {
    shifts.value = shifts.value.filter((r) => r !== row)
  }

  const saveNewRow = async (row: ShiftRow): Promise<void> => {
    if (!selectedClient.value) return
    // Re-entrancy guard: the Save button stays clickable through the overlap
    // dialog and the POST, so a double click would create the shift twice.
    if (row._isSaving) return
    const start = normalizeTime(row.start_time)
    const end = normalizeTime(row.end_time)
    if (!row.shift_name || !start || !end) {
      notify.showError(t('admin.shifts.fillRequiredFields'))
      return
    }

    row._isSaving = true
    try {
      // Pre-validate, so the overlap is raised before the row is committed.
      const { data: overlap } = await checkShiftOverlap({
        client_id: String(selectedClient.value),
        start_time: start,
        end_time: end,
      })
      if (overlap.has_overlaps && !(await confirmOverlap(overlap.overlaps))) return

      const { data } = await createShift({
        client_id: String(selectedClient.value),
        shift_name: row.shift_name,
        start_time: start,
        end_time: end,
      })
      reportWarnings(data.warnings)
      invalidateReferenceType('shifts')
      notify.showSuccess(t('admin.shifts.shiftCreated'))
      // Drop the local draft before reloading; the server copy replaces it.
      removeNewRow(row)
      await loadShifts()
    } catch (error) {
      notify.showError(errorDetail(error, t('errors.general')))
    } finally {
      row._isSaving = false
    }
  }

  const onCellValueChanged = async (event: { data: ShiftRow }): Promise<void> => {
    if (event.data._isNew) return
    if (!event.data.shift_id) return
    if (event.data._isSaving) return

    // shift_name is min_length=1 server-side; clearing the cell would 422.
    if (!event.data.shift_name) {
      notify.showError(t('admin.shifts.fillRequiredFields'))
      await loadShifts()
      return
    }
    const start = normalizeTime(event.data.start_time)
    const end = normalizeTime(event.data.end_time)
    if (!start || !end) {
      notify.showError(t('admin.shifts.invalidTime'))
      await loadShifts()
      return
    }

    event.data._isSaving = true
    try {
      const { data } = await updateShift(event.data.shift_id, {
        shift_name: event.data.shift_name,
        start_time: start,
        end_time: end,
        is_active: event.data.is_active !== false,
      })
      reportWarnings(data.warnings)
      invalidateReferenceType('shifts')
      notify.showSuccess(t('admin.shifts.shiftUpdated'))
    } catch (error) {
      notify.showError(errorDetail(error, t('errors.general')))
      await loadShifts()
    } finally {
      event.data._isSaving = false
    }
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('admin.shifts.shiftName'),
      field: 'shift_name',
      editable: true,
      cellEditor: 'agTextCellEditor',
      pinned: 'left',
      width: 200,
    },
    {
      headerName: t('filters.client'),
      field: 'client_id',
      editable: false,
      // Only meaningful when the list spans clients; a client is fixed at
      // creation and no endpoint can move a shift between tenants.
      hide: !showAllClients.value,
      width: 150,
    },
    {
      headerName: t('admin.shifts.startTime'),
      field: 'start_time',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 130,
    },
    {
      headerName: t('admin.shifts.endTime'),
      field: 'end_time',
      editable: true,
      cellEditor: 'agTextCellEditor',
      width: 130,
    },
    {
      headerName: t('common.active'),
      field: 'is_active',
      // POST has no is_active, so it is read-only until the row exists.
      editable: (params) => !params.data._isNew,
      cellEditor: 'agCheckboxCellEditor',
      cellRenderer: (params) => renderCheckmark(params.data.is_active !== false),
      width: 90,
    },
    {
      headerName: t('common.actions'),
      field: '_actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params) =>
        renderActions(params, { saveNewRow, removeNewRow, onConfirmDelete }),
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
  params: { data: ShiftRow },
  handlers: {
    saveNewRow: (_row: ShiftRow) => Promise<void>
    removeNewRow: (_row: ShiftRow) => void
    onConfirmDelete: (_row: ShiftRow) => void
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
