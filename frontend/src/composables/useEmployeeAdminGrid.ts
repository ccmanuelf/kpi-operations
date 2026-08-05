/**
 * Composable for AdminEmployees inline-grid editing — the Employees admin
 * surface (Cycle 3 PR-A, Task 7). This surface was the missing "employee
 * admin" referenced by FloatingPoolManagement.vue's docstring ("pool
 * membership is set elsewhere") and by docs/audit/entry-surface-inventory.md
 * — no frontend page previously exposed general Employee fields.
 *
 * Scope is intentionally lean: employee_code/employee_name/department are
 * read-only reference columns; labor_class is the only editable field,
 * following the same inline-cell-edit-to-PUT pattern as
 * useFloatingPoolGridData.ts's current_assignment column (edit fires
 * immediately, no separate Save button).
 *
 * Backend alignment: PUT /api/employees/{employee_id} (EmployeeUpdate.labor_class,
 * explicit null clears the override back to unclassified).
 */
import { computed, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { LABOR_CLASS_CODES, laborClassLabelKey } from '@/constants/laborTaxonomy'

export interface EmployeeGridRow {
  employee_id?: string | number
  employee_code?: string
  employee_name?: string
  department?: string | null
  labor_class?: string | null
  is_active?: number
  _isSaving?: boolean
  [key: string]: unknown
}

interface ColumnDef {
  headerName?: string
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: {
    values?: (string | null)[]
    formatValue?: (_v: unknown) => string
  }
  valueFormatter?: (_params: { value?: unknown }) => string
  width?: number
  pinned?: 'left' | 'right'
}

interface SnackbarLike {
  showSuccess?: (_m: string) => void
  showError?: (_m: string) => void
  show?: (_m: string, _color?: string) => void
}

interface UseEmployeeAdminGridOptions {
  fetchData: () => Promise<void> | void
  notify: SnackbarLike
}

interface UseEmployeeAdminGridReturn {
  columnDefs: ComputedRef<ColumnDef[]>
  onCellValueChanged: (_event: {
    data: EmployeeGridRow
    column?: { colId?: string }
    colDef?: { field?: string }
    newValue?: unknown
  }) => Promise<void>
  updateLaborClass: (_row: EmployeeGridRow, _value: string | null) => Promise<void>
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

export default function useEmployeeAdminGrid(
  options: UseEmployeeAdminGridOptions,
): UseEmployeeAdminGridReturn {
  const { t } = useI18n()
  const { fetchData, notify } = options

  const updateLaborClass = async (row: EmployeeGridRow, value: string | null): Promise<void> => {
    if (!row.employee_id) return
    row._isSaving = true
    try {
      await api.put(`/employees/${row.employee_id}`, { labor_class: value })
      notifySuccess(notify, t('admin.employees.updateSuccess'))
      await fetchData()
    } catch (error) {
      notifyError(notify, errorDetail(error, t('admin.employees.errors.updateFailed')))
      await fetchData()
    } finally {
      row._isSaving = false
    }
  }

  const onCellValueChanged = async (event: {
    data: EmployeeGridRow
    column?: { colId?: string }
    colDef?: { field?: string }
    newValue?: unknown
  }): Promise<void> => {
    const field = event.colDef?.field || event.column?.colId
    if (field !== 'labor_class') return
    await updateLaborClass(event.data, (event.newValue as string | null) || null)
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('admin.employees.employeeId'),
      field: 'employee_id',
      editable: false,
      pinned: 'left',
      width: 100,
    },
    {
      headerName: t('admin.employees.employeeCode'),
      field: 'employee_code',
      editable: false,
      pinned: 'left',
      width: 140,
    },
    {
      headerName: t('admin.employees.employeeName'),
      field: 'employee_name',
      editable: false,
      width: 220,
    },
    {
      headerName: t('admin.employees.department'),
      field: 'department',
      editable: false,
      width: 160,
    },
    {
      headerName: t('labor.laborClass'),
      field: 'labor_class',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: [null, ...LABOR_CLASS_CODES],
        formatValue: (v: unknown) =>
          v ? t(laborClassLabelKey(String(v))) : t('labor.unclassified'),
      },
      // Resting-value display: EMPTY for null (no-low-contrast-placeholder
      // rule — most rows are unclassified by default, so "Unclassified"
      // text on every row would read as noise, not signal).
      valueFormatter: (params: { value?: unknown }) =>
        params.value ? t(laborClassLabelKey(String(params.value))) : '',
      width: 160,
    },
  ])

  return { columnDefs, onCellValueChanged, updateLaborClass }
}
