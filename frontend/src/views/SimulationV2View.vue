<template>
  <v-container fluid>
    <!-- Header -->
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon start color="primary">mdi-chart-timeline-variant</v-icon>
            Production Line Simulation v2.0
            <v-spacer />
            <v-chip color="info" variant="tonal" class="mr-2">
              SimPy Engine
            </v-chip>
            <v-btn
              color="info"
              variant="outlined"
              size="small"
              @click="showGuide = true"
            >
              <v-icon start>mdi-help-circle</v-icon>
              How to Use
            </v-btn>
          </v-card-title>
          <v-card-subtitle>
            Discrete-event simulation for multi-product production lines with bottleneck analysis and rebalancing suggestions
          </v-card-subtitle>
        </v-card>
      </v-col>
    </v-row>

    <!-- Summary Stats Bar -->
    <v-row v-if="store.operations.length > 0" class="mt-2">
      <v-col cols="12">
        <v-card variant="tonal" color="primary">
          <v-card-text class="d-flex align-center justify-space-around py-2">
            <div class="text-center">
              <div class="text-h6">{{ store.productsCount }}</div>
              <div class="text-caption">Products</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.operationsCount }}</div>
              <div class="text-caption">Operations</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.machineTools.length }}</div>
              <div class="text-caption">Machines</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.dailyPlannedHours.toFixed(1) }}h</div>
              <div class="text-caption">Daily Hours</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.horizonDays }}d</div>
              <div class="text-caption">Horizon</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Main Content Tabs -->
    <v-row class="mt-3">
      <v-col cols="12">
        <v-tabs v-model="activeTab" color="primary" grow>
          <v-tab value="operations">
            <v-icon start>mdi-cogs</v-icon>
            Operations
            <v-badge v-if="store.operations.length" :content="store.operations.length" color="primary" inline class="ml-2" />
          </v-tab>
          <v-tab value="schedule">
            <v-icon start>mdi-clock-outline</v-icon>
            Schedule
          </v-tab>
          <v-tab value="demand">
            <v-icon start>mdi-chart-bar</v-icon>
            Demand
            <v-badge v-if="store.demands.length" :content="store.demands.length" color="secondary" inline class="ml-2" />
          </v-tab>
          <v-tab value="breakdowns">
            <v-icon start>mdi-wrench-clock</v-icon>
            Breakdowns
            <v-badge v-if="store.breakdowns.length" :content="store.breakdowns.length" color="warning" inline class="ml-2" />
          </v-tab>
        </v-tabs>

        <v-tabs-window v-model="activeTab" class="mt-4">
          <!-- Operations Tab -->
          <v-tabs-window-item value="operations">
            <OperationsGrid />
          </v-tabs-window-item>

          <!-- Schedule Tab -->
          <v-tabs-window-item value="schedule">
            <ScheduleForm />
          </v-tabs-window-item>

          <!-- Demand Tab -->
          <v-tabs-window-item value="demand">
            <DemandGrid />
          </v-tabs-window-item>

          <!-- Breakdowns Tab -->
          <v-tabs-window-item value="breakdowns">
            <BreakdownsGrid />
          </v-tabs-window-item>
        </v-tabs-window>
      </v-col>
    </v-row>

    <!-- Validation Panel -->
    <v-row v-if="store.showValidationPanel && store.validationReport" class="mt-3">
      <v-col cols="12">
        <ValidationPanel :report="store.validationReport" />
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
              @click="handleValidate"
              :loading="store.isValidating"
              :disabled="store.operations.length === 0"
            >
              <v-icon start>mdi-check-circle-outline</v-icon>
              Validate Configuration
            </v-btn>

            <v-btn
              color="success"
              variant="elevated"
              @click="handleRun"
              :loading="store.isRunning"
              :disabled="!canRunSimulation"
            >
              <v-icon start>mdi-play</v-icon>
              Run Simulation
            </v-btn>

            <v-spacer />

            <v-btn
              color="primary"
              variant="tonal"
              @click="showImportDialog = true"
            >
              <v-icon start>mdi-upload</v-icon>
              Import Config
            </v-btn>

            <v-btn
              color="primary"
              variant="tonal"
              @click="exportConfig"
              :disabled="store.operations.length === 0"
            >
              <v-icon start>mdi-download</v-icon>
              Export Config
            </v-btn>

            <v-btn
              color="error"
              variant="outlined"
              @click="confirmReset"
            >
              <v-icon start>mdi-refresh</v-icon>
              Reset
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Error Display -->
    <v-row v-if="store.error" class="mt-3">
      <v-col cols="12">
        <v-alert type="error" closable @click:close="store.error = null">
          {{ store.error }}
        </v-alert>
      </v-col>
    </v-row>

    <!-- Results Dialog -->
    <ResultsView
      v-model="store.showResultsDialog"
      :results="store.results"
    />

    <!-- How-To Guide Dialog -->
    <v-dialog v-model="showGuide" max-width="800" scrollable>
      <v-card>
        <v-card-title class="bg-primary text-white">
          <v-icon start>mdi-help-circle</v-icon>
          Production Line Simulation v2.0 Guide
        </v-card-title>
        <v-card-text class="pa-4">
          <v-expansion-panels>
            <v-expansion-panel title="Quick Start">
              <v-expansion-panel-text>
                <v-list density="compact">
                  <v-list-item prepend-icon="mdi-numeric-1-circle">
                    <strong>Operations:</strong> Define your production operations using the grid. Paste from Excel or add manually.
                  </v-list-item>
                  <v-list-item prepend-icon="mdi-numeric-2-circle">
                    <strong>Schedule:</strong> Configure shifts, work days, and overtime settings.
                  </v-list-item>
                  <v-list-item prepend-icon="mdi-numeric-3-circle">
                    <strong>Demand:</strong> Set daily/weekly demand per product or use mix percentages.
                  </v-list-item>
                  <v-list-item prepend-icon="mdi-numeric-4-circle">
                    <strong>Run:</strong> Click "Run Simulation" to execute the discrete-event simulation.
                  </v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>

            <v-expansion-panel title="Operations Grid">
              <v-expansion-panel-text>
                <p class="mb-2">Each operation requires:</p>
                <v-list density="compact">
                  <v-list-item><strong>Product:</strong> Product identifier</v-list-item>
                  <v-list-item><strong>Step:</strong> Sequence number (operations run in order)</v-list-item>
                  <v-list-item><strong>Operation:</strong> Operation name</v-list-item>
                  <v-list-item><strong>Machine/Tool:</strong> Equipment used (creates shared resources)</v-list-item>
                  <v-list-item><strong>SAM (min):</strong> Standard Allowed Minutes per piece</v-list-item>
                  <v-list-item><strong>Operators:</strong> Number of operators at this station</v-list-item>
                  <v-list-item><strong>Grade %:</strong> Operator efficiency (affects process time)</v-list-item>
                  <v-list-item><strong>FPD %:</strong> First Pass Defect rate</v-list-item>
                </v-list>
                <v-alert type="info" variant="tonal" density="compact" class="mt-3">
                  <strong>Tip:</strong> Copy/paste data directly from Excel. The grid auto-detects columns.
                </v-alert>
              </v-expansion-panel-text>
            </v-expansion-panel>

            <v-expansion-panel title="Processing Time Formula">
              <v-expansion-panel-text>
                <v-code class="d-block pa-3 bg-grey-lighten-4 rounded">
                  Actual Time = SAM × (1 + Variability + FPD/100 + (100-Grade)/100)
                </v-code>
                <v-list density="compact" class="mt-3">
                  <v-list-item><strong>Variability:</strong> 10% random variation (default)</v-list-item>
                  <v-list-item><strong>FPD:</strong> First Pass Defect adds rework time</v-list-item>
                  <v-list-item><strong>Grade:</strong> Lower grade = longer time</v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>

            <v-expansion-panel title="Output Blocks">
              <v-expansion-panel-text>
                <p class="mb-2">The simulation produces 8 output blocks:</p>
                <v-list density="compact">
                  <v-list-item><strong>Block 1:</strong> Weekly Demand vs Capacity</v-list-item>
                  <v-list-item><strong>Block 2:</strong> Daily Summary</v-list-item>
                  <v-list-item><strong>Block 3:</strong> Station Performance</v-list-item>
                  <v-list-item><strong>Block 4:</strong> Free Capacity Hours</v-list-item>
                  <v-list-item><strong>Block 5:</strong> Bundle Metrics</v-list-item>
                  <v-list-item><strong>Block 6:</strong> Per-Product Summary</v-list-item>
                  <v-list-item><strong>Block 7:</strong> Rebalancing Suggestions</v-list-item>
                  <v-list-item><strong>Block 8:</strong> Assumption Log</v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>

            <v-expansion-panel title="Bottleneck Detection">
              <v-expansion-panel-text>
                <v-list density="compact">
                  <v-list-item prepend-icon="mdi-alert-circle" class="text-error">
                    <strong>Bottleneck:</strong> Utilization ≥ 95%
                  </v-list-item>
                  <v-list-item prepend-icon="mdi-check-circle" class="text-success">
                    <strong>Donor Candidate:</strong> Utilization ≤ 70% with multiple operators
                  </v-list-item>
                </v-list>
                <p class="mt-2">
                  The rebalancing suggestions identify stations that could donate operators to bottleneck stations.
                </p>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="primary" @click="showGuide = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Import Configuration Dialog -->
    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>Import Configuration</v-card-title>
        <v-card-text>
          <v-textarea
            v-model="importJson"
            label="Paste JSON configuration"
            rows="10"
            variant="outlined"
            placeholder='{"operations": [...], "schedule": {...}, "demands": [...]}'
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">Cancel</v-btn>
          <v-btn color="primary" @click="importConfig">Import</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Reset Confirmation Dialog -->
    <v-dialog v-model="showResetDialog" max-width="450">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon start color="warning">mdi-alert-circle</v-icon>
          Reset Configuration
        </v-card-title>
        <v-card-text>
          <p class="mb-4">Choose how you want to reset the simulation:</p>
          <v-list density="compact">
            <v-list-item
              prepend-icon="mdi-delete-sweep"
              title="Clear All"
              subtitle="Remove all data and start with empty configuration"
              @click="handleResetClear"
              class="rounded-lg mb-2"
              :class="{ 'bg-grey-lighten-4': true }"
              style="cursor: pointer;"
            />
            <v-list-item
              prepend-icon="mdi-tshirt-crew"
              title="Load Sample Data"
              subtitle="Reset with T-Shirt manufacturing example for learning"
              @click="handleResetToSample"
              class="rounded-lg"
              :class="{ 'bg-blue-lighten-5': true }"
              style="cursor: pointer;"
            />
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showResetDialog = false">Cancel</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- First Visit Welcome Snackbar -->
    <v-snackbar
      v-model="showWelcomeMessage"
      timeout="6000"
      color="info"
      location="top"
      multi-line
    >
      <div class="d-flex align-center">
        <v-icon start>mdi-tshirt-crew</v-icon>
        <div>
          <strong>Welcome!</strong> Sample T-Shirt manufacturing data has been loaded to help you get started.
        </div>
      </div>
      <template v-slot:actions>
        <v-btn variant="text" @click="showWelcomeMessage = false">Got it</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSimulationV2Store } from '@/stores/simulationV2Store'
import OperationsGrid from '@/components/simulation/OperationsGrid.vue'
import ScheduleForm from '@/components/simulation/ScheduleForm.vue'
import DemandGrid from '@/components/simulation/DemandGrid.vue'
import BreakdownsGrid from '@/components/simulation/BreakdownsGrid.vue'
import ValidationPanel from '@/components/simulation/ValidationPanel.vue'
import ResultsView from '@/components/simulation/ResultsView.vue'

const store = useSimulationV2Store()

// Local state
const activeTab = ref('operations')
const showGuide = ref(false)
const showImportDialog = ref(false)
const showResetDialog = ref(false)
const importJson = ref('')
const showWelcomeMessage = ref(false)

// Computed
const canRunSimulation = computed(() => {
  return store.operations.length > 0 &&
         store.demands.length > 0 &&
         !store.isRunning &&
         (!store.validationReport || store.validationReport.is_valid)
})

// Methods
async function handleValidate() {
  try {
    await store.validate()
  } catch (error) {
    console.error('Validation error:', error)
  }
}

async function handleRun() {
  try {
    // Validate first if not already validated
    if (!store.validationReport) {
      await store.validate()
    }
    // Only run if valid
    if (store.validationReport?.is_valid) {
      await store.run()
    }
  } catch (error) {
    console.error('Simulation error:', error)
  }
}

function confirmReset() {
  showResetDialog.value = true
}

function handleResetClear() {
  store.reset()
  showResetDialog.value = false
}

function handleResetToSample() {
  store.resetToSample()
  showResetDialog.value = false
}

// Legacy function for backwards compatibility
function handleReset() {
  handleResetClear()
}

function importConfig() {
  try {
    const config = JSON.parse(importJson.value)
    store.loadConfiguration(config)
    showImportDialog.value = false
    importJson.value = ''
  } catch (error) {
    store.error = 'Invalid JSON format: ' + error.message
  }
}

function exportConfig() {
  const config = store.exportConfiguration()
  const json = JSON.stringify(config, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `simulation-config-${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  URL.revokeObjectURL(url)
}

// Lifecycle
onMounted(async () => {
  await store.fetchToolInfo()

  // Auto-load sample data on first visit for better onboarding
  if (store.isFirstVisit() && store.operations.length === 0) {
    store.loadSampleData()
    showWelcomeMessage.value = true
  }
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
