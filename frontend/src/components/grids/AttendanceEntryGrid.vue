<template>
  <v-card>
    <v-card-title class="bg-primary">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-account-clock</v-icon>
        <span class="text-h5">{{ $t('grids.attendance.title') }}</span>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Date and Shift Selector -->
      <v-row class="mb-3">
        <v-col cols="12" md="3">
          <v-text-field
            v-model="selectedDate"
            type="date"
            :label="$t('grids.attendance.attendanceDate')"
            variant="outlined"
            density="compact"
            :disabled="loading"
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="selectedShift"
            :items="shifts"
            item-title="shift_name"
            item-value="shift_id"
            :label="$t('filters.shift')"
            variant="outlined"
            density="compact"
            :disabled="loading"
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-btn
            color="primary"
            @click="loadEmployees"
            :loading="loading"
            :disabled="!selectedDate || !selectedShift"
            block
          >
            <v-icon left>mdi-account-multiple</v-icon>
            {{ $t('grids.attendance.loadEmployees') }}
          </v-btn>
        </v-col>
        <v-col cols="12" md="3">
          <v-btn
            color="success"
            @click="bulkSetStatus"
            :disabled="attendanceData.length === 0"
            block
          >
            <v-icon left>mdi-check-all</v-icon>
            {{ $t('grids.attendance.markAllPresent') }}
          </v-btn>
        </v-col>
      </v-row>

      <!-- Quick Stats -->
      <v-row class="mb-3" v-if="attendanceData.length > 0">
        <v-col cols="12" md="2">
          <v-chip color="success" label>
            <v-icon left small>mdi-check</v-icon>
            {{ $t('grids.attendance.present') }}: {{ statusCounts.present }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="2">
          <v-chip color="error" label>
            <v-icon left small>mdi-close</v-icon>
            {{ $t('grids.attendance.absent') }}: {{ statusCounts.absent }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="2">
          <v-chip color="warning" label>
            <v-icon left small>mdi-clock-alert</v-icon>
            {{ $t('grids.attendance.late') }}: {{ statusCounts.late }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="2">
          <v-chip color="info" label>
            <v-icon left small>mdi-calendar-remove</v-icon>
            {{ $t('grids.attendance.leave') }}: {{ statusCounts.leave }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="2">
          <v-chip color="purple" label>
            <v-icon left small>mdi-briefcase-clock</v-icon>
            {{ $t('grids.attendance.halfDay') }}: {{ statusCounts.halfDay }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="2">
          <v-chip label>
            {{ $t('grids.attendance.total') }}: {{ attendanceData.length }}
          </v-chip>
        </v-col>
      </v-row>

      <!-- Info Alert -->
      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        <strong>{{ $t('grids.bulkEntryTips') }}:</strong>
        {{ $t('grids.bulkEntryHints') }}
      </v-alert>

      <AGGridBase
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="attendanceData"
        height="600px"
        :pagination="true"
        :paginationPageSize="100"
        entry-type="attendance"
        @cell-value-changed="markRowAsChanged"
        @grid-ready="onGridReady"
        @rows-pasted="onRowsPasted"
      />

      <v-btn
        color="success"
        @click="saveAttendance"
        class="mt-3"
        :loading="saving"
        :disabled="!hasChanges"
        size="large"
        block
      >
        <v-icon left>mdi-content-save</v-icon>
        {{ $t('grids.attendance.saveRecords', { count: changedRowsCount }) }}
      </v-btn>
    </v-card-text>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      :title="$t('grids.attendance.confirmTitle')"
      :subtitle="$t('grids.attendance.confirmSubtitle')"
      :data="pendingData"
      :field-config="confirmationFieldConfig"
      :loading="saving"
      :warning-message="pendingRowsCount > 1 ? $t('grids.attendance.confirmWarning', { count: pendingRowsCount }) : ''"
      @confirm="onConfirmSave"
      @cancel="onCancelSave"
    />

    <!-- Paste Preview Dialog -->
    <PastePreviewDialog
      v-model="showPasteDialog"
      :parsed-data="parsedPasteData"
      :converted-rows="convertedPasteRows"
      :validation-result="pasteValidationResult"
      :column-mapping="pasteColumnMapping"
      :grid-columns="columnDefs"
      @confirm="onPasteConfirm"
      @cancel="onPasteCancel"
    />

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from './AGGridBase.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'
import PastePreviewDialog from '@/components/dialogs/PastePreviewDialog.vue'
import api from '@/services/api'
import { format } from 'date-fns'

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
  const counts = {
    present: 0,
    absent: 0,
    late: 0,
    leave: 0,
    halfDay: 0
  }

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
    cellEditor: 'agTextCellEditor',
    cellEditorParams: {
      placeholder: 'HH:MM'
    },
    width: 120
  },
  {
    headerName: t('grids.columns.clockOut'),
    field: 'clock_out',
    editable: true,
    cellEditor: 'agTextCellEditor',
    cellEditorParams: {
      placeholder: 'HH:MM'
    },
    width: 120
  },
  {
    headerName: t('grids.columns.lateMinutes'),
    field: 'late_minutes',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      precision: 0
    },
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
        'Sick Leave',
        'Personal Leave',
        'Family Emergency',
        'Medical Appointment',
        'No Show',
        'Unauthorized',
        'Vacation',
        'Other'
      ]
    },
    width: 180
  },
  {
    headerName: t('grids.columns.excused'),
    field: 'is_excused',
    editable: true,
    cellRenderer: (params) => {
      return params.value ? '✓' : ''
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

const onGridReady = (params) => {
  // Auto-fit columns
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
    // Load all active employees (simulated - adjust based on your API)
    const response = await api.get('/employees', {
      params: { shift_id: selectedShift.value, active: true }
    })

    // Check if attendance already exists for this date/shift
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

  // Auto-calculate late minutes if clock_in is provided
  if (event.colDef.field === 'clock_in' && event.data.clock_in) {
    // Simple logic: if clock_in > shift start time, mark as late
    // This would need to be enhanced with actual shift start times
    event.data.status = 'Late'
  }

  // Refresh the grid to update status counts
  gridRef.value?.refreshCells()
}

const bulkSetStatus = () => {
  const api = gridRef.value?.gridApi
  if (!api) return

  api.forEachNode(node => {
    node.data.status = 'Present'
    node.data._hasChanges = true
  })

  api.refreshCells()
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

  // Store pending rows and show confirmation for first row
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

// Paste handlers
const onRowsPasted = (pasteData) => {
  parsedPasteData.value = pasteData.parsedData
  convertedPasteRows.value = pasteData.convertedRows
  pasteValidationResult.value = pasteData.validationResult
  pasteColumnMapping.value = pasteData.columnMapping
  showPasteDialog.value = true
}

const onPasteConfirm = (rowsToAdd) => {
  const api = gridRef.value?.gridApi
  if (!api) return

  // Prepare rows with required fields
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

  api.applyTransaction({ add: preparedRows, addIndex: 0 })
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

const showSnackbar = (message, color = 'success') => {
  snackbar.value = { show: true, message, color }
}

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
</script>

<style scoped>
/* Component-specific styles */
</style>
