<template>
  <v-container fluid class="pa-4">
    <!-- Header with filters -->
    <v-row class="mb-4">
      <v-col cols="12" md="6">
        <h1 class="text-h3">KPI Dashboard</h1>
        <p class="text-subtitle-1 text-grey">Real-time performance metrics across all operations</p>
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center justify-end">
        <v-select
          v-model="selectedClient"
          :items="clients"
          item-title="name"
          item-value="id"
          label="Client"
          variant="outlined"
          density="compact"
          class="mr-2"
          style="max-width: 200px"
          @update:model-value="handleClientChange"
        />
        <v-menu :close-on-content-click="false">
          <template v-slot:activator="{ props }">
            <v-btn
              color="primary"
              variant="outlined"
              v-bind="props"
              prepend-icon="mdi-calendar-range"
            >
              {{ dateRangeText }}
            </v-btn>
          </template>
          <v-card>
            <v-card-text>
              <v-date-picker
                v-model="dateRange"
                range
                @update:model-value="handleDateChange"
              />
            </v-card-text>
          </v-card>
        </v-menu>
        <v-btn
          icon="mdi-refresh"
          variant="text"
          class="ml-2"
          @click="refreshData"
          :loading="loading"
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
        <v-card
          :color="getCardColor(kpi)"
          variant="outlined"
          class="kpi-card"
          @click="navigateToDetail(kpi.route)"
          hover
        >
          <v-card-text>
            <div class="d-flex justify-space-between align-start mb-3">
              <div>
                <div class="text-caption text-grey-darken-1">{{ kpi.title }}</div>
                <div class="text-h4 font-weight-bold mt-1">
                  {{ formatValue(kpi.value, kpi.unit) }}
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
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Trend Charts Section -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex justify-space-between align-center">
            <span>Performance Trends</span>
            <v-btn-toggle
              v-model="trendPeriod"
              mandatory
              density="compact"
              @update:model-value="refreshData"
            >
              <v-btn value="7" size="small">7 Days</v-btn>
              <v-btn value="30" size="small">30 Days</v-btn>
              <v-btn value="90" size="small">90 Days</v-btn>
            </v-btn-toggle>
          </v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="12" md="6">
                <Line
                  v-if="efficiencyChartData.labels.length"
                  :data="efficiencyChartData"
                  :options="chartOptions"
                />
              </v-col>
              <v-col cols="12" md="6">
                <Line
                  v-if="qualityChartData.labels.length"
                  :data="qualityChartData"
                  :options="chartOptions"
                />
              </v-col>
              <v-col cols="12" md="6">
                <Line
                  v-if="availabilityChartData.labels.length"
                  :data="availabilityChartData"
                  :options="chartOptions"
                />
              </v-col>
              <v-col cols="12" md="6">
                <Line
                  v-if="oeeChartData.labels.length"
                  :data="oeeChartData"
                  :options="chartOptions"
                />
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
  Legend
} from 'chart.js'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import api from '@/services/api'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

const router = useRouter()
const kpiStore = useKPIStore()

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

onMounted(async () => {
  await loadClients()
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
</style>
