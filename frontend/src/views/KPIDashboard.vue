<template>
  <v-container fluid class="pa-4" role="main" aria-labelledby="kpi-dashboard-title">
    <!-- Header with title and actions -->
    <v-row class="mb-2">
      <v-col cols="12" md="6">
        <h1 id="kpi-dashboard-title" class="text-h3">{{ t('navigation.kpiDashboard') }}</h1>
        <p class="text-subtitle-1 text-grey">{{ t('kpi.title') }}</p>
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center justify-end ga-2">
        <!-- QR Scanner Quick Access Button -->
        <v-tooltip location="bottom">
          <template v-slot:activator="{ props }">
            <v-btn
              v-bind="props"
              color="secondary"
              variant="tonal"
              prepend-icon="mdi-qrcode-scan"
              @click="showQRScanner = true"
              aria-label="Open QR code scanner for quick data entry"
            >
              {{ t('common.search') }}
            </v-btn>
          </template>
          <span>{{ t('filters.scanQrForQuickEntry') }}</span>
        </v-tooltip>

        <!-- Saved Filters Quick Access -->
        <v-menu v-if="filtersStore.savedFilters.length > 0" offset-y>
          <template v-slot:activator="{ props }">
            <v-btn
              v-bind="props"
              variant="tonal"
              prepend-icon="mdi-filter-check"
              :color="filtersStore.hasActiveFilter ? 'primary' : undefined"
            >
              {{ filtersStore.hasActiveFilter ? filtersStore.activeFilter.filter_name : t('filters.savedFilters') }}
              <v-icon end>mdi-chevron-down</v-icon>
            </v-btn>
          </template>
          <v-list density="compact" max-width="300">
            <v-list-subheader>
              <v-icon start size="small">mdi-bookmark-multiple</v-icon>
              {{ t('filters.quickApplyFilter') }}
            </v-list-subheader>
            <v-list-item
              v-for="filter in filtersStore.savedFilters.slice(0, 5)"
              :key="filter.filter_id"
              :active="filtersStore.activeFilter?.filter_id === filter.filter_id"
              @click="applyQuickSavedFilter(filter)"
            >
              <template v-slot:prepend>
                <v-icon :color="filter.is_default ? 'primary' : undefined">
                  {{ filter.is_default ? 'mdi-star' : 'mdi-filter-outline' }}
                </v-icon>
              </template>
              <v-list-item-title>{{ filter.filter_name }}</v-list-item-title>
              <v-list-item-subtitle>{{ filter.filter_type }}</v-list-item-subtitle>
            </v-list-item>
            <v-divider v-if="filtersStore.savedFilters.length > 5" />
            <v-list-item @click="showFilterManager = true">
              <template v-slot:prepend>
                <v-icon>mdi-cog-outline</v-icon>
              </template>
              <v-list-item-title>{{ t('filters.manageAllFilters') }}</v-list-item-title>
            </v-list-item>
            <v-list-item v-if="filtersStore.hasActiveFilter" @click="filtersStore.clearActiveFilter()">
              <template v-slot:prepend>
                <v-icon color="error">mdi-filter-off</v-icon>
              </template>
              <v-list-item-title class="text-error">{{ t('filters.clearActiveFilter') }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>

        <!-- Save Current Filter Button -->
        <v-tooltip location="bottom">
          <template v-slot:activator="{ props }">
            <v-btn
              v-bind="props"
              icon
              variant="text"
              @click="showSaveFilterDialog = true"
            >
              <v-icon>mdi-content-save-outline</v-icon>
            </v-btn>
          </template>
          <span>{{ t('filters.saveFilterConfig') }}</span>
        </v-tooltip>

        <!-- Dashboard Customize Button -->
        <v-btn
          variant="outlined"
          prepend-icon="mdi-view-dashboard-edit"
          @click="showCustomizer = true"
        >
          {{ t('common.edit') }}
        </v-btn>

        <!-- Report Actions Menu -->
        <v-menu>
          <template v-slot:activator="{ props }">
            <v-btn
              color="primary"
              variant="flat"
              v-bind="props"
              prepend-icon="mdi-file-download"
            >
              {{ t('reports.title') }}
            </v-btn>
          </template>
          <v-list>
            <v-list-item @click="downloadPDF" :loading="downloadingPDF">
              <template v-slot:prepend>
                <v-icon>mdi-file-pdf-box</v-icon>
              </template>
              <v-list-item-title>{{ t('reports.exportPdf') }}</v-list-item-title>
            </v-list-item>
            <v-list-item @click="downloadExcel" :loading="downloadingExcel">
              <template v-slot:prepend>
                <v-icon>mdi-file-excel</v-icon>
              </template>
              <v-list-item-title>{{ t('reports.exportExcel') }}</v-list-item-title>
            </v-list-item>
            <v-list-item @click="emailDialog = true">
              <template v-slot:prepend>
                <v-icon>mdi-email</v-icon>
              </template>
              <v-list-item-title>{{ t('reports.title') }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>

        <v-btn
          icon="mdi-refresh"
          variant="text"
          @click="refreshData"
          :loading="loading"
          aria-label="Refresh dashboard data"
          :aria-busy="loading"
        />
      </v-col>
    </v-row>

    <!-- Filter Bar -->
    <v-row class="mb-4">
      <v-col cols="12">
        <FilterBar
          filter-type="dashboard"
          :clients="clients"
          @filter-change="handleFilterChange"
        />
      </v-col>
    </v-row>

    <!-- KPI Cards Grid -->
    <v-row>
      <v-col
        v-for="kpi in kpiStore.allKPIs"
        :key="kpi.key"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props: tooltipProps }">
            <v-card
              v-bind="tooltipProps"
              :color="getCardColor(kpi)"
              variant="outlined"
              class="kpi-card"
              :class="{ 'estimated-card': kpi.inference?.is_estimated }"
              @click="navigateToDetail(kpi.route)"
              hover
            >
              <v-card-text>
                <div class="d-flex justify-space-between align-start mb-3">
                  <div>
                    <div class="d-flex align-center">
                      <span class="text-caption text-grey-darken-1">{{ kpi.title }}</span>
                      <!-- Phase 7.3: Inference Indicator -->
                      <InferenceIndicator
                        v-if="kpi.inference"
                        :is-estimated="kpi.inference.is_estimated"
                        :confidence-score="kpi.inference.confidence_score"
                        :inference-details="kpi.inference.details"
                      />
                    </div>
                    <div class="text-h4 font-weight-bold mt-1" :class="{ 'text-estimated': kpi.inference?.is_estimated }">
                      {{ formatValue(kpi.value, kpi.unit) }}
                    </div>
                    <div v-if="kpi.subtitle" class="text-caption text-grey-darken-2 mt-1">
                      {{ kpi.subtitle }}
                    </div>
                  </div>
                  <v-icon
                    :color="getStatusColor(kpi)"
                    size="40"
                  >
                    {{ kpiStore.kpiIcon(kpi.value, kpi.target, kpi.higherBetter) }}
                  </v-icon>
                </div>

                <!-- Progress bar -->
                <v-progress-linear
                  :model-value="getProgress(kpi)"
                  :color="getStatusColor(kpi)"
                  height="8"
                  rounded
                  class="mb-2"
                />

                <!-- Target and status -->
                <div class="d-flex justify-space-between text-caption">
                  <span class="text-grey-darken-1">
                    {{ t('kpi.target') }}: {{ kpi.target }}{{ kpi.unit }}
                  </span>
                  <span :class="`text-${getStatusColor(kpi)}`">
                    {{ getStatusText(kpi) }}
                  </span>
                </div>

                <!-- Phase 7.3: Confidence indicator bar (subtle) -->
                <div v-if="kpi.inference?.is_estimated" class="confidence-bar mt-2">
                  <v-tooltip location="bottom">
                    <template v-slot:activator="{ props }">
                      <v-progress-linear
                        v-bind="props"
                        :model-value="kpi.inference.confidence_score * 100"
                        :color="getConfidenceColor(kpi.inference.confidence_score)"
                        height="3"
                        rounded
                        bg-opacity="0.2"
                      />
                    </template>
                    <span>{{ $t('kpi.confidence') }}: {{ Math.round(kpi.inference.confidence_score * 100) }}%</span>
                  </v-tooltip>
                </div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ getKpiTooltip(kpi.key).title }}</div>
            <div v-if="getKpiTooltip(kpi.key).formula" class="tooltip-formula">{{ getKpiTooltip(kpi.key).formula }}</div>
            <div class="tooltip-title">{{ t('common.details') }}:</div>
            <div class="tooltip-meaning">{{ getKpiTooltip(kpi.key).meaning }}</div>
            <!-- Phase 7.3: Show inference info in tooltip if estimated -->
            <div v-if="kpi.inference?.is_estimated" class="tooltip-inference mt-2">
              <v-divider class="my-2" />
              <div class="tooltip-title">{{ t('quality.title') }}:</div>
              <div class="tooltip-meaning">
                {{ $t('kpi.estimated') }} - {{ Math.round(kpi.inference.confidence_score * 100) }}% {{ $t('kpi.confidence') }}
              </div>
            </div>
          </div>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- Trend Charts Section -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card role="region" aria-labelledby="trends-title">
          <v-card-title class="d-flex justify-space-between align-center">
            <span id="trends-title">{{ t('kpi.performanceTrend') }}</span>
            <v-btn-toggle
              v-model="trendPeriod"
              mandatory
              density="compact"
              @update:model-value="refreshData"
              aria-label="Select trend period"
            >
              <v-btn value="7" size="small" aria-label="Show 7 days trend">7 {{ t('common.days') }}</v-btn>
              <v-btn value="30" size="small" aria-label="Show 30 days trend">30 {{ t('common.days') }}</v-btn>
              <v-btn value="90" size="small" aria-label="Show 90 days trend">90 {{ t('common.days') }}</v-btn>
            </v-btn-toggle>
          </v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="12" md="6">
                <figure role="img" aria-label="Efficiency trend chart showing performance over time">
                  <Line
                    v-if="efficiencyChartData.labels.length"
                    :data="efficiencyChartData"
                    :options="chartOptions"
                  />
                  <figcaption class="sr-only">
                    Efficiency trend chart displaying {{ efficiencyChartData.labels.length }} data points.
                    Latest value: {{ efficiencyChartData.datasets[0]?.data?.slice(-1)[0] || t('common.na') }}%
                  </figcaption>
                </figure>
              </v-col>
              <v-col cols="12" md="6">
                <figure role="img" aria-label="Quality FPY trend chart showing first pass yield over time">
                  <Line
                    v-if="qualityChartData.labels.length"
                    :data="qualityChartData"
                    :options="chartOptions"
                  />
                  <figcaption class="sr-only">
                    Quality FPY trend chart displaying {{ qualityChartData.labels.length }} data points.
                    Latest value: {{ qualityChartData.datasets[0]?.data?.slice(-1)[0] || t('common.na') }}%
                  </figcaption>
                </figure>
              </v-col>
              <v-col cols="12" md="6">
                <figure role="img" aria-label="Availability trend chart showing equipment uptime over time">
                  <Line
                    v-if="availabilityChartData.labels.length"
                    :data="availabilityChartData"
                    :options="chartOptions"
                  />
                  <figcaption class="sr-only">
                    Availability trend chart displaying {{ availabilityChartData.labels.length }} data points.
                    Latest value: {{ availabilityChartData.datasets[0]?.data?.slice(-1)[0] || t('common.na') }}%
                  </figcaption>
                </figure>
              </v-col>
              <v-col cols="12" md="6">
                <figure role="img" aria-label="OEE trend chart showing overall equipment effectiveness over time">
                  <Line
                    v-if="oeeChartData.labels.length"
                    :data="oeeChartData"
                    :options="chartOptions"
                  />
                  <figcaption class="sr-only">
                    OEE trend chart displaying {{ oeeChartData.labels.length }} data points.
                    Latest value: {{ oeeChartData.datasets[0]?.data?.slice(-1)[0] || t('common.na') }}%
                  </figcaption>
                </figure>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Summary Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>{{ t('reports.summary') }}</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="summaryHeaders"
              :items="summaryItems"
              :loading="loading"
              density="comfortable"
              class="elevation-0"
            >
              <template v-slot:item.status="{ item }">
                <v-chip
                  :color="item.status"
                  size="small"
                  variant="flat"
                >
                  {{ item.statusText }}
                </v-chip>
              </template>
              <template v-slot:item.trend="{ item }">
                <v-icon
                  :color="item.trendColor"
                  size="small"
                >
                  {{ item.trendIcon }}
                </v-icon>
              </template>
              <template v-slot:item.actions="{ item }">
                <v-btn
                  icon="mdi-chevron-right"
                  size="small"
                  variant="text"
                  @click="navigateToDetail(item.route)"
                />
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Loading overlay -->
    <v-overlay
      v-model="loading"
      class="align-center justify-center"
      contained
    >
      <v-progress-circular
        indeterminate
        size="64"
        color="primary"
      />
    </v-overlay>

    <!-- Email Report Dialog -->
    <v-dialog
      v-model="emailDialog"
      max-width="500px"
      role="dialog"
      aria-modal="true"
      aria-labelledby="email-dialog-title"
    >
      <v-card>
        <v-card-title id="email-dialog-title" class="text-h5">{{ t('reports.title') }}</v-card-title>
        <v-card-text>
          <v-form ref="emailForm" v-model="emailFormValid">
            <v-combobox
              v-model="emailRecipients"
              :label="t('filters.recipients')"
              chips
              multiple
              variant="outlined"
              :hint="t('filters.pressEnterToAdd')"
              persistent-hint
              :rules="[v => (v && v.length > 0) || t('filters.atLeastOneRecipient')]"
            >
              <template v-slot:chip="{ item, props }">
                <v-chip v-bind="props" closable>
                  {{ item }}
                </v-chip>
              </template>
            </v-combobox>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="grey" variant="text" @click="emailDialog = false">
            {{ t('common.cancel') }}
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            @click="sendEmailReport"
            :loading="sendingEmail"
            :disabled="!emailFormValid"
          >
            {{ t('common.submit') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Success/Error Snackbar -->
    <v-snackbar
      v-model="snackbar"
      :color="snackbarColor"
      :timeout="4000"
      role="alert"
      :aria-live="snackbarColor === 'error' ? 'assertive' : 'polite'"
    >
      {{ snackbarMessage }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar = false" aria-label="Close notification">
          {{ t('common.close') }}
        </v-btn>
      </template>
    </v-snackbar>

    <!-- Dashboard Customizer Dialog -->
    <DashboardCustomizer
      v-model="showCustomizer"
      @saved="onCustomizerSaved"
    />

    <!-- Filter Manager Dialog -->
    <FilterManager
      v-model="showFilterManager"
    />

    <!-- QR Scanner Dialog -->
    <v-dialog
      v-model="showQRScanner"
      max-width="500px"
      role="dialog"
      aria-modal="true"
      aria-labelledby="qr-scanner-title"
    >
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" aria-hidden="true">mdi-qrcode-scan</v-icon>
          <span id="qr-scanner-title">{{ t('filters.quickQrScanner') }}</span>
          <v-spacer />
          <v-btn icon variant="text" @click="showQRScanner = false" aria-label="Close QR scanner">
            <v-icon aria-hidden="true">mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text class="pa-0">
          <QRCodeScanner
            @auto-fill="handleQRAutoFill"
            @scanned="handleQRScanned"
          />
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Save Filter Dialog -->
    <v-dialog
      v-model="showSaveFilterDialog"
      max-width="450px"
      role="dialog"
      aria-modal="true"
      aria-labelledby="save-filter-title"
    >
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" aria-hidden="true">mdi-content-save</v-icon>
          <span id="save-filter-title">{{ t('filters.saveCurrentFilter') }}</span>
        </v-card-title>
        <v-card-text>
          <v-form ref="saveFilterForm" v-model="saveFilterFormValid">
            <v-text-field
              v-model="newFilterName"
              :label="t('filters.filterName')"
              :placeholder="t('filters.filterNamePlaceholder')"
              variant="outlined"
              :rules="[v => !!v || t('filters.nameRequired')]"
              class="mb-3"
            />
            <v-select
              v-model="newFilterType"
              :items="filterTypeOptions"
              :label="t('filters.filterType')"
              variant="outlined"
              class="mb-3"
            />
            <v-checkbox
              v-model="newFilterIsDefault"
              :label="t('filters.setAsDefault')"
              hide-details
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="grey" variant="text" @click="showSaveFilterDialog = false">
            {{ t('common.cancel') }}
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            @click="saveCurrentFilter"
            :loading="savingFilter"
            :disabled="!saveFilterFormValid"
          >
            {{ t('filters.saveFilter') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'

// Components
import FilterBar from '@/components/filters/FilterBar.vue'
import DashboardCustomizer from '@/components/dashboard/DashboardCustomizer.vue'
import FilterManager from '@/components/filters/FilterManager.vue'
import QRCodeScanner from '@/components/QRCodeScanner.vue'
import InferenceIndicator from '@/components/kpi/InferenceIndicator.vue'

// Composables
import { useKPIDashboardData } from '@/composables/useKPIDashboardData'
import { useKPIReports } from '@/composables/useKPIReports'
import { useKPIFilters } from '@/composables/useKPIFilters'
import { useKPIChartData } from '@/composables/useKPIChartData'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const { t } = useI18n()
const router = useRouter()
const kpiStore = useKPIStore()

// Snackbar state (shared across composables)
const snackbar = ref(false)
const snackbarMessage = ref('')
const snackbarColor = ref('success')
const showSnackbar = (message, color = 'success') => {
  snackbarMessage.value = message
  snackbarColor.value = color
  snackbar.value = true
}

// Data & filter composable
const {
  loading,
  selectedClient,
  dateRange,
  trendPeriod,
  clients,
  filtersStore,
  refreshData,
  handleFilterChange,
  initialize
} = useKPIDashboardData(showSnackbar)

// Report composable
const {
  downloadingPDF,
  downloadingExcel,
  emailDialog,
  emailRecipients,
  emailFormValid,
  sendingEmail,
  downloadPDF,
  downloadExcel,
  sendEmailReport
} = useKPIReports(
  showSnackbar,
  () => selectedClient.value,
  () => dateRange.value
)

// Filter management composable
const {
  showSaveFilterDialog,
  saveFilterForm,
  saveFilterFormValid,
  newFilterName,
  newFilterType,
  newFilterIsDefault,
  savingFilter,
  filterTypeOptions,
  showFilterManager,
  applyQuickSavedFilter,
  saveCurrentFilter
} = useKPIFilters(
  showSnackbar,
  handleFilterChange,
  () => selectedClient.value,
  () => dateRange.value
)

// Chart data composable
const {
  chartOptions,
  efficiencyChartData,
  qualityChartData,
  availabilityChartData,
  oeeChartData
} = useKPIChartData()

// Local UI state
const showCustomizer = ref(false)
const showQRScanner = ref(false)
const emailForm = ref(null)

// Computed
const dateRangeText = computed(() => {
  if (!dateRange.value || dateRange.value.length === 0) return 'Select Date Range'
  const start = format(dateRange.value[0], 'MMM dd')
  const end = dateRange.value[1] ? format(dateRange.value[1], 'MMM dd') : start
  return `${start} - ${end}`
})

const summaryHeaders = [
  { title: 'KPI', key: 'title', sortable: true },
  { title: 'Current', key: 'value', sortable: true },
  { title: 'Target', key: 'target', sortable: true },
  { title: 'Status', key: 'status', sortable: true },
  { title: 'Trend', key: 'trend', sortable: false },
  { title: '', key: 'actions', sortable: false, width: 50 }
]

const summaryItems = computed(() => {
  return kpiStore.allKPIs.map(kpi => ({
    title: kpi.title,
    value: formatValue(kpi.value, kpi.unit),
    target: `${kpi.target}${kpi.unit}`,
    status: getStatusColor(kpi),
    statusText: getStatusText(kpi),
    trendIcon: getTrendIcon(kpi),
    trendColor: getTrendColor(kpi),
    route: kpi.route
  }))
})

// KPI display helpers
const formatValue = (value, unit) => {
  if (value === null || value === undefined) return t('common.na')
  return `${Number(value).toFixed(1)}${unit}`
}

const getCardColor = (kpi) => {
  return 'surface'
}

const getStatusColor = (kpi) => {
  return kpiStore.kpiStatus(kpi.value, kpi.target, kpi.higherBetter)
}

const getStatusText = (kpi) => {
  const status = getStatusColor(kpi)
  return status === 'success' ? t('operationsHealth.onTarget') : status === 'warning' ? t('operationsHealth.atRisk') : t('operationsHealth.critical')
}

const getProgress = (kpi) => {
  if (!kpi.value || !kpi.target) return 0
  const percentage = (kpi.value / kpi.target) * 100
  return kpi.higherBetter ? Math.min(percentage, 100) : Math.max(100 - percentage, 0)
}

const getTrendIcon = (kpi) => {
  return 'mdi-trending-up'
}

const getTrendColor = (kpi) => {
  return 'success'
}

const getConfidenceColor = (confidence) => {
  if (confidence >= 0.8) return 'success'
  if (confidence >= 0.5) return 'warning'
  return 'error'
}

// KPI Tooltip descriptions
const kpiTooltips = {
  efficiency: {
    title: 'Formula:',
    formula: 'Efficiency = (Actual Output / Expected Output) × 100',
    meaning: 'Measures how well resources are utilized to produce output. Higher efficiency means more output with the same resources.'
  },
  wipAging: {
    title: 'Formula:',
    formula: 'WIP Age = Days Since Work Order Started',
    meaning: 'Average time work-in-process items spend in production. Lower is better - indicates faster throughput and fewer bottlenecks.'
  },
  onTimeDelivery: {
    title: 'Formula:',
    formula: 'OTD = (Orders Delivered On Time / Total Orders) × 100',
    meaning: 'Percentage of orders delivered by the promised date. Critical for customer satisfaction and reliability.'
  },
  availability: {
    title: 'Formula:',
    formula: 'Availability = (Uptime / Planned Production Time) × 100',
    meaning: 'Percentage of scheduled time that equipment is available for production. Accounts for breakdowns and changeovers.'
  },
  performance: {
    title: 'Formula:',
    formula: 'Performance = (Actual Rate / Ideal Rate) × 100',
    meaning: 'Measures production speed relative to the designed capacity. Accounts for slow cycles and minor stoppages.'
  },
  quality: {
    title: 'Formula:',
    formula: 'FPY = (Good Units First Pass / Total Units) × 100',
    meaning: 'First Pass Yield - percentage of units that pass inspection on the first attempt without rework or repair.'
  },
  oee: {
    title: 'Formula:',
    formula: 'OEE = Availability × Performance × Quality',
    meaning: 'Overall Equipment Effectiveness - comprehensive metric combining availability, performance, and quality to measure manufacturing productivity.'
  },
  absenteeism: {
    title: 'Formula:',
    formula: 'Absenteeism = (Absent Hours / Scheduled Hours) × 100',
    meaning: 'Percentage of scheduled work hours lost due to employee absence. Lower is better for workforce planning and productivity.'
  },
  defectRates: {
    title: 'Formula:',
    formula: 'PPM = (Defective Units / Total Units) × 1,000,000',
    meaning: 'Parts Per Million - number of defective parts per million produced. Industry standard for measuring quality at scale.'
  },
  throughputTime: {
    title: 'Formula:',
    formula: 'Throughput = Total Time from Start to Completion',
    meaning: 'Average time to complete a production order from start to finish. Lower times indicate more efficient processes.'
  }
}

const getKpiTooltip = (key) => {
  return kpiTooltips[key] || {
    title: 'Info:',
    formula: null,
    meaning: 'Key performance indicator tracking operational metrics.'
  }
}

const navigateToDetail = (route) => {
  router.push(route)
}

const onCustomizerSaved = () => {
  showSnackbar(t('success.dashboardPreferencesSaved'), 'success')
}

// QR Scanner handlers
const handleQRScanned = (data) => {
  showSnackbar(`Scanned: ${data.entity_type} - ${data.entity_data?.id || 'ID'}`, 'info')
}

const handleQRAutoFill = (data) => {
  showQRScanner.value = false
  showSnackbar(`Auto-filled form data for ${data.entity_type}`, 'success')
  if (data.entity_type === 'work_order') {
    router.push({ name: 'production-entry', query: { work_order_id: data.entity_data?.id } })
  } else if (data.entity_type === 'product') {
    router.push({ name: 'production-entry', query: { product_id: data.entity_data?.id } })
  }
}

onMounted(async () => {
  await initialize()
})
</script>

<style scoped>
.kpi-card {
  cursor: pointer;
  transition: all 0.2s ease;
  border-width: 2px !important;
}

.kpi-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

/* Phase 7.3: Estimated card styling */
.estimated-card {
  border-style: dashed !important;
  border-color: rgba(var(--v-theme-warning), 0.4) !important;
}

.text-estimated {
  opacity: 0.9;
}

.confidence-bar {
  opacity: 0.7;
}
</style>

<style>
/* Tooltip styling - unscoped to affect Vuetify tooltip portal */
.v-tooltip > .v-overlay__content {
  background-color: rgba(33, 33, 33, 0.95) !important;
  color: #ffffff !important;
  padding: 12px 16px !important;
  font-size: 14px !important;
  line-height: 1.5 !important;
}

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
