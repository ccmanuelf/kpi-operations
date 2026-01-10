<template>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center bg-primary">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-factory</v-icon>
        <span class="text-h5">Production Data Entry</span>
      </div>
      <div>
        <v-btn color="white" variant="outlined" @click="addNewEntry" class="mr-2">
          <v-icon left>mdi-plus</v-icon>
          Add Entry
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
            Ctrl+Z (undo) | Drag fill handle (copy values)
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
            v-model="productFilter"
            :items="products"
            item-title="product_name"
            item-value="product_id"
            label="Filter by Product"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="shiftFilter"
            :items="shifts"
            item-title="shift_name"
            item-value="shift_id"
            label="Filter by Shift"
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
              <div class="text-caption">Total Entries</div>
              <div class="text-h6">{{ filteredEntries.length }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">Total Units</div>
              <div class="text-h6">{{ totalUnits.toLocaleString() }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">Total Runtime</div>
              <div class="text-h6">{{ totalRuntime.toFixed(1) }} hrs</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">Avg Efficiency</div>
              <div class="text-h6">{{ avgEfficiency.toFixed(1) }}%</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      title="Confirm Production Entry - Read Back"
      subtitle="Please verify the following production data before saving:"
      :data="pendingData"
      :field-config="confirmationFieldConfig"
      :loading="saving"
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

// Field configuration for confirmation dialog
const confirmationFieldConfig = computed(() => {
  const productName = products.value.find(p => p.product_id === pendingData.value.product_id)?.product_name || 'N/A'
  const shiftName = shifts.value.find(s => s.shift_id === pendingData.value.shift_id)?.shift_name || 'N/A'

  return [
    { key: 'production_date', label: 'Production Date', type: 'date' },
    { key: 'product_id', label: 'Product', type: 'text', displayValue: productName },
    { key: 'shift_id', label: 'Shift', type: 'text', displayValue: shiftName },
    { key: 'work_order_number', label: 'Work Order', type: 'text' },
    { key: 'units_produced', label: 'Units Produced', type: 'number' },
    { key: 'run_time_hours', label: 'Runtime (hours)', type: 'number' },
    { key: 'employees_assigned', label: 'Employees Assigned', type: 'number' },
    { key: 'defect_count', label: 'Defects', type: 'number' },
    { key: 'scrap_count', label: 'Scrap', type: 'number' }
  ]
})

// Filters
const dateFilter = ref(null)
const productFilter = ref(null)
const shiftFilter = ref(null)

const entries = computed(() => kpiStore.productionEntries)
const products = computed(() => kpiStore.products)
const shifts = computed(() => kpiStore.shifts)
const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

// Filtered entries
const filteredEntries = ref([])

// Summary statistics
const totalUnits = computed(() => {
  return filteredEntries.value.reduce((sum, e) => sum + (e.units_produced || 0), 0)
})

const totalRuntime = computed(() => {
  return filteredEntries.value.reduce((sum, e) => sum + (e.run_time_hours || 0), 0)
})

const avgEfficiency = computed(() => {
  if (filteredEntries.value.length === 0) return 0
  const totalEff = filteredEntries.value.reduce((sum, e) => {
    const efficiency = (e.units_produced || 0) / ((e.run_time_hours || 1) * (e.employees_assigned || 1))
    return sum + efficiency
  }, 0)
  return (totalEff / filteredEntries.value.length) * 100
})

// Column definitions
const columnDefs = [
  {
    headerName: 'Date',
    field: 'production_date',
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
    headerName: 'Product',
    field: 'product_id',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: () => ({
      values: products.value.map(p => p.product_id)
    }),
    valueFormatter: (params) => {
      const product = products.value.find(p => p.product_id === params.value)
      return product?.product_name || `ID: ${params.value}`
    },
    width: 200
  },
  {
    headerName: 'Shift',
    field: 'shift_id',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: () => ({
      values: shifts.value.map(s => s.shift_id)
    }),
    valueFormatter: (params) => {
      const shift = shifts.value.find(s => s.shift_id === params.value)
      return shift?.shift_name || `ID: ${params.value}`
    },
    width: 120
  },
  {
    headerName: 'Work Order',
    field: 'work_order_number',
    editable: true,
    width: 150
  },
  {
    headerName: 'Units Produced',
    field: 'units_produced',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      precision: 0
    },
    valueFormatter: (params) => {
      return params.value ? params.value.toLocaleString() : '0'
    },
    cellStyle: (params) => {
      return params.value > 0
        ? { color: '#2e7d32', fontWeight: 'bold' }
        : { color: '#c62828' }
    },
    width: 160
  },
  {
    headerName: 'Runtime (hrs)',
    field: 'run_time_hours',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      max: 24,
      precision: 2
    },
    valueFormatter: (params) => {
      return params.value ? params.value.toFixed(2) : '0.00'
    },
    width: 140
  },
  {
    headerName: 'Employees',
    field: 'employees_assigned',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 1,
      precision: 0
    },
    width: 130
  },
  {
    headerName: 'Defects',
    field: 'defect_count',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      precision: 0
    },
    cellStyle: (params) => {
      return params.value > 0 ? { backgroundColor: '#ffebee', color: '#c62828' } : {}
    },
    width: 110
  },
  {
    headerName: 'Scrap',
    field: 'scrap_count',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      precision: 0
    },
    cellStyle: (params) => {
      return params.value > 0 ? { backgroundColor: '#ffebee', color: '#c62828' } : {}
    },
    width: 110
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
  const rowId = event.data.entry_id || event.node.id
  unsavedChanges.value.add(rowId)

  // Mark row data as changed
  event.data._hasChanges = true

  // Refresh cell to show visual indicator
  event.api.refreshCells({ rowNodes: [event.node], force: true })
}

const addNewEntry = () => {
  const newEntry = {
    entry_id: `temp_${Date.now()}`,
    production_date: format(new Date(), 'yyyy-MM-dd'),
    product_id: products.value[0]?.product_id || null,
    shift_id: shifts.value[0]?.shift_id || null,
    work_order_number: '',
    units_produced: 0,
    run_time_hours: 0,
    employees_assigned: 1,
    defect_count: 0,
    scrap_count: 0,
    _isNew: true,
    _hasChanges: true
  }

  const api = gridRef.value?.gridApi
  if (api) {
    api.applyTransaction({ add: [newEntry], addIndex: 0 })
    unsavedChanges.value.add(newEntry.entry_id)

    // Start editing the first cell
    setTimeout(() => {
      api.startEditingCell({
        rowIndex: 0,
        colKey: 'production_date'
      })
    }, 100)
  }
}

const deleteEntry = async (rowData) => {
  if (!confirm('Are you sure you want to delete this entry?')) return

  const api = gridRef.value?.gridApi
  if (!api) return

  // If it's a new unsaved entry, just remove it
  if (rowData._isNew) {
    api.applyTransaction({ remove: [rowData] })
    unsavedChanges.value.delete(rowData.entry_id)
    showSnackbar('Entry removed', 'info')
    return
  }

  // Delete from backend
  try {
    await kpiStore.deleteProductionEntry(rowData.entry_id)
    api.applyTransaction({ remove: [rowData] })
    unsavedChanges.value.delete(rowData.entry_id)
    showSnackbar('Entry deleted successfully', 'success')
  } catch (error) {
    showSnackbar('Error deleting entry: ' + error.message, 'error')
  }
}

const saveChanges = async () => {
  const api = gridRef.value?.gridApi
  if (!api) return

  const rowsToSave = []
  api.forEachNode(node => {
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
        product_id: row.product_id,
        shift_id: row.shift_id,
        production_date: row.production_date,
        work_order_number: row.work_order_number || '',
        units_produced: row.units_produced || 0,
        run_time_hours: row.run_time_hours || 0,
        employees_assigned: row.employees_assigned || 1,
        defect_count: row.defect_count || 0,
        scrap_count: row.scrap_count || 0
      }

      try {
        if (row._isNew) {
          const result = await kpiStore.createProductionEntry(data)
          if (result.success) {
            row.entry_id = result.data.entry_id
            row._isNew = false
            successCount++
          } else {
            errorCount++
          }
        } else {
          const result = await kpiStore.updateProductionEntry(row.entry_id, data)
          if (result.success) {
            successCount++
          } else {
            errorCount++
          }
        }

        row._hasChanges = false
        unsavedChanges.value.delete(row.entry_id)
      } catch (err) {
        errorCount++
        console.error('Error saving row:', err)
      }
    }

    // Refresh grid data from store
    await kpiStore.fetchProductionEntries()
    applyFilters()

    if (errorCount === 0) {
      showSnackbar(`${successCount} entries saved successfully!`, 'success')
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
    filtered = filtered.filter(e => e.production_date === dateFilter.value)
  }

  if (productFilter.value) {
    filtered = filtered.filter(e => e.product_id === productFilter.value)
  }

  if (shiftFilter.value) {
    filtered = filtered.filter(e => e.shift_id === shiftFilter.value)
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
  await kpiStore.fetchProductionEntries()
  applyFilters()
})
</script>

<style scoped>
/* Component-specific styles */
</style>
