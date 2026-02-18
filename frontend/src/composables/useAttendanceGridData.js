/**
 * Composable for AttendanceEntryGrid script logic.
 *
 * Encapsulates reactive state, column definitions, CRUD operations,
 * paste handling, employee loading, bulk status, status counts,
 * and read-back confirmation for the attendance entry grid.
 *
 * API dependency: @/services/api (direct, no store)
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { format } from 'date-fns'

export default function useAttendanceGridData({ TimePickerCellEditor } = {}) {
  const { t } = useI18n()

  const gridRef = ref(null)
  const selectedDate = ref(format(new Date(), 'yyyy-MM-dd'))
  const selectedShift = ref(null)
  const shifts = ref([])
  const attendanceData = ref([])
  const loading = ref(false)
  const saving = ref(false)
  const snackbar = ref({ show: false, message: '', color: 'success' })

  // Read-back confirmation state
  const showConfirmDialog = ref(false)
  const pendingData = ref({})
  const pendingRows = ref([])

  // Paste preview state
  const showPasteDialog = ref(false)
  const parsedPasteData = ref(null)
  const convertedPasteRows = ref([])
  const pasteValidationResult = ref(null)
  const pasteColumnMapping = ref(null)

  const pendingRowsCount = computed(() => pendingRows.value.length)

  // Field configuration for confirmation dialog
  const confirmationFieldConfig = computed(() => {
    const shiftName = shifts.value.find(s => s.shift_id === selectedShift.value)?.shift_name || 'N/A'

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
      { key: 'is_excused', label: 'Excused', type: 'boolean' }
    ]
  })

  // Track changed rows
  const hasChanges = computed(() => {
    return attendanceData.value.some(row => row._hasChanges)
  })

  const changedRowsCount = computed(() => {
    return attendanceData.value.filter(row => row._hasChanges).length
  })

  // Status counts for quick stats
  const statusCounts = computed(() => {
    const counts = { present: 0, absent: 0, late: 0, leave: 0, halfDay: 0 }

    attendanceData.value.forEach(row => {
      const status = row.status?.toLowerCase()
      if (status === 'present') counts.present++
      else if (status === 'absent') counts.absent++
      else if (status === 'late') counts.late++
      else if (status === 'leave') counts.leave++
      else if (status === 'half day') counts.halfDay++
    })

    return counts
  })

  // Column definitions
  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.employeeId'),
      field: 'employee_id',
      editable: false,
      pinned: 'left',
      width: 130,
      cellClass: 'font-weight-bold'
    },
    {
      headerName: t('grids.columns.employeeName'),
      field: 'employee_name',
      editable: false,
      pinned: 'left',
      width: 200,
      cellClass: 'font-weight-bold'
    },
    {
      headerName: t('grids.columns.department'),
      field: 'department',
      editable: false,
      width: 150
    },
    {
      headerName: t('grids.columns.status'),
      field: 'status',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: ['Present', 'Absent', 'Late', 'Half Day', 'Leave']
      },
      cellStyle: (params) => {
        const statusColors = {
          'Present': { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' },
          'Absent': { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' },
          'Late': { backgroundColor: '#fff3e0', color: '#f57c00', fontWeight: 'bold' },
          'Half Day': { backgroundColor: '#fff9c4', color: '#f57f17', fontWeight: 'bold' },
          'Leave': { backgroundColor: '#f3e5f5', color: '#7b1fa2', fontWeight: 'bold' }
        }
        return statusColors[params.value] || {}
      },
      width: 130
    },
    {
      headerName: t('grids.columns.clockIn'),
      field: 'clock_in',
      editable: true,
      cellEditor: TimePickerCellEditor || undefined,
      cellEditorPopup: false,
      width: 120,
      valueFormatter: (params) => params.value || '--:--'
    },
    {
      headerName: t('grids.columns.clockOut'),
      field: 'clock_out',
      editable: true,
      cellEditor: TimePickerCellEditor || undefined,
      cellEditorPopup: false,
      width: 120,
      valueFormatter: (params) => params.value || '--:--'
    },
    {
      headerName: t('grids.columns.lateMinutes'),
      field: 'late_minutes',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      cellStyle: (params) => {
        return params.value > 0 ? { backgroundColor: '#fff3e0', color: '#f57c00' } : {}
      },
      width: 120
    },
    {
      headerName: t('grids.columns.absenceReason'),
      field: 'absence_reason',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: [
          'Sick Leave', 'Personal Leave', 'Family Emergency',
          'Medical Appointment', 'No Show', 'Unauthorized',
          'Vacation', 'Other'
        ]
      },
      width: 180
    },
    {
      headerName: t('grids.columns.excused'),
      field: 'is_excused',
      editable: true,
      cellRenderer: (params) => {
        return params.value ? '\u2713' : ''
      },
      cellEditor: 'agCheckboxCellEditor',
      cellStyle: { textAlign: 'center' },
      width: 100
    },
    {
      headerName: t('grids.columns.notes'),
      field: 'notes',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      width: 250
    }
  ])

  // --- Methods ---

  const onGridReady = (params) => {
    setTimeout(() => {
      params.api.sizeColumnsToFit()
    }, 100)
  }

  const loadEmployees = async () => {
    if (!selectedDate.value || !selectedShift.value) {
      showSnackbar('Please select both date and shift', 'warning')
      return
    }

    loading.value = true
    try {
      const response = await api.get('/employees', {
        params: { shift_id: selectedShift.value, active: true }
      })

      const existingAttendance = await api.getAttendanceEntries({
        date: selectedDate.value,
        shift_id: selectedShift.value
      })

      const existingMap = new Map(
        existingAttendance.data.map(a => [a.employee_id, a])
      )

      attendanceData.value = response.data.map(emp => {
        const existing = existingMap.get(emp.employee_id)

        if (existing) {
          return {
            ...existing,
            employee_name: emp.full_name || emp.name,
            department: emp.department,
            _isExisting: true
          }
        }

        return {
          employee_id: emp.employee_id,
          employee_name: emp.full_name || emp.name,
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
          _isNew: true
        }
      })

      showSnackbar(t('grids.attendance.loadedEmployees', { count: attendanceData.value.length }), 'success')
    } catch (error) {
      console.error('Error loading employees:', error)
      showSnackbar('Error loading employees: ' + error.message, 'error')
    } finally {
      loading.value = false
    }
  }

  const markRowAsChanged = (event) => {
    event.data._hasChanges = true

    if (event.colDef.field === 'clock_in' && event.data.clock_in) {
      event.data.status = 'Late'
    }

    gridRef.value?.refreshCells()
  }

  const bulkSetStatus = () => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    gridApi.forEachNode(node => {
      node.data.status = 'Present'
      node.data._hasChanges = true
    })

    gridApi.refreshCells()
    showSnackbar(t('grids.attendance.markedPresent'), 'success')
  }

  const saveAttendance = async () => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const changedRows = []
    gridApi.forEachNode(node => {
      if (node.data._hasChanges) {
        changedRows.push(node.data)
      }
    })

    if (changedRows.length === 0) {
      showSnackbar(t('grids.noChanges'), 'info')
      return
    }

    pendingRows.value = changedRows
    pendingData.value = changedRows[0]
    showConfirmDialog.value = true
  }

  const onConfirmSave = async () => {
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
          notes: row.notes || ''
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
          console.error('Error saving attendance for employee:', row.employee_id, err)
        }
      }

      if (errorCount === 0) {
        showSnackbar(t('grids.attendance.savedRecords', { success: successCount }), 'success')
        attendanceData.value = []
      } else {
        showSnackbar(t('grids.attendance.savedWithErrors', { success: successCount, failed: errorCount }), 'warning')
      }
    } catch (error) {
      showSnackbar('Error saving attendance: ' + error.message, 'error')
    } finally {
      saving.value = false
      pendingRows.value = []
      pendingData.value = {}
    }
  }

  const onCancelSave = () => {
    showConfirmDialog.value = false
    pendingRows.value = []
    pendingData.value = {}
    showSnackbar(t('grids.saveCancelled'), 'info')
  }

  const showSnackbar = (message, color = 'success') => {
    snackbar.value = { show: true, message, color }
  }

  // Paste handlers
  const onRowsPasted = (pasteData) => {
    parsedPasteData.value = pasteData.parsedData
    convertedPasteRows.value = pasteData.convertedRows
    pasteValidationResult.value = pasteData.validationResult
    pasteColumnMapping.value = pasteData.columnMapping
    showPasteDialog.value = true
  }

  const onPasteConfirm = (rowsToAdd) => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const preparedRows = rowsToAdd.map(row => ({
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
      _isNew: true
    }))

    gridApi.applyTransaction({ add: preparedRows, addIndex: 0 })
    showPasteDialog.value = false
    showSnackbar(t('paste.rowsAdded', { count: preparedRows.length }), 'success')
  }

  const onPasteCancel = () => {
    showPasteDialog.value = false
    parsedPasteData.value = null
    convertedPasteRows.value = []
    pasteValidationResult.value = null
    pasteColumnMapping.value = null
  }

  // Lifecycle
  onMounted(async () => {
    try {
      const response = await api.getShifts()
      shifts.value = response.data
      if (shifts.value.length > 0) {
        selectedShift.value = shifts.value[0].shift_id
      }
    } catch (error) {
      console.error('Error loading shifts:', error)
      showSnackbar('Error loading shifts', 'error')
    }
  })

  return {
    // Refs
    gridRef,
    selectedDate,
    selectedShift,
    shifts,
    attendanceData,
    loading,
    saving,
    snackbar,
    // Confirmation
    showConfirmDialog,
    pendingData,
    pendingRowsCount,
    confirmationFieldConfig,
    // Paste
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    // Data
    hasChanges,
    changedRowsCount,
    statusCounts,
    columnDefs,
    // Methods
    onGridReady,
    loadEmployees,
    markRowAsChanged,
    bulkSetStatus,
    saveAttendance,
    onConfirmSave,
    onCancelSave,
    onRowsPasted,
    onPasteConfirm,
    onPasteCancel
  }
}
