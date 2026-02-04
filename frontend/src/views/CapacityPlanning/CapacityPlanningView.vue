<template>
  <v-container fluid>
    <!-- Header -->
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon start color="primary">mdi-factory</v-icon>
            Capacity Planning
            <v-spacer />
            <v-chip color="info" variant="tonal" class="mr-2">
              13 Worksheets
            </v-chip>
            <v-btn
              color="success"
              variant="elevated"
              :loading="store.isSaving"
              :disabled="!store.hasUnsavedChanges"
              @click="saveAll"
            >
              <v-icon start>mdi-content-save</v-icon>
              Save All Changes
            </v-btn>
          </v-card-title>
          <v-card-subtitle>
            Production planning workbook with orders, BOM, capacity analysis, and scheduling
          </v-card-subtitle>
        </v-card>
      </v-col>
    </v-row>

    <!-- Unsaved Changes Warning -->
    <v-row v-if="store.hasUnsavedChanges" class="mt-2">
      <v-col cols="12">
        <v-alert type="warning" variant="tonal" density="compact" closable>
          <div class="d-flex align-center">
            <v-icon start>mdi-alert-circle</v-icon>
            <span>You have unsaved changes in: {{ store.dirtyWorksheets.join(', ') }}</span>
          </div>
        </v-alert>
      </v-col>
    </v-row>

    <!-- Error Display -->
    <v-row v-if="store.globalError" class="mt-2">
      <v-col cols="12">
        <v-alert type="error" closable @click:close="store.clearError">
          {{ store.globalError }}
        </v-alert>
      </v-col>
    </v-row>

    <!-- Loading Overlay -->
    <v-overlay :model-value="store.isLoading" class="align-center justify-center">
      <v-progress-circular indeterminate size="64" color="primary" />
      <div class="mt-4 text-h6">Loading workbook...</div>
    </v-overlay>

    <!-- Summary Stats Bar -->
    <v-row v-if="!store.isLoading" class="mt-2">
      <v-col cols="12">
        <v-card variant="tonal" color="primary">
          <v-card-text class="d-flex align-center justify-space-around py-2">
            <div class="text-center">
              <div class="text-h6">{{ store.worksheets.orders.data.length }}</div>
              <div class="text-caption">Orders</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.activeLineCount }}</div>
              <div class="text-caption">Lines</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.bomCount }}</div>
              <div class="text-caption">BOMs</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.workingDaysCount }}</div>
              <div class="text-caption">Working Days</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.shortageCount }}</div>
              <div class="text-caption text-error">Shortages</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Tab Navigation -->
    <v-row class="mt-3">
      <v-col cols="12">
        <v-tabs v-model="activeTab" color="primary" show-arrows>
          <v-tab value="orders">
            <v-icon start>mdi-clipboard-list</v-icon>
            Orders
            <v-badge
              v-if="worksheetIsDirty('orders')"
              dot
              color="warning"
              class="ml-1"
            />
          </v-tab>
          <v-tab value="masterCalendar">
            <v-icon start>mdi-calendar</v-icon>
            Calendar
          </v-tab>
          <v-tab value="productionLines">
            <v-icon start>mdi-factory</v-icon>
            Lines
          </v-tab>
          <v-tab value="productionStandards">
            <v-icon start>mdi-timer</v-icon>
            Standards
          </v-tab>
          <v-tab value="bom">
            <v-icon start>mdi-file-tree</v-icon>
            BOM
          </v-tab>
          <v-tab value="stockSnapshot">
            <v-icon start>mdi-package-variant</v-icon>
            Stock
          </v-tab>
          <v-tab value="componentCheck">
            <v-icon start>mdi-check-decagram</v-icon>
            Component Check
          </v-tab>
          <v-tab value="capacityAnalysis">
            <v-icon start>mdi-chart-bar</v-icon>
            Analysis
          </v-tab>
          <v-tab value="productionSchedule">
            <v-icon start>mdi-calendar-clock</v-icon>
            Schedule
          </v-tab>
          <v-tab value="whatIfScenarios">
            <v-icon start>mdi-help-rhombus</v-icon>
            Scenarios
          </v-tab>
          <v-tab value="kpiTracking">
            <v-icon start>mdi-target</v-icon>
            KPI Tracking
          </v-tab>
        </v-tabs>

        <v-tabs-window v-model="activeTab" class="mt-4">
          <!-- Orders Tab -->
          <v-tabs-window-item value="orders">
            <OrdersGrid />
          </v-tabs-window-item>

          <!-- Calendar Tab -->
          <v-tabs-window-item value="masterCalendar">
            <CalendarGrid />
          </v-tabs-window-item>

          <!-- Production Lines Tab -->
          <v-tabs-window-item value="productionLines">
            <ProductionLinesGrid />
          </v-tabs-window-item>

          <!-- Standards Tab -->
          <v-tabs-window-item value="productionStandards">
            <StandardsGrid />
          </v-tabs-window-item>

          <!-- BOM Tab -->
          <v-tabs-window-item value="bom">
            <BOMGrid />
          </v-tabs-window-item>

          <!-- Stock Tab -->
          <v-tabs-window-item value="stockSnapshot">
            <StockGrid />
          </v-tabs-window-item>

          <!-- Component Check Tab -->
          <v-tabs-window-item value="componentCheck">
            <ComponentCheckPanel />
          </v-tabs-window-item>

          <!-- Capacity Analysis Tab -->
          <v-tabs-window-item value="capacityAnalysis">
            <CapacityAnalysisPanel />
          </v-tabs-window-item>

          <!-- Schedule Tab -->
          <v-tabs-window-item value="productionSchedule">
            <SchedulePanel />
          </v-tabs-window-item>

          <!-- Scenarios Tab -->
          <v-tabs-window-item value="whatIfScenarios">
            <ScenariosPanel />
          </v-tabs-window-item>

          <!-- KPI Tracking Tab -->
          <v-tabs-window-item value="kpiTracking">
            <KPITrackingPanel />
          </v-tabs-window-item>
        </v-tabs-window>
      </v-col>
    </v-row>

    <!-- Action Buttons -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-text class="d-flex align-center flex-wrap gap-2">
            <v-btn
              color="info"
              variant="outlined"
              :loading="store.isRunningMRP"
              @click="runComponentCheck"
            >
              <v-icon start>mdi-check-decagram</v-icon>
              Run Component Check
            </v-btn>

            <v-btn
              color="primary"
              variant="outlined"
              :loading="store.isRunningAnalysis"
              @click="showAnalysisDialog = true"
            >
              <v-icon start>mdi-chart-bar</v-icon>
              Run Capacity Analysis
            </v-btn>

            <v-btn
              color="success"
              variant="outlined"
              :loading="store.isGeneratingSchedule"
              @click="showScheduleDialog = true"
            >
              <v-icon start>mdi-calendar-clock</v-icon>
              Generate Schedule
            </v-btn>

            <v-spacer />

            <v-btn
              color="secondary"
              variant="tonal"
              @click="showExportDialog = true"
            >
              <v-icon start>mdi-download</v-icon>
              Export
            </v-btn>

            <v-btn
              color="secondary"
              variant="tonal"
              @click="showImportDialog = true"
            >
              <v-icon start>mdi-upload</v-icon>
              Import
            </v-btn>

            <v-btn
              color="error"
              variant="outlined"
              @click="showResetDialog = true"
            >
              <v-icon start>mdi-refresh</v-icon>
              Reset
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- MRP Results Dialog -->
    <MRPResultsDialog
      v-model="store.showMRPResultsDialog"
      :results="store.mrpResults"
      @close="store.showMRPResultsDialog = false"
    />

    <!-- Scenario Compare Dialog -->
    <ScenarioCompareDialog
      v-model="store.showScenarioCompareDialog"
      :results="store.scenarioComparisonResults"
      @close="store.showScenarioCompareDialog = false"
    />

    <!-- Schedule Commit Dialog -->
    <ScheduleCommitDialog
      v-model="store.showScheduleCommitDialog"
      :schedule="store.activeSchedule"
      @close="store.showScheduleCommitDialog = false"
      @commit="handleCommitSchedule"
    />

    <!-- Analysis Date Range Dialog -->
    <v-dialog v-model="showAnalysisDialog" max-width="500">
      <v-card>
        <v-card-title>Run Capacity Analysis</v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="6">
              <v-text-field
                v-model="analysisStartDate"
                label="Start Date"
                type="date"
                variant="outlined"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="analysisEndDate"
                label="End Date"
                type="date"
                variant="outlined"
              />
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showAnalysisDialog = false">Cancel</v-btn>
          <v-btn color="primary" @click="runCapacityAnalysis">Run Analysis</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Schedule Generation Dialog -->
    <v-dialog v-model="showScheduleDialog" max-width="500">
      <v-card>
        <v-card-title>Generate Production Schedule</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="scheduleName"
            label="Schedule Name"
            variant="outlined"
            class="mb-2"
          />
          <v-row>
            <v-col cols="6">
              <v-text-field
                v-model="scheduleStartDate"
                label="Start Date"
                type="date"
                variant="outlined"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="scheduleEndDate"
                label="End Date"
                type="date"
                variant="outlined"
              />
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showScheduleDialog = false">Cancel</v-btn>
          <v-btn color="success" @click="generateSchedule">Generate</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Export Dialog -->
    <v-dialog v-model="showExportDialog" max-width="400">
      <v-card>
        <v-card-title>Export Workbook</v-card-title>
        <v-card-text>
          <v-select
            v-model="exportFormat"
            :items="['JSON', 'CSV']"
            label="Format"
            variant="outlined"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showExportDialog = false">Cancel</v-btn>
          <v-btn color="primary" @click="exportWorkbook">Export</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Import Dialog -->
    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>Import Data</v-card-title>
        <v-card-text>
          <v-file-input
            v-model="importFile"
            label="Select file"
            accept=".json,.csv"
            variant="outlined"
            prepend-icon="mdi-file-upload"
          />
          <v-select
            v-model="importTarget"
            :items="worksheetOptions"
            label="Target Worksheet"
            variant="outlined"
            class="mt-2"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">Cancel</v-btn>
          <v-btn color="primary" @click="importData">Import</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Reset Confirmation Dialog -->
    <v-dialog v-model="showResetDialog" max-width="400">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon start color="warning">mdi-alert-circle</v-icon>
          Reset Workbook
        </v-card-title>
        <v-card-text>
          Are you sure you want to reset all data? This will discard any unsaved changes.
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showResetDialog = false">Cancel</v-btn>
          <v-btn color="error" @click="handleReset">Reset</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'
import { useRoute } from 'vue-router'

// Grid components
import OrdersGrid from './components/grids/OrdersGrid.vue'
import CalendarGrid from './components/grids/CalendarGrid.vue'
import ProductionLinesGrid from './components/grids/ProductionLinesGrid.vue'
import StandardsGrid from './components/grids/StandardsGrid.vue'
import BOMGrid from './components/grids/BOMGrid.vue'
import StockGrid from './components/grids/StockGrid.vue'

// Panel components
import ComponentCheckPanel from './components/panels/ComponentCheckPanel.vue'
import CapacityAnalysisPanel from './components/panels/CapacityAnalysisPanel.vue'
import SchedulePanel from './components/panels/SchedulePanel.vue'
import ScenariosPanel from './components/panels/ScenariosPanel.vue'
import KPITrackingPanel from './components/panels/KPITrackingPanel.vue'

// Dialog components
import MRPResultsDialog from './components/dialogs/MRPResultsDialog.vue'
import ScenarioCompareDialog from './components/dialogs/ScenarioCompareDialog.vue'
import ScheduleCommitDialog from './components/dialogs/ScheduleCommitDialog.vue'

const store = useCapacityPlanningStore()
const route = useRoute()

// Local state
const activeTab = ref('orders')
const showAnalysisDialog = ref(false)
const showScheduleDialog = ref(false)
const showExportDialog = ref(false)
const showImportDialog = ref(false)
const showResetDialog = ref(false)

// Analysis form
const analysisStartDate = ref('')
const analysisEndDate = ref('')

// Schedule form
const scheduleName = ref('')
const scheduleStartDate = ref('')
const scheduleEndDate = ref('')

// Export/Import
const exportFormat = ref('JSON')
const importFile = ref(null)
const importTarget = ref('orders')

const worksheetOptions = [
  { title: 'Orders', value: 'orders' },
  { title: 'Calendar', value: 'masterCalendar' },
  { title: 'Production Lines', value: 'productionLines' },
  { title: 'Standards', value: 'productionStandards' },
  { title: 'BOM', value: 'bom' },
  { title: 'Stock', value: 'stockSnapshot' }
]

// Computed
const worksheetIsDirty = (key) => {
  return store.worksheets[key]?.dirty || false
}

// Lifecycle
onMounted(async () => {
  const clientId = route.query.client_id || localStorage.getItem('selectedClientId')
  if (clientId) {
    try {
      await store.loadWorkbook(clientId)
    } catch (error) {
      console.error('Failed to load workbook:', error)
    }
  }

  // Set default dates for analysis and schedule
  const today = new Date()
  const thirtyDaysLater = new Date(today)
  thirtyDaysLater.setDate(thirtyDaysLater.getDate() + 30)

  analysisStartDate.value = today.toISOString().slice(0, 10)
  analysisEndDate.value = thirtyDaysLater.toISOString().slice(0, 10)
  scheduleStartDate.value = today.toISOString().slice(0, 10)
  scheduleEndDate.value = thirtyDaysLater.toISOString().slice(0, 10)

  // Warn about unsaved changes before leaving
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

// Methods
const handleBeforeUnload = (e) => {
  if (store.hasUnsavedChanges) {
    e.preventDefault()
    e.returnValue = ''
  }
}

const saveAll = async () => {
  try {
    await store.saveAllDirty()
  } catch (error) {
    console.error('Failed to save:', error)
  }
}

const runComponentCheck = async () => {
  try {
    await store.runComponentCheck()
    activeTab.value = 'componentCheck'
  } catch (error) {
    console.error('Component check failed:', error)
  }
}

const runCapacityAnalysis = async () => {
  showAnalysisDialog.value = false
  try {
    await store.runCapacityAnalysis(analysisStartDate.value, analysisEndDate.value)
    activeTab.value = 'capacityAnalysis'
  } catch (error) {
    console.error('Capacity analysis failed:', error)
  }
}

const generateSchedule = async () => {
  showScheduleDialog.value = false
  try {
    await store.generateSchedule(
      scheduleName.value || 'New Schedule',
      scheduleStartDate.value,
      scheduleEndDate.value
    )
    activeTab.value = 'productionSchedule'
  } catch (error) {
    console.error('Schedule generation failed:', error)
  }
}

const handleCommitSchedule = async (kpiCommitments) => {
  try {
    await store.commitSchedule(store.activeSchedule.id, kpiCommitments)
  } catch (error) {
    console.error('Schedule commit failed:', error)
  }
}

const exportWorkbook = () => {
  showExportDialog.value = false
  const json = store.exportWorkbookJSON()
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `capacity-workbook-${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  URL.revokeObjectURL(url)
}

const importData = async () => {
  showImportDialog.value = false
  if (!importFile.value) return

  try {
    const text = await importFile.value.text()
    const data = JSON.parse(text)
    store.importData(importTarget.value, Array.isArray(data) ? data : [data])
  } catch (error) {
    console.error('Import failed:', error)
  }
}

const handleReset = () => {
  showResetDialog.value = false
  store.reset()
}
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
