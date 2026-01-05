<template>
  <v-card>
    <v-card-title class="bg-primary">
      <div class="d-flex align-center justify-space-between" style="width: 100%;">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-clipboard-check</v-icon>
          <span class="text-h5">Quality Inspection - Batch Entry</span>
        </div>
        <div>
          <v-btn
            color="white"
            variant="outlined"
            @click="addRow"
            class="mr-2"
          >
            <v-icon left>mdi-plus</v-icon>
            Add Inspection
          </v-btn>
          <v-btn
            color="success"
            @click="saveInspections"
            :loading="saving"
            :disabled="!hasChanges"
          >
            <v-icon left>mdi-content-save</v-icon>
            Save All ({{ changedRowsCount }})
          </v-btn>
        </div>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Quick Stats -->
      <v-row class="mb-3">
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">Total Inspected</div>
              <div class="text-h6">{{ totalInspected.toLocaleString() }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">Total Defects</div>
              <div class="text-h6 error--text">{{ totalDefects.toLocaleString() }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" :color="avgFPY >= 99 ? 'success' : avgFPY >= 95 ? 'warning' : 'error'">
            <v-card-text>
              <div class="text-caption">Avg FPY</div>
              <div class="text-h6">{{ avgFPY.toFixed(2) }}%</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">Avg PPM</div>
              <div class="text-h6">{{ avgPPM.toLocaleString() }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Info Alert -->
      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        <strong>Quality Metrics:</strong>
        FPY (First Pass Yield) = (1 - Defects/Inspected) × 100% |
        PPM (Parts Per Million) = (Defects/Inspected) × 1,000,000 |
        Target: FPY ≥ 99%, PPM ≤ 10,000
      </v-alert>

      <AGGridBase
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="qualityData"
        height="600px"
        :pagination="true"
        :paginationPageSize="50"
        @cell-value-changed="onCellValueChanged"
        @grid-ready="onGridReady"
      />
    </v-card-text>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import AGGridBase from './AGGridBase.vue'
import api from '@/services/api'
import { format } from 'date-fns'

const gridRef = ref(null)
const qualityData = ref([])
const products = ref([])
const defectTypes = ref([])
const saving = ref(false)
const snackbar = ref({ show: false, message: '', color: 'success' })

// Computed properties
const hasChanges = computed(() => {
  return qualityData.value.some(row => row._hasChanges)
})

const changedRowsCount = computed(() => {
  return qualityData.value.filter(row => row._hasChanges).length
})

const totalInspected = computed(() => {
  return qualityData.value.reduce((sum, row) => sum + (row.inspected_quantity || 0), 0)
})

const totalDefects = computed(() => {
  return qualityData.value.reduce((sum, row) => sum + (row.defect_quantity || 0), 0)
})

const avgFPY = computed(() => {
  if (totalInspected.value === 0) return 0
  return ((totalInspected.value - totalDefects.value) / totalInspected.value) * 100
})

const avgPPM = computed(() => {
  if (totalInspected.value === 0) return 0
  return (totalDefects.value / totalInspected.value) * 1000000
})

const columnDefs = [
  {
    headerName: 'Inspection Date',
    field: 'inspection_date',
    editable: true,
    cellEditor: 'agDateStringCellEditor',
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd, yyyy') : ''
    },
    width: 140
  },
  {
    headerName: 'Work Order',
    field: 'work_order_id',
    editable: true,
    width: 150
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
      return product?.product_name || params.value || 'N/A'
    },
    width: 200
  },
  {
    headerName: 'Inspected Qty',
    field: 'inspected_quantity',
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
    width: 140
  },
  {
    headerName: 'Defect Qty',
    field: 'defect_quantity',
    editable: true,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    cellEditorParams: {
      min: 0,
      precision: 0
    },
    cellStyle: (params) => {
      return params.value > 0 ? { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' } : {}
    },
    width: 130
  },
  {
    headerName: 'FPY %',
    field: 'fpy',
    editable: false,
    valueGetter: (params) => {
      const inspected = params.data.inspected_quantity || 0
      const defects = params.data.defect_quantity || 0
      if (inspected === 0) return 0
      return ((1 - defects / inspected) * 100).toFixed(2)
    },
    cellStyle: (params) => {
      const fpy = parseFloat(params.value)
      if (fpy >= 99) return { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' }
      if (fpy >= 95) return { backgroundColor: '#fff3e0', color: '#f57c00', fontWeight: 'bold' }
      return { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' }
    },
    width: 110
  },
  {
    headerName: 'PPM',
    field: 'ppm',
    editable: false,
    valueGetter: (params) => {
      const inspected = params.data.inspected_quantity || 0
      const defects = params.data.defect_quantity || 0
      if (inspected === 0) return 0
      return Math.round((defects / inspected) * 1000000)
    },
    valueFormatter: (params) => {
      return params.value ? params.value.toLocaleString() : '0'
    },
    cellStyle: (params) => {
      const ppm = params.value || 0
      if (ppm === 0) return { backgroundColor: '#e8f5e9', color: '#2e7d32' }
      if (ppm <= 10000) return { backgroundColor: '#fff3e0', color: '#f57c00' }
      return { backgroundColor: '#ffebee', color: '#c62828' }
    },
    width: 110
  },
  {
    headerName: 'Defect Type',
    field: 'defect_type_id',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: () => ({
      values: defectTypes.value.map(d => d.defect_type_id)
    }),
    valueFormatter: (params) => {
      const defectType = defectTypes.value.find(d => d.defect_type_id === params.value)
      return defectType?.defect_name || params.value || 'N/A'
    },
    width: 150
  },
  {
    headerName: 'Severity',
    field: 'severity',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: ['Critical', 'Major', 'Minor', 'Cosmetic']
    },
    cellStyle: (params) => {
      const severityColors = {
        'Critical': { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' },
        'Major': { backgroundColor: '#fff3e0', color: '#f57c00', fontWeight: 'bold' },
        'Minor': { backgroundColor: '#fff9c4', color: '#f57f17' },
        'Cosmetic': { backgroundColor: '#e3f2fd', color: '#1976d2' }
      }
      return severityColors[params.value] || {}
    },
    width: 120
  },
  {
    headerName: 'Disposition',
    field: 'disposition',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: ['Accept', 'Reject', 'Rework', 'Use As Is', 'Return to Supplier', 'Scrap']
    },
    cellStyle: (params) => {
      const dispositionColors = {
        'Accept': { backgroundColor: '#e8f5e9', color: '#2e7d32' },
        'Reject': { backgroundColor: '#ffebee', color: '#c62828' },
        'Rework': { backgroundColor: '#fff3e0', color: '#f57c00' },
        'Scrap': { backgroundColor: '#ffebee', color: '#c62828' }
      }
      return dispositionColors[params.value] || {}
    },
    width: 150
  },
  {
    headerName: 'Inspector',
    field: 'inspector_id',
    editable: true,
    width: 130
  },
  {
    headerName: 'Notes',
    field: 'defect_description',
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
        deleteRow(params.data)
      })
      return div
    },
    width: 100,
    pinned: 'right'
  }
]

const onGridReady = (params) => {
  setTimeout(() => {
    params.api.sizeColumnsToFit()
  }, 100)
}

const onCellValueChanged = (event) => {
  event.data._hasChanges = true

  // Recalculate FPY and PPM when quantities change
  if (event.column.colId === 'inspected_quantity' || event.column.colId === 'defect_quantity') {
    event.api.refreshCells({
      rowNodes: [event.node],
      columns: ['fpy', 'ppm'],
      force: true
    })
  }
}

const addRow = () => {
  const newRow = {
    inspection_id: `temp_${Date.now()}`,
    inspection_date: format(new Date(), 'yyyy-MM-dd'),
    work_order_id: '',
    product_id: products.value[0]?.product_id || null,
    inspected_quantity: 0,
    defect_quantity: 0,
    defect_type_id: defectTypes.value[0]?.defect_type_id || null,
    severity: 'Minor',
    disposition: 'Accept',
    inspector_id: '',
    defect_description: '',
    _hasChanges: true,
    _isNew: true
  }

  const api = gridRef.value?.gridApi
  if (api) {
    api.applyTransaction({ add: [newRow], addIndex: 0 })

    setTimeout(() => {
      api.startEditingCell({
        rowIndex: 0,
        colKey: 'work_order_id'
      })
    }, 100)
  }
}

const deleteRow = (rowData) => {
  if (!confirm('Are you sure you want to delete this inspection?')) return

  const api = gridRef.value?.gridApi
  if (!api) return

  api.applyTransaction({ remove: [rowData] })
  showSnackbar('Inspection removed', 'info')
}

const saveInspections = async () => {
  const api = gridRef.value?.gridApi
  if (!api) return

  const changedRows = []
  api.forEachNode(node => {
    if (node.data._hasChanges) {
      changedRows.push(node.data)
    }
  })

  if (changedRows.length === 0) {
    showSnackbar('No changes to save', 'info')
    return
  }

  saving.value = true
  let successCount = 0
  let errorCount = 0

  try {
    for (const row of changedRows) {
      const data = {
        inspection_date: row.inspection_date,
        work_order_id: row.work_order_id,
        product_id: row.product_id,
        inspected_quantity: row.inspected_quantity || 0,
        defect_quantity: row.defect_quantity || 0,
        defect_type_id: row.defect_type_id,
        severity: row.severity,
        disposition: row.disposition,
        inspector_id: row.inspector_id,
        defect_description: row.defect_description || ''
      }

      try {
        if (row._isNew) {
          await api.createQualityEntry(data)
          successCount++
        } else if (row.inspection_id) {
          await api.updateQualityEntry(row.inspection_id, data)
          successCount++
        }

        row._hasChanges = false
        row._isNew = false
      } catch (err) {
        errorCount++
        console.error('Error saving inspection:', err)
      }
    }

    if (errorCount === 0) {
      showSnackbar(`${successCount} quality inspections saved successfully!`, 'success')
    } else {
      showSnackbar(`${successCount} saved, ${errorCount} failed`, 'warning')
    }
  } catch (error) {
    showSnackbar('Error saving inspections: ' + error.message, 'error')
  } finally {
    saving.value = false
  }
}

const showSnackbar = (message, color = 'success') => {
  snackbar.value = { show: true, message, color }
}

onMounted(async () => {
  try {
    const [productsRes, defectTypesRes] = await Promise.all([
      api.getProducts(),
      api.getDefectTypes()
    ])

    products.value = productsRes.data
    defectTypes.value = defectTypesRes.data

    // Load existing quality entries
    const qualityRes = await api.getQualityEntries()
    qualityData.value = qualityRes.data.map(entry => ({
      ...entry,
      _hasChanges: false,
      _isNew: false
    }))
  } catch (error) {
    console.error('Error loading reference data:', error)
    showSnackbar('Error loading data', 'error')
  }
})
</script>

<style scoped>
/* Component-specific styles */
</style>
