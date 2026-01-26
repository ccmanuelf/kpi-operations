<template>
  <v-dialog v-model="dialog" max-width="1200px" persistent scrollable>
    <template v-slot:activator="{ props }">
      <v-btn color="primary" v-bind="props" prepend-icon="mdi-file-upload">
        Import CSV
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="bg-primary text-white">
        <span class="text-h5">CSV Import - 3-Step Confirmation</span>
        <v-spacer></v-spacer>
        <v-btn icon variant="text" @click="closeDialog">
          <v-icon color="white">mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-0">
        <v-stepper v-model="step" :items="steps" flat>
          <!-- Step 1: Upload & Validate -->
          <template v-slot:item.1>
            <v-card flat>
              <v-card-text>
                <v-alert type="info" variant="tonal" class="mb-4">
                  <strong>Step 1: Upload & Validate</strong><br>
                  Select a CSV file. We'll validate the columns and data before importing.
                </v-alert>

                <v-file-input
                  v-model="file"
                  accept=".csv,.xlsx"
                  label="Select CSV or Excel File"
                  prepend-icon="mdi-file-delimited"
                  @change="handleFileUpload"
                  :loading="validating"
                  show-size
                  clearable
                  class="mb-4"
                ></v-file-input>

                <v-btn
                  text
                  @click="downloadTemplate"
                  class="mb-4"
                  prepend-icon="mdi-download"
                >
                  Download CSV Template
                </v-btn>

                <v-alert v-if="validationErrors.length > 0" type="error" class="mt-4">
                  <strong>Validation Errors:</strong>
                  <ul>
                    <li v-for="(error, idx) in validationErrors.slice(0, 10)" :key="idx">
                      {{ error }}
                    </li>
                    <li v-if="validationErrors.length > 10">
                      ... and {{ validationErrors.length - 10 }} more errors
                    </li>
                  </ul>
                </v-alert>

                <v-alert v-if="validationSummary" type="success" variant="tonal" class="mt-4">
                  <strong>Validation Summary:</strong>
                  <ul>
                    <li>Total Rows: {{ validationSummary.totalRows }}</li>
                    <li>Valid Rows: {{ validationSummary.validRows }}</li>
                    <li>Invalid Rows: {{ validationSummary.invalidRows }}</li>
                  </ul>
                </v-alert>
              </v-card-text>
              <v-card-actions>
                <v-spacer></v-spacer>
                <v-btn @click="closeDialog">Cancel</v-btn>
                <v-btn
                  color="primary"
                  @click="nextStep"
                  :disabled="!parsedData || parsedData.length === 0 || validating"
                >
                  Next: Preview Data
                </v-btn>
              </v-card-actions>
            </v-card>
          </template>

          <!-- Step 2: Preview & Edit -->
          <template v-slot:item.2>
            <v-card flat>
              <v-card-text>
                <v-alert type="info" variant="tonal" class="mb-4">
                  <strong>Step 2: Preview & Edit</strong><br>
                  Review the data below. You can edit cells inline to fix errors before importing.
                  Valid rows are highlighted in green, errors in red.
                </v-alert>

                <v-alert v-if="previewSummary" type="info" variant="outlined" class="mb-4">
                  <strong>Preview Summary:</strong>
                  <v-row>
                    <v-col cols="3">Total Rows: {{ previewSummary.total }}</v-col>
                    <v-col cols="3">Valid: <span class="text-success">{{ previewSummary.valid }}</span></v-col>
                    <v-col cols="3">Invalid: <span class="text-error">{{ previewSummary.invalid }}</span></v-col>
                    <v-col cols="3">Avg Efficiency: {{ previewSummary.avgEfficiency }}%</v-col>
                  </v-row>
                </v-alert>

                <div class="ag-theme-material" style="height: 500px; width: 100%;">
                  <ag-grid-vue
                    ref="previewGrid"
                    :columnDefs="columnDefs"
                    :rowData="parsedData"
                    :defaultColDef="defaultColDef"
                    :rowSelection="'multiple'"
                    :suppressRowClickSelection="true"
                    :enableRangeSelection="true"
                    :enableClipboard="true"
                    :singleClickEdit="true"
                    :enterMovesDownAfterEdit="true"
                    @grid-ready="onGridReady"
                    @cell-value-changed="onCellValueChanged"
                    :getRowStyle="getRowStyle"
                  />
                </div>
              </v-card-text>
              <v-card-actions>
                <v-btn @click="previousStep">Back</v-btn>
                <v-spacer></v-spacer>
                <v-btn @click="closeDialog">Cancel</v-btn>
                <v-btn
                  color="primary"
                  @click="nextStep"
                  :disabled="!canProceedToConfirm"
                >
                  Next: Confirm Import
                </v-btn>
              </v-card-actions>
            </v-card>
          </template>

          <!-- Step 3: Confirm & Import -->
          <template v-slot:item.3>
            <v-card flat>
              <v-card-text>
                <v-alert type="warning" variant="tonal" class="mb-4">
                  <strong>Step 3: Final Confirmation</strong><br>
                  Please review the summary below and confirm the import.
                </v-alert>

                <v-card variant="outlined" class="mb-4">
                  <v-card-text>
                    <v-row>
                      <v-col cols="12" md="4">
                        <div class="text-h4 text-success">{{ validRowCount }}</div>
                        <div class="text-caption">Rows to Import</div>
                      </v-col>
                      <v-col cols="12" md="4">
                        <div class="text-h4 text-error">{{ invalidRowCount }}</div>
                        <div class="text-caption">Rows to Skip</div>
                      </v-col>
                      <v-col cols="12" md="4">
                        <div class="text-h4 text-info">{{ totalRowCount }}</div>
                        <div class="text-caption">Total Rows</div>
                      </v-col>
                    </v-row>
                  </v-card-text>
                </v-card>

                <v-alert v-if="invalidRowCount > 0" type="warning" class="mb-4">
                  {{ invalidRowCount }} row(s) with errors will be skipped. You can go back to fix them or proceed to import only valid rows.
                </v-alert>

                <v-alert v-if="importProgress" type="info" class="mb-4">
                  <v-progress-linear
                    :model-value="importProgress.percentage"
                    color="primary"
                    height="25"
                  >
                    <strong>{{ importProgress.percentage }}% - {{ importProgress.message }}</strong>
                  </v-progress-linear>
                </v-alert>

                <v-alert v-if="importResult" :type="importResult.type" class="mb-4">
                  <strong>{{ importResult.message }}</strong>
                  <div v-if="importResult.details" class="mt-2">
                    <ul>
                      <li>Successfully Imported: {{ importResult.details.successful }}</li>
                      <li>Failed: {{ importResult.details.failed }}</li>
                      <li v-if="importResult.details.importLogId">Import Log ID: {{ importResult.details.importLogId }}</li>
                    </ul>
                  </div>
                </v-alert>
              </v-card-text>
              <v-card-actions>
                <v-btn @click="previousStep" :disabled="importing">Back</v-btn>
                <v-spacer></v-spacer>
                <v-btn @click="closeDialog" :disabled="importing">Cancel</v-btn>
                <v-btn
                  color="success"
                  @click="confirmImport"
                  :loading="importing"
                  :disabled="importing || validRowCount === 0"
                  prepend-icon="mdi-check"
                >
                  Confirm & Import {{ validRowCount }} Rows
                </v-btn>
              </v-card-actions>
            </v-card>
          </template>
        </v-stepper>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import Papa from 'papaparse'
import { useKPIStore } from '@/stores/kpiStore'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-material.css'

const kpiStore = useKPIStore()

const dialog = ref(false)
const step = ref(1)
const file = ref(null)
const validating = ref(false)
const importing = ref(false)
const parsedData = ref([])
const validationErrors = ref([])
const validationSummary = ref(null)
const importProgress = ref(null)
const importResult = ref(null)
const previewGrid = ref(null)

const steps = [
  { title: 'Upload', value: 1 },
  { title: 'Preview', value: 2 },
  { title: 'Confirm', value: 3 }
]

// Required CSV columns - aligned with backend/routes/production.py
const requiredColumns = [
  'client_id',           // Multi-tenant isolation - REQUIRED
  'product_id',          // Product reference
  'shift_id',            // Shift reference
  'production_date',     // Format: YYYY-MM-DD
  'units_produced',      // Must be > 0
  'run_time_hours',      // Decimal hours
  'employees_assigned'   // Number of employees
]

// AG Grid column definitions
const columnDefs = ref([
  {
    headerName: 'Status',
    field: '_validationStatus',
    width: 100,
    cellRenderer: (params) => {
      if (params.value === 'valid') {
        return '<span style="color: green;">✓ Valid</span>'
      } else if (params.value === 'error') {
        return '<span style="color: red;">✗ Error</span>'
      }
      return ''
    }
  },
  {
    headerName: 'Client ID',
    field: 'client_id',
    editable: true,
    width: 120
  },
  {
    headerName: 'Date',
    field: 'production_date',
    editable: true,
    width: 130
  },
  {
    headerName: 'Product ID',
    field: 'product_id',
    editable: true,
    type: 'numericColumn',
    width: 120
  },
  {
    headerName: 'Shift ID',
    field: 'shift_id',
    editable: true,
    type: 'numericColumn',
    width: 100
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
    width: 140
  },
  {
    headerName: 'Runtime (hrs)',
    field: 'run_time_hours',
    editable: true,
    type: 'numericColumn',
    width: 130
  },
  {
    headerName: 'Employees',
    field: 'employees_assigned',
    editable: true,
    type: 'numericColumn',
    width: 120
  },
  {
    headerName: 'Defects',
    field: 'defect_count',
    editable: true,
    type: 'numericColumn',
    width: 100
  },
  {
    headerName: 'Scrap',
    field: 'scrap_count',
    editable: true,
    type: 'numericColumn',
    width: 100
  },
  {
    headerName: 'Efficiency %',
    field: '_calculatedEfficiency',
    editable: false,
    width: 120,
    valueFormatter: (params) => params.value ? `${params.value}%` : '-'
  },
  {
    headerName: 'Errors',
    field: '_validationErrors',
    editable: false,
    width: 300,
    cellStyle: { color: 'red', fontSize: '12px' }
  },
  {
    headerName: 'Notes',
    field: 'notes',
    editable: true,
    width: 200
  }
])

const defaultColDef = {
  sortable: true,
  filter: true,
  resizable: true
}

// Computed properties
const validRowCount = computed(() => {
  return parsedData.value.filter(row => row._validationStatus === 'valid').length
})

const invalidRowCount = computed(() => {
  return parsedData.value.filter(row => row._validationStatus === 'error').length
})

const totalRowCount = computed(() => parsedData.value.length)

const canProceedToConfirm = computed(() => {
  return validRowCount.value > 0
})

const previewSummary = computed(() => {
  if (!parsedData.value || parsedData.value.length === 0) return null

  const validRows = parsedData.value.filter(row => row._validationStatus === 'valid')
  const avgEff = validRows.reduce((sum, row) => sum + (row._calculatedEfficiency || 0), 0) / (validRows.length || 1)

  return {
    total: parsedData.value.length,
    valid: validRowCount.value,
    invalid: invalidRowCount.value,
    avgEfficiency: avgEff.toFixed(2)
  }
})

// File upload handler
const handleFileUpload = async () => {
  if (!file.value) return

  validating.value = true
  validationErrors.value = []
  parsedData.value = []
  validationSummary.value = null

  try {
    const fileContent = await readFileAsText(file.value)

    Papa.parse(fileContent, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        validateAndParseCSV(results)
        validating.value = false
      },
      error: (error) => {
        validationErrors.value.push(`CSV parsing error: ${error.message}`)
        validating.value = false
      }
    })
  } catch (error) {
    validationErrors.value.push(`File read error: ${error.message}`)
    validating.value = false
  }
}

const readFileAsText = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve(e.target.result)
    reader.onerror = (e) => reject(e)
    reader.readAsText(file)
  })
}

const validateAndParseCSV = (results) => {
  const errors = []
  const data = []

  // Check for required columns
  const headers = results.meta.fields || []
  const missingColumns = requiredColumns.filter(col => !headers.includes(col))

  if (missingColumns.length > 0) {
    errors.push(`Missing required columns: ${missingColumns.join(', ')}`)
    validationErrors.value = errors
    return
  }

  // Validate each row
  results.data.forEach((row, index) => {
    const rowErrors = []
    const rowData = { ...row }

    // Validate client_id (REQUIRED)
    if (!row.client_id || String(row.client_id).trim() === '') {
      rowErrors.push('client_id is required')
    } else {
      rowData.client_id = String(row.client_id).trim()
    }

    // Validate production_date
    if (!row.production_date || !/^\d{4}-\d{2}-\d{2}$/.test(row.production_date)) {
      rowErrors.push('Invalid date format (use YYYY-MM-DD)')
    }

    // Validate product_id
    if (!row.product_id || isNaN(parseInt(row.product_id))) {
      rowErrors.push('Invalid product_id')
    } else {
      rowData.product_id = parseInt(row.product_id)
    }

    // Validate shift_id
    if (!row.shift_id || isNaN(parseInt(row.shift_id))) {
      rowErrors.push('Invalid shift_id')
    } else {
      rowData.shift_id = parseInt(row.shift_id)
    }

    // Validate units_produced
    if (!row.units_produced || isNaN(parseInt(row.units_produced)) || parseInt(row.units_produced) < 0) {
      rowErrors.push('Invalid units_produced')
    } else {
      rowData.units_produced = parseInt(row.units_produced)
    }

    // Validate run_time_hours
    if (!row.run_time_hours || isNaN(parseFloat(row.run_time_hours)) || parseFloat(row.run_time_hours) <= 0) {
      rowErrors.push('Invalid run_time_hours')
    } else {
      rowData.run_time_hours = parseFloat(row.run_time_hours)
    }

    // Validate employees_assigned
    if (!row.employees_assigned || isNaN(parseInt(row.employees_assigned)) || parseInt(row.employees_assigned) < 1) {
      rowErrors.push('Invalid employees_assigned')
    } else {
      rowData.employees_assigned = parseInt(row.employees_assigned)
    }

    // Optional fields with defaults
    rowData.defect_count = parseInt(row.defect_count || 0)
    rowData.scrap_count = parseInt(row.scrap_count || 0)
    rowData.work_order_number = row.work_order_number || ''
    rowData.notes = row.notes || ''

    // Calculate efficiency (mock calculation)
    if (rowErrors.length === 0) {
      const standardHours = rowData.units_produced * 0.05 // Assume 0.05 hrs per unit
      rowData._calculatedEfficiency = ((standardHours / rowData.run_time_hours) * 100).toFixed(2)
    }

    // Add validation metadata
    rowData._validationStatus = rowErrors.length > 0 ? 'error' : 'valid'
    rowData._validationErrors = rowErrors.join('; ')
    rowData._rowIndex = index + 1

    data.push(rowData)

    if (rowErrors.length > 0) {
      errors.push(`Row ${index + 2}: ${rowErrors.join(', ')}`)
    }
  })

  parsedData.value = data
  validationErrors.value = errors

  validationSummary.value = {
    totalRows: data.length,
    validRows: data.filter(r => r._validationStatus === 'valid').length,
    invalidRows: data.filter(r => r._validationStatus === 'error').length
  }
}

// Grid event handlers
const onGridReady = (params) => {
  params.api.sizeColumnsToFit()
}

const onCellValueChanged = (event) => {
  // Re-validate the edited row
  const row = event.data
  const rowErrors = []

  // Re-run validations
  if (!row.production_date || !/^\d{4}-\d{2}-\d{2}$/.test(row.production_date)) {
    rowErrors.push('Invalid date format')
  }
  if (!row.product_id || isNaN(parseInt(row.product_id))) {
    rowErrors.push('Invalid product_id')
  }
  if (!row.shift_id || isNaN(parseInt(row.shift_id))) {
    rowErrors.push('Invalid shift_id')
  }
  if (!row.units_produced || isNaN(parseInt(row.units_produced)) || parseInt(row.units_produced) < 0) {
    rowErrors.push('Invalid units_produced')
  }
  if (!row.run_time_hours || isNaN(parseFloat(row.run_time_hours)) || parseFloat(row.run_time_hours) <= 0) {
    rowErrors.push('Invalid run_time_hours')
  }
  if (!row.employees_assigned || isNaN(parseInt(row.employees_assigned)) || parseInt(row.employees_assigned) < 1) {
    rowErrors.push('Invalid employees_assigned')
  }

  row._validationStatus = rowErrors.length > 0 ? 'error' : 'valid'
  row._validationErrors = rowErrors.join('; ')

  // Recalculate efficiency
  if (rowErrors.length === 0) {
    const standardHours = row.units_produced * 0.05
    row._calculatedEfficiency = ((standardHours / row.run_time_hours) * 100).toFixed(2)
  }

  // Refresh the row
  event.api.refreshCells({ rowNodes: [event.node], force: true })
}

const getRowStyle = (params) => {
  if (params.data._validationStatus === 'valid') {
    return { background: '#e8f5e9' }
  } else if (params.data._validationStatus === 'error') {
    return { background: '#ffebee' }
  }
  return null
}

// Step navigation
const nextStep = () => {
  if (step.value < 3) {
    step.value++
  }
}

const previousStep = () => {
  if (step.value > 1) {
    step.value--
  }
}

// Import confirmation
const confirmImport = async () => {
  importing.value = true
  importProgress.value = { percentage: 0, message: 'Preparing import...' }
  importResult.value = null

  try {
    // Filter only valid rows
    const validRows = parsedData.value.filter(row => row._validationStatus === 'valid')

    // Remove validation metadata - aligned with backend production schema
    const cleanedData = validRows.map(row => ({
      client_id: row.client_id,
      production_date: row.production_date,
      product_id: row.product_id,
      shift_id: row.shift_id,
      work_order_id: row.work_order_id || row.work_order_number || '',
      job_id: row.job_id || '',
      units_produced: row.units_produced,
      run_time_hours: row.run_time_hours,
      employees_assigned: row.employees_assigned,
      employees_present: row.employees_present || null,
      defect_count: row.defect_count || 0,
      scrap_count: row.scrap_count || 0,
      rework_count: row.rework_count || 0,
      setup_time_hours: row.setup_time_hours || null,
      downtime_hours: row.downtime_hours || null,
      maintenance_hours: row.maintenance_hours || null,
      ideal_cycle_time: row.ideal_cycle_time || null,
      shift_date: row.shift_date || row.production_date,
      notes: row.notes || ''
    }))

    importProgress.value = { percentage: 30, message: 'Uploading data...' }

    // Call batch import API
    const result = await kpiStore.batchImportProduction(cleanedData)

    importProgress.value = { percentage: 100, message: 'Import complete!' }

    if (result.success) {
      importResult.value = {
        type: 'success',
        message: 'Import completed successfully!',
        details: {
          successful: result.data.successful,
          failed: result.data.failed,
          importLogId: result.data.import_log_id
        }
      }

      // Refresh production entries
      await kpiStore.fetchProductionEntries()

      // Close dialog after 3 seconds
      setTimeout(() => {
        closeDialog()
      }, 3000)
    } else {
      importResult.value = {
        type: 'error',
        message: result.error || 'Import failed',
        details: null
      }
    }
  } catch (error) {
    importResult.value = {
      type: 'error',
      message: `Import error: ${error.message}`,
      details: null
    }
  } finally {
    importing.value = false
  }
}

// Download template - aligned with backend/routes/production.py
const downloadTemplate = () => {
  // Required: client_id, product_id, shift_id, production_date, units_produced, run_time_hours, employees_assigned
  // Optional: shift_date, work_order_id, job_id, employees_present, defect_count, scrap_count, rework_count,
  //           setup_time_hours, downtime_hours, maintenance_hours, ideal_cycle_time, notes
  const csvContent = `client_id,product_id,shift_id,production_date,units_produced,run_time_hours,employees_assigned,work_order_id,job_id,employees_present,defect_count,scrap_count,rework_count,setup_time_hours,downtime_hours,maintenance_hours,ideal_cycle_time,shift_date,notes
CLIENT001,1,1,2026-01-20,250,7.5,5,WO-2026-001,,5,3,1,0,0.25,0.5,0.1,0.03,2026-01-20,Example production entry
CLIENT001,2,2,2026-01-20,180,7.0,4,WO-2026-002,,4,2,1,1,0.15,0.25,0,0.04,2026-01-20,Second shift production`

  const blob = new Blob([csvContent], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', 'production_entry_template.csv')
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// Close dialog
const closeDialog = () => {
  dialog.value = false
  step.value = 1
  file.value = null
  parsedData.value = []
  validationErrors.value = []
  validationSummary.value = null
  importProgress.value = null
  importResult.value = null
}
</script>

<style scoped>
.ag-theme-material {
  --ag-header-background-color: #1a237e;
  --ag-header-foreground-color: white;
  --ag-row-hover-color: rgba(26, 35, 126, 0.05);
  --ag-selected-row-background-color: rgba(26, 35, 126, 0.1);
}
</style>
