<template>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center bg-primary">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-alert-circle</v-icon>
        <span class="text-h5">Downtime Entry - Excel-like Grid</span>
      </div>
      <div>
        <v-btn color="white" variant="outlined" @click="addNewEntry" class="mr-2">
          <v-icon left>mdi-plus</v-icon>
          Add Downtime
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
            Ctrl+Z (undo) | F1 (help) | Drag fill handle (copy values)
          </div>
        </div>
      </v-alert>

      <!-- Filter controls -->
      <v-row class="mb-3">
        <v-col cols="12" md="3">
          <v-text-field
            v-model="dateFilter"
            type="date"
            label="Filter by Date"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="categoryFilter"
            :items="categories"
            label="Filter by Category"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="statusFilter"
            :items="['Resolved', 'Unresolved']"
            label="Filter by Status"
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
              <div class="text-caption">Total Downtime Entries</div>
              <div class="text-h6">{{ filteredEntries.length }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" color="error">
            <v-card-text>
              <div class="text-caption">Total Hours Lost</div>
              <div class="text-h6">{{ totalHours.toFixed(1) }} hrs</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" color="warning">
            <v-card-text>
              <div class="text-caption">Unresolved Issues</div>
              <div class="text-h6">{{ unresolvedCount }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" color="success">
            <v-card-text>
              <div class="text-caption">Resolved Issues</div>
              <div class="text-h6">{{ resolvedCount }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      title="Confirm Downtime Entry - Read Back"
      subtitle="Please verify the following downtime data before saving:"
      :data="pendingData"
      :field-config="confirmationFieldConfig"
      :loading="saving"
      :warning-message="pendingRowsCount > 1 ? `This will save ${pendingRowsCount} downtime entries.` : ''"
      @confirm="onConfirmSave"
      @cancel="onCancelSave"
    />

    <!-- Snackbar for notifications -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useKPIStore } from '@/stores/kpiStore'
import { format } from 'date-fns'
import AGGridBase from './AGGridBase.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'

const kpiStore = useKPIStore()
const gridRef = ref(null)
const unsavedChanges = ref(new Set())
const saving = ref(false)
const snackbar = ref({ show: false, message: '', color: 'success' })

// Read-back confirmation state
const showConfirmDialog = ref(false)
const pendingData = ref({})
const pendingRows = ref([])

const pendingRowsCount = computed(() => pendingRows.value.length)

// Field configuration for confirmation dialog
const confirmationFieldConfig = computed(() => {
  const workOrderNumber = workOrders.value.find(w => w.work_order_id === pendingData.value.work_order_id)?.work_order_number || 'N/A'

  return [
    { key: 'downtime_start_time', label: 'Start Time', type: 'datetime' },
    { key: 'work_order_id', label: 'Work Order', type: 'text', displayValue: workOrderNumber },
    { key: 'downtime_reason', label: 'Reason', type: 'text' },
    { key: 'category', label: 'Category', type: 'text' },
    { key: 'duration_hours', label: 'Duration (hours)', type: 'number' },
    { key: 'impact_on_wip_hours', label: 'WIP Impact (hours)', type: 'number' },
    { key: 'is_resolved', label: 'Resolved', type: 'boolean' },
    { key: 'resolution_notes', label: 'Resolution Notes', type: 'text' }
  ]
})

// Filters
const dateFilter = ref(null)
const categoryFilter = ref(null)
const statusFilter = ref(null)

const categories = [
  'Planned Maintenance',
  'Unplanned Breakdown',
  'Changeover',
  'Material Shortage',
  'Quality Issue',
  'Operator Absence',
  'Other'
]

const entries = computed(() => kpiStore.downtimeEntries || [])
const workOrders = computed(() => kpiStore.workOrders || [])
const downtimeReasons = computed(() => kpiStore.downtimeReasons || [])
const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

// Filtered entries
const filteredEntries = ref([])

// Summary statistics
const totalHours = computed(() => {
  return filteredEntries.value.reduce((sum, e) => sum + (e.duration_hours || 0), 0)
})

const unresolvedCount = computed(() => {
  return filteredEntries.value.filter(e => !e.is_resolved).length
})

const resolvedCount = computed(() => {
  return filteredEntries.value.filter(e => e.is_resolved).length
})

// Column definitions
const columnDefs = [
  {
    headerName: 'Start Time',
    field: 'downtime_start_time',
    editable: true,
    cellEditor: 'agDateStringCellEditor',
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd, yyyy HH:mm') : ''
    },
    cellClass: 'font-weight-bold',
    pinned: 'left',
    width: 180,
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
    headerName: 'Reason',
    field: 'downtime_reason',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: () => ({
      values: downtimeReasons.value.map(r => r.reason_name)
    }),
    width: 200
  },
  {
    headerName: 'Category',
    field: 'category',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: categories
    },
    cellStyle: (params) => {
      const categoryColors = {
        'Planned Maintenance': { backgroundColor: '#e3f2fd', color: '#1976d2' },
        'Unplanned Breakdown': { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' },
        'Changeover': { backgroundColor: '#fff9c4', color: '#f57f17' },
        'Material Shortage': { backgroundColor: '#fff3e0', color: '#f57c00' },
        'Quality Issue': { backgroundColor: '#fce4ec', color: '#c2185b' },
        'Operator Absence': { backgroundColor: '#f3e5f5', color: '#7b1fa2' }
      }
      return categoryColors[params.value] || {}
    },
    width: 180
  },
  {
    headerName: 'Duration (hrs)',
    field: 'duration_hours',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      precision: 2
    },
    valueFormatter: (params) => {
      return params.value ? params.value.toFixed(2) : '0.00'
    },
    cellStyle: (params) => {
      const hours = params.value || 0
      if (hours >= 4) return { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' }
      if (hours >= 2) return { backgroundColor: '#fff3e0', color: '#f57c00' }
      return {}
    },
    width: 140
  },
  {
    headerName: 'WIP Impact (hrs)',
    field: 'impact_on_wip_hours',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      precision: 2
    },
    valueFormatter: (params) => {
      return params.value ? params.value.toFixed(2) : '0.00'
    },
    width: 150
  },
  {
    headerName: 'Status',
    field: 'is_resolved',
    editable: true,
    cellRenderer: (params) => {
      return params.value ? 'Resolved' : 'Unresolved'
    },
    cellEditor: 'agCheckboxCellEditor',
    cellStyle: (params) => {
      return params.value
        ? { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' }
        : { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' }
    },
    width: 130
  },
  {
    headerName: 'Resolution Notes',
    field: 'resolution_notes',
    editable: true,
    cellEditor: 'agLargeTextCellEditor',
    cellEditorPopup: true,
    width: 250
  },
  {
    headerName: 'Actions',
    field: 'actions',
    editable: false,
    sortable: false,
    filter: false,
    cellRenderer: (params) => {
      const div = document.createElement('div')
      div.innerHTML = `
        <button class="ag-grid-delete-btn" style="
          background: #c62828;
          color: white;
          border: none;
          padding: 4px 8px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 12px;
        ">Delete</button>
      `
      div.querySelector('.ag-grid-delete-btn').addEventListener('click', () => {
        deleteEntry(params.data)
      })
      return div
    },
    width: 100,
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
  const rowId = event.data.downtime_id || event.node.id
  unsavedChanges.value.add(rowId)

  // Mark row data as changed
  event.data._hasChanges = true

  // Refresh cell to show visual indicator
  event.api.refreshCells({ rowNodes: [event.node], force: true })
}

const addNewEntry = () => {
  const newEntry = {
    downtime_id: `temp_${Date.now()}`,
    downtime_start_time: new Date().toISOString(),
    work_order_id: workOrders.value[0]?.work_order_id || null,
    downtime_reason: downtimeReasons.value[0]?.reason_name || '',
    category: 'Unplanned Breakdown',
    duration_hours: 0,
    impact_on_wip_hours: 0,
    is_resolved: false,
    resolution_notes: '',
    _isNew: true,
    _hasChanges: true
  }

  const api = gridRef.value?.gridApi
  if (api) {
    api.applyTransaction({ add: [newEntry], addIndex: 0 })
    unsavedChanges.value.add(newEntry.downtime_id)

    // Start editing the first cell
    setTimeout(() => {
      api.startEditingCell({
        rowIndex: 0,
        colKey: 'downtime_start_time'
      })
    }, 100)
  }
}

const deleteEntry = async (rowData) => {
  if (!confirm('Are you sure you want to delete this downtime entry?')) return

  const api = gridRef.value?.gridApi
  if (!api) return

  // If it's a new unsaved entry, just remove it
  if (rowData._isNew) {
    api.applyTransaction({ remove: [rowData] })
    unsavedChanges.value.delete(rowData.downtime_id)
    showSnackbar('Entry removed', 'info')
    return
  }

  // Delete from backend
  try {
    await kpiStore.deleteDowntimeEntry(rowData.downtime_id)
    api.applyTransaction({ remove: [rowData] })
    unsavedChanges.value.delete(rowData.downtime_id)
    showSnackbar('Entry deleted successfully', 'success')
  } catch (error) {
    showSnackbar('Error deleting entry: ' + error.message, 'error')
  }
}

const saveChanges = async () => {
  const gridApi = gridRef.value?.gridApi
  if (!gridApi) return

  const rowsToSave = []
  gridApi.forEachNode(node => {
    if (node.data._hasChanges) {
      rowsToSave.push(node.data)
    }
  })

  if (rowsToSave.length === 0) {
    showSnackbar('No changes to save', 'info')
    return
  }

  // Store pending rows and show confirmation for first row
  pendingRows.value = rowsToSave
  pendingData.value = rowsToSave[0]
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
        work_order_id: row.work_order_id,
        downtime_start_time: row.downtime_start_time,
        downtime_reason: row.downtime_reason,
        category: row.category,
        duration_hours: row.duration_hours || 0,
        impact_on_wip_hours: row.impact_on_wip_hours || 0,
        is_resolved: row.is_resolved || false,
        resolution_notes: row.resolution_notes || ''
      }

      try {
        if (row._isNew) {
          const result = await kpiStore.createDowntimeEntry(data)
          if (result.success) {
            row.downtime_id = result.data.downtime_id
            row._isNew = false
            successCount++
          } else {
            errorCount++
          }
        } else {
          const result = await kpiStore.updateDowntimeEntry(row.downtime_id, data)
          if (result.success) {
            successCount++
          } else {
            errorCount++
          }
        }

        row._hasChanges = false
        unsavedChanges.value.delete(row.downtime_id)
      } catch (err) {
        errorCount++
        console.error('Error saving row:', err)
      }
    }

    // Refresh grid data from store
    await kpiStore.fetchDowntimeEntries()
    applyFilters()

    if (errorCount === 0) {
      showSnackbar(`${successCount} downtime entries saved successfully!`, 'success')
    } else {
      showSnackbar(`${successCount} saved, ${errorCount} failed`, 'warning')
    }
  } catch (error) {
    showSnackbar('Error saving changes: ' + error.message, 'error')
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
  showSnackbar('Save cancelled', 'info')
}

const applyFilters = () => {
  let filtered = [...entries.value]

  if (dateFilter.value) {
    filtered = filtered.filter(e => {
      const entryDate = new Date(e.downtime_start_time).toISOString().split('T')[0]
      return entryDate === dateFilter.value
    })
  }

  if (categoryFilter.value) {
    filtered = filtered.filter(e => e.category === categoryFilter.value)
  }

  if (statusFilter.value) {
    const isResolved = statusFilter.value === 'Resolved'
    filtered = filtered.filter(e => e.is_resolved === isResolved)
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
  await kpiStore.fetchDowntimeEntries()
  applyFilters()
})
</script>

<style scoped>
/* Component-specific styles */
</style>
