<template>
  <div class="my-shift-dashboard" role="region" aria-label="My Shift Dashboard">
    <!-- Header Section -->
    <v-row class="mb-4">
      <v-col cols="12">
        <v-card class="shift-header-card" elevation="2">
          <v-card-text class="pa-4">
            <div class="d-flex flex-column flex-sm-row justify-space-between align-start align-sm-center gap-3">
              <!-- Shift Info -->
              <div class="d-flex align-center gap-3">
                <v-avatar :color="shiftStatusColor" size="56" class="elevation-2">
                  <v-icon size="28" color="white">{{ shiftStatusIcon }}</v-icon>
                </v-avatar>
                <div>
                  <h1 class="text-h5 font-weight-bold mb-1">
                    {{ hasActiveShift ? `${t('production.shift')} ${activeShift?.shift_number || 1}` : t('navigation.myShift') }}
                  </h1>
                  <div class="d-flex align-center gap-2 flex-wrap">
                    <v-chip
                      :color="shiftStatusColor"
                      size="small"
                      variant="flat"
                      class="font-weight-medium"
                    >
                      {{ shiftStatusText }}
                    </v-chip>
                    <span v-if="hasActiveShift" class="text-body-2 text-grey">
                      {{ t('shifts.started') }} {{ formatTime(activeShift?.start_time) }} ({{ shiftDuration }})
                    </span>
                    <span v-else class="text-body-2 text-grey">
                      {{ currentDateFormatted }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Quick Actions -->
              <div class="d-flex gap-2">
                <v-btn
                  v-if="!hasActiveShift"
                  color="success"
                  size="large"
                  class="touch-target"
                  @click="handleStartShift"
                >
                  <v-icon start>mdi-play-circle</v-icon>
                  {{ t('common.start') }} {{ t('production.shift') }}
                </v-btn>
                <v-btn
                  v-else
                  color="error"
                  variant="outlined"
                  size="large"
                  class="touch-target"
                  @click="handleEndShift"
                >
                  <v-icon start>mdi-stop-circle</v-icon>
                  {{ t('common.end') }} {{ t('production.shift') }}
                </v-btn>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Main Content Grid -->
    <v-row>
      <!-- Left Column: Tasks & Stats -->
      <v-col cols="12" lg="8">
        <!-- My Tasks Panel -->
        <v-card class="mb-4" elevation="2">
          <v-card-title class="d-flex align-center bg-primary text-white py-3">
            <v-icon class="mr-2">mdi-clipboard-check-outline</v-icon>
            {{ t('navigation.myShift') }}
            <v-spacer />
            <v-chip color="white" variant="flat" size="small" class="text-primary">
              {{ assignedWorkOrders.length }} {{ t('common.active') }}
            </v-chip>
          </v-card-title>
          <v-card-text class="pa-0">
            <v-list v-if="assignedWorkOrders.length > 0" class="py-0">
              <template v-for="(wo, index) in assignedWorkOrders" :key="wo.id">
                <v-divider v-if="index > 0" />
                <v-list-item class="py-3 px-4">
                  <template v-slot:prepend>
                    <v-progress-circular
                      :model-value="getProgressPercent(wo)"
                      :color="getProgressColor(wo)"
                      :size="48"
                      :width="5"
                      class="mr-3"
                    >
                      <span class="text-caption font-weight-bold">{{ getProgressPercent(wo) }}%</span>
                    </v-progress-circular>
                  </template>

                  <v-list-item-title class="font-weight-medium mb-1">
                    {{ wo.work_order_id }}
                  </v-list-item-title>
                  <v-list-item-subtitle>
                    <span class="text-body-2">
                      {{ wo.product_name }} - {{ wo.produced || 0 }} / {{ wo.target_qty }} units
                    </span>
                  </v-list-item-subtitle>

                  <template v-slot:append>
                    <v-btn
                      color="primary"
                      variant="elevated"
                      size="small"
                      class="touch-target-small"
                      @click="openQuickLog(wo)"
                    >
                      <v-icon start size="18">mdi-plus</v-icon>
                      {{ t('shifts.log') }}
                    </v-btn>
                  </template>
                </v-list-item>
              </template>
            </v-list>

            <div v-else class="pa-6 text-center">
              <v-icon size="48" color="grey-lighten-1" class="mb-3">mdi-clipboard-text-off-outline</v-icon>
              <p class="text-body-1 text-grey">{{ t('common.noData') }}</p>
              <v-btn color="primary" variant="outlined" class="mt-2" @click="goToWorkOrders">
                {{ t('navigation.workOrders') }}
              </v-btn>
            </div>
          </v-card-text>
        </v-card>

        <!-- My Stats Panel -->
        <v-card class="mb-4" elevation="2">
          <v-card-title class="d-flex align-center bg-grey-darken-3 text-white py-3">
            <v-icon class="mr-2">mdi-chart-bar</v-icon>
            {{ t('dashboard.todaySummary') }}
          </v-card-title>
          <v-card-text class="pa-4">
            <v-row>
              <v-col v-for="stat in statCards" :key="stat.key" cols="6" sm="3">
                <div class="stat-card text-center pa-3">
                  <v-icon :color="stat.color" size="32" class="mb-2">{{ stat.icon }}</v-icon>
                  <div class="text-h4 font-weight-bold" :class="`text-${stat.color}`">{{ stat.value }}{{ stat.suffix || '' }}</div>
                  <div class="text-caption text-grey">{{ t(stat.labelKey) }}</div>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- Recent Activity -->
        <v-card elevation="2">
          <v-card-title class="d-flex align-center bg-grey-darken-3 text-white py-3">
            <v-icon class="mr-2">mdi-history</v-icon>
            {{ t('common.recentActivity') }}
            <v-spacer />
            <v-btn icon variant="text" size="small" color="white" @click="refreshActivity">
              <v-icon>mdi-refresh</v-icon>
            </v-btn>
          </v-card-title>
          <v-card-text class="pa-0">
            <v-list v-if="recentActivity.length > 0" class="py-0">
              <template v-for="(activity, index) in recentActivity" :key="activity.id">
                <v-divider v-if="index > 0" />
                <v-list-item class="py-2 px-4">
                  <template v-slot:prepend>
                    <v-avatar :color="getActivityColor(activity.type)" size="36">
                      <v-icon size="18" color="white">{{ getActivityIcon(activity.type) }}</v-icon>
                    </v-avatar>
                  </template>

                  <v-list-item-title class="text-body-2">
                    {{ activity.description }}
                  </v-list-item-title>
                  <v-list-item-subtitle class="text-caption">
                    {{ formatRelativeTime(activity.timestamp) }}
                  </v-list-item-subtitle>

                  <template v-slot:append>
                    <v-btn icon variant="text" size="small" @click="editActivity(activity)">
                      <v-icon size="18">mdi-pencil</v-icon>
                    </v-btn>
                  </template>
                </v-list-item>
              </template>
            </v-list>

            <div v-else class="pa-6 text-center">
              <v-icon size="40" color="grey-lighten-1" class="mb-2">mdi-history</v-icon>
              <p class="text-body-2 text-grey">{{ t('common.noData') }}</p>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Right Column: Data Completeness & Quick Entry -->
      <v-col cols="12" lg="4">
        <!-- Data Completeness -->
        <v-card class="mb-4" elevation="2">
          <v-card-title class="bg-grey-darken-3 text-white py-3">
            <v-icon class="mr-2">mdi-clipboard-check</v-icon>
            {{ t('common.status') }}
          </v-card-title>
          <v-card-text class="pa-3">
            <DataCompletenessIndicator
              :date="currentDate"
              :shift="activeShift?.shift_number?.toString()"
              compact
              @navigate="handleCompletenessNavigate"
            />
          </v-card-text>
        </v-card>

        <!-- Quick Entry Cards -->
        <v-card elevation="2">
          <v-card-title class="bg-primary text-white py-3">
            <v-icon class="mr-2">mdi-lightning-bolt</v-icon>
            {{ t('common.actions') }}
          </v-card-title>
          <v-card-text class="pa-4">
            <v-row class="quick-actions-grid">
              <v-col v-for="action in quickActions" :key="action.key" cols="6">
                <v-card class="quick-action-card elevation-1" :color="action.color" @click="action.handler" role="button" tabindex="0">
                  <v-card-text class="text-center pa-4">
                    <v-icon size="40" color="white" class="mb-2">{{ action.icon }}</v-icon>
                    <div class="text-body-1 font-weight-medium text-white">{{ t(action.labelKey) }}</div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>

            <!-- Quick Production Presets -->
            <v-divider class="my-4" />
            <div class="text-subtitle-2 text-grey mb-3">{{ t('common.units') }}</div>
            <div class="d-flex gap-2 flex-wrap justify-center">
              <v-btn
                v-for="preset in productionPresets"
                :key="preset"
                color="primary"
                variant="outlined"
                size="large"
                class="touch-target preset-btn"
                :disabled="!selectedWorkOrder"
                @click="quickLogProduction(preset)"
              >
                +{{ preset }}
              </v-btn>
            </div>
            <p v-if="!selectedWorkOrder" class="text-caption text-grey text-center mt-2">
              {{ t('shifts.selectWorkOrderForQuickLog') }}
            </p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Dialogs (extracted sub-component) -->
    <ShiftDashboardDialogs
      v-model:show-production-dialog="showProductionDialog"
      v-model:show-downtime-dialog="showDowntimeDialog"
      v-model:show-quality-dialog="showQualityDialog"
      v-model:show-help-dialog="showHelpDialog"
      :is-submitting="isSubmitting"
      :production-form="productionForm"
      :downtime-form="downtimeForm"
      :quality-form="qualityForm"
      :help-form="helpForm"
      :work-order-options="workOrderOptions"
      :production-presets="productionPresets"
      :downtime-reasons="downtimeReasons"
      :defect-types="defectTypes"
      :help-types="helpTypes"
      @submit-production="submitProduction"
      @submit-downtime="submitDowntime"
      @submit-quality="submitQuality"
      @submit-help-request="submitHelpRequest"
    />

    <!-- Success Snackbar -->
    <v-snackbar
      v-model="showSuccess"
      :timeout="3000"
      color="success"
      location="bottom"
    >
      {{ successMessage }}
      <template v-slot:actions>
        <v-btn variant="text" @click="showSuccess = false">{{ t('common.close') }}</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useWorkflowStore } from '@/stores/workflowStore'
import DataCompletenessIndicator from '@/components/DataCompletenessIndicator.vue'
import ShiftDashboardDialogs from '@/components/dialogs/ShiftDashboardDialogs.vue'

// Composables
import { useShiftDashboardData } from '@/composables/useShiftDashboardData'
import { useShiftForms } from '@/composables/useShiftForms'

const { t } = useI18n()
const router = useRouter()
const workflowStore = useWorkflowStore()

// Data, timer, and display logic
const {
  assignedWorkOrders,
  recentActivity,
  myStats,
  activeShift,
  hasActiveShift,
  currentDate,
  currentDateFormatted,
  shiftStatusColor,
  shiftStatusIcon,
  shiftStatusText,
  shiftDuration,
  workOrderOptions,
  formatTime,
  formatRelativeTime,
  getProgressPercent,
  getProgressColor,
  getActivityColor,
  getActivityIcon,
  fetchMyShiftData,
  initialize,
  cleanup
} = useShiftDashboardData()

// Form and submission logic
const {
  showProductionDialog,
  showDowntimeDialog,
  showQualityDialog,
  showHelpDialog,
  isSubmitting,
  showSuccess,
  successMessage,
  selectedWorkOrder,
  productionForm,
  downtimeForm,
  qualityForm,
  helpForm,
  productionPresets,
  downtimeReasons,
  defectTypes,
  helpTypes,
  openQuickLog,
  openQuickProductionDialog,
  openDowntimeDialog,
  openQualityDialog,
  openHelpDialog,
  quickLogProduction,
  submitProduction,
  submitDowntime,
  submitQuality,
  submitHelpRequest
} = useShiftForms(
  () => activeShift.value,
  () => currentDate.value,
  () => assignedWorkOrders.value,
  fetchMyShiftData
)

// Data-driven template helpers
const quickActions = [
  { key: 'production', color: 'primary', icon: 'mdi-package-variant-plus', labelKey: 'production.title', handler: openQuickProductionDialog },
  { key: 'downtime', color: 'warning', icon: 'mdi-clock-alert', labelKey: 'downtime.title', handler: openDowntimeDialog },
  { key: 'quality', color: 'success', icon: 'mdi-check-decagram', labelKey: 'quality.title', handler: openQualityDialog },
  { key: 'help', color: 'error', icon: 'mdi-hand-wave', labelKey: 'common.help', handler: openHelpDialog }
]

const statCards = computed(() => [
  { key: 'units', color: 'primary', icon: 'mdi-package-variant', value: myStats.value.unitsProduced, labelKey: 'production.unitsProduced' },
  { key: 'efficiency', color: 'success', icon: 'mdi-speedometer', value: myStats.value.efficiency, suffix: '%', labelKey: 'kpi.efficiency' },
  { key: 'downtime', color: 'warning', icon: 'mdi-clock-alert', value: myStats.value.downtimeIncidents, labelKey: 'downtime.title' },
  { key: 'quality', color: 'info', icon: 'mdi-check-decagram', value: myStats.value.qualityChecks, labelKey: 'quality.title' }
])

// Shift workflow actions
const handleStartShift = () => {
  workflowStore.startWorkflow('shift-start')
}

const handleEndShift = () => {
  workflowStore.startWorkflow('shift-end')
}

// Navigation
const handleCompletenessNavigate = (categoryId, route) => {
  router.push(route)
}

const goToWorkOrders = () => {
  router.push('/work-orders')
}

const refreshActivity = () => {
  fetchMyShiftData()
}

const editActivity = (activity) => {
  const routes = {
    production: '/production-entry',
    downtime: '/data-entry/downtime',
    quality: '/data-entry/quality',
    hold: '/data-entry/hold-resume'
  }
  router.push(routes[activity.type] || '/')
}

// Lifecycle
onMounted(async () => {
  await initialize()
})

onUnmounted(() => {
  cleanup()
})
</script>

<style scoped>
.my-shift-dashboard { max-width: 1400px; margin: 0 auto; }
.shift-header-card { background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%); color: white; }
.shift-header-card .v-card-text { color: white !important; }
.stat-card { background: rgba(0, 0, 0, 0.03); border-radius: 12px; }
.touch-target { min-height: 48px !important; min-width: 48px !important; }
.touch-target-small { min-height: 44px !important; min-width: 44px !important; }
.preset-btn { min-width: 64px !important; font-weight: bold; }
.gap-2 { gap: 8px; }
.gap-3 { gap: 12px; }
.text-h4.font-weight-bold { letter-spacing: -0.5px; }
.v-btn, .v-list-item, .quick-action-card { -webkit-tap-highlight-color: transparent; }

.quick-action-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  border-radius: 12px !important;
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.quick-action-card:hover, .quick-action-card:focus {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2) !important;
}
.quick-action-card:active { transform: translateY(0); }

@media (max-width: 600px) {
  .my-shift-dashboard { padding: 0 8px; }
  .v-card-title { font-size: 1rem; padding: 12px 16px !important; }
  .quick-action-card { min-height: 100px; }
  .quick-action-card .v-icon { font-size: 32px !important; }
  .quick-action-card .text-body-1 { font-size: 0.875rem !important; }
  .stat-card { padding: 8px !important; }
  .stat-card .text-h4 { font-size: 1.5rem !important; }
  .preset-btn { min-width: 56px !important; padding: 0 12px !important; }
}
</style>
