<template>
  <v-card>
    <v-card-title class="bg-primary">
      <div class="d-flex align-center justify-space-between" style="width: 100%;">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-cog-outline</v-icon>
          <span class="text-h6">{{ t('simulation.operations.title') }}</span>
          <v-chip class="ml-2" size="small" color="white" variant="outlined">
            {{ t('simulation.operations.opsCount', { ops: store.operationsCount, products: store.productsCount }) }}
          </v-chip>
        </div>
        <div>
          <v-btn
            color="white"
            variant="outlined"
            size="small"
            @click="addRow"
            class="mr-2"
          >
            <v-icon left>mdi-plus</v-icon>
            {{ t('simulation.operations.addOperation') }}
          </v-btn>
          <v-btn
            color="white"
            variant="outlined"
            size="small"
            @click="showImportDialog = true"
            class="mr-2"
          >
            <v-icon left>mdi-file-import</v-icon>
            {{ t('simulation.operations.importCsv') }}
          </v-btn>
        </div>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Empty State with Sample Data Option -->
      <v-card v-if="store.operations.length === 0" variant="outlined" class="mb-3 pa-6 text-center">
        <v-icon size="64" color="grey-lighten-1" class="mb-4">mdi-tshirt-crew-outline</v-icon>
        <h3 class="text-h6 mb-2">{{ t('simulation.operations.emptyTitle') }}</h3>
        <p class="text-body-2 text-grey mb-4">
          {{ t('simulation.operations.emptyDescription') }}
        </p>
        <div class="d-flex justify-center gap-2">
          <v-btn color="primary" variant="tonal" @click="loadSampleData">
            <v-icon start>mdi-tshirt-crew</v-icon>
            {{ t('simulation.sampleData.loadSample') }}
          </v-btn>
          <v-btn color="secondary" variant="outlined" @click="addRow">
            <v-icon start>mdi-plus</v-icon>
            {{ t('simulation.operations.addManually') }}
          </v-btn>
          <v-btn color="secondary" variant="outlined" @click="showImportDialog = true">
            <v-icon start>mdi-file-import</v-icon>
            {{ t('simulation.operations.importCsv') }}
          </v-btn>
        </div>
      </v-card>

      <div class="ag-theme-material" style="height: 500px; width: 100%;">
        <ag-grid-vue
          style="width: 100%; height: 100%;"
          :columnDefs="columnDefs"
          :rowData="store.operations"
          :defaultColDef="defaultColDef"
          :gridOptions="gridOptions"
          :getRowId="getRowId"
          @grid-ready="onGridReady"
          @cell-value-changed="onCellValueChanged"
        />
      </div>
    </v-card-text>

    <!-- Import Dialog -->
    <v-dialog v-model="showImportDialog" max-width="800">
      <v-card>
        <v-card-title>
          <v-icon left>mdi-file-import</v-icon>
          {{ t('databaseConfig.importOperations') }}
        </v-card-title>
        <v-card-text>
          <v-textarea
            v-model="csvText"
            :label="t('simulation.operations.csvLabel')"
            placeholder="product,step,operation,machine_tool,sam_min,operators,grade_pct,fpd_pct&#10;TSHIRT_A,1,Cut fabric,Cutting Table,2.0,2,85,15"
            rows="10"
            variant="outlined"
          />
          <!-- CSV column headers in the placeholder above are intentionally
               left in English: they're literal field names that map 1:1 to
               the backend Pydantic schema, not user-facing prose. -->
          <v-alert type="info" variant="tonal" density="compact" class="mt-2">
            {{ t('simulation.operations.csvRequired') }}<br/>
            {{ t('simulation.operations.csvOptional') }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="importCsv">{{ t('common.import') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="3000"
    >
      {{ snackbar.text }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { AgGridVue } from 'ag-grid-vue3'
import { useSimulationV2Store } from '@/stores/simulationV2Store'
import Papa from 'papaparse'

const { t } = useI18n()

const store = useSimulationV2Store()
const gridApi = ref(null)
const showImportDialog = ref(false)
const csvText = ref('')
const snackbar = ref({ show: false, text: '', color: 'info' })

const getRowId = (params) => String(params.data._id)

const defaultColDef = {
  sortable: true,
  filter: true,
  resizable: true,
  editable: true,
  minWidth: 80
}

const gridOptions = {
  theme: 'legacy',
  singleClickEdit: true,
  stopEditingWhenCellsLoseFocus: true,
  undoRedoCellEditing: true,
  enterNavigatesVertically: true,
  enterNavigatesVerticallyAfterEdit: true
}

const variabilityOptions = ['triangular', 'deterministic']
const sequenceOptions = ['Cutting', 'Assembly', 'Finishing', 'Packaging', 'QC']

const columnDefs = computed(() => [
  {
    headerName: '',
    field: 'actions',
    width: 60,
    editable: false,
    sortable: false,
    filter: false,
    cellRenderer: (params) => {
      const btn = document.createElement('button')
      btn.innerHTML = '✕'
      btn.className = 'delete-btn'
      btn.style.cssText = 'cursor:pointer;color:red;border:none;background:none;font-size:16px;'
      btn.onclick = () => removeRow(params.node.rowIndex)
      return btn
    }
  },
  {
    headerName: t('simulation.operations.columns.product'),
    field: 'product',
    width: 120,
    cellEditor: 'agTextCellEditor'
  },
  {
    headerName: t('simulation.operations.columns.step'),
    field: 'step',
    width: 70,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor'
  },
  {
    headerName: t('simulation.operations.columns.operation'),
    field: 'operation',
    width: 200,
    cellEditor: 'agTextCellEditor'
  },
  {
    headerName: t('simulation.operations.columns.machineTool'),
    field: 'machine_tool',
    width: 150,
    cellEditor: 'agTextCellEditor'
  },
  {
    headerName: t('timeStandard.samMin'),
    field: 'sam_min',
    width: 100,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    valueFormatter: (params) => params.value?.toFixed(2)
  },
  {
    headerName: t('simulation.operations.columns.operators'),
    field: 'operators',
    width: 90,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor'
  },
  {
    headerName: t('simulation.operations.columns.gradePct'),
    field: 'grade_pct',
    width: 90,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    valueFormatter: (params) => params.value?.toFixed(0)
  },
  {
    headerName: t('simulation.operations.columns.fpdPct'),
    field: 'fpd_pct',
    width: 80,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    valueFormatter: (params) => params.value?.toFixed(0)
  },
  {
    headerName: t('simulation.operations.columns.reworkPct'),
    field: 'rework_pct',
    width: 90,
    type: 'numericColumn',
    cellEditor: 'agNumberCellEditor',
    valueFormatter: (params) => params.value?.toFixed(1)
  },
  {
    headerName: t('simulation.operations.columns.variability'),
    field: 'variability',
    width: 110,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: { values: variabilityOptions }
  },
  {
    headerName: t('simulation.operations.columns.sequence'),
    field: 'sequence',
    width: 110,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: { values: sequenceOptions }
  },
  {
    headerName: t('simulation.operations.columns.grouping'),
    field: 'grouping',
    width: 100,
    cellEditor: 'agTextCellEditor'
  }
])

const onGridReady = (params) => {
  gridApi.value = params.api
  params.api.sizeColumnsToFit()
}

const onCellValueChanged = (event) => {
  const index = store.operations.findIndex(op => op._id === event.data._id)
  if (index >= 0) {
    store.updateOperation(index, { [event.colDef.field]: event.newValue })
  }
}

const addRow = () => {
  store.addOperation()
  // Scroll to bottom after adding
  setTimeout(() => {
    if (gridApi.value) {
      gridApi.value.ensureIndexVisible(store.operations.length - 1)
    }
  }, 100)
}

const loadSampleData = () => {
  store.loadSampleData()
}

const removeRow = (index) => {
  store.removeOperation(index)
}

const importCsv = () => {
  if (!csvText.value.trim()) return

  Papa.parse(csvText.value, {
    header: true,
    skipEmptyLines: true,
    complete: (results) => {
      if (results.data && results.data.length > 0) {
        const operations = results.data.map(row => ({
          product: row.product || '',
          step: parseInt(row.step, 10) || 1,
          operation: row.operation || '',
          machine_tool: row.machine_tool || '',
          sam_min: parseFloat(row.sam_min) || 1.0,
          sequence: row.sequence || 'Assembly',
          grouping: row.grouping || '',
          operators: parseInt(row.operators, 10) || 1,
          variability: row.variability || 'triangular',
          rework_pct: parseFloat(row.rework_pct) || 0,
          grade_pct: parseFloat(row.grade_pct) || 85,
          fpd_pct: parseFloat(row.fpd_pct) || 15
        }))
        store.importOperations(operations)
        showImportDialog.value = false
        csvText.value = ''
      }
    },
    error: (error) => {
      console.error('CSV parse error:', error)
      snackbar.value = {
        show: true,
        text: t('simulation.operations.parseError'),
        color: 'error'
      }
    }
  })
}
</script>

<style scoped>
.ag-theme-material {
  font-family: 'Roboto', sans-serif;
}
</style>
