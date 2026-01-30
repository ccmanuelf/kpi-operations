<template>
  <v-container fluid class="pa-4" role="region" aria-label="Operations Health Dashboard">
    <!-- Header Section -->
    <v-row class="mb-4">
      <v-col cols="12" md="6">
        <h1 class="text-h3 font-weight-bold">{{ t('navigation.operationsHealth') }}</h1>
        <p class="text-subtitle-1 text-grey-darken-1">
          {{ t('dashboard.overview') }}
        </p>
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center justify-end ga-2">
        <v-select
          v-model="selectedShift"
          :items="shifts"
          item-title="shift_name"
          item-value="shift_id"
          :label="t('production.shift')"
          density="compact"
          variant="outlined"
          hide-details
          style="max-width: 150px"
          clearable
          @update:model-value="refreshData"
        />
        <v-btn
          icon="mdi-refresh"
          variant="text"
          :loading="loading"
          @click="refreshData"
          aria-label="Refresh dashboard data"
        />
        <v-chip
          v-if="lastUpdated"
          size="small"
          variant="outlined"
          prepend-icon="mdi-clock-outline"
        >
          {{ lastUpdated }}
        </v-chip>
      </v-col>
    </v-row>

    <!-- Hero Section: OEE Gauge + Critical Alerts -->
    <v-row class="mb-4">
      <!-- OEE Gauge Widget -->
      <v-col cols="12" lg="5">
        <v-card elevation="2" class="h-100">
          <v-card-title class="text-center pb-0">
            <span class="text-h6">{{ t('kpi.oee') }}</span>
          </v-card-title>
          <v-card-text class="d-flex flex-column align-center">
            <!-- OEE Gauge -->
            <v-tooltip location="bottom" max-width="300">
              <template v-slot:activator="{ props }">
                <v-progress-circular
                  v-bind="props"
                  :model-value="oeeData.overall"
                  :size="200"
                  :width="20"
                  :color="getOEEColor(oeeData.overall)"
                  class="my-4"
                  :aria-label="`Overall Equipment Effectiveness: ${oeeData.overall} percent`"
                >
                  <div class="text-center">
                    <div class="text-h3 font-weight-bold">{{ oeeData.overall.toFixed(1) }}%</div>
                    <div class="text-caption text-grey">OEE</div>
                  </div>
                </v-progress-circular>
              </template>
              <div>
                <div class="tooltip-title">Formula:</div>
                <div class="tooltip-formula">OEE = Availability x Performance x Quality</div>
                <div class="tooltip-meaning">Comprehensive metric measuring manufacturing productivity</div>
              </div>
            </v-tooltip>

            <!-- OEE Component Breakdown -->
            <v-row class="w-100 mt-2" dense>
              <v-col cols="4" class="text-center">
                <v-tooltip location="bottom">
                  <template v-slot:activator="{ props }">
                    <div v-bind="props" class="cursor-help">
                      <div class="text-h5 font-weight-bold" :class="getStatusTextClass(oeeData.availability, 90, 80)">
                        {{ oeeData.availability.toFixed(1) }}%
                      </div>
                      <div class="text-caption text-grey-darken-1">Availability</div>
                      <v-progress-linear
                        :model-value="oeeData.availability"
                        :color="getStatusColor(oeeData.availability, 90, 80)"
                        height="4"
                        rounded
                        class="mt-1"
                      />
                    </div>
                  </template>
                  <span>Equipment uptime vs scheduled production time</span>
                </v-tooltip>
              </v-col>
              <v-col cols="4" class="text-center">
                <v-tooltip location="bottom">
                  <template v-slot:activator="{ props }">
                    <div v-bind="props" class="cursor-help">
                      <div class="text-h5 font-weight-bold" :class="getStatusTextClass(oeeData.performance, 95, 85)">
                        {{ oeeData.performance.toFixed(1) }}%
                      </div>
                      <div class="text-caption text-grey-darken-1">Performance</div>
                      <v-progress-linear
                        :model-value="oeeData.performance"
                        :color="getStatusColor(oeeData.performance, 95, 85)"
                        height="4"
                        rounded
                        class="mt-1"
                      />
                    </div>
                  </template>
                  <span>Actual production rate vs ideal rate</span>
                </v-tooltip>
              </v-col>
              <v-col cols="4" class="text-center">
                <v-tooltip location="bottom">
                  <template v-slot:activator="{ props }">
                    <div v-bind="props" class="cursor-help">
                      <div class="text-h5 font-weight-bold" :class="getStatusTextClass(oeeData.quality, 99, 95)">
                        {{ oeeData.quality.toFixed(1) }}%
                      </div>
                      <div class="text-caption text-grey-darken-1">Quality</div>
                      <v-progress-linear
                        :model-value="oeeData.quality"
                        :color="getStatusColor(oeeData.quality, 99, 95)"
                        height="4"
                        rounded
                        class="mt-1"
                      />
                    </div>
                  </template>
                  <span>Good units produced vs total units</span>
                </v-tooltip>
              </v-col>
            </v-row>

            <!-- Target Indicator -->
            <v-divider class="my-3 w-100" />
            <div class="d-flex align-center justify-space-between w-100">
              <span class="text-body-2 text-grey-darken-1">
                Target: {{ oeeData.target }}%
              </span>
              <v-chip
                :color="getOEEColor(oeeData.overall)"
                size="small"
                variant="flat"
              >
                {{ getOEEStatusText(oeeData.overall) }}
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Critical Alerts Panel -->
      <v-col cols="12" lg="7">
        <v-card elevation="2" class="h-100">
          <v-card-title class="d-flex align-center bg-error-darken-1 text-white">
            <v-icon class="mr-2">mdi-alert-circle</v-icon>
            Critical Alerts
            <v-chip class="ml-2" size="x-small" color="white" variant="flat">
              {{ criticalAlerts.length }}
            </v-chip>
            <v-spacer />
            <v-btn
              v-if="criticalAlerts.length > 0"
              variant="text"
              size="small"
              color="white"
              @click="clearDismissedAlerts"
            >
              Clear All
            </v-btn>
          </v-card-title>
          <v-card-text class="pa-0" style="max-height: 280px; overflow-y: auto;">
            <v-list v-if="criticalAlerts.length > 0" density="compact" class="py-0">
              <v-list-item
                v-for="alert in criticalAlerts"
                :key="alert.id"
                :class="alert.severity === 'critical' ? 'bg-error-lighten-5' : 'bg-warning-lighten-5'"
                class="border-b"
                role="alert"
              >
                <template v-slot:prepend>
                  <v-icon
                    :color="alert.severity === 'critical' ? 'error' : 'warning'"
                    size="24"
                  >
                    {{ getAlertIcon(alert.type) }}
                  </v-icon>
                </template>
                <v-list-item-title class="font-weight-medium">
                  {{ alert.message }}
                </v-list-item-title>
                <v-list-item-subtitle class="text-caption">
                  {{ formatAlertTime(alert.timestamp) }}
                </v-list-item-subtitle>
                <template v-slot:append>
                  <v-btn
                    v-if="alert.actionUrl"
                    size="small"
                    variant="text"
                    color="primary"
                    @click="navigateTo(alert.actionUrl)"
                  >
                    View
                  </v-btn>
                  <v-btn
                    icon="mdi-close"
                    size="x-small"
                    variant="text"
                    @click="dismissAlert(alert.id)"
                    aria-label="Dismiss alert"
                  />
                </template>
              </v-list-item>
            </v-list>
            <div v-else class="d-flex flex-column align-center justify-center pa-8 text-grey">
              <v-icon size="48" class="mb-2">mdi-check-circle-outline</v-icon>
              <span>No critical alerts</span>
              <span class="text-caption">All systems operating normally</span>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Metric Cards Grid -->
    <v-row class="mb-4">
      <!-- Production Today Card -->
      <v-col cols="12" sm="6" lg="2">
        <v-tooltip location="bottom" max-width="250">
          <template v-slot:activator="{ props }">
            <v-card
              v-bind="props"
              elevation="2"
              class="metric-card h-100"
              @click="navigateTo('/production-entry')"
              hover
              role="article"
              aria-labelledby="metric-production-label"
            >
              <v-card-text>
                <div class="d-flex justify-space-between align-start mb-2">
                  <v-icon color="primary" size="32">mdi-factory</v-icon>
                  <v-sparkline
                    v-if="productionData.trend.length > 0"
                    :model-value="productionData.trend.map(t => t.value)"
                    :gradient="['#4CAF50', '#81C784']"
                    :line-width="2"
                    :padding="4"
                    smooth
                    auto-draw
                    style="width: 60px; height: 30px;"
                  />
                </div>
                <div class="text-h4 font-weight-bold">
                  {{ productionData.today }} / {{ productionData.target }}
                </div>
                <div id="metric-production-label" class="text-caption text-grey-darken-1">
                  Production Today
                </div>
                <v-progress-linear
                  :model-value="(productionData.today / productionData.target) * 100"
                  :color="getStatusColor((productionData.today / productionData.target) * 100, 90, 80)"
                  height="6"
                  rounded
                  class="mt-2"
                />
              </v-card-text>
            </v-card>
          </template>
          <span>Units produced today vs daily target</span>
        </v-tooltip>
      </v-col>

      <!-- Active Downtime Card -->
      <v-col cols="12" sm="6" lg="2">
        <v-tooltip location="bottom" max-width="250">
          <template v-slot:activator="{ props }">
            <v-card
              v-bind="props"
              elevation="2"
              class="metric-card h-100"
              :class="{ 'border-error': downtimeData.activeCount >= 3 }"
              @click="navigateTo('/kpi/availability')"
              hover
              role="article"
            >
              <v-card-text>
                <div class="d-flex justify-space-between align-start mb-2">
                  <v-icon :color="getDowntimeColor(downtimeData.activeCount)" size="32">
                    mdi-clock-alert
                  </v-icon>
                  <v-chip
                    v-if="downtimeData.activeCount > 0"
                    :color="getDowntimeColor(downtimeData.activeCount)"
                    size="x-small"
                    variant="flat"
                  >
                    ACTIVE
                  </v-chip>
                </div>
                <div class="text-h4 font-weight-bold" :class="getDowntimeTextClass(downtimeData.activeCount)">
                  {{ downtimeData.activeCount }}
                </div>
                <div class="text-caption text-grey-darken-1">Active Downtime</div>
                <div v-if="downtimeData.activeEvents.length > 0" class="text-caption text-grey mt-1">
                  {{ downtimeData.activeEvents[0]?.machine }} - {{ downtimeData.activeEvents[0]?.duration }}
                </div>
              </v-card-text>
            </v-card>
          </template>
          <span>Number of machines currently experiencing downtime</span>
        </v-tooltip>
      </v-col>

      <!-- Quality Alerts Card -->
      <v-col cols="12" sm="6" lg="2">
        <v-tooltip location="bottom" max-width="250">
          <template v-slot:activator="{ props }">
            <v-card
              v-bind="props"
              elevation="2"
              class="metric-card h-100"
              @click="navigateTo('/kpi/quality')"
              hover
              role="article"
            >
              <v-card-text>
                <div class="d-flex justify-space-between align-start mb-2">
                  <v-icon :color="getQualityAlertColor(qualityData.alertCount)" size="32">
                    mdi-alert-octagon
                  </v-icon>
                  <v-sparkline
                    v-if="qualityData.defectTrend.length > 0"
                    :model-value="qualityData.defectTrend.map(t => t.value)"
                    :gradient="['#f44336', '#e57373']"
                    :line-width="2"
                    :padding="4"
                    smooth
                    auto-draw
                    style="width: 60px; height: 30px;"
                  />
                </div>
                <div class="text-h4 font-weight-bold" :class="getQualityAlertTextClass(qualityData.alertCount)">
                  {{ qualityData.alertCount }}
                </div>
                <div class="text-caption text-grey-darken-1">Quality Alerts</div>
                <div v-if="qualityData.holdCount > 0" class="text-caption text-warning mt-1">
                  {{ qualityData.holdCount }} holds pending
                </div>
              </v-card-text>
            </v-card>
          </template>
          <span>Active quality issues and holds requiring attention</span>
        </v-tooltip>
      </v-col>

      <!-- Attendance Coverage Card -->
      <v-col cols="12" sm="6" lg="2">
        <v-tooltip location="bottom" max-width="250">
          <template v-slot:activator="{ props }">
            <v-card
              v-bind="props"
              elevation="2"
              class="metric-card h-100"
              @click="navigateTo('/kpi/absenteeism')"
              hover
              role="article"
            >
              <v-card-text>
                <div class="d-flex justify-space-between align-start mb-2">
                  <v-icon :color="getStatusColor(attendanceData.coveragePercent, 95, 85)" size="32">
                    mdi-account-group
                  </v-icon>
                </div>
                <div class="text-h4 font-weight-bold">
                  {{ attendanceData.coveragePercent.toFixed(1) }}%
                </div>
                <div class="text-caption text-grey-darken-1">Attendance Coverage</div>
                <v-progress-linear
                  :model-value="attendanceData.coveragePercent"
                  :color="getStatusColor(attendanceData.coveragePercent, 95, 85)"
                  height="6"
                  rounded
                  class="mt-2"
                />
                <div class="text-caption text-grey mt-1">
                  {{ attendanceData.present }}/{{ attendanceData.scheduled }} present
                </div>
              </v-card-text>
            </v-card>
          </template>
          <span>Percentage of scheduled workforce present today</span>
        </v-tooltip>
      </v-col>

      <!-- Work Orders Active Card -->
      <v-col cols="12" sm="6" lg="2">
        <v-tooltip location="bottom" max-width="250">
          <template v-slot:activator="{ props }">
            <v-card
              v-bind="props"
              elevation="2"
              class="metric-card h-100"
              @click="navigateTo('/kpi/wip-aging')"
              hover
              role="article"
            >
              <v-card-text>
                <div class="d-flex justify-space-between align-start mb-2">
                  <v-icon color="info" size="32">mdi-clipboard-list</v-icon>
                </div>
                <div class="text-h4 font-weight-bold">
                  {{ workOrdersData.activeCount }}
                </div>
                <div class="text-caption text-grey-darken-1">Work Orders Active</div>
                <div class="d-flex ga-1 mt-2">
                  <v-chip
                    v-for="bucket in workOrdersData.agingDistribution"
                    :key="bucket.label"
                    :color="bucket.color"
                    size="x-small"
                    variant="flat"
                  >
                    {{ bucket.count }}
                  </v-chip>
                </div>
              </v-card-text>
            </v-card>
          </template>
          <span>Active work orders by aging: Green(&lt;7d), Yellow(7-14d), Red(&gt;14d)</span>
        </v-tooltip>
      </v-col>

      <!-- On-Time Delivery Card -->
      <v-col cols="12" sm="6" lg="2">
        <v-tooltip location="bottom" max-width="250">
          <template v-slot:activator="{ props }">
            <v-card
              v-bind="props"
              elevation="2"
              class="metric-card h-100"
              @click="navigateTo('/kpi/on-time-delivery')"
              hover
              role="article"
            >
              <v-card-text>
                <div class="d-flex justify-space-between align-start mb-2">
                  <v-icon :color="getStatusColor(otdData.percentage, 95, 90)" size="32">
                    mdi-truck-check
                  </v-icon>
                  <v-sparkline
                    v-if="otdData.trend.length > 0"
                    :model-value="otdData.trend.map(t => t.value)"
                    :gradient="['#2196F3', '#64B5F6']"
                    :line-width="2"
                    :padding="4"
                    smooth
                    auto-draw
                    style="width: 60px; height: 30px;"
                  />
                </div>
                <div class="text-h4 font-weight-bold">
                  {{ otdData.percentage.toFixed(1) }}%
                </div>
                <div class="text-caption text-grey-darken-1">On-Time Delivery</div>
                <v-progress-linear
                  :model-value="otdData.percentage"
                  :color="getStatusColor(otdData.percentage, 95, 90)"
                  height="6"
                  rounded
                  class="mt-2"
                />
              </v-card-text>
            </v-card>
          </template>
          <span>Percentage of orders delivered by promised date</span>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- Bottom Section: Activity Feed + Quick Actions -->
    <v-row>
      <!-- Recent Activity Feed -->
      <v-col cols="12" lg="8">
        <v-card elevation="2">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-history</v-icon>
            Recent Activity
            <v-spacer />
            <v-btn variant="text" size="small" @click="showAllActivity = !showAllActivity">
              {{ showAllActivity ? 'Show Less' : 'View All' }}
            </v-btn>
          </v-card-title>
          <v-card-text class="pa-0">
            <v-list density="compact" class="py-0" role="log">
              <v-list-item
                v-for="activity in displayedActivities"
                :key="activity.id"
                class="border-b"
              >
                <template v-slot:prepend>
                  <v-avatar :color="getActivityColor(activity.type)" size="32" class="mr-3">
                    <v-icon size="16" color="white">{{ getActivityIcon(activity.type) }}</v-icon>
                  </v-avatar>
                </template>
                <v-list-item-title>{{ activity.description }}</v-list-item-title>
                <v-list-item-subtitle class="d-flex align-center ga-2">
                  <span>{{ formatActivityTime(activity.timestamp) }}</span>
                  <span v-if="activity.user" class="text-grey">by {{ activity.user }}</span>
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item v-if="recentActivity.length === 0" class="text-center text-grey">
                No recent activity
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Quick Actions Panel -->
      <v-col cols="12" lg="4">
        <v-card elevation="2" class="h-100">
          <v-card-title>
            <v-icon class="mr-2">mdi-lightning-bolt</v-icon>
            Quick Actions
          </v-card-title>
          <v-card-text>
            <v-btn
              block
              color="primary"
              variant="flat"
              prepend-icon="mdi-plus"
              class="mb-3"
              @click="navigateTo('/production-entry')"
            >
              Log Production
            </v-btn>
            <v-btn
              block
              color="warning"
              variant="outlined"
              prepend-icon="mdi-clock-alert"
              class="mb-3"
              @click="navigateTo('/data-entry/downtime')"
            >
              Report Downtime
            </v-btn>
            <v-btn
              block
              color="error"
              variant="outlined"
              prepend-icon="mdi-alert"
              class="mb-3"
              @click="navigateTo('/data-entry/quality')"
            >
              Quality Entry
            </v-btn>
            <v-btn
              block
              color="info"
              variant="text"
              prepend-icon="mdi-chart-box"
              @click="navigateTo('/kpi-dashboard')"
            >
              View All KPIs
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Loading Overlay -->
    <v-overlay
      v-model="loading"
      class="align-center justify-center"
      contained
      persistent
    >
      <v-progress-circular indeterminate size="64" color="primary" />
    </v-overlay>

    <!-- Snackbar for notifications -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="4000"
    >
      {{ snackbar.message }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar.show = false">Close</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
import { useRouter } from 'vue-router'
import { format, formatDistanceToNow } from 'date-fns'
import api from '@/services/api'

// Types
interface TrendPoint {
  date: string
  value: number
}

interface CriticalAlert {
  id: string
  type: 'downtime' | 'quality' | 'attendance' | 'oee'
  severity: 'critical' | 'warning'
  message: string
  timestamp: string
  actionUrl?: string
}

interface ActivityItem {
  id: string
  type: 'production' | 'downtime' | 'quality' | 'attendance'
  description: string
  timestamp: string
  user?: string
}

interface DowntimeEvent {
  id: string
  machine: string
  duration: string
  category: string
}

interface AgingBucket {
  label: string
  count: number
  color: string
}

// Router
const router = useRouter()

// State
const loading = ref(false)
const lastUpdated = ref('')
const selectedShift = ref<number | null>(null)
const shifts = ref<Array<{ shift_id: number; shift_name: string }>>([])
const showAllActivity = ref(false)
const refreshInterval = ref<ReturnType<typeof setInterval> | null>(null)
const dismissedAlertIds = ref<Set<string>>(new Set())

const snackbar = ref({
  show: false,
  message: '',
  color: 'success'
})

// OEE Data
const oeeData = ref({
  overall: 0,
  availability: 0,
  performance: 0,
  quality: 0,
  target: 85,
  trend: [] as TrendPoint[]
})

// Production Data
const productionData = ref({
  today: 0,
  target: 100,
  trend: [] as TrendPoint[]
})

// Downtime Data
const downtimeData = ref({
  activeCount: 0,
  activeEvents: [] as DowntimeEvent[]
})

// Quality Data
const qualityData = ref({
  alertCount: 0,
  holdCount: 0,
  defectTrend: [] as TrendPoint[]
})

// Attendance Data
const attendanceData = ref({
  coveragePercent: 0,
  scheduled: 0,
  present: 0,
  absent: 0
})

// Work Orders Data
const workOrdersData = ref({
  activeCount: 0,
  agingDistribution: [] as AgingBucket[]
})

// OTD Data
const otdData = ref({
  percentage: 0,
  trend: [] as TrendPoint[]
})

// Alerts
const criticalAlerts = ref<CriticalAlert[]>([])

// Recent Activity
const recentActivity = ref<ActivityItem[]>([])

// Computed
const displayedActivities = computed(() => {
  return showAllActivity.value ? recentActivity.value : recentActivity.value.slice(0, 5)
})

// Status Color Functions
function getStatusColor(value: number, greenThreshold: number, yellowThreshold: number): string {
  if (value >= greenThreshold) return 'success'
  if (value >= yellowThreshold) return 'warning'
  return 'error'
}

function getStatusTextClass(value: number, greenThreshold: number, yellowThreshold: number): string {
  if (value >= greenThreshold) return 'text-success'
  if (value >= yellowThreshold) return 'text-warning'
  return 'text-error'
}

function getOEEColor(oee: number): string {
  return getStatusColor(oee, 85, 70)
}

function getOEEStatusText(oee: number): string {
  if (oee >= 85) return 'On Target'
  if (oee >= 70) return 'At Risk'
  return 'Critical'
}

function getDowntimeColor(count: number): string {
  if (count === 0) return 'success'
  if (count <= 2) return 'warning'
  return 'error'
}

function getDowntimeTextClass(count: number): string {
  if (count === 0) return 'text-success'
  if (count <= 2) return 'text-warning'
  return 'text-error'
}

function getQualityAlertColor(count: number): string {
  if (count === 0) return 'success'
  if (count <= 3) return 'warning'
  return 'error'
}

function getQualityAlertTextClass(count: number): string {
  if (count === 0) return 'text-success'
  if (count <= 3) return 'text-warning'
  return 'text-error'
}

// Alert Functions
function getAlertIcon(type: string): string {
  const icons: Record<string, string> = {
    downtime: 'mdi-clock-alert',
    quality: 'mdi-alert-octagon',
    attendance: 'mdi-account-alert',
    oee: 'mdi-gauge-low'
  }
  return icons[type] || 'mdi-alert'
}

function formatAlertTime(timestamp: string): string {
  return formatDistanceToNow(new Date(timestamp), { addSuffix: true })
}

function dismissAlert(alertId: string): void {
  dismissedAlertIds.value.add(alertId)
  criticalAlerts.value = criticalAlerts.value.filter(a => a.id !== alertId)
}

function clearDismissedAlerts(): void {
  criticalAlerts.value = []
}

// Activity Functions
function getActivityColor(type: string): string {
  const colors: Record<string, string> = {
    production: 'primary',
    downtime: 'warning',
    quality: 'error',
    attendance: 'info'
  }
  return colors[type] || 'grey'
}

function getActivityIcon(type: string): string {
  const icons: Record<string, string> = {
    production: 'mdi-factory',
    downtime: 'mdi-clock-alert',
    quality: 'mdi-alert-octagon',
    attendance: 'mdi-account-check'
  }
  return icons[type] || 'mdi-information'
}

function formatActivityTime(timestamp: string): string {
  return format(new Date(timestamp), 'HH:mm')
}

// Navigation
function navigateTo(path: string): void {
  router.push(path)
}

// Data Fetching
async function fetchOEEData(): Promise<void> {
  try {
    const params = selectedShift.value ? { shift_id: selectedShift.value } : {}
    const response = await api.get('/kpi/oee', { params })
    if (response.data) {
      oeeData.value.overall = response.data.oee || 0
      oeeData.value.availability = response.data.availability || 0
      oeeData.value.performance = response.data.performance || 0
      oeeData.value.quality = response.data.quality || 0
    }
  } catch (error) {
    console.error('Error fetching OEE data:', error)
  }
}

async function fetchProductionData(): Promise<void> {
  try {
    const params = selectedShift.value ? { shift_id: selectedShift.value } : {}
    const response = await api.get('/kpi/efficiency', { params })
    if (response.data) {
      productionData.value.today = response.data.units_produced || 0
      productionData.value.target = response.data.target || 100
    }
  } catch (error) {
    console.error('Error fetching production data:', error)
  }
}

async function fetchDowntimeData(): Promise<void> {
  try {
    const response = await api.get('/downtime', { params: { active: true, limit: 10 } })
    if (response.data && Array.isArray(response.data)) {
      downtimeData.value.activeCount = response.data.filter((d: any) => !d.end_time).length
      downtimeData.value.activeEvents = response.data
        .filter((d: any) => !d.end_time)
        .slice(0, 3)
        .map((d: any) => ({
          id: d.downtime_id,
          machine: d.machine_id || 'Unknown',
          duration: d.duration_hours ? `${d.duration_hours.toFixed(1)}h` : 'Active',
          category: d.downtime_category || 'Unknown'
        }))
    }
  } catch (error) {
    console.error('Error fetching downtime data:', error)
  }
}

async function fetchQualityData(): Promise<void> {
  try {
    const [qualityRes, holdsRes] = await Promise.all([
      api.get('/kpi/quality/fpy'),
      api.get('/holds', { params: { status: 'active' } }).catch(() => ({ data: [] }))
    ])

    qualityData.value.holdCount = Array.isArray(holdsRes.data) ? holdsRes.data.length : 0
    qualityData.value.alertCount = qualityData.value.holdCount
  } catch (error) {
    console.error('Error fetching quality data:', error)
  }
}

async function fetchAttendanceData(): Promise<void> {
  try {
    const response = await api.get('/kpi/absenteeism')
    if (response.data) {
      const absenteeismRate = response.data.absenteeism_rate || 0
      attendanceData.value.coveragePercent = 100 - absenteeismRate
      attendanceData.value.scheduled = response.data.scheduled_employees || 0
      attendanceData.value.present = response.data.present_employees || 0
      attendanceData.value.absent = response.data.absent_employees || 0
    }
  } catch (error) {
    console.error('Error fetching attendance data:', error)
  }
}

async function fetchWorkOrdersData(): Promise<void> {
  try {
    const response = await api.get('/kpi/wip-aging')
    if (response.data) {
      workOrdersData.value.activeCount = response.data.total_wip_count || 0
      // Create aging distribution buckets
      workOrdersData.value.agingDistribution = [
        { label: '<7d', count: response.data.under_7_days || 0, color: 'success' },
        { label: '7-14d', count: response.data.between_7_14_days || 0, color: 'warning' },
        { label: '>14d', count: response.data.over_14_days || 0, color: 'error' }
      ]
    }
  } catch (error) {
    console.error('Error fetching work orders data:', error)
  }
}

async function fetchOTDData(): Promise<void> {
  try {
    const response = await api.get('/kpi/on-time-delivery')
    if (response.data) {
      otdData.value.percentage = response.data.otd_percentage || 0
    }
  } catch (error) {
    console.error('Error fetching OTD data:', error)
  }
}

async function fetchAlerts(): Promise<void> {
  // Generate alerts based on current data
  const alerts: CriticalAlert[] = []

  // Check OEE
  if (oeeData.value.overall > 0 && oeeData.value.overall < 70) {
    alerts.push({
      id: 'oee-critical',
      type: 'oee',
      severity: 'critical',
      message: `OEE dropped to ${oeeData.value.overall.toFixed(1)}% - below 70% threshold`,
      timestamp: new Date().toISOString(),
      actionUrl: '/kpi/oee'
    })
  }

  // Check downtime
  if (downtimeData.value.activeCount >= 3) {
    alerts.push({
      id: 'downtime-high',
      type: 'downtime',
      severity: 'critical',
      message: `${downtimeData.value.activeCount} machines currently down`,
      timestamp: new Date().toISOString(),
      actionUrl: '/kpi/availability'
    })
  }

  // Check quality holds
  if (qualityData.value.holdCount > 0) {
    alerts.push({
      id: 'quality-holds',
      type: 'quality',
      severity: 'warning',
      message: `${qualityData.value.holdCount} quality hold(s) pending inspection`,
      timestamp: new Date().toISOString(),
      actionUrl: '/data-entry/hold-resume'
    })
  }

  // Check attendance
  if (attendanceData.value.coveragePercent < 85) {
    alerts.push({
      id: 'attendance-low',
      type: 'attendance',
      severity: 'warning',
      message: `Attendance coverage at ${attendanceData.value.coveragePercent.toFixed(1)}%`,
      timestamp: new Date().toISOString(),
      actionUrl: '/kpi/absenteeism'
    })
  }

  // Filter out dismissed alerts
  criticalAlerts.value = alerts.filter(a => !dismissedAlertIds.value.has(a.id))
}

async function fetchRecentActivity(): Promise<void> {
  // Mock recent activity - in production, this would come from an audit log API
  const activities: ActivityItem[] = []

  // Generate sample activities based on current time
  const now = new Date()
  const types = ['production', 'downtime', 'quality', 'attendance'] as const
  const descriptions: Record<typeof types[number], string[]> = {
    production: ['Production batch completed', 'Units logged for WO-2024', 'Shift production recorded'],
    downtime: ['Downtime event started', 'Machine maintenance logged', 'Downtime resolved'],
    quality: ['Quality inspection passed', 'Defect reported', 'Quality hold placed'],
    attendance: ['Shift attendance recorded', 'Coverage update logged', 'Operator checked in']
  }

  for (let i = 0; i < 10; i++) {
    const type = types[i % 4]
    const descList = descriptions[type]
    activities.push({
      id: `activity-${i}`,
      type,
      description: descList[i % descList.length],
      timestamp: new Date(now.getTime() - i * 15 * 60000).toISOString(),
      user: ['Operator A', 'Supervisor B', 'Manager C'][i % 3]
    })
  }

  recentActivity.value = activities
}

async function fetchShifts(): Promise<void> {
  try {
    const response = await api.getShifts()
    if (response.data) {
      shifts.value = response.data
    }
  } catch (error) {
    console.error('Error fetching shifts:', error)
  }
}

async function refreshData(): Promise<void> {
  loading.value = true
  try {
    await Promise.all([
      fetchOEEData(),
      fetchProductionData(),
      fetchDowntimeData(),
      fetchQualityData(),
      fetchAttendanceData(),
      fetchWorkOrdersData(),
      fetchOTDData(),
      fetchRecentActivity()
    ])
    await fetchAlerts()
    lastUpdated.value = format(new Date(), 'HH:mm:ss')
  } catch (error) {
    console.error('Error refreshing dashboard data:', error)
    snackbar.value = {
      show: true,
      message: 'Error refreshing data. Please try again.',
      color: 'error'
    }
  } finally {
    loading.value = false
  }
}

// Lifecycle
onMounted(async () => {
  await fetchShifts()
  await refreshData()

  // Set up auto-refresh every 60 seconds
  refreshInterval.value = setInterval(refreshData, 60000)
})

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})
</script>

<style scoped>
.metric-card {
  cursor: pointer;
  transition: all 0.2s ease;
}

.metric-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.border-error {
  border: 2px solid rgb(var(--v-theme-error)) !important;
}

.cursor-help {
  cursor: help;
}

.h-100 {
  height: 100%;
}

.w-100 {
  width: 100%;
}

.border-b {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}
</style>

<style>
/* Tooltip styling - unscoped to affect Vuetify tooltip portal */
.v-tooltip .tooltip-title {
  font-weight: 600;
  margin-bottom: 4px;
  color: #90caf9;
}

.v-tooltip .tooltip-formula {
  font-family: 'Courier New', monospace;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 8px;
  color: #ffffff;
}

.v-tooltip .tooltip-meaning {
  color: rgba(255, 255, 255, 0.9);
}
</style>
