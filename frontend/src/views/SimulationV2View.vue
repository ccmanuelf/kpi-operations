<template>
  <v-container fluid>
    <!-- Header -->
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon start color="primary">mdi-chart-timeline-variant</v-icon>
            {{ t('simulationV2.title') }}
            <v-spacer />
            <v-chip color="info" variant="tonal" class="mr-2">
              {{ t('simulationV2.simpyEngine') }}
            </v-chip>
            <v-btn
              color="info"
              variant="outlined"
              size="small"
              @click="showGuide = true"
            >
              <v-icon start>mdi-help-circle</v-icon>
              {{ t('simulationV2.howToUse') }}
            </v-btn>
          </v-card-title>
          <v-card-subtitle>
            {{ t('simulationV2.subtitle') }}
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
              <div class="text-caption">{{ t('simulationV2.stats.products') }}</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.operationsCount }}</div>
              <div class="text-caption">{{ t('simulationV2.stats.operations') }}</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.machineTools.length }}</div>
              <div class="text-caption">{{ t('simulationV2.stats.machines') }}</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.dailyPlannedHours.toFixed(1) }}h</div>
              <div class="text-caption">{{ t('simulationV2.stats.dailyHours') }}</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.horizonDays }}d</div>
              <div class="text-caption">{{ t('simulationV2.stats.horizon') }}</div>
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
            {{ t('simulationV2.tabs.operations') }}
            <v-badge v-if="store.operations.length" :content="store.operations.length" color="primary" inline class="ml-2" />
          </v-tab>
          <v-tab value="schedule">
            <v-icon start>mdi-clock-outline</v-icon>
            {{ t('simulationV2.tabs.schedule') }}
          </v-tab>
          <v-tab value="demand">
            <v-icon start>mdi-chart-bar</v-icon>
            {{ t('simulationV2.tabs.demand') }}
            <v-badge v-if="store.demands.length" :content="store.demands.length" color="secondary" inline class="ml-2" />
          </v-tab>
          <v-tab value="breakdowns">
            <v-icon start>mdi-wrench-clock</v-icon>
            {{ t('simulationV2.tabs.breakdowns') }}
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
              {{ t('simulationV2.actions.validateConfiguration') }}
            </v-btn>

            <v-btn
              color="success"
              variant="elevated"
              @click="handleRun"
              :loading="store.isRunning"
              :disabled="!canRunSimulation"
            >
              <v-icon start>mdi-play</v-icon>
              {{ t('simulationV2.actions.runSimulation') }}
            </v-btn>

            <v-spacer />

            <v-btn
              color="primary"
              variant="tonal"
              @click="showImportDialog = true"
            >
              <v-icon start>mdi-upload</v-icon>
              {{ t('simulationV2.actions.importConfig') }}
            </v-btn>

            <v-btn
              color="primary"
              variant="tonal"
              @click="exportConfig"
              :disabled="store.operations.length === 0"
            >
              <v-icon start>mdi-download</v-icon>
              {{ t('simulationV2.actions.exportConfig') }}
            </v-btn>

            <v-btn
              color="error"
              variant="outlined"
              @click="confirmReset"
            >
              <v-icon start>mdi-refresh</v-icon>
              {{ t('simulationV2.actions.reset') }}
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
          {{ t('simulationV2.guide.title') }}
        </v-card-title>
        <v-card-text class="pa-4">
          <v-expansion-panels>
            <v-expansion-panel :title="t('simulationV2.guide.quickStart')">
              <v-expansion-panel-text>
                <v-list density="compact">
                  <v-list-item prepend-icon="mdi-numeric-1-circle">
                    <strong>{{ t('simulationV2.tabs.operations') }}:</strong> {{ t('simulationV2.guide.step1') }}
                  </v-list-item>
                  <v-list-item prepend-icon="mdi-numeric-2-circle">
                    <strong>{{ t('simulationV2.tabs.schedule') }}:</strong> {{ t('simulationV2.guide.step2') }}
                  </v-list-item>
                  <v-list-item prepend-icon="mdi-numeric-3-circle">
                    <strong>{{ t('simulationV2.tabs.demand') }}:</strong> {{ t('simulationV2.guide.step3') }}
                  </v-list-item>
                  <v-list-item prepend-icon="mdi-numeric-4-circle">
                    <strong>{{ t('simulationV2.guide.runLabel') }}:</strong> {{ t('simulationV2.guide.step4') }}
                  </v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>

            <v-expansion-panel :title="t('simulationV2.guide.operationsGrid')">
              <v-expansion-panel-text>
                <p class="mb-2">{{ t('simulationV2.guide.eachOpRequires') }}</p>
                <v-list density="compact">
                  <v-list-item><strong>{{ t('simulationV2.guide.fieldProduct') }}:</strong> {{ t('simulationV2.guide.fieldProductDesc') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.fieldStep') }}:</strong> {{ t('simulationV2.guide.fieldStepDesc') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.fieldOperation') }}:</strong> {{ t('simulationV2.guide.fieldOperationDesc') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.fieldMachine') }}:</strong> {{ t('simulationV2.guide.fieldMachineDesc') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.fieldSam') }}:</strong> {{ t('simulationV2.guide.fieldSamDesc') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.fieldOperators') }}:</strong> {{ t('simulationV2.guide.fieldOperatorsDesc') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.fieldGrade') }}:</strong> {{ t('simulationV2.guide.fieldGradeDesc') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.fieldFpd') }}:</strong> {{ t('simulationV2.guide.fieldFpdDesc') }}</v-list-item>
                </v-list>
                <v-alert type="info" variant="tonal" density="compact" class="mt-3">
                  <strong>{{ t('simulationV2.guide.tip') }}:</strong> {{ t('simulationV2.guide.tipPasteExcel') }}
                </v-alert>
              </v-expansion-panel-text>
            </v-expansion-panel>

            <v-expansion-panel :title="t('simulationV2.guide.processingTimeFormula')">
              <v-expansion-panel-text>
                <v-code class="d-block pa-3 bg-grey-lighten-4 rounded">
                  Actual Time = SAM × (1 + Variability + FPD/100 + (100-Grade)/100)
                </v-code>
                <v-list density="compact" class="mt-3">
                  <v-list-item><strong>{{ t('simulationV2.guide.variability') }}:</strong> {{ t('simulationV2.guide.variabilityDesc') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.fpdLabel') }}:</strong> {{ t('simulationV2.guide.fpdDesc') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.gradeLabel') }}:</strong> {{ t('simulationV2.guide.gradeDesc') }}</v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>

            <v-expansion-panel :title="t('simulationV2.guide.outputBlocks')">
              <v-expansion-panel-text>
                <p class="mb-2">{{ t('simulationV2.guide.outputIntro') }}</p>
                <v-list density="compact">
                  <v-list-item><strong>{{ t('simulationV2.guide.block') }} 1:</strong> {{ t('simulationV2.guide.block1') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.block') }} 2:</strong> {{ t('simulationV2.guide.block2') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.block') }} 3:</strong> {{ t('simulationV2.guide.block3') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.block') }} 4:</strong> {{ t('simulationV2.guide.block4') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.block') }} 5:</strong> {{ t('simulationV2.guide.block5') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.block') }} 6:</strong> {{ t('simulationV2.guide.block6') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.block') }} 7:</strong> {{ t('simulationV2.guide.block7') }}</v-list-item>
                  <v-list-item><strong>{{ t('simulationV2.guide.block') }} 8:</strong> {{ t('simulationV2.guide.block8') }}</v-list-item>
                </v-list>
              </v-expansion-panel-text>
            </v-expansion-panel>

            <v-expansion-panel :title="t('simulationV2.guide.bottleneckDetection')">
              <v-expansion-panel-text>
                <v-list density="compact">
                  <v-list-item prepend-icon="mdi-alert-circle" class="text-error">
                    <strong>{{ t('simulationV2.guide.bottleneckLabel') }}:</strong> {{ t('simulationV2.guide.bottleneckThreshold') }}
                  </v-list-item>
                  <v-list-item prepend-icon="mdi-check-circle" class="text-success">
                    <strong>{{ t('simulationV2.guide.donorCandidate') }}:</strong> {{ t('simulationV2.guide.donorThreshold') }}
                  </v-list-item>
                </v-list>
                <p class="mt-2">
                  {{ t('simulationV2.guide.rebalancingExplanation') }}
                </p>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="primary" @click="showGuide = false">{{ t('common.close') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Import Configuration Dialog -->
    <v-dialog v-model="showImportDialog" max-width="600">
      <v-card>
        <v-card-title>{{ t('simulationV2.importDialog.title') }}</v-card-title>
        <v-card-text>
          <v-textarea
            v-model="importJson"
            :label="t('simulationV2.importDialog.pasteJsonLabel')"
            rows="10"
            variant="outlined"
            placeholder='{"operations": [...], "schedule": {...}, "demands": [...]}'
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showImportDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="importConfig">{{ t('common.import') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Reset Confirmation Dialog -->
    <v-dialog v-model="showResetDialog" max-width="450">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon start color="warning">mdi-alert-circle</v-icon>
          {{ t('simulationV2.resetDialog.title') }}
        </v-card-title>
        <v-card-text>
          <p class="mb-4">{{ t('simulationV2.resetDialog.prompt') }}</p>
          <v-list density="compact">
            <v-list-item
              prepend-icon="mdi-delete-sweep"
              :title="t('simulationV2.resetDialog.clearAll')"
              :subtitle="t('simulationV2.resetDialog.clearAllSubtitle')"
              @click="handleResetClear"
              class="rounded-lg mb-2"
              :class="{ 'bg-grey-lighten-4': true }"
              style="cursor: pointer;"
            />
            <v-list-item
              prepend-icon="mdi-tshirt-crew"
              :title="t('simulationV2.resetDialog.loadSampleData')"
              :subtitle="t('simulationV2.resetDialog.loadSampleSubtitle')"
              @click="handleResetToSample"
              class="rounded-lg"
              :class="{ 'bg-blue-lighten-5': true }"
              style="cursor: pointer;"
            />
          </v-list>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showResetDialog = false">{{ t('common.cancel') }}</v-btn>
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
          <strong>{{ t('simulationV2.welcome.title') }}</strong> {{ t('simulationV2.welcome.message') }}
        </div>
      </div>
      <template v-slot:actions>
        <v-btn variant="text" @click="showWelcomeMessage = false">{{ t('simulationV2.welcome.gotIt') }}</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSimulationV2Store } from '@/stores/simulationV2Store'
import OperationsGrid from '@/components/simulation/OperationsGrid.vue'
import ScheduleForm from '@/components/simulation/ScheduleForm.vue'
import DemandGrid from '@/components/simulation/DemandGrid.vue'
import BreakdownsGrid from '@/components/simulation/BreakdownsGrid.vue'
import ValidationPanel from '@/components/simulation/ValidationPanel.vue'
import ResultsView from '@/components/simulation/ResultsView.vue'

const { t } = useI18n()
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
    store.error = t('simulationV2.importDialog.invalidJson') + ': ' + error.message
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
