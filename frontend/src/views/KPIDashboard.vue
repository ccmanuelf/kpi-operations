<template>
  <v-container fluid class="pa-4" role="main" aria-labelledby="kpi-dashboard-title">
    <!-- Header with title and actions -->
    <v-row class="mb-2">
      <v-col cols="12" md="6">
        <h1 id="kpi-dashboard-title" class="text-h3">KPI Dashboard</h1>
        <p class="text-subtitle-1 text-grey">Real-time performance metrics across all operations</p>
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
              QR Scanner
            </v-btn>
          </template>
          <span>Scan QR codes for quick data entry</span>
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
              {{ filtersStore.hasActiveFilter ? filtersStore.activeFilter.filter_name : 'Saved Filters' }}
              <v-icon end>mdi-chevron-down</v-icon>
            </v-btn>
          </template>
          <v-list density="compact" max-width="300">
            <v-list-subheader>
              <v-icon start size="small">mdi-bookmark-multiple</v-icon>
              Quick Apply Filter
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
              <v-list-item-title>Manage All Filters</v-list-item-title>
            </v-list-item>
            <v-list-item v-if="filtersStore.hasActiveFilter" @click="filtersStore.clearActiveFilter()">
              <template v-slot:prepend>
                <v-icon color="error">mdi-filter-off</v-icon>
              </template>
              <v-list-item-title class="text-error">Clear Active Filter</v-list-item-title>
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
          <span>Save current filter configuration</span>
        </v-tooltip>

        <!-- Dashboard Customize Button -->
        <v-btn
          variant="outlined"
          prepend-icon="mdi-view-dashboard-edit"
          @click="showCustomizer = true"
        >
          Customize
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
              Reports
            </v-btn>
          </template>
          <v-list>
            <v-list-item @click="downloadPDF" :loading="downloadingPDF">
              <template v-slot:prepend>
                <v-icon>mdi-file-pdf-box</v-icon>
              </template>
              <v-list-item-title>Download PDF</v-list-item-title>
            </v-list-item>
            <v-list-item @click="downloadExcel" :loading="downloadingExcel">
              <template v-slot:prepend>
                <v-icon>mdi-file-excel</v-icon>
              </template>
              <v-list-item-title>Download Excel</v-list-item-title>
            </v-list-item>
            <v-list-item @click="emailDialog = true">
              <template v-slot:prepend>
                <v-icon>mdi-email</v-icon>
              </template>
              <v-list-item-title>Email Report</v-list-item-title>
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
                    Target: {{ kpi.target }}{{ kpi.unit }}
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
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">{{ getKpiTooltip(kpi.key).meaning }}</div>
            <!-- Phase 7.3: Show inference info in tooltip if estimated -->
            <div v-if="kpi.inference?.is_estimated" class="tooltip-inference mt-2">
              <v-divider class="my-2" />
              <div class="tooltip-title">Data Quality:</div>
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
            <span id="trends-title">Performance Trends</span>
            <v-btn-toggle
              v-model="trendPeriod"
              mandatory
              density="compact"
              @update:model-value="refreshData"
              aria-label="Select trend period"
            >
              <v-btn value="7" size="small" aria-label="Show 7 days trend">7 Days</v-btn>
              <v-btn value="30" size="small" aria-label="Show 30 days trend">30 Days</v-btn>
              <v-btn value="90" size="small" aria-label="Show 90 days trend">90 Days</v-btn>
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
                    Latest value: {{ efficiencyChartData.datasets[0]?.data?.slice(-1)[0] || 'N/A' }}%
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
                    Latest value: {{ qualityChartData.datasets[0]?.data?.slice(-1)[0] || 'N/A' }}%
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
                    Latest value: {{ availabilityChartData.datasets[0]?.data?.slice(-1)[0] || 'N/A' }}%
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
                    Latest value: {{ oeeChartData.datasets[0]?.data?.slice(-1)[0] || 'N/A' }}%
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
          <v-card-title>KPI Summary</v-card-title>
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
        <v-card-title id="email-dialog-title" class="text-h5">Email Report</v-card-title>
        <v-card-text>
          <v-form ref="emailForm" v-model="emailFormValid">
            <v-combobox
              v-model="emailRecipients"
              label="Recipients"
              chips
              multiple
              variant="outlined"
              hint="Press Enter to add email addresses"
              persistent-hint
              :rules="[v => (v && v.length > 0) || 'At least one recipient required']"
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
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            @click="sendEmailReport"
            :loading="sendingEmail"
            :disabled="!emailFormValid"
          >
            Send Report
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
          Close
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
          <span id="qr-scanner-title">Quick QR Scanner</span>
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
          <span id="save-filter-title">Save Current Filter</span>
        </v-card-title>
        <v-card-text>
          <v-form ref="saveFilterForm" v-model="saveFilterFormValid">
            <v-text-field
              v-model="newFilterName"
              label="Filter Name"
              placeholder="e.g., Last Week - Client A"
              variant="outlined"
              :rules="[v => !!v || 'Name is required']"
              class="mb-3"
            />
            <v-select
              v-model="newFilterType"
              :items="filterTypeOptions"
              label="Filter Type"
              variant="outlined"
              class="mb-3"
            />
            <v-checkbox
              v-model="newFilterIsDefault"
              label="Set as default for this filter type"
              hide-details
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="grey" variant="text" @click="showSaveFilterDialog = false">
            Cancel
          </v-btn>
          <v-btn
            color="primary"
            variant="flat"
            @click="saveCurrentFilter"
            :loading="savingFilter"
            :disabled="!saveFilterFormValid"
          >
            Save Filter
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
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
import { useDashboardStore } from '@/stores/dashboardStore'
import { useFiltersStore } from '@/stores/filtersStore'
import api from '@/services/api'

// New components for custom dashboards and filters
import FilterBar from '@/components/filters/FilterBar.vue'
import DashboardCustomizer from '@/components/dashboard/DashboardCustomizer.vue'
import FilterManager from '@/components/filters/FilterManager.vue'
import QRCodeScanner from '@/components/QRCodeScanner.vue'
// Phase 7.3: Inference indicator component
import InferenceIndicator from '@/components/kpi/InferenceIndicator.vue'

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

const router = useRouter()
const kpiStore = useKPIStore()
const dashboardStore = useDashboardStore()
const filtersStore = useFiltersStore()

// State
const loading = ref(false)
const selectedClient = ref(null)
const dateRange = ref([
  new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
  new Date()
])
const trendPeriod = ref('30')
const clients = ref([
  { id: null, name: 'All Clients' }
])

// New feature dialogs
const showCustomizer = ref(false)
const showFilterManager = ref(false)
const showQRScanner = ref(false)

// Save filter dialog state
const showSaveFilterDialog = ref(false)
const saveFilterForm = ref(null)
const saveFilterFormValid = ref(false)
const newFilterName = ref('')
const newFilterType = ref('dashboard')
const newFilterIsDefault = ref(false)
const savingFilter = ref(false)
const filterTypeOptions = [
  { title: 'Dashboard', value: 'dashboard' },
  { title: 'Production', value: 'production' },
  { title: 'Quality', value: 'quality' },
  { title: 'Attendance', value: 'attendance' },
  { title: 'Downtime', value: 'downtime' }
]

// Report functionality
const downloadingPDF = ref(false)
const downloadingExcel = ref(false)
const emailDialog = ref(false)
const emailRecipients = ref([])
const emailFormValid = ref(false)
const sendingEmail = ref(false)
const snackbar = ref(false)
const snackbarMessage = ref('')
const snackbarColor = ref('success')

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

// Chart data
const efficiencyChartData = computed(() => ({
  labels: kpiStore.trends.efficiency.map(d => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label: 'Efficiency %',
      data: kpiStore.trends.efficiency.map(d => d.value),
      borderColor: '#2e7d32',
      backgroundColor: 'rgba(46, 125, 50, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'Target',
      data: Array(kpiStore.trends.efficiency.length).fill(85),
      borderColor: '#f57c00',
      borderDash: [5, 5],
      pointRadius: 0
    }
  ]
}))

const qualityChartData = computed(() => ({
  labels: kpiStore.trends.quality.map(d => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label: 'FPY %',
      data: kpiStore.trends.quality.map(d => d.value),
      borderColor: '#1976d2',
      backgroundColor: 'rgba(25, 118, 210, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'Target',
      data: Array(kpiStore.trends.quality.length).fill(99),
      borderColor: '#f57c00',
      borderDash: [5, 5],
      pointRadius: 0
    }
  ]
}))

const availabilityChartData = computed(() => ({
  labels: kpiStore.trends.availability.map(d => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label: 'Availability %',
      data: kpiStore.trends.availability.map(d => d.value),
      borderColor: '#7b1fa2',
      backgroundColor: 'rgba(123, 31, 162, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'Target',
      data: Array(kpiStore.trends.availability.length).fill(90),
      borderColor: '#f57c00',
      borderDash: [5, 5],
      pointRadius: 0
    }
  ]
}))

const oeeChartData = computed(() => ({
  labels: kpiStore.trends.oee.map(d => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label: 'OEE %',
      data: kpiStore.trends.oee.map(d => d.value),
      borderColor: '#d32f2f',
      backgroundColor: 'rgba(211, 47, 47, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'Target',
      data: Array(kpiStore.trends.oee.length).fill(85),
      borderColor: '#f57c00',
      borderDash: [5, 5],
      pointRadius: 0
    }
  ]
}))

const chartOptions = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: {
      display: true,
      position: 'top'
    },
    tooltip: {
      mode: 'index',
      intersect: false
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      ticks: {
        callback: (value) => `${value}%`
      }
    }
  },
  interaction: {
    mode: 'nearest',
    axis: 'x',
    intersect: false
  }
}

// Methods
const formatValue = (value, unit) => {
  if (value === null || value === undefined) return 'N/A'
  return `${Number(value).toFixed(1)}${unit}`
}

const getCardColor = (kpi) => {
  const status = kpiStore.kpiStatus(kpi.value, kpi.target, kpi.higherBetter)
  return status === 'success' ? 'surface' : status === 'warning' ? 'surface' : 'surface'
}

const getStatusColor = (kpi) => {
  return kpiStore.kpiStatus(kpi.value, kpi.target, kpi.higherBetter)
}

const getStatusText = (kpi) => {
  const status = getStatusColor(kpi)
  return status === 'success' ? 'On Target' : status === 'warning' ? 'At Risk' : 'Critical'
}

const getProgress = (kpi) => {
  if (!kpi.value || !kpi.target) return 0
  const percentage = (kpi.value / kpi.target) * 100
  return kpi.higherBetter ? Math.min(percentage, 100) : Math.max(100 - percentage, 0)
}

const getTrendIcon = (kpi) => {
  // This would ideally calculate from historical data
  return 'mdi-trending-up'
}

const getTrendColor = (kpi) => {
  return 'success'
}

// Phase 7.3: Get color based on confidence score
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

const handleClientChange = () => {
  kpiStore.setClient(selectedClient.value)
  refreshData()
}

const handleDateChange = () => {
  if (dateRange.value && dateRange.value.length === 2) {
    kpiStore.setDateRange(
      format(dateRange.value[0], 'yyyy-MM-dd'),
      format(dateRange.value[1], 'yyyy-MM-dd')
    )
    refreshData()
  }
}

const refreshData = async () => {
  loading.value = true
  try {
    await kpiStore.fetchAllKPIs()
  } catch (error) {
    console.error('Error refreshing data:', error)
  } finally {
    loading.value = false
  }
}

const loadClients = async () => {
  try {
    const response = await api.getClients()
    clients.value = [
      { id: null, name: 'All Clients' },
      ...response.data
    ]
  } catch (error) {
    console.error('Error loading clients:', error)
  }
}

const downloadPDF = async () => {
  downloadingPDF.value = true
  try {
    const params = new URLSearchParams()
    if (selectedClient.value) params.append('client_id', selectedClient.value)
    if (dateRange.value && dateRange.value.length === 2) {
      params.append('start_date', format(dateRange.value[0], 'yyyy-MM-dd'))
      params.append('end_date', format(dateRange.value[1], 'yyyy-MM-dd'))
    }

    const response = await api.get(`/reports/pdf?${params.toString()}`, {
      responseType: 'blob'
    })

    // Create download link
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `KPI_Report_${format(new Date(), 'yyyyMMdd')}.pdf`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    showSnackbar('PDF report downloaded successfully', 'success')
  } catch (error) {
    console.error('Error downloading PDF:', error)
    showSnackbar('Failed to download PDF report', 'error')
  } finally {
    downloadingPDF.value = false
  }
}

const downloadExcel = async () => {
  downloadingExcel.value = true
  try {
    const params = new URLSearchParams()
    if (selectedClient.value) params.append('client_id', selectedClient.value)
    if (dateRange.value && dateRange.value.length === 2) {
      params.append('start_date', format(dateRange.value[0], 'yyyy-MM-dd'))
      params.append('end_date', format(dateRange.value[1], 'yyyy-MM-dd'))
    }

    const response = await api.get(`/reports/excel?${params.toString()}`, {
      responseType: 'blob'
    })

    // Create download link
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `KPI_Report_${format(new Date(), 'yyyyMMdd')}.xlsx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    showSnackbar('Excel report downloaded successfully', 'success')
  } catch (error) {
    console.error('Error downloading Excel:', error)
    showSnackbar('Failed to download Excel report', 'error')
  } finally {
    downloadingExcel.value = false
  }
}

const sendEmailReport = async () => {
  if (!emailFormValid.value || emailRecipients.value.length === 0) {
    showSnackbar('Please add at least one recipient', 'warning')
    return
  }

  sendingEmail.value = true
  try {
    const payload = {
      client_id: selectedClient.value || null,
      start_date: dateRange.value && dateRange.value.length === 2
        ? format(dateRange.value[0], 'yyyy-MM-dd')
        : format(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), 'yyyy-MM-dd'),
      end_date: dateRange.value && dateRange.value.length === 2
        ? format(dateRange.value[1], 'yyyy-MM-dd')
        : format(new Date(), 'yyyy-MM-dd'),
      recipient_emails: emailRecipients.value,
      include_excel: false
    }

    await api.post('/reports/email', payload)

    showSnackbar('Report sent successfully!', 'success')
    emailDialog.value = false
    emailRecipients.value = []
  } catch (error) {
    console.error('Error sending email:', error)
    showSnackbar('Failed to send email report', 'error')
  } finally {
    sendingEmail.value = false
  }
}

const showSnackbar = (message, color = 'success') => {
  snackbarMessage.value = message
  snackbarColor.value = color
  snackbar.value = true
}

// New feature handlers
const handleFilterChange = (filterParams) => {
  // Apply client filter
  if (filterParams.client_id !== undefined) {
    selectedClient.value = filterParams.client_id
    kpiStore.setClient(filterParams.client_id)
  }

  // Apply date range filter - handle both nested and flat formats
  if (filterParams.date_range) {
    const filterDateRange = filterParams.date_range
    if (filterDateRange.type === 'absolute' && filterDateRange.start_date && filterDateRange.end_date) {
      kpiStore.setDateRange(filterDateRange.start_date, filterDateRange.end_date)
      dateRange.value = [new Date(filterDateRange.start_date), new Date(filterDateRange.end_date)]
    } else if (filterDateRange.type === 'relative' && filterDateRange.relative_days !== undefined) {
      const end = new Date()
      const start = new Date()
      start.setDate(start.getDate() - filterDateRange.relative_days)
      const startStr = format(start, 'yyyy-MM-dd')
      const endStr = format(end, 'yyyy-MM-dd')
      kpiStore.setDateRange(startStr, endStr)
      dateRange.value = [start, end]
    }
  } else if (filterParams.start_date && filterParams.end_date) {
    // Fallback for flat date format
    kpiStore.setDateRange(filterParams.start_date, filterParams.end_date)
    dateRange.value = [new Date(filterParams.start_date), new Date(filterParams.end_date)]
  }

  refreshData()
}

const onCustomizerSaved = () => {
  showSnackbar('Dashboard preferences saved', 'success')
}

// QR Scanner handlers
const handleQRScanned = (data) => {
  showSnackbar(`Scanned: ${data.entity_type} - ${data.entity_data?.id || 'ID'}`, 'info')
}

const handleQRAutoFill = (data) => {
  showQRScanner.value = false
  showSnackbar(`Auto-filled form data for ${data.entity_type}`, 'success')
  // Navigate to appropriate entry form based on entity type
  if (data.entity_type === 'work_order') {
    router.push({ name: 'production-entry', query: { work_order_id: data.entity_data?.id } })
  } else if (data.entity_type === 'product') {
    router.push({ name: 'production-entry', query: { product_id: data.entity_data?.id } })
  }
}

// Saved filter handlers
const applyQuickSavedFilter = async (filter) => {
  try {
    const filterConfig = await filtersStore.applyFilter(filter)
    handleFilterChange(filterConfig)
    showSnackbar(`Applied filter: ${filter.filter_name}`, 'success')
  } catch (error) {
    console.error('Error applying filter:', error)
    showSnackbar('Failed to apply filter', 'error')
  }
}

const saveCurrentFilter = async () => {
  if (!saveFilterFormValid.value || !newFilterName.value) {
    showSnackbar('Please enter a filter name', 'warning')
    return
  }

  savingFilter.value = true
  try {
    // Build filter config from current state
    const filterConfig = filtersStore.createFilterConfig({
      client_id: selectedClient.value,
      date_range: dateRange.value && dateRange.value.length === 2 ? {
        type: 'absolute',
        start_date: format(dateRange.value[0], 'yyyy-MM-dd'),
        end_date: format(dateRange.value[1], 'yyyy-MM-dd')
      } : { type: 'relative', relative_days: 30 }
    })

    const newFilter = await filtersStore.createFilter({
      filter_name: newFilterName.value,
      filter_type: newFilterType.value,
      filter_config: filterConfig,
      is_default: newFilterIsDefault.value
    })

    if (newFilter) {
      showSnackbar(`Filter "${newFilterName.value}" saved successfully`, 'success')
      showSaveFilterDialog.value = false
      // Reset form
      newFilterName.value = ''
      newFilterIsDefault.value = false
    } else {
      showSnackbar('Failed to save filter', 'error')
    }
  } catch (error) {
    console.error('Error saving filter:', error)
    showSnackbar('Failed to save filter', 'error')
  } finally {
    savingFilter.value = false
  }
}

onMounted(async () => {
  await loadClients()
  await dashboardStore.initializePreferences()
  await filtersStore.initializeFilters()
  await refreshData()
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
