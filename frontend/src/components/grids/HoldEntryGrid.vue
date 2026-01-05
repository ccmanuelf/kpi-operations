<template>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center bg-primary">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-pause-circle</v-icon>
        <span class="text-h5">Hold/Resume Entry - Excel-like Grid</span>
      </div>
      <div>
        <v-btn color="white" variant="outlined" @click="addNewHold" class="mr-2">
          <v-icon left>mdi-plus</v-icon>
          Add Hold
        </v-btn>
        <v-btn
          color="success"
          @click="saveChanges"
          :disabled="!hasUnsavedChanges"
          :loading="saving"
        >
          <v-icon left>mdi-content-save</v-icon>
          Save All ({{ unsavedChanges.size }})
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Keyboard shortcuts help -->
      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-keyboard</v-icon>
          <div>
            <strong>Excel-like Shortcuts:</strong>
            Tab (next cell) | Enter (move down) | Ctrl+C/V (copy/paste) | Delete (clear) |
            Ctrl+Z (undo) | F1 (help) | Click Resume button to mark hold as resumed
          </div>
        </div>
      </v-alert>

      <!-- Filter controls -->
      <v-row class="mb-3">
        <v-col cols="12" md="3">
          <v-text-field
            v-model="dateFilter"
            type="date"
            label="Filter by Hold Date"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="statusFilter"
            :items="['ACTIVE', 'RESUMED']"
            label="Filter by Status"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="reasonFilter"
            :items="holdReasons"
            label="Filter by Reason"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-btn color="primary" @click="applyFilters" block>
            <v-icon left>mdi-filter</v-icon>
            Apply Filters
          </v-btn>
        </v-col>
      </v-row>

      <AGGridBase
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="filteredEntries"
        height="600px"
        :pagination="true"
        :paginationPageSize="50"
        @grid-ready="onGridReady"
        @cell-value-changed="onCellValueChanged"
      />

      <!-- Summary stats -->
      <v-row class="mt-3">
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">Total Holds</div>
              <div class="text-h6">{{ filteredEntries.length }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" color="warning">
            <v-card-text>
              <div class="text-caption">Active Holds</div>
              <div class="text-h6">{{ activeCount }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" color="success">
            <v-card-text>
              <div class="text-caption">Resumed Holds</div>
              <div class="text-h6">{{ resumedCount }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" color="info">
            <v-card-text>
              <div class="text-caption">Avg Days on Hold</div>
              <div class="text-h6">{{ avgDaysOnHold.toFixed(1) }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- Resume Hold Dialog -->
    <v-dialog v-model="resumeDialog.show" max-width="600">
      <v-card>
        <v-card-title class="bg-primary">
          Resume Hold - {{ resumeDialog.hold?.work_order_number }}
        </v-card-title>
        <v-card-text class="pt-4">
          <v-row>
            <v-col cols="12">
              <v-text-field
                v-model="resumeDialog.actual_resume_date"
                type="datetime-local"
                label="Resume Date/Time *"
                variant="outlined"
                density="compact"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="resumeDialog.resumed_by_user_id"
                label="Resumed By User ID *"
                variant="outlined"
                density="compact"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="resumeDialog.resume_approved_at"
                type="datetime-local"
                label="Resume Approved At"
                variant="outlined"
                density="compact"
              />
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="resumeDialog.show = false">Cancel</v-btn>
          <v-btn color="success" @click="confirmResume">Resume Hold</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar for notifications -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useKPIStore } from '@/stores/kpiStore'
import { format, differenceInDays } from 'date-fns'
import AGGridBase from './AGGridBase.vue'

const kpiStore = useKPIStore()
const gridRef = ref(null)
const unsavedChanges = ref(new Set())
const saving = ref(false)
const snackbar = ref({ show: false, message: '', color: 'success' })
const resumeDialog = ref({
  show: false,
  hold: null,
  actual_resume_date: null,
  resumed_by_user_id: '',
  resume_approved_at: null
})

// Filters
const dateFilter = ref(null)
const statusFilter = ref(null)
const reasonFilter = ref(null)

const holdReasons = [
  'Quality Issue',
  'Material Defect',
  'Process Non-Conformance',
  'Customer Request',
  'Engineering Change',
  'Inspection Failure',
  'Supplier Issue',
  'Other'
]

const entries = computed(() => kpiStore.holdEntries || [])
const workOrders = computed(() => kpiStore.workOrders || [])
const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

// Filtered entries
const filteredEntries = ref([])

// Summary statistics
const activeCount = computed(() => {
  return filteredEntries.value.filter(e => !e.actual_resume_date).length
})

const resumedCount = computed(() => {
  return filteredEntries.value.filter(e => e.actual_resume_date).length
})

const avgDaysOnHold = computed(() => {
  if (filteredEntries.value.length === 0) return 0

  const totalDays = filteredEntries.value.reduce((sum, e) => {
    const startDate = new Date(e.placed_on_hold_date)
    const endDate = e.actual_resume_date ? new Date(e.actual_resume_date) : new Date()
    return sum + differenceInDays(endDate, startDate)
  }, 0)

  return totalDays / filteredEntries.value.length
})

// Column definitions
const columnDefs = [
  {
    headerName: 'Hold Date',
    field: 'placed_on_hold_date',
    editable: true,
    cellEditor: 'agDateStringCellEditor',
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd, yyyy') : ''
    },
    cellClass: 'font-weight-bold',
    pinned: 'left',
    width: 140,
    sort: 'desc'
  },
  {
    headerName: 'Work Order',
    field: 'work_order_id',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: () => ({
      values: workOrders.value.map(w => w.work_order_id)
    }),
    valueFormatter: (params) => {
      const wo = workOrders.value.find(w => w.work_order_id === params.value)
      return wo?.work_order_number || params.value || 'N/A'
    },
    width: 150
  },
  {
    headerName: 'Hold Reason',
    field: 'hold_reason',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: holdReasons
    },
    width: 200
  },
  {
    headerName: 'Status',
    field: 'status',
    editable: false,
    valueGetter: (params) => {
      return params.data.actual_resume_date ? 'RESUMED' : 'ACTIVE'
    },
    cellStyle: (params) => {
      return params.value === 'ACTIVE'
        ? { backgroundColor: '#fff3e0', color: '#f57c00', fontWeight: 'bold' }
        : { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' }
    },
    width: 130
  },
  {
    headerName: 'Expected Resume',
    field: 'expected_resume_date',
    editable: true,
    cellEditor: 'agDateStringCellEditor',
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd, yyyy') : ''
    },
    width: 150
  },
  {
    headerName: 'Actual Resume',
    field: 'actual_resume_date',
    editable: false,
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd, yyyy HH:mm') : 'Not Yet Resumed'
    },
    cellStyle: (params) => {
      return params.value ? { backgroundColor: '#e8f5e9', color: '#2e7d32' } : {}
    },
    width: 180
  },
  {
    headerName: 'Days on Hold',
    field: 'days_on_hold',
    editable: false,
    valueGetter: (params) => {
      const startDate = new Date(params.data.placed_on_hold_date)
      const endDate = params.data.actual_resume_date
        ? new Date(params.data.actual_resume_date)
        : new Date()
      return differenceInDays(endDate, startDate)
    },
    cellStyle: (params) => {
      const days = params.value || 0
      if (days > 7) return { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' }
      if (days > 3) return { backgroundColor: '#fff3e0', color: '#f57c00' }
      return {}
    },
    width: 130
  },
  {
    headerName: 'Resumed By',
    field: 'resumed_by_user_id',
    editable: false,
    width: 130
  },
  {
    headerName: 'Hold Approved',
    field: 'hold_approved_at',
    editable: true,
    cellEditor: 'agDateStringCellEditor',
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd HH:mm') : 'Pending'
    },
    width: 150
  },
  {
    headerName: 'Resume Approved',
    field: 'resume_approved_at',
    editable: false,
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd HH:mm') : 'N/A'
    },
    width: 150
  },
  {
    headerName: 'Actions',
    field: 'actions',
    editable: false,
    sortable: false,
    filter: false,
    cellRenderer: (params) => {
      const div = document.createElement('div')
      const isActive = !params.data.actual_resume_date

      div.innerHTML = `
        <div style="display: flex; gap: 4px;">
          ${isActive ? `
            <button class="ag-grid-resume-btn" style="
              background: #4caf50;
              color: white;
              border: none;
              padding: 4px 8px;
              border-radius: 4px;
              cursor: pointer;
              font-size: 12px;
            ">Resume</button>
          ` : ''}
          <button class="ag-grid-delete-btn" style="
            background: #c62828;
            color: white;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
          ">Delete</button>
        </div>
      `

      const resumeBtn = div.querySelector('.ag-grid-resume-btn')
      if (resumeBtn) {
        resumeBtn.addEventListener('click', () => {
          openResumeDialog(params.data)
        })
      }

      div.querySelector('.ag-grid-delete-btn').addEventListener('click', () => {
        deleteEntry(params.data)
      })

      return div
    },
    width: 150,
    pinned: 'right'
  }
]

const onGridReady = (params) => {
  // Auto-fit columns initially
  setTimeout(() => {
    params.api.sizeColumnsToFit()
  }, 100)
}

const onCellValueChanged = (event) => {
  // Mark row as unsaved
  const rowId = event.data.hold_id || event.node.id
  unsavedChanges.value.add(rowId)

  // Mark row data as changed
  event.data._hasChanges = true

  // Refresh cell to show visual indicator
  event.api.refreshCells({ rowNodes: [event.node], force: true })
}

const addNewHold = () => {
  const newHold = {
    hold_id: `temp_${Date.now()}`,
    work_order_id: workOrders.value[0]?.work_order_id || null,
    placed_on_hold_date: format(new Date(), 'yyyy-MM-dd'),
    hold_reason: 'Quality Issue',
    expected_resume_date: null,
    actual_resume_date: null,
    resumed_by_user_id: null,
    hold_approved_at: null,
    resume_approved_at: null,
    _isNew: true,
    _hasChanges: true
  }

  const api = gridRef.value?.gridApi
  if (api) {
    api.applyTransaction({ add: [newHold], addIndex: 0 })
    unsavedChanges.value.add(newHold.hold_id)

    // Start editing the first cell
    setTimeout(() => {
      api.startEditingCell({
        rowIndex: 0,
        colKey: 'work_order_id'
      })
    }, 100)
  }
}

const openResumeDialog = (hold) => {
  resumeDialog.value = {
    show: true,
    hold,
    actual_resume_date: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
    resumed_by_user_id: '',
    resume_approved_at: format(new Date(), "yyyy-MM-dd'T'HH:mm")
  }
}

const confirmResume = () => {
  const { hold, actual_resume_date, resumed_by_user_id, resume_approved_at } = resumeDialog.value

  if (!resumed_by_user_id) {
    showSnackbar('Please enter User ID who resumed the hold', 'warning')
    return
  }

  // Update the hold data
  hold.actual_resume_date = actual_resume_date
  hold.resumed_by_user_id = resumed_by_user_id
  hold.resume_approved_at = resume_approved_at
  hold._hasChanges = true

  unsavedChanges.value.add(hold.hold_id)

  // Refresh grid
  const api = gridRef.value?.gridApi
  if (api) {
    api.refreshCells({ force: true })
  }

  resumeDialog.value.show = false
  showSnackbar('Hold marked for resume. Click Save All to persist changes.', 'info')
}

const deleteEntry = async (rowData) => {
  if (!confirm('Are you sure you want to delete this hold entry?')) return

  const api = gridRef.value?.gridApi
  if (!api) return

  // If it's a new unsaved entry, just remove it
  if (rowData._isNew) {
    api.applyTransaction({ remove: [rowData] })
    unsavedChanges.value.delete(rowData.hold_id)
    showSnackbar('Entry removed', 'info')
    return
  }

  // Delete from backend
  try {
    await kpiStore.deleteHoldEntry(rowData.hold_id)
    api.applyTransaction({ remove: [rowData] })
    unsavedChanges.value.delete(rowData.hold_id)
    showSnackbar('Entry deleted successfully', 'success')
  } catch (error) {
    showSnackbar('Error deleting entry: ' + error.message, 'error')
  }
}

const saveChanges = async () => {
  const api = gridRef.value?.gridApi
  if (!api) return

  saving.value = true

  const rowsToSave = []
  api.forEachNode(node => {
    if (node.data._hasChanges) {
      rowsToSave.push(node.data)
    }
  })

  let successCount = 0
  let errorCount = 0

  try {
    for (const row of rowsToSave) {
      const data = {
        work_order_id: row.work_order_id,
        placed_on_hold_date: row.placed_on_hold_date,
        hold_reason: row.hold_reason,
        expected_resume_date: row.expected_resume_date,
        actual_resume_date: row.actual_resume_date,
        resumed_by_user_id: row.resumed_by_user_id,
        hold_approved_at: row.hold_approved_at,
        resume_approved_at: row.resume_approved_at
      }

      try {
        if (row._isNew) {
          const result = await kpiStore.createHoldEntry(data)
          if (result.success) {
            row.hold_id = result.data.hold_id
            row._isNew = false
            successCount++
          } else {
            errorCount++
          }
        } else {
          const result = await kpiStore.updateHoldEntry(row.hold_id, data)
          if (result.success) {
            successCount++
          } else {
            errorCount++
          }
        }

        row._hasChanges = false
        unsavedChanges.value.delete(row.hold_id)
      } catch (err) {
        errorCount++
        console.error('Error saving row:', err)
      }
    }

    // Refresh grid data from store
    await kpiStore.fetchHoldEntries()
    applyFilters()

    if (errorCount === 0) {
      showSnackbar(`${successCount} hold entries saved successfully!`, 'success')
    } else {
      showSnackbar(`${successCount} saved, ${errorCount} failed`, 'warning')
    }
  } catch (error) {
    showSnackbar('Error saving changes: ' + error.message, 'error')
  } finally {
    saving.value = false
  }
}

const applyFilters = () => {
  let filtered = [...entries.value]

  if (dateFilter.value) {
    filtered = filtered.filter(e => {
      const entryDate = new Date(e.placed_on_hold_date).toISOString().split('T')[0]
      return entryDate === dateFilter.value
    })
  }

  if (statusFilter.value) {
    if (statusFilter.value === 'ACTIVE') {
      filtered = filtered.filter(e => !e.actual_resume_date)
    } else {
      filtered = filtered.filter(e => e.actual_resume_date)
    }
  }

  if (reasonFilter.value) {
    filtered = filtered.filter(e => e.hold_reason === reasonFilter.value)
  }

  filteredEntries.value = filtered
}

const showSnackbar = (message, color = 'success') => {
  snackbar.value = { show: true, message, color }
}

// Watch for changes in store data
watch(entries, () => {
  applyFilters()
}, { immediate: true })

onMounted(async () => {
  await kpiStore.fetchReferenceData()
  await kpiStore.fetchHoldEntries()
  applyFilters()
})
</script>

<style scoped>
/* Component-specific styles */
</style>
