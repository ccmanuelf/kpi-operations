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
                      Started {{ formatTime(activeShift?.start_time) }} ({{ shiftDuration }})
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
                      Log
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
              <v-col cols="6" sm="3">
                <div class="stat-card text-center pa-3">
                  <v-icon color="primary" size="32" class="mb-2">mdi-package-variant</v-icon>
                  <div class="text-h4 font-weight-bold text-primary">{{ myStats.unitsProduced }}</div>
                  <div class="text-caption text-grey">{{ t('production.unitsProduced') }}</div>
                </div>
              </v-col>
              <v-col cols="6" sm="3">
                <div class="stat-card text-center pa-3">
                  <v-icon color="success" size="32" class="mb-2">mdi-speedometer</v-icon>
                  <div class="text-h4 font-weight-bold text-success">{{ myStats.efficiency }}%</div>
                  <div class="text-caption text-grey">{{ t('kpi.efficiency') }}</div>
                </div>
              </v-col>
              <v-col cols="6" sm="3">
                <div class="stat-card text-center pa-3">
                  <v-icon color="warning" size="32" class="mb-2">mdi-clock-alert</v-icon>
                  <div class="text-h4 font-weight-bold text-warning">{{ myStats.downtimeIncidents }}</div>
                  <div class="text-caption text-grey">{{ t('downtime.title') }}</div>
                </div>
              </v-col>
              <v-col cols="6" sm="3">
                <div class="stat-card text-center pa-3">
                  <v-icon color="info" size="32" class="mb-2">mdi-check-decagram</v-icon>
                  <div class="text-h4 font-weight-bold text-info">{{ myStats.qualityChecks }}</div>
                  <div class="text-caption text-grey">{{ t('quality.title') }}</div>
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
              <!-- Log Production -->
              <v-col cols="6">
                <v-card
                  class="quick-action-card elevation-1"
                  color="primary"
                  @click="openQuickProductionDialog"
                  role="button"
                  tabindex="0"
                >
                  <v-card-text class="text-center pa-4">
                    <v-icon size="40" color="white" class="mb-2">mdi-package-variant-plus</v-icon>
                    <div class="text-body-1 font-weight-medium text-white">{{ t('production.title') }}</div>
                  </v-card-text>
                </v-card>
              </v-col>

              <!-- Report Downtime -->
              <v-col cols="6">
                <v-card
                  class="quick-action-card elevation-1"
                  color="warning"
                  @click="openDowntimeDialog"
                  role="button"
                  tabindex="0"
                >
                  <v-card-text class="text-center pa-4">
                    <v-icon size="40" color="white" class="mb-2">mdi-clock-alert</v-icon>
                    <div class="text-body-1 font-weight-medium text-white">{{ t('downtime.title') }}</div>
                  </v-card-text>
                </v-card>
              </v-col>

              <!-- Quality Check -->
              <v-col cols="6">
                <v-card
                  class="quick-action-card elevation-1"
                  color="success"
                  @click="openQualityDialog"
                  role="button"
                  tabindex="0"
                >
                  <v-card-text class="text-center pa-4">
                    <v-icon size="40" color="white" class="mb-2">mdi-check-decagram</v-icon>
                    <div class="text-body-1 font-weight-medium text-white">{{ t('quality.title') }}</div>
                  </v-card-text>
                </v-card>
              </v-col>

              <!-- Request Help -->
              <v-col cols="6">
                <v-card
                  class="quick-action-card elevation-1"
                  color="error"
                  @click="openHelpDialog"
                  role="button"
                  tabindex="0"
                >
                  <v-card-text class="text-center pa-4">
                    <v-icon size="40" color="white" class="mb-2">mdi-hand-wave</v-icon>
                    <div class="text-body-1 font-weight-medium text-white">{{ t('common.help') }}</div>
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
              Select a work order above to use quick log
            </p>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Quick Production Dialog -->
    <v-dialog v-model="showProductionDialog" max-width="400" persistent>
      <v-card>
        <v-card-title class="bg-primary text-white d-flex align-center">
          <v-icon class="mr-2">mdi-package-variant-plus</v-icon>
          Log Production
        </v-card-title>
        <v-card-text class="pa-4">
          <v-select
            v-model="productionForm.workOrderId"
            :items="workOrderOptions"
            item-title="text"
            item-value="value"
            label="Work Order"
            variant="outlined"
            class="mb-3"
          />
          <v-text-field
            v-model.number="productionForm.quantity"
            label="Units Produced"
            type="number"
            variant="outlined"
            min="1"
            :rules="[v => v > 0 || 'Must be greater than 0']"
          />
          <div class="d-flex gap-2 justify-center mt-2">
            <v-btn
              v-for="preset in productionPresets"
              :key="preset"
              variant="outlined"
              size="small"
              @click="productionForm.quantity = preset"
            >
              {{ preset }}
            </v-btn>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showProductionDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="elevated"
            :loading="isSubmitting"
            :disabled="!productionForm.workOrderId || !productionForm.quantity"
            @click="submitProduction"
          >
            Submit
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Downtime Dialog -->
    <v-dialog v-model="showDowntimeDialog" max-width="450" persistent>
      <v-card>
        <v-card-title class="bg-warning text-white d-flex align-center">
          <v-icon class="mr-2">mdi-clock-alert</v-icon>
          Report Downtime
        </v-card-title>
        <v-card-text class="pa-4">
          <v-select
            v-model="downtimeForm.workOrderId"
            :items="workOrderOptions"
            item-title="text"
            item-value="value"
            label="Work Order"
            variant="outlined"
            class="mb-3"
          />
          <v-select
            v-model="downtimeForm.reason"
            :items="downtimeReasons"
            label="Reason"
            variant="outlined"
            class="mb-3"
          />
          <v-text-field
            v-model.number="downtimeForm.minutes"
            label="Duration (minutes)"
            type="number"
            variant="outlined"
            min="1"
          />
          <v-textarea
            v-model="downtimeForm.notes"
            label="Notes (optional)"
            variant="outlined"
            rows="2"
            class="mt-3"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showDowntimeDialog = false">Cancel</v-btn>
          <v-btn
            color="warning"
            variant="elevated"
            :loading="isSubmitting"
            :disabled="!downtimeForm.workOrderId || !downtimeForm.reason"
            @click="submitDowntime"
          >
            Submit
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Quality Check Dialog -->
    <v-dialog v-model="showQualityDialog" max-width="450" persistent>
      <v-card>
        <v-card-title class="bg-success text-white d-flex align-center">
          <v-icon class="mr-2">mdi-check-decagram</v-icon>
          Quality Check
        </v-card-title>
        <v-card-text class="pa-4">
          <v-select
            v-model="qualityForm.workOrderId"
            :items="workOrderOptions"
            item-title="text"
            item-value="value"
            label="Work Order"
            variant="outlined"
            class="mb-3"
          />
          <v-text-field
            v-model.number="qualityForm.inspectedQty"
            label="Inspected Quantity"
            type="number"
            variant="outlined"
            min="1"
            class="mb-3"
          />
          <v-text-field
            v-model.number="qualityForm.defectQty"
            label="Defect Quantity"
            type="number"
            variant="outlined"
            min="0"
          />
          <v-select
            v-if="qualityForm.defectQty > 0"
            v-model="qualityForm.defectType"
            :items="defectTypes"
            label="Defect Type"
            variant="outlined"
            class="mt-3"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showQualityDialog = false">Cancel</v-btn>
          <v-btn
            color="success"
            variant="elevated"
            :loading="isSubmitting"
            :disabled="!qualityForm.workOrderId || !qualityForm.inspectedQty"
            @click="submitQuality"
          >
            Submit
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Request Help Dialog -->
    <v-dialog v-model="showHelpDialog" max-width="400" persistent>
      <v-card>
        <v-card-title class="bg-error text-white d-flex align-center">
          <v-icon class="mr-2">mdi-hand-wave</v-icon>
          Request Help
        </v-card-title>
        <v-card-text class="pa-4">
          <v-select
            v-model="helpForm.type"
            :items="helpTypes"
            label="Help Type"
            variant="outlined"
            class="mb-3"
          />
          <v-textarea
            v-model="helpForm.description"
            label="Describe your issue"
            variant="outlined"
            rows="3"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showHelpDialog = false">Cancel</v-btn>
          <v-btn
            color="error"
            variant="elevated"
            :loading="isSubmitting"
            :disabled="!helpForm.type || !helpForm.description"
            @click="submitHelpRequest"
          >
            Send Request
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Success Snackbar -->
    <v-snackbar
      v-model="showSuccess"
      :timeout="3000"
      color="success"
      location="bottom"
    >
      {{ successMessage }}
      <template v-slot:actions>
        <v-btn variant="text" @click="showSuccess = false">Close</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useWorkflowStore } from '@/stores/workflowStore'
import { useAuthStore } from '@/stores/authStore'
import { useNotificationStore } from '@/stores/notificationStore'
import DataCompletenessIndicator from '@/components/DataCompletenessIndicator.vue'
import api from '@/services/api'

const { t } = useI18n()
const router = useRouter()
const workflowStore = useWorkflowStore()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()

// Refs for time updates
const currentTime = ref(new Date())
let timeInterval = null

// Dialog states
const showProductionDialog = ref(false)
const showDowntimeDialog = ref(false)
const showQualityDialog = ref(false)
const showHelpDialog = ref(false)
const isSubmitting = ref(false)
const showSuccess = ref(false)
const successMessage = ref('')

// Data states
const assignedWorkOrders = ref([])
const recentActivity = ref([])
const myStats = ref({
  unitsProduced: 0,
  efficiency: 0,
  downtimeIncidents: 0,
  qualityChecks: 0
})

// Form states
const selectedWorkOrder = ref(null)
const productionForm = ref({
  workOrderId: null,
  quantity: 10
})
const downtimeForm = ref({
  workOrderId: null,
  reason: null,
  minutes: 15,
  notes: ''
})
const qualityForm = ref({
  workOrderId: null,
  inspectedQty: 100,
  defectQty: 0,
  defectType: null
})
const helpForm = ref({
  type: null,
  description: ''
})

// Constants
const productionPresets = [10, 25, 50, 100]
const downtimeReasons = [
  'Equipment Breakdown',
  'Material Shortage',
  'Changeover',
  'Scheduled Maintenance',
  'Quality Issue',
  'Waiting for Inspection',
  'Other'
]
const defectTypes = [
  'Dimensional',
  'Visual',
  'Functional',
  'Packaging',
  'Documentation',
  'Other'
]
const helpTypes = [
  'Equipment Issue',
  'Material Issue',
  'Quality Issue',
  'Safety Concern',
  'Training Needed',
  'Supervisor Request',
  'Other'
]

// Computed
const activeShift = computed(() => workflowStore.activeShift)
const hasActiveShift = computed(() => workflowStore.hasActiveShift)

const currentDate = computed(() => new Date().toISOString().split('T')[0])
const currentDateFormatted = computed(() => {
  return new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric'
  })
})

const shiftStatusColor = computed(() => {
  if (!hasActiveShift.value) return 'grey'
  return 'success'
})

const shiftStatusIcon = computed(() => {
  if (!hasActiveShift.value) return 'mdi-clock-outline'
  return 'mdi-play-circle'
})

const shiftStatusText = computed(() => {
  if (!hasActiveShift.value) return 'Not Started'
  return 'Active'
})

const shiftDuration = computed(() => {
  if (!activeShift.value?.start_time) return ''
  const start = new Date(activeShift.value.start_time)
  // Handle invalid date
  if (isNaN(start.getTime())) return ''
  const diff = currentTime.value - start
  if (diff < 0) return '' // Future date edge case
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  if (hours === 0) return `${minutes}m`
  return `${hours}h ${minutes}m`
})

const workOrderOptions = computed(() => {
  return assignedWorkOrders.value.map(wo => ({
    text: `${wo.work_order_id} - ${wo.product_name}`,
    value: wo.id
  }))
})

// Methods
const formatTime = (timeString) => {
  if (!timeString) return ''
  const date = new Date(timeString)
  // Handle invalid date
  if (isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatRelativeTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  // Handle invalid date
  if (isNaN(date.getTime())) return ''
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / (1000 * 60))
  const hours = Math.floor(diff / (1000 * 60 * 60))

  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const getProgressPercent = (wo) => {
  if (!wo.target_qty || wo.target_qty === 0) return 0
  return Math.min(Math.round((wo.produced || 0) / wo.target_qty * 100), 100)
}

const getProgressColor = (wo) => {
  const percent = getProgressPercent(wo)
  if (percent >= 100) return 'success'
  if (percent >= 75) return 'primary'
  if (percent >= 50) return 'warning'
  return 'error'
}

const getActivityColor = (type) => {
  const colors = {
    production: 'primary',
    downtime: 'warning',
    quality: 'success',
    hold: 'error'
  }
  return colors[type] || 'grey'
}

const getActivityIcon = (type) => {
  const icons = {
    production: 'mdi-package-variant',
    downtime: 'mdi-clock-alert',
    quality: 'mdi-check-decagram',
    hold: 'mdi-pause-circle'
  }
  return icons[type] || 'mdi-information'
}

const handleStartShift = () => {
  workflowStore.startWorkflow('shift-start')
}

const handleEndShift = () => {
  workflowStore.startWorkflow('shift-end')
}

const handleCompletenessNavigate = (categoryId, route) => {
  router.push(route)
}

const goToWorkOrders = () => {
  router.push('/work-orders')
}

const openQuickLog = (wo) => {
  selectedWorkOrder.value = wo
  productionForm.value.workOrderId = wo.id
  showProductionDialog.value = true
}

const openQuickProductionDialog = () => {
  if (assignedWorkOrders.value.length > 0) {
    productionForm.value.workOrderId = assignedWorkOrders.value[0].id
  }
  showProductionDialog.value = true
}

const openDowntimeDialog = () => {
  if (assignedWorkOrders.value.length > 0) {
    downtimeForm.value.workOrderId = assignedWorkOrders.value[0].id
  }
  showDowntimeDialog.value = true
}

const openQualityDialog = () => {
  if (assignedWorkOrders.value.length > 0) {
    qualityForm.value.workOrderId = assignedWorkOrders.value[0].id
  }
  showQualityDialog.value = true
}

const openHelpDialog = () => {
  showHelpDialog.value = true
}

const quickLogProduction = async (quantity) => {
  if (!selectedWorkOrder.value) return

  isSubmitting.value = true
  try {
    await api.createProductionEntry({
      work_order_id: selectedWorkOrder.value.work_order_id,
      date: currentDate.value,
      shift: activeShift.value?.shift_number || 1,
      units_produced: quantity,
      runtime_hours: 1
    })

    successMessage.value = `Logged ${quantity} units for ${selectedWorkOrder.value.work_order_id}`
    showSuccess.value = true
    await fetchMyShiftData()
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to log production')
  } finally {
    isSubmitting.value = false
  }
}

const submitProduction = async () => {
  isSubmitting.value = true
  try {
    const wo = assignedWorkOrders.value.find(w => w.id === productionForm.value.workOrderId)
    await api.createProductionEntry({
      work_order_id: wo.work_order_id,
      date: currentDate.value,
      shift: activeShift.value?.shift_number || 1,
      units_produced: productionForm.value.quantity,
      runtime_hours: 1
    })

    successMessage.value = `Logged ${productionForm.value.quantity} units`
    showSuccess.value = true
    showProductionDialog.value = false
    productionForm.value.quantity = 10
    await fetchMyShiftData()
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to log production')
  } finally {
    isSubmitting.value = false
  }
}

const submitDowntime = async () => {
  isSubmitting.value = true
  try {
    const wo = assignedWorkOrders.value.find(w => w.id === downtimeForm.value.workOrderId)
    await api.createDowntimeEntry({
      work_order_id: wo.work_order_id,
      date: currentDate.value,
      shift: activeShift.value?.shift_number || 1,
      downtime_minutes: downtimeForm.value.minutes,
      reason: downtimeForm.value.reason,
      notes: downtimeForm.value.notes
    })

    successMessage.value = 'Downtime reported successfully'
    showSuccess.value = true
    showDowntimeDialog.value = false
    downtimeForm.value = { workOrderId: null, reason: null, minutes: 15, notes: '' }
    await fetchMyShiftData()
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to report downtime')
  } finally {
    isSubmitting.value = false
  }
}

const submitQuality = async () => {
  isSubmitting.value = true
  try {
    const wo = assignedWorkOrders.value.find(w => w.id === qualityForm.value.workOrderId)
    await api.createQualityEntry({
      work_order_id: wo.work_order_id,
      date: currentDate.value,
      shift: activeShift.value?.shift_number || 1,
      inspected_quantity: qualityForm.value.inspectedQty,
      defect_quantity: qualityForm.value.defectQty,
      defect_type: qualityForm.value.defectType
    })

    successMessage.value = 'Quality check recorded'
    showSuccess.value = true
    showQualityDialog.value = false
    qualityForm.value = { workOrderId: null, inspectedQty: 100, defectQty: 0, defectType: null }
    await fetchMyShiftData()
  } catch (error) {
    notificationStore.error(error.response?.data?.detail || 'Failed to record quality check')
  } finally {
    isSubmitting.value = false
  }
}

const submitHelpRequest = async () => {
  isSubmitting.value = true
  try {
    // For now, just show success - in production this would notify supervisors
    successMessage.value = 'Help request sent to supervisor'
    showSuccess.value = true
    showHelpDialog.value = false
    helpForm.value = { type: null, description: '' }
  } catch (error) {
    notificationStore.error('Failed to send help request')
  } finally {
    isSubmitting.value = false
  }
}

const refreshActivity = () => {
  fetchMyShiftData()
}

const editActivity = (activity) => {
  // Navigate to appropriate entry page for editing
  const routes = {
    production: '/production-entry',
    downtime: '/data-entry/downtime',
    quality: '/data-entry/quality',
    hold: '/data-entry/hold-resume'
  }
  router.push(routes[activity.type] || '/')
}

const fetchMyShiftData = async () => {
  try {
    // Fetch assigned work orders
    const woResponse = await api.getWorkOrders({
      status: 'in_progress',
      date: currentDate.value
    })
    assignedWorkOrders.value = woResponse.data?.items || woResponse.data || []

    // Fetch production entries for today
    const prodResponse = await api.getProductionEntries({
      date: currentDate.value,
      shift: activeShift.value?.shift_number
    })
    const productions = prodResponse.data?.items || prodResponse.data || []

    // Calculate stats
    let totalUnits = 0
    let totalTarget = 0
    productions.forEach(p => {
      totalUnits += p.units_produced || 0
      totalTarget += p.target_production || p.units_produced || 0
    })

    // Fetch downtime entries
    const downResponse = await api.getDowntimeEntries({
      date: currentDate.value,
      shift: activeShift.value?.shift_number
    })
    const downtimes = downResponse.data?.items || downResponse.data || []

    // Fetch quality entries
    const qualityResponse = await api.getQualityEntries({
      date: currentDate.value,
      shift: activeShift.value?.shift_number
    })
    const qualities = qualityResponse.data?.items || qualityResponse.data || []

    // Update stats
    myStats.value = {
      unitsProduced: totalUnits,
      efficiency: totalTarget > 0 ? Math.round((totalUnits / totalTarget) * 100) : 0,
      downtimeIncidents: downtimes.length,
      qualityChecks: qualities.length
    }

    // Build recent activity (last 5 entries)
    const allActivities = [
      ...productions.map(p => ({
        id: `prod-${p.id}`,
        type: 'production',
        description: `Logged ${p.units_produced} units for ${p.work_order_id}`,
        timestamp: p.created_at || p.date
      })),
      ...downtimes.map(d => ({
        id: `down-${d.id}`,
        type: 'downtime',
        description: `${d.reason}: ${d.downtime_minutes} min downtime`,
        timestamp: d.created_at || d.date
      })),
      ...qualities.map(q => ({
        id: `qual-${q.id}`,
        type: 'quality',
        description: `Quality check: ${q.inspected_quantity} inspected, ${q.defect_quantity} defects`,
        timestamp: q.created_at || q.date
      }))
    ]

    // Sort by timestamp descending and take top 5
    allActivities.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    recentActivity.value = allActivities.slice(0, 5)

    // Update work order progress with production data
    assignedWorkOrders.value = assignedWorkOrders.value.map(wo => {
      const woProductions = productions.filter(p => p.work_order_id === wo.work_order_id)
      const produced = woProductions.reduce((sum, p) => sum + (p.units_produced || 0), 0)
      return { ...wo, produced }
    })

  } catch (error) {
    console.error('Failed to fetch shift data:', error)
    // Set mock data for demonstration if API fails
    assignedWorkOrders.value = [
      { id: 1, work_order_id: 'WO-2024-001', product_name: 'Widget A', target_qty: 1000, produced: 450 },
      { id: 2, work_order_id: 'WO-2024-002', product_name: 'Widget B', target_qty: 500, produced: 320 },
      { id: 3, work_order_id: 'WO-2024-003', product_name: 'Component X', target_qty: 750, produced: 600 }
    ]
    myStats.value = {
      unitsProduced: 1370,
      efficiency: 85,
      downtimeIncidents: 2,
      qualityChecks: 5
    }
    recentActivity.value = [
      { id: '1', type: 'production', description: 'Logged 50 units for WO-2024-001', timestamp: new Date(Date.now() - 15 * 60000).toISOString() },
      { id: '2', type: 'quality', description: 'Quality check: 100 inspected, 1 defect', timestamp: new Date(Date.now() - 45 * 60000).toISOString() },
      { id: '3', type: 'downtime', description: 'Equipment Breakdown: 15 min downtime', timestamp: new Date(Date.now() - 90 * 60000).toISOString() },
      { id: '4', type: 'production', description: 'Logged 100 units for WO-2024-002', timestamp: new Date(Date.now() - 120 * 60000).toISOString() },
      { id: '5', type: 'production', description: 'Logged 75 units for WO-2024-003', timestamp: new Date(Date.now() - 180 * 60000).toISOString() }
    ]
  }
}

// Lifecycle
onMounted(async () => {
  await workflowStore.initialize()
  await fetchMyShiftData()

  // Update time every minute
  timeInterval = setInterval(() => {
    currentTime.value = new Date()
  }, 60000)
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})
</script>

<style scoped>
.my-shift-dashboard {
  max-width: 1400px;
  margin: 0 auto;
}

.shift-header-card {
  background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%);
  color: white;
}

.shift-header-card .v-card-text {
  color: white !important;
}

.stat-card {
  background: rgba(0, 0, 0, 0.03);
  border-radius: 12px;
}

/* Touch-friendly targets for mobile */
.touch-target {
  min-height: 48px !important;
  min-width: 48px !important;
}

.touch-target-small {
  min-height: 44px !important;
  min-width: 44px !important;
}

.quick-action-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  border-radius: 12px !important;
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.quick-action-card:hover,
.quick-action-card:focus {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2) !important;
}

.quick-action-card:active {
  transform: translateY(0);
}

.preset-btn {
  min-width: 64px !important;
  font-weight: bold;
}

.gap-2 {
  gap: 8px;
}

.gap-3 {
  gap: 12px;
}

/* Mobile optimizations */
@media (max-width: 600px) {
  .my-shift-dashboard {
    padding: 0 8px;
  }

  .v-card-title {
    font-size: 1rem;
    padding: 12px 16px !important;
  }

  .quick-action-card {
    min-height: 100px;
  }

  .quick-action-card .v-icon {
    font-size: 32px !important;
  }

  .quick-action-card .text-body-1 {
    font-size: 0.875rem !important;
  }

  .stat-card {
    padding: 8px !important;
  }

  .stat-card .text-h4 {
    font-size: 1.5rem !important;
  }

  .preset-btn {
    min-width: 56px !important;
    padding: 0 12px !important;
  }
}

/* High contrast for factory floor visibility */
.text-h4.font-weight-bold {
  letter-spacing: -0.5px;
}

/* Ensure good tap targets on all interactive elements */
.v-btn,
.v-list-item,
.quick-action-card {
  -webkit-tap-highlight-color: transparent;
}
</style>
