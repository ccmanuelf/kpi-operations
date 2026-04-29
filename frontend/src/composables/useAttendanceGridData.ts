/**
 * Composable for AttendanceEntryGrid script logic — reactive
 * state, column definitions, CRUD, paste handling, employee
 * loading, bulk status, status counts, read-back confirmation.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { format } from 'date-fns'

export interface AttendanceRow {
  attendance_id?: string | number
  employee_id?: string | number
  employee_name?: string
  department?: string
  date?: string
  shift_id?: string | number | null
  status?: string
  clock_in?: string
  clock_out?: string
  late_minutes?: number
  absence_reason?: string
  is_excused?: boolean
  notes?: string
  _hasChanges?: boolean
  _isNew?: boolean
  _isExisting?: boolean
  [key: string]: unknown
}

export interface ShiftRef {
  shift_id: string | number
  shift_name?: string
  [key: string]: unknown
}

interface AGGridApi {
  sizeColumnsToFit: () => void
  refreshCells: () => void
  applyTransaction: (params: { add?: AttendanceRow[]; addIndex?: number }) => void
  forEachNode: (cb: (node: { data: AttendanceRow }) => void) => void
}

interface AGGridRef {
  gridApi?: AGGridApi
  refreshCells?: () => void
}

interface SnackbarState {
  show: boolean
  message: string
  color: string
}

export interface ConfirmationField {
  key: string
  label: string
  type: 'text' | 'date' | 'number' | 'boolean'
  displayValue?: string | number
}

interface PasteData {
  parsedData: unknown
  convertedRows: AttendanceRow[]
  validationResult: unknown
  columnMapping: unknown
  [key: string]: unknown
}

interface UseAttendanceGridDataOptions {
  TimePickerCellEditor?: unknown
}

export default function useAttendanceGridData(
  { TimePickerCellEditor }: UseAttendanceGridDataOptions = {},
) {
  const { t } = useI18n()

  const gridRef = ref<AGGridRef | null>(null)
  const selectedDate = ref(format(new Date(), 'yyyy-MM-dd'))
  const selectedShift = ref<string | number | null>(null)
  const selectedLine = ref<string | number | null>(null)
  const shifts = ref<ShiftRef[]>([])
  const attendanceData = ref<AttendanceRow[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const snackbar = ref<SnackbarState>({ show: false, message: '', color: 'success' })

  const showConfirmDialog = ref(false)
  const pendingData = ref<AttendanceRow>({})
  const pendingRows = ref<AttendanceRow[]>([])

  const showPasteDialog = ref(false)
  const parsedPasteData = ref<unknown | null>(null)
  const convertedPasteRows = ref<AttendanceRow[]>([])
  const pasteValidationResult = ref<unknown | null>(null)
  const pasteColumnMapping = ref<unknown | null>(null)

  const pendingRowsCount = computed(() => pendingRows.value.length)

  const confirmationFieldConfig = computed<ConfirmationField[]>(() => {
    const shiftName =
      shifts.value.find((s) => s.shift_id === selectedShift.value)?.shift_name || 'N/A'

    return [
      { key: 'employee_id', label: 'Employee ID', type: 'text' },
      { key: 'employee_name', label: 'Employee Name', type: 'text' },
      { key: 'department', label: 'Department', type: 'text' },
      { key: 'date', label: 'Date', type: 'date', displayValue: selectedDate.value },
      { key: 'shift_id', label: 'Shift', type: 'text', displayValue: shiftName },
      { key: 'status', label: 'Status', type: 'text' },
      { key: 'clock_in', label: 'Clock In', type: 'text' },
      { key: 'clock_out', label: 'Clock Out', type: 'text' },
      { key: 'late_minutes', label: 'Late (minutes)', type: 'number' },
      { key: 'absence_reason', label: 'Absence Reason', type: 'text' },
      { key: 'is_excused', label: 'Excused', type: 'boolean' },
    ]
  })

  const hasChanges = computed(() => attendanceData.value.some((row) => row._hasChanges))

  const changedRowsCount = computed(
    () => attendanceData.value.filter((row) => row._hasChanges).length,
  )

  const statusCounts = computed(() => {
    const counts = { present: 0, absent: 0, late: 0, leave: 0, halfDay: 0 }

    attendanceData.value.forEach((row) => {
      const status = row.status?.toLowerCase()
      if (status === 'present') counts.present++
      else if (status === 'absent') counts.absent++
      else if (status === 'late') counts.late++
      else if (status === 'leave') counts.leave++
      else if (status === 'half day') counts.halfDay++
    })

    return counts
  })

  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.employeeId'),
      field: 'employee_id',
      editable: false,
      pinned: 'left' as const,
      width: 130,
      cellClass: 'font-weight-bold',
    },
    {
      headerName: t('grids.columns.employeeName'),
      field: 'employee_name',
      editable: false,
      pinned: 'left' as const,
      width: 200,
      cellClass: 'font-weight-bold',
    },
    {
      headerName: t('grids.columns.department'),
      field: 'department',
      editable: false,
      width: 150,
    },
    {
      headerName: t('grids.columns.status'),
      field: 'status',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: ['Present', 'Absent', 'Late', 'Half Day', 'Leave'] },
      cellClass: (params: { value?: string }) => {
        const classes: Record<string, string> = {
          Present: 'ag-cell-success ag-cell-bold',
          Absent: 'ag-cell-error ag-cell-bold',
          Late: 'ag-cell-warning ag-cell-bold',
          'Half Day': 'ag-cell-warning-light ag-cell-bold',
          Leave: 'ag-cell-purple ag-cell-bold',
        }
        return classes[params.value || ''] || ''
      },
      width: 130,
    },
    {
      headerName: t('grids.columns.clockIn'),
      field: 'clock_in',
      editable: true,
      cellEditor: TimePickerCellEditor || undefined,
      cellEditorPopup: false,
      width: 120,
      valueFormatter: (params: { value?: string }) => params.value || '--:--',
    },
    {
      headerName: t('grids.columns.clockOut'),
      field: 'clock_out',
      editable: true,
      cellEditor: TimePickerCellEditor || undefined,
      cellEditorPopup: false,
      width: 120,
      valueFormatter: (params: { value?: string }) => params.value || '--:--',
    },
    {
      headerName: t('grids.columns.lateMinutes'),
      field: 'late_minutes',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      cellClass: (params: { value?: number }) =>
        (params.value ?? 0) > 0 ? 'ag-cell-warning' : '',
      width: 120,
    },
    {
      headerName: t('grids.columns.absenceReason'),
      field: 'absence_reason',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: [
          'Sick Leave',
          'Personal Leave',
          'Family Emergency',
          'Medical Appointment',
          'No Show',
          'Unauthorized',
          'Vacation',
          'Other',
        ],
      },
      width: 180,
    },
    {
      headerName: t('grids.columns.excused'),
      field: 'is_excused',
      editable: true,
      cellRenderer: (params: { value?: boolean }) => (params.value ? '\u2713' : ''),
      cellEditor: 'agCheckboxCellEditor',
      cellStyle: { textAlign: 'center' },
      width: 100,
    },
    {
      headerName: t('grids.columns.notes'),
      field: 'notes',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      width: 250,
    },
  ])

  const showSnackbar = (message: string, color: string = 'success'): void => {
    snackbar.value = { show: true, message, color }
  }

  const onGridReady = (params: { api: AGGridApi }): void => {
    setTimeout(() => params.api.sizeColumnsToFit(), 100)
  }

  const loadEmployees = async (): Promise<void> => {
    if (!selectedDate.value || !selectedShift.value) {
      showSnackbar('Please select both date and shift', 'warning')
      return
    }

    loading.value = true
    try {
      const response = await api.get('/employees', {
        params: { shift_id: selectedShift.value, active: true },
      })

      const existingAttendance = await api.getAttendanceEntries({
        date: selectedDate.value,
        shift_id: selectedShift.value,
      })

      const existingMap = new Map(
        (existingAttendance.data as AttendanceRow[]).map((a) => [a.employee_id, a]),
      )

      attendanceData.value = (response.data as AttendanceRow[]).map((emp) => {
        const existing = existingMap.get(emp.employee_id)

        if (existing) {
          return {
            ...existing,
            employee_name: emp.employee_name || (emp as { name?: string }).name,
            department: emp.department,
            _isExisting: true,
          }
        }

        return {
          employee_id: emp.employee_id,
          employee_name: emp.employee_name || (emp as { name?: string }).name,
          department: emp.department,
          date: selectedDate.value,
          shift_id: selectedShift.value,
          status: 'Present',
          clock_in: '',
          clock_out: '',
          absence_reason: '',
          is_excused: false,
          late_minutes: 0,
          notes: '',
          _hasChanges: false,
          _isNew: true,
        }
      })

      showSnackbar(
        t('grids.attendance.loadedEmployees', { count: attendanceData.value.length }),
        'success',
      )
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading employees:', error)
      const ax = error as { message?: string }
      showSnackbar('Error loading employees: ' + (ax?.message || ''), 'error')
    } finally {
      loading.value = false
    }
  }

  const markRowAsChanged = (event: {
    data: AttendanceRow
    colDef: { field: string }
  }): void => {
    event.data._hasChanges = true

    if (event.colDef.field === 'clock_in' && event.data.clock_in) {
      event.data.status = 'Late'
    }

    gridRef.value?.refreshCells?.()
  }

  const bulkSetStatus = (): void => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    gridApi.forEachNode((node) => {
      node.data.status = 'Present'
      node.data._hasChanges = true
    })

    gridApi.refreshCells()
    showSnackbar(t('grids.attendance.markedPresent'), 'success')
  }

  const saveAttendance = async (): Promise<void> => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const changedRows: AttendanceRow[] = []
    gridApi.forEachNode((node) => {
      if (node.data._hasChanges) changedRows.push(node.data)
    })

    if (changedRows.length === 0) {
      showSnackbar(t('grids.noChanges'), 'info')
      return
    }

    pendingRows.value = changedRows
    pendingData.value = changedRows[0]
    showConfirmDialog.value = true
  }

  const onConfirmSave = async (): Promise<void> => {
    showConfirmDialog.value = false
    saving.value = true

    let successCount = 0
    let errorCount = 0

    try {
      for (const row of pendingRows.value) {
        const data = {
          employee_id: row.employee_id,
          date: selectedDate.value,
          shift_id: selectedShift.value,
          status: row.status,
          clock_in: row.clock_in || null,
          clock_out: row.clock_out || null,
          late_minutes: row.late_minutes || 0,
          absence_reason: row.absence_reason || null,
          is_excused: row.is_excused || false,
          notes: row.notes || '',
        }

        try {
          if (row._isNew && !row._isExisting) {
            await api.createAttendanceEntry(data)
            successCount++
          } else if (row.attendance_id) {
            await api.updateAttendanceEntry(row.attendance_id, data)
            successCount++
          } else {
            await api.createAttendanceEntry(data)
            successCount++
          }

          row._hasChanges = false
          row._isNew = false
        } catch (err) {
          errorCount++
          // eslint-disable-next-line no-console
          console.error('Error saving attendance for employee:', row.employee_id, err)
        }
      }

      if (errorCount === 0) {
        showSnackbar(
          t('grids.attendance.savedRecords', { success: successCount }),
          'success',
        )
        attendanceData.value = []
      } else {
        showSnackbar(
          t('grids.attendance.savedWithErrors', {
            success: successCount,
            failed: errorCount,
          }),
          'warning',
        )
      }
    } catch (error) {
      const ax = error as { message?: string }
      showSnackbar('Error saving attendance: ' + (ax?.message || ''), 'error')
    } finally {
      saving.value = false
      pendingRows.value = []
      pendingData.value = {}
    }
  }

  const onCancelSave = (): void => {
    showConfirmDialog.value = false
    pendingRows.value = []
    pendingData.value = {}
    showSnackbar(t('grids.saveCancelled'), 'info')
  }

  const onRowsPasted = (pasteData: PasteData): void => {
    parsedPasteData.value = pasteData.parsedData
    convertedPasteRows.value = pasteData.convertedRows
    pasteValidationResult.value = pasteData.validationResult
    pasteColumnMapping.value = pasteData.columnMapping
    showPasteDialog.value = true
  }

  const onPasteConfirm = (rowsToAdd: Partial<AttendanceRow>[]): void => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const preparedRows: AttendanceRow[] = rowsToAdd.map((row) => ({
      attendance_id: `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      employee_id: row.employee_id || '',
      employee_name: row.employee_name || '',
      department: row.department || '',
      date: row.date || selectedDate.value,
      shift_id: row.shift_id || selectedShift.value,
      status: row.status || 'Present',
      clock_in: row.clock_in || '',
      clock_out: row.clock_out || '',
      late_minutes: row.late_minutes || 0,
      absence_reason: row.absence_reason || '',
      is_excused: row.is_excused || false,
      notes: row.notes || '',
      _hasChanges: true,
      _isNew: true,
    }))

    gridApi.applyTransaction({ add: preparedRows, addIndex: 0 })
    showPasteDialog.value = false
    showSnackbar(t('paste.rowsAdded', { count: preparedRows.length }), 'success')
  }

  const onPasteCancel = (): void => {
    showPasteDialog.value = false
    parsedPasteData.value = null
    convertedPasteRows.value = []
    pasteValidationResult.value = null
    pasteColumnMapping.value = null
  }

  onMounted(async () => {
    try {
      const response = await api.getShifts()
      shifts.value = response.data
      if (shifts.value.length > 0) {
        selectedShift.value = shifts.value[0].shift_id
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading shifts:', error)
      showSnackbar('Error loading shifts', 'error')
    }
  })

  return {
    gridRef,
    selectedDate,
    selectedShift,
    selectedLine,
    shifts,
    attendanceData,
    loading,
    saving,
    snackbar,
    showConfirmDialog,
    pendingData,
    pendingRowsCount,
    confirmationFieldConfig,
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    hasChanges,
    changedRowsCount,
    statusCounts,
    columnDefs,
    onGridReady,
    loadEmployees,
    markRowAsChanged,
    bulkSetStatus,
    saveAttendance,
    onConfirmSave,
    onCancelSave,
    onRowsPasted,
    onPasteConfirm,
    onPasteCancel,
  }
}
