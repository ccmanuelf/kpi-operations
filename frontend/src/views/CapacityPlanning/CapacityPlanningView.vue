<template>
  <v-container fluid>
    <!-- Header -->
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <v-icon start color="primary">mdi-factory</v-icon>
            {{ t('capacityPlanningView.title') }}
            <v-spacer />
            <!-- Client Selector -->
            <v-select
              v-model="selectedClient"
              :items="clients"
              item-title="client_name"
              item-value="client_id"
              :label="t('common.client')"
              density="compact"
              variant="outlined"
              hide-details
              :loading="clientsLoading"
              class="mr-4"
              style="max-width: 250px;"
            >
              <template v-slot:item="{ props, item }">
                <v-list-item v-bind="props">
                  <template v-slot:subtitle>
                    ID: {{ item.raw.client_id }}
                  </template>
                </v-list-item>
              </template>
            </v-select>
            <v-btn
              icon
              size="small"
              variant="text"
              :disabled="!store.canUndo"
              @click="store.undo()"
              :title="t('capacityPlanningView.undoTooltip')"
              class="mr-1"
            >
              <v-icon>mdi-undo</v-icon>
            </v-btn>
            <v-btn
              icon
              size="small"
              variant="text"
              :disabled="!store.canRedo"
              @click="store.redo()"
              :title="t('capacityPlanningView.redoTooltip')"
              class="mr-2"
            >
              <v-icon>mdi-redo</v-icon>
            </v-btn>
            <v-chip color="info" variant="tonal" class="mr-2">
              {{ t('capacityPlanningView.worksheetCount') }}
            </v-chip>
            <v-btn
              color="success"
              variant="elevated"
              :loading="store.isSaving"
              :disabled="!store.hasUnsavedChanges"
              @click="saveAll"
            >
              <v-icon start>mdi-content-save</v-icon>
              {{ t('capacityPlanningView.saveAllChanges') }}
            </v-btn>
          </v-card-title>
          <v-card-subtitle>
            {{ t('capacityPlanningView.subtitle') }}
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
            <span>{{ t('capacityPlanningView.unsavedChangesIn', { worksheets: store.dirtyWorksheets.join(', ') }) }}</span>
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
      <div class="mt-4 text-h6">{{ t('capacityPlanningView.loadingWorkbook') }}</div>
    </v-overlay>

    <!-- No Client Selected Warning -->
    <v-row v-if="!selectedClient && !clientsLoading && !store.isLoading" class="mt-2">
      <v-col cols="12">
        <v-alert type="info" variant="tonal">
          <div class="d-flex align-center">
            <v-icon start>mdi-information</v-icon>
            <span>{{ t('capacityPlanningView.selectClientPrompt') }}</span>
          </div>
        </v-alert>
      </v-col>
    </v-row>

    <!-- Summary Stats Bar -->
    <v-row v-if="!store.isLoading && selectedClient" class="mt-2">
      <v-col cols="12">
        <v-card variant="tonal" color="primary">
          <v-card-text class="d-flex align-center justify-space-around py-2">
            <div class="text-center">
              <div class="text-h6">{{ store.worksheets.orders.data.length }}</div>
              <div class="text-caption">{{ t('capacityPlanningView.stats.orders') }}</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.activeLineCount }}</div>
              <div class="text-caption">{{ t('capacityPlanningView.stats.lines') }}</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.bomCount }}</div>
              <div class="text-caption">{{ t('capacityPlanningView.stats.boms') }}</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.workingDaysCount }}</div>
              <div class="text-caption">{{ t('capacityPlanningView.stats.workingDays') }}</div>
            </div>
            <v-divider vertical class="mx-2" />
            <div class="text-center">
              <div class="text-h6">{{ store.shortageCount }}</div>
              <div class="text-caption text-error">{{ t('capacityPlanningView.stats.shortages') }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Tab Navigation -->
    <v-row v-if="selectedClient" class="mt-3">
      <v-col cols="12">
        <v-tabs v-model="activeTab" color="primary" show-arrows>
          <v-tab value="orders">
            <v-icon start>mdi-clipboard-list</v-icon>
            {{ t('capacityPlanningView.tabs.orders') }}
            <v-badge
              v-if="worksheetIsDirty('orders')"
              dot
              color="warning"
              class="ml-1"
            />
          </v-tab>
          <v-tab value="masterCalendar">
            <v-icon start>mdi-calendar</v-icon>
            {{ t('capacityPlanningView.tabs.calendar') }}
          </v-tab>
          <v-tab value="productionLines">
            <v-icon start>mdi-factory</v-icon>
            {{ t('capacityPlanningView.tabs.lines') }}
          </v-tab>
          <v-tab value="productionStandards">
            <v-icon start>mdi-timer</v-icon>
            {{ t('capacityPlanningView.tabs.standards') }}
          </v-tab>
          <v-tab value="bom">
            <v-icon start>mdi-file-tree</v-icon>
            {{ t('capacityPlanningView.tabs.bom') }}
          </v-tab>
          <v-tab value="stockSnapshot">
            <v-icon start>mdi-package-variant</v-icon>
            {{ t('capacityPlanningView.tabs.stock') }}
          </v-tab>
          <v-tab value="componentCheck">
            <v-icon start>mdi-check-decagram</v-icon>
            {{ t('capacityPlanningView.tabs.componentCheck') }}
          </v-tab>
          <v-tab value="capacityAnalysis">
            <v-icon start>mdi-chart-bar</v-icon>
            {{ t('capacityPlanningView.tabs.analysis') }}
          </v-tab>
          <v-tab value="productionSchedule">
            <v-icon start>mdi-calendar-clock</v-icon>
            {{ t('capacityPlanningView.tabs.schedule') }}
          </v-tab>
          <v-tab value="whatIfScenarios">
            <v-icon start>mdi-help-rhombus</v-icon>
            {{ t('capacityPlanningView.tabs.scenarios') }}
          </v-tab>
          <v-tab value="kpiTracking">
            <v-icon start>mdi-target</v-icon>
            {{ t('capacityPlanningView.tabs.kpiTracking') }}
          </v-tab>
          <v-tab value="dashboardInputs">
            <v-icon start>mdi-tune</v-icon>
            {{ t('capacityPlanningView.tabs.dashboardInputs') }}
          </v-tab>
          <v-tab value="instructions">
            <v-icon start>mdi-book-open-variant</v-icon>
            {{ t('capacityPlanningView.tabs.instructions') }}
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

          <!-- Dashboard Inputs Tab -->
          <v-tabs-window-item value="dashboardInputs">
            <DashboardInputsPanel />
          </v-tabs-window-item>

          <!-- Instructions Tab -->
          <v-tabs-window-item value="instructions">
            <InstructionsPanel />
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
              {{ t('capacityPlanningView.actions.runComponentCheck') }}
            </v-btn>

            <v-btn
              color="primary"
              variant="outlined"
              :loading="store.isRunningAnalysis"
              @click="showAnalysisDialog = true"
            >
              <v-icon start>mdi-chart-bar</v-icon>
              {{ t('capacityPlanningView.actions.runCapacityAnalysis') }}
            </v-btn>

            <v-btn
              color="success"
              variant="outlined"
              :loading="store.isGeneratingSchedule"
              @click="showScheduleDialog = true"
            >
              <v-icon start>mdi-calendar-clock</v-icon>
              {{ t('capacityPlanningView.actions.generateSchedule') }}
            </v-btn>

            <v-spacer />

            <v-btn
              color="secondary"
              variant="tonal"
              @click="showExportDialog = true"
            >
              <v-icon start>mdi-download</v-icon>
              {{ t('common.export') }}
            </v-btn>

            <v-btn
              color="secondary"
              variant="tonal"
              @click="showImportDialog = true"
            >
              <v-icon start>mdi-upload</v-icon>
              {{ t('common.import') }}
            </v-btn>

            <v-btn
              color="error"
              variant="outlined"
              @click="showResetDialog = true"
            >
              <v-icon start>mdi-refresh</v-icon>
              {{ t('common.reset') }}
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

    <!-- Workbook Action Dialogs (Analysis, Schedule, Export, Import, Reset) -->
    <WorkbookActionDialogs
      :state="dialogState"
      @runAnalysis="runCapacityAnalysis"
      @generateSchedule="generateSchedule"
      @exportWorkbook="exportWorkbook"
      @importData="importData"
      @handleReset="handleReset"
    />
  </v-container>
</template>

<script setup>
import { reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityData } from '@/composables/useCapacityData'
import { useCapacityExport } from '@/composables/useCapacityExport'

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
import DashboardInputsPanel from './components/panels/DashboardInputsPanel.vue'
import InstructionsPanel from './components/panels/InstructionsPanel.vue'

// Dialog components
import MRPResultsDialog from './components/dialogs/MRPResultsDialog.vue'
import ScenarioCompareDialog from './components/dialogs/ScenarioCompareDialog.vue'
import ScheduleCommitDialog from './components/dialogs/ScheduleCommitDialog.vue'
import WorkbookActionDialogs from './components/dialogs/WorkbookActionDialogs.vue'

const { t } = useI18n()

// Workbook data management, client selection, actions, lifecycle
const {
  store,
  clients,
  selectedClient,
  clientsLoading,
  activeTab,
  showAnalysisDialog,
  showScheduleDialog,
  showResetDialog,
  analysisStartDate,
  analysisEndDate,
  scheduleName,
  scheduleStartDate,
  scheduleEndDate,
  worksheetIsDirty,
  saveAll,
  runComponentCheck,
  runCapacityAnalysis,
  generateSchedule,
  handleCommitSchedule,
  handleReset,
} = useCapacityData()

// Import/export functionality
const {
  showExportDialog,
  showImportDialog,
  exportFormat,
  importFile,
  importTarget,
  worksheetOptions,
  exportWorkbook,
  importData,
} = useCapacityExport(activeTab)

// Reactive state object for dialog sub-component (auto-unwraps refs)
const dialogState = reactive({
  showAnalysisDialog,
  analysisStartDate,
  analysisEndDate,
  showScheduleDialog,
  scheduleName,
  scheduleStartDate,
  scheduleEndDate,
  showExportDialog,
  exportFormat,
  showImportDialog,
  importFile,
  importTarget,
  worksheetOptions,
  showResetDialog,
})
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
