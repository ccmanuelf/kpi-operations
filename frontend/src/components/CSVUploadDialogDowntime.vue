<template>
  <v-dialog v-model="dialog" max-width="1000px" persistent scrollable>
    <template v-slot:activator="{ props }">
      <v-btn color="primary" v-bind="props" prepend-icon="mdi-file-upload">
        Import CSV
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="bg-primary text-white d-flex justify-space-between align-center">
        <span class="text-h5">CSV Import - Downtime Events</span>
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
                  Select a CSV file with downtime events. We'll validate the data before importing.
                </v-alert>

                <v-file-input
                  v-model="file"
                  accept=".csv"
                  label="Select CSV File"
                  prepend-icon="mdi-file-delimited"
                  @change="handleFileUpload"
                  :loading="validating"
                  show-size
                  clearable
                  class="mb-4"
                ></v-file-input>

                <v-btn text @click="downloadTemplate" class="mb-4" prepend-icon="mdi-download">
                  Download CSV Template
                </v-btn>

                <v-alert v-if="validationErrors.length > 0" type="error" class="mt-4">
                  <strong>Validation Errors:</strong>
                  <ul>
                    <li v-for="(error, idx) in validationErrors.slice(0, 10)" :key="idx">{{ error }}</li>
                    <li v-if="validationErrors.length > 10">... and {{ validationErrors.length - 10 }} more errors</li>
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
                <v-btn color="primary" @click="nextStep" :disabled="!parsedData.length || validating">
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
                </v-alert>

                <v-alert v-if="previewSummary" type="info" variant="outlined" class="mb-4">
                  <v-row>
                    <v-col cols="4">Total Rows: {{ previewSummary.total }}</v-col>
                    <v-col cols="4">Valid: <span class="text-success">{{ previewSummary.valid }}</span></v-col>
                    <v-col cols="4">Invalid: <span class="text-error">{{ previewSummary.invalid }}</span></v-col>
                  </v-row>
                </v-alert>

                <div class="ag-theme-material" style="height: 400px; width: 100%;">
                  <ag-grid-vue
                    ref="previewGrid"
                    :columnDefs="columnDefs"
                    :rowData="parsedData"
                    :defaultColDef="defaultColDef"
                    :rowSelection="'multiple'"
                    :singleClickEdit="true"
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
                <v-btn color="primary" @click="nextStep" :disabled="validRowCount === 0">
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
                      <v-col cols="4" class="text-center">
                        <div class="text-h4 text-success">{{ validRowCount }}</div>
                        <div class="text-caption">Rows to Import</div>
                      </v-col>
                      <v-col cols="4" class="text-center">
                        <div class="text-h4 text-error">{{ invalidRowCount }}</div>
                        <div class="text-caption">Rows to Skip</div>
                      </v-col>
                      <v-col cols="4" class="text-center">
                        <div class="text-h4 text-info">{{ totalRowCount }}</div>
                        <div class="text-caption">Total Rows</div>
                      </v-col>
                    </v-row>
                  </v-card-text>
                </v-card>

                <v-alert v-if="importProgress" type="info" class="mb-4">
                  <v-progress-linear :model-value="importProgress.percentage" color="primary" height="25">
                    <strong>{{ importProgress.percentage }}% - {{ importProgress.message }}</strong>
                  </v-progress-linear>
                </v-alert>

                <v-alert v-if="importResult" :type="importResult.type" class="mb-4">
                  <strong>{{ importResult.message }}</strong>
                  <div v-if="importResult.details" class="mt-2">
                    <ul>
                      <li>Successfully Imported: {{ importResult.details.successful }}</li>
                      <li>Failed: {{ importResult.details.failed }}</li>
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
import api from '@/services/api'
import 'ag-grid-community/styles/ag-grid.css'
import 'ag-grid-community/styles/ag-theme-material.css'

const emit = defineEmits(['imported'])

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

// Required CSV columns for downtime
const requiredColumns = [
  'downtime_date',
  'work_order_id',
  'shift_id',
  'downtime_reason',
  'downtime_duration_minutes'
]

// AG Grid column definitions
const columnDefs = ref([
  {
    headerName: 'Status',
    field: '_validationStatus',
    width: 90,
    cellRenderer: (params) => {
      return params.value === 'valid' 
        ? '<span style="color: green;">✓</span>' 
        : '<span style="color: red;">✗</span>'
    }
  },
  { headerName: 'Date', field: 'downtime_date', editable: true, width: 120 },
  { headerName: 'Work Order', field: 'work_order_id', editable: true, width: 140 },
  { headerName: 'Shift', field: 'shift_id', editable: true, width: 80 },
  { headerName: 'Category', field: 'downtime_category', editable: true, width: 120 },
  { headerName: 'Reason', field: 'downtime_reason', editable: true, width: 200 },
  { headerName: 'Duration (min)', field: 'downtime_duration_minutes', editable: true, width: 130 },
  { headerName: 'Notes', field: 'notes', editable: true, width: 180 },
  { headerName: 'Errors', field: '_validationErrors', editable: false, width: 200, cellStyle: { color: 'red', fontSize: '12px' } }
])

const defaultColDef = {
  sortable: true,
  filter: true,
  resizable: true
}

const validRowCount = computed(() => parsedData.value.filter(row => row._validationStatus === 'valid').length)
const invalidRowCount = computed(() => parsedData.value.filter(row => row._validationStatus === 'error').length)
const totalRowCount = computed(() => parsedData.value.length)
const previewSummary = computed(() => {
  if (!parsedData.value.length) return null
  return { total: totalRowCount.value, valid: validRowCount.value, invalid: invalidRowCount.value }
})

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
  const headers = results.meta.fields || []
  const missingColumns = requiredColumns.filter(col => !headers.includes(col))

  if (missingColumns.length > 0) {
    errors.push(`Missing required columns: ${missingColumns.join(', ')}`)
    validationErrors.value = errors
    return
  }

  results.data.forEach((row, index) => {
    const rowErrors = []
    const rowData = { ...row }

    if (!row.downtime_date || !/^\d{4}-\d{2}-\d{2}$/.test(row.downtime_date)) {
      rowErrors.push('Invalid date (YYYY-MM-DD)')
    }
    if (!row.work_order_id || row.work_order_id.trim() === '') {
      rowErrors.push('Missing work_order_id')
    }
    if (!row.shift_id || isNaN(parseInt(row.shift_id))) {
      rowErrors.push('Invalid shift_id')
    }
    if (!row.downtime_reason || row.downtime_reason.trim() === '') {
      rowErrors.push('Missing downtime_reason')
    }
    if (!row.downtime_duration_minutes || isNaN(parseInt(row.downtime_duration_minutes)) || parseInt(row.downtime_duration_minutes) <= 0) {
      rowErrors.push('Invalid duration')
    }

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

const onGridReady = (params) => params.api.sizeColumnsToFit()

const onCellValueChanged = (event) => {
  const row = event.data
  const rowErrors = []

  if (!row.downtime_date || !/^\d{4}-\d{2}-\d{2}$/.test(row.downtime_date)) rowErrors.push('Invalid date')
  if (!row.work_order_id) rowErrors.push('Missing work_order_id')
  if (!row.shift_id || isNaN(parseInt(row.shift_id))) rowErrors.push('Invalid shift_id')
  if (!row.downtime_reason) rowErrors.push('Missing reason')
  if (!row.downtime_duration_minutes || isNaN(parseInt(row.downtime_duration_minutes))) rowErrors.push('Invalid duration')

  row._validationStatus = rowErrors.length > 0 ? 'error' : 'valid'
  row._validationErrors = rowErrors.join('; ')
  event.api.refreshCells({ rowNodes: [event.node], force: true })
}

const getRowStyle = (params) => {
  if (params.data._validationStatus === 'valid') return { background: '#e8f5e9' }
  if (params.data._validationStatus === 'error') return { background: '#ffebee' }
  return null
}

const nextStep = () => { if (step.value < 3) step.value++ }
const previousStep = () => { if (step.value > 1) step.value-- }

const confirmImport = async () => {
  importing.value = true
  importProgress.value = { percentage: 0, message: 'Preparing import...' }
  importResult.value = null

  try {
    const validRows = parsedData.value.filter(row => row._validationStatus === 'valid')
    const csvContent = Papa.unparse(validRows.map(row => ({
      downtime_date: row.downtime_date,
      work_order_id: row.work_order_id,
      shift_id: row.shift_id,
      downtime_category: row.downtime_category || '',
      downtime_reason: row.downtime_reason,
      downtime_duration_minutes: row.downtime_duration_minutes,
      notes: row.notes || ''
    })))

    importProgress.value = { percentage: 30, message: 'Uploading data...' }

    const formData = new FormData()
    const blob = new Blob([csvContent], { type: 'text/csv' })
    formData.append('file', blob, 'downtime_import.csv')

    const response = await api.post('/downtime/upload/csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    importProgress.value = { percentage: 100, message: 'Import complete!' }

    importResult.value = {
      type: 'success',
      message: 'Import completed successfully!',
      details: { successful: response.data.successful, failed: response.data.failed }
    }

    emit('imported')
    setTimeout(() => closeDialog(), 3000)
  } catch (error) {
    importResult.value = {
      type: 'error',
      message: `Import error: ${error.response?.data?.detail || error.message}`,
      details: null
    }
  } finally {
    importing.value = false
  }
}

const downloadTemplate = () => {
  // CSV Template aligned with backend/schemas/downtime_entry.py
  // Required: client_id, work_order_id, shift_date, downtime_reason, downtime_duration_minutes
  // Optional: machine_id, equipment_code, root_cause_category, corrective_action, notes
  const csvContent = `client_id,work_order_id,shift_date,downtime_reason,downtime_duration_minutes,machine_id,equipment_code,root_cause_category,corrective_action,notes
CLIENT001,WO-2026-001,2026-01-20,Machine breakdown,30,MACH-001,EQ-100,Equipment,Replaced motor,Example downtime event
CLIENT001,WO-2026-002,2026-01-20,Material shortage,45,,,Material,Ordered from supplier,Waiting for material delivery`

  const blob = new Blob([csvContent], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', 'downtime_entry_template.csv')
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

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
}
</style>
