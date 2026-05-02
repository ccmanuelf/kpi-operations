/**
 * Composable for FloatingPoolManagement inline-grid editing —
 * Group H Surface #21.
 *
 * Each row is a pool entry; pool membership is set elsewhere (employee
 * admin), so this surface intentionally has no "Add Row" path. The
 * operator's job here is to assign / unassign / re-tune existing pool
 * entries.
 *
 * Inline-edit policy:
 *   - current_assignment (Client) — agSelectCellEditor against the
 *     loaded client list. Empty/clear value triggers /unassign;
 *     non-empty triggers /assign (which creates or replaces the
 *     assignment with the row's current dates + notes).
 *   - available_from / available_to — agDateStringCellEditor; on edit
 *     for an assigned row, re-fires /assign (legacy "edit" semantics —
 *     the legacy dialog also re-POSTed /assign). For unassigned rows
 *     the change is local-only (no endpoint to set window without a
 *     client).
 *   - notes — agLargeTextCellEditor popup.
 *
 * Quick-action button column:
 *   - Unassign (only when current_assignment is set).
 *
 * Backend alignment:
 *   - POST /floating-pool/assign  (FloatingPoolAssignmentRequest:
 *     employee_id, client_id, available_from, available_to, notes)
 *   - POST /floating-pool/unassign (FloatingPoolUnassignmentRequest:
 *     pool_id)
 */
import { computed, type ComputedRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'

export interface FloatingPoolGridRow {
  pool_id?: string | number | null
  employee_id?: string | number
  employee_code?: string
  employee_name?: string
  position?: string
  current_assignment?: string | number | null
  available_from?: string | null
  available_to?: string | null
  notes?: string | null
  _isSaving?: boolean
  [key: string]: unknown
}

export interface ClientOption {
  client_id: string | number
  name?: string
}

interface ColumnDef {
  headerName?: string
  field?: string
  editable?: boolean | ((params: { data: FloatingPoolGridRow }) => boolean)
  cellEditor?: string
  cellEditorPopup?: boolean
  cellEditorParams?: {
    values?: (string | number | null)[]
    formatValue?: (v: unknown) => string
    rows?: number
    cols?: number
  }
  cellRenderer?: (params: {
    data: FloatingPoolGridRow
    rowIndex: number
    value?: unknown
  }) => HTMLElement
  valueGetter?: (params: { data: FloatingPoolGridRow }) => unknown
  valueFormatter?: (params: { value?: unknown; data?: FloatingPoolGridRow }) => string
  width?: number
  pinned?: 'left' | 'right'
  sortable?: boolean
  filter?: boolean
}

interface SnackbarLike {
  showSuccess?: (m: string) => void
  showError?: (m: string) => void
  show?: (m: string, color?: string) => void
}

interface UseFloatingPoolGridDataOptions {
  entries: Ref<FloatingPoolGridRow[]>
  clientOptions: Ref<ClientOption[]> | ComputedRef<ClientOption[]>
  fetchData: () => Promise<void> | void
  notify: SnackbarLike
}

interface UseFloatingPoolGridDataReturn {
  columnDefs: ComputedRef<ColumnDef[]>
  onCellValueChanged: (event: {
    data: FloatingPoolGridRow
    column?: { colId?: string }
    colDef?: { field?: string }
    oldValue?: unknown
    newValue?: unknown
  }) => Promise<void>
  unassignRow: (row: FloatingPoolGridRow) => Promise<void>
}

const errorDetail = (e: unknown, fallback: string): string => {
  const ax = e as { response?: { data?: { detail?: string } }; message?: string }
  return ax?.response?.data?.detail || ax?.message || fallback
}

const notifySuccess = (notify: SnackbarLike, msg: string): void => {
  if (notify.showSuccess) notify.showSuccess(msg)
  else if (notify.show) notify.show(msg, 'success')
}

const notifyError = (notify: SnackbarLike, msg: string): void => {
  if (notify.showError) notify.showError(msg)
  else if (notify.show) notify.show(msg, 'error')
}

const formatDateTime = (value: unknown): string => {
  if (!value) return '-'
  const d = new Date(String(value))
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString()
}

export default function useFloatingPoolGridData(
  options: UseFloatingPoolGridDataOptions,
): UseFloatingPoolGridDataReturn {
  const { t } = useI18n()
  // `entries` is part of the options surface for caller symmetry, but
  // the composable doesn't read from it directly — fetchData() owns
  // the refresh path after every mutation.
  const { clientOptions, fetchData, notify } = options

  const clientLookup = computed(() => {
    const map = new Map<string, string>()
    clientOptions.value.forEach((c) => {
      map.set(String(c.client_id), c.name || String(c.client_id))
    })
    return map
  })

  const callAssign = async (row: FloatingPoolGridRow): Promise<void> => {
    if (!row.employee_id) {
      notifyError(notify, t('admin.floatingPool.errors.assignFailed'))
      return
    }
    if (!row.current_assignment) {
      notifyError(notify, t('admin.floatingPool.selectClientRequired'))
      return
    }
    row._isSaving = true
    try {
      await api.post('/floating-pool/assign', {
        employee_id: row.employee_id,
        client_id: row.current_assignment,
        available_from: row.available_from || null,
        available_to: row.available_to || null,
        notes: row.notes || null,
      })
      notifySuccess(notify, t('admin.floatingPool.assignmentSuccess'))
      await fetchData()
    } catch (error) {
      notifyError(notify, errorDetail(error, t('admin.floatingPool.errors.assignFailed')))
      await fetchData()
    } finally {
      row._isSaving = false
    }
  }

  const callUnassign = async (row: FloatingPoolGridRow): Promise<void> => {
    if (!row.pool_id) {
      notifyError(notify, t('admin.floatingPool.errors.noPoolId'))
      return
    }
    row._isSaving = true
    try {
      await api.post('/floating-pool/unassign', { pool_id: row.pool_id })
      notifySuccess(notify, t('admin.floatingPool.unassignmentSuccess'))
      await fetchData()
    } catch (error) {
      notifyError(notify, errorDetail(error, t('admin.floatingPool.errors.unassignFailed')))
      await fetchData()
    } finally {
      row._isSaving = false
    }
  }

  const onCellValueChanged = async (event: {
    data: FloatingPoolGridRow
    column?: { colId?: string }
    colDef?: { field?: string }
    oldValue?: unknown
    newValue?: unknown
  }): Promise<void> => {
    const field = event.colDef?.field || event.column?.colId
    const row = event.data
    if (!row || !field) return

    if (field === 'current_assignment') {
      const oldHadValue = Boolean(event.oldValue)
      const newHasValue = Boolean(event.newValue)
      if (newHasValue) {
        await callAssign(row)
      } else if (oldHadValue && !newHasValue) {
        await callUnassign(row)
      }
      return
    }

    // Date or notes change. Only push to backend when the row already
    // has an assignment — there's no API to store a window/notes for an
    // unassigned pool entry from this surface (PUT /{pool_id} would
    // require the pool entry to exist, which it does only after assign).
    if (
      field === 'available_from'
      || field === 'available_to'
      || field === 'notes'
    ) {
      if (!row.current_assignment) return
      await callAssign(row)
    }
  }

  const unassignRow = async (row: FloatingPoolGridRow): Promise<void> => {
    await callUnassign(row)
  }

  const columnDefs = computed<ColumnDef[]>(() => {
    const clientValues: (string | number | null)[] = [
      null,
      ...clientOptions.value.map((c) => c.client_id),
    ]
    return [
      {
        headerName: t('admin.floatingPool.employeeId'),
        field: 'employee_id',
        editable: false,
        pinned: 'left',
        width: 110,
      },
      {
        headerName: t('admin.floatingPool.employeeName'),
        field: 'employee_name',
        editable: false,
        pinned: 'left',
        width: 200,
      },
      {
        headerName: t('admin.floatingPool.status'),
        field: '_status',
        editable: false,
        sortable: true,
        filter: false,
        valueGetter: (params) =>
          params.data.current_assignment ? 'ASSIGNED' : 'AVAILABLE',
        cellRenderer: (params) =>
          renderStatusChip(
            params.data.current_assignment ? 'ASSIGNED' : 'AVAILABLE',
            t,
          ),
        width: 130,
      },
      {
        headerName: t('admin.floatingPool.assignedTo'),
        field: 'current_assignment',
        editable: true,
        cellEditor: 'agSelectCellEditor',
        cellEditorParams: {
          values: clientValues,
          formatValue: (v: unknown) => {
            if (!v) return t('admin.floatingPool.notAssigned')
            return clientLookup.value.get(String(v)) || String(v)
          },
        },
        valueFormatter: (params) => {
          if (!params.value) return t('admin.floatingPool.notAssigned')
          return clientLookup.value.get(String(params.value)) || String(params.value)
        },
        width: 200,
      },
      {
        headerName: t('admin.floatingPool.availableFrom'),
        field: 'available_from',
        editable: true,
        cellEditor: 'agDateStringCellEditor',
        valueFormatter: (params) => formatDateTime(params.value),
        width: 180,
      },
      {
        headerName: t('admin.floatingPool.availableTo'),
        field: 'available_to',
        editable: true,
        cellEditor: 'agDateStringCellEditor',
        valueFormatter: (params) => formatDateTime(params.value),
        width: 180,
      },
      {
        headerName: t('admin.floatingPool.notes'),
        field: 'notes',
        editable: true,
        cellEditor: 'agLargeTextCellEditor',
        cellEditorPopup: true,
        cellEditorParams: { rows: 3, cols: 50 },
        width: 220,
      },
      {
        headerName: t('admin.floatingPool.actions'),
        field: '_actions',
        editable: false,
        sortable: false,
        filter: false,
        cellRenderer: (params) => renderActions(params, { unassignRow, t }),
        width: 130,
        pinned: 'right',
      },
    ]
  })

  return {
    columnDefs,
    onCellValueChanged,
    unassignRow,
  }
}

const renderStatusChip = (status: string, t: (k: string) => string): HTMLElement => {
  const span = document.createElement('span')
  const isAssigned = status === 'ASSIGNED'
  span.textContent = isAssigned
    ? t('admin.floatingPool.assigned')
    : t('admin.floatingPool.available')
  span.style.cssText = `
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    color: white;
    background: ${isAssigned ? '#ed6c02' : '#2e7d32'};
  `
  return span
}

const renderActions = (
  params: { data: FloatingPoolGridRow; rowIndex: number },
  ctx: {
    unassignRow: (row: FloatingPoolGridRow) => Promise<void>
    t: (k: string) => string
  },
): HTMLElement => {
  const div = document.createElement('div')
  div.style.cssText = 'display: flex; gap: 4px;'
  if (!params.data.current_assignment) {
    const note = document.createElement('span')
    note.textContent = '—'
    note.style.color = '#9e9e9e'
    div.appendChild(note)
    return div
  }
  div.innerHTML = `
    <button class="ag-grid-unassign-btn" title="${ctx.t('admin.floatingPool.unassign')}" style="
      background: #ed6c02;
      color: white;
      border: none;
      padding: 2px 8px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 11px;
      font-weight: 600;
    ">${ctx.t('admin.floatingPool.unassign')}</button>
  `
  div
    .querySelector('.ag-grid-unassign-btn')
    ?.addEventListener('click', () => ctx.unassignRow(params.data))
  return div
}
