<template>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center bg-primary">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-factory</v-icon>
        <span class="text-h5">{{ $t('production.entry') }}</span>
      </div>
      <div>
        <v-btn color="white" variant="outlined" @click="addNewEntry" class="mr-2">
          <v-icon left>mdi-plus</v-icon>
          {{ $t('dataEntry.addRow') }}
        </v-btn>
        <v-btn
          color="success"
          @click="saveChanges"
          :disabled="!hasUnsavedChanges"
          :loading="saving"
        >
          <v-icon left>mdi-content-save</v-icon>
          {{ $t('common.save') }} ({{ unsavedChanges.size }})
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Keyboard shortcuts help -->
      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-keyboard</v-icon>
          <div>
            <strong>{{ $t('grids.keyboardShortcuts') }}:</strong>
            {{ $t('grids.shortcutsList') }}
          </div>
        </div>
      </v-alert>

      <!-- Filter controls -->
      <v-row class="mb-3">
        <v-col cols="12" md="3">
          <v-text-field
            v-model="dateFilter"
            type="date"
            :label="$t('grids.filterByDate')"
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
            :label="$t('grids.filterByProduct')"
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
            :label="$t('grids.filterByShift')"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-btn color="primary" @click="applyFilters" block>
            <v-icon left>mdi-filter</v-icon>
            {{ $t('filters.apply') }}
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
        :enable-excel-paste="true"
        entry-type="production"
        @grid-ready="onGridReady"
        @cell-value-changed="onCellValueChanged"
        @rows-pasted="onRowsPasted"
      />

      <!-- Summary stats -->
      <v-row class="mt-3">
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.totalEntries') }}</div>
              <div class="text-h6">{{ filteredEntries.length }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('kpi.totalUnits') }}</div>
              <div class="text-h6">{{ totalUnits.toLocaleString() }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.totalRuntime') }}</div>
              <div class="text-h6">{{ totalRuntime.toFixed(1) }} hrs</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.avgEfficiency') }}</div>
              <div class="text-h6">{{ avgEfficiency.toFixed(1) }}%</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      :title="$t('grids.production.confirmTitle')"
      :subtitle="$t('grids.production.confirmSubtitle')"
      :data="pendingData"
      :field-config="confirmationFieldConfig"
      :loading="saving"
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
      :grid-columns="pasteGridColumns"
      @confirm="onPasteConfirm"
      @cancel="onPasteCancel"
    />

    <!-- Snackbar for notifications -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useKPIStore } from '@/stores/kpiStore'
import { format } from 'date-fns'
import AGGridBase from './AGGridBase.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'
import PastePreviewDialog from '@/components/dialogs/PastePreviewDialog.vue'

const { t } = useI18n()
const kpiStore = useKPIStore()
const gridRef = ref(null)
const unsavedChanges = ref(new Set())
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
const pasteGridColumns = ref([])

// Field configuration for confirmation dialog
const confirmationFieldConfig = computed(() => {
  const productName = products.value.find(p => p.product_id === pendingData.value.product_id)?.product_name || 'N/A'
  const shiftName = shifts.value.find(s => s.shift_id === pendingData.value.shift_id)?.shift_name || 'N/A'

  return [
    { key: 'production_date', label: 'Production Date', type: 'date' },
    { key: 'product_id', label: 'Product', type: 'text', displayValue: productName },
    { key: 'shift_id', label: 'Shift', type: 'text', displayValue: shiftName },
    { key: 'work_order_id', label: 'Work Order', type: 'text' },
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
  const total = filteredEntries.value.reduce((sum, e) => sum + (Number(e.run_time_hours) || 0), 0)
  return Number(total) || 0
})

const avgEfficiency = computed(() => {
  if (filteredEntries.value.length === 0) return 0
  const totalEff = filteredEntries.value.reduce((sum, e) => {
    const units = Number(e.units_produced) || 0
    const runtime = Number(e.run_time_hours) || 1
    const employees = Number(e.employees_assigned) || 1
    const efficiency = units / (runtime * employees)
    return sum + efficiency
  }, 0)
  return Number((totalEff / filteredEntries.value.length) * 100) || 0
})

// Column definitions
const columnDefs = computed(() => [
  {
    headerName: t('grids.columns.date'),
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
    headerName: t('grids.columns.product'),
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
    headerName: t('grids.columns.shift'),
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
    headerName: t('grids.columns.workOrder'),
    field: 'work_order_id',
    editable: true,
    width: 150
  },
  {
    headerName: t('grids.columns.unitsProduced'),
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
    headerName: t('grids.columns.runtimeHrs'),
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
      const val = Number(params.value)
      return !isNaN(val) ? val.toFixed(2) : '0.00'
    },
    width: 140
  },
  {
    headerName: t('grids.columns.employees'),
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
    headerName: t('grids.columns.defects'),
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
    headerName: t('grids.columns.scrap'),
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
    headerName: t('grids.columns.actions'),
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
        ">${t('common.delete')}</button>
      `
      div.querySelector('.ag-grid-delete-btn').addEventListener('click', () => {
        deleteEntry(params.data)
      })
      return div
    },
    width: 100,
    pinned: 'right'
  }
])

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
    work_order_id: '',
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
  if (!confirm(t('grids.deleteConfirm'))) return

  const api = gridRef.value?.gridApi
  if (!api) return

  // If it's a new unsaved entry, just remove it
  if (rowData._isNew) {
    api.applyTransaction({ remove: [rowData] })
    unsavedChanges.value.delete(rowData.entry_id)
    showSnackbar(t('grids.entryRemoved'), 'info')
    return
  }

  // Delete from backend
  try {
    await kpiStore.deleteProductionEntry(rowData.entry_id)
    api.applyTransaction({ remove: [rowData] })
    unsavedChanges.value.delete(rowData.entry_id)
    showSnackbar(t('grids.entryDeleted'), 'success')
  } catch (error) {
    showSnackbar(t('grids.deleteError') + ': ' + error.message, 'error')
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
    showSnackbar(t('grids.noChanges'), 'info')
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
        work_order_id: row.work_order_id || '',
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
      showSnackbar(t('grids.entriesSaved', { count: successCount }), 'success')
    } else {
      showSnackbar(`${successCount} ${t('success.saved')}, ${errorCount} ${t('dataEntry.rowsInvalid')}`, 'warning')
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
  showSnackbar(t('grids.saveCancelled'), 'info')
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

// Handle pasted rows from AGGridBase
const onRowsPasted = (pasteData) => {
  parsedPasteData.value = pasteData.parsedData
  convertedPasteRows.value = pasteData.convertedRows
  pasteValidationResult.value = pasteData.validationResult
  pasteColumnMapping.value = pasteData.columnMapping
  pasteGridColumns.value = pasteData.gridColumns
  showPasteDialog.value = true
}

// Handle paste confirmation
const onPasteConfirm = (rowsToAdd) => {
  showPasteDialog.value = false

  if (!rowsToAdd || rowsToAdd.length === 0) {
    showSnackbar(t('paste.noValidRows'), 'warning')
    return
  }

  // Add temporary IDs and mark as new
  const preparedRows = rowsToAdd.map((row, idx) => ({
    ...row,
    entry_id: `temp_paste_${Date.now()}_${idx}`,
    _isNew: true,
    _hasChanges: true
  }))

  // Add rows to grid
  const api = gridRef.value?.gridApi
  if (api) {
    api.applyTransaction({ add: preparedRows, addIndex: 0 })

    // Mark all pasted rows as unsaved
    preparedRows.forEach(row => {
      unsavedChanges.value.add(row.entry_id)
    })

    showSnackbar(t('paste.rowsAdded', { count: preparedRows.length }), 'success')
  }

  // Clear paste state
  parsedPasteData.value = null
  convertedPasteRows.value = []
  pasteValidationResult.value = null
  pasteColumnMapping.value = null
}

// Handle paste cancellation
const onPasteCancel = () => {
  showPasteDialog.value = false
  parsedPasteData.value = null
  convertedPasteRows.value = []
  pasteValidationResult.value = null
  pasteColumnMapping.value = null
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
