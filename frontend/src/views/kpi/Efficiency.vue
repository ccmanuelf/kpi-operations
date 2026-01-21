<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">Operational Efficiency</h1>
        <p class="text-subtitle-1 text-grey-darken-1">Monitor resource utilization and productivity metrics</p>
      </v-col>
      <v-col cols="12" md="6" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2 text-white" variant="flat">
          {{ formatValue(efficiencyData?.current) }}%
        </v-chip>
        <v-chip color="grey-darken-2">Target: 85%</v-chip>
      </v-col>
    </v-row>

    <!-- Filters -->
    <v-row class="mt-2">
      <v-col cols="12" md="4">
        <v-select
          v-model="selectedClient"
          :items="clients"
          item-title="client_name"
          item-value="client_id"
          label="Filter by Client"
          clearable
          density="compact"
          variant="outlined"
          @update:model-value="onClientChange"
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-text-field
          v-model="startDate"
          type="date"
          label="Start Date"
          density="compact"
          variant="outlined"
          @change="onDateChange"
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-text-field
          v-model="endDate"
          type="date"
          label="End Date"
          density="compact"
          variant="outlined"
          @change="onDateChange"
        />
      </v-col>
      <v-col cols="12" md="2">
        <v-btn color="primary" block @click="refreshData" :loading="loading">
          <v-icon left>mdi-refresh</v-icon> Refresh
        </v-btn>
      </v-col>
    </v-row>

    <!-- Summary Cards -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">Current Efficiency</div>
                <div class="text-h4 font-weight-bold">{{ formatValue(efficiencyData?.current) }}%</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">Formula:</div>
            <div class="tooltip-formula">Efficiency = (Actual Output / Expected Output) × 100</div>
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">Measures how well resources are utilized to produce output. Target is 85%. Higher efficiency indicates better resource utilization.</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">Actual Output</div>
                <div class="text-h4 font-weight-bold">{{ efficiencyData?.actual_output || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">Total number of units actually produced within the selected period. This is the numerator for efficiency calculation.</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">Expected Output</div>
                <div class="text-h4 font-weight-bold">{{ efficiencyData?.expected_output || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">Target number of units based on standard production rates and available time. This is the benchmark for measuring efficiency.</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">Gap</div>
                <div class="text-h4 font-weight-bold" :class="gapColor">
                  {{ efficiencyData?.gap || 0 }} units
                </div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">Formula:</div>
            <div class="tooltip-formula">Gap = Actual Output - Expected Output</div>
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">Difference between actual and expected output. Positive (green) means exceeding target; negative (red) means below target.</div>
          </div>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- Efficiency Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <span>Efficiency Trend</span>
            <v-spacer />
            <v-switch
              v-model="showForecast"
              label="Show Forecast"
              color="purple"
              density="compact"
              hide-details
              class="mr-4"
              @change="onForecastToggle"
            />
            <v-select
              v-if="showForecast"
              v-model="forecastDays"
              :items="[3, 7, 14, 21, 30]"
              label="Forecast Days"
              density="compact"
              variant="outlined"
              style="max-width: 120px"
              hide-details
              @update:model-value="fetchPrediction"
            />
          </v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
            <v-alert v-else type="info" variant="tonal">No trend data available</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Prediction Details Card -->
    <v-row v-if="showForecast && predictionData" class="mt-4">
      <v-col cols="12" md="4">
        <v-card variant="outlined" class="border-purple">
          <v-card-title class="text-purple-darken-1">
            <v-icon start>mdi-crystal-ball</v-icon>
            Prediction Summary
          </v-card-title>
          <v-card-text>
            <div class="d-flex justify-space-between mb-2">
              <span class="text-grey-darken-1">Predicted Average:</span>
              <span class="font-weight-bold">{{ predictionData.predicted_average?.toFixed(1) }}%</span>
            </div>
            <div class="d-flex justify-space-between mb-2">
              <span class="text-grey-darken-1">Current Value:</span>
              <span>{{ predictionData.current_value?.toFixed(1) }}%</span>
            </div>
            <div class="d-flex justify-space-between mb-2">
              <span class="text-grey-darken-1">Expected Change:</span>
              <v-chip :color="predictionData.expected_change_percent >= 0 ? 'success' : 'error'" size="small">
                {{ predictionData.expected_change_percent >= 0 ? '+' : '' }}{{ predictionData.expected_change_percent?.toFixed(1) }}%
              </v-chip>
            </div>
            <div class="d-flex justify-space-between mb-2">
              <span class="text-grey-darken-1">Model Accuracy:</span>
              <span>{{ predictionData.model_accuracy?.toFixed(0) }}%</span>
            </div>
            <div class="d-flex justify-space-between">
              <span class="text-grey-darken-1">Method:</span>
              <v-chip size="x-small" color="purple" variant="outlined">
                {{ predictionData.prediction_method?.replace(/_/g, ' ') }}
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card variant="outlined">
          <v-card-title>
            <v-icon start>mdi-heart-pulse</v-icon>
            Health Assessment
          </v-card-title>
          <v-card-text v-if="predictionData.health_assessment">
            <div class="d-flex align-center mb-3">
              <v-progress-circular
                :model-value="predictionData.health_assessment.health_score"
                :color="getHealthColor(predictionData.health_assessment.health_score)"
                :size="60"
                :width="6"
              >
                {{ predictionData.health_assessment.health_score?.toFixed(0) }}
              </v-progress-circular>
              <div class="ml-3">
                <div class="text-body-2 text-grey-darken-1">Health Score</div>
                <v-chip :color="getTrendColor(predictionData.health_assessment.trend)" size="small">
                  <v-icon start size="small">{{ getTrendIcon(predictionData.health_assessment.trend) }}</v-icon>
                  {{ predictionData.health_assessment.trend }}
                </v-chip>
              </div>
            </div>
            <div class="text-caption text-grey-darken-1">
              {{ predictionData.health_assessment.current_vs_target }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card variant="outlined">
          <v-card-title>
            <v-icon start>mdi-lightbulb</v-icon>
            Recommendations
          </v-card-title>
          <v-card-text v-if="predictionData.health_assessment?.recommendations">
            <v-list density="compact" class="pa-0">
              <v-list-item
                v-for="(rec, index) in predictionData.health_assessment.recommendations.slice(0, 3)"
                :key="index"
                class="px-0"
              >
                <template v-slot:prepend>
                  <v-icon size="small" color="amber-darken-2">mdi-arrow-right</v-icon>
                </template>
                <v-list-item-title class="text-body-2">{{ rec }}</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Historical Data Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            Historical Production Data
            <v-spacer />
            <v-text-field
              v-model="tableSearch"
              append-icon="mdi-magnify"
              label="Search"
              single-line
              hide-details
              density="compact"
              style="max-width: 300px"
            />
          </v-card-title>
          <v-card-text>
            <v-data-table
              :headers="historyHeaders"
              :items="historicalData"
              :search="tableSearch"
              :loading="loading"
              :items-per-page="10"
              class="elevation-0"
            >
              <template v-slot:item.date="{ item }">
                {{ formatDate(item.date) }}
              </template>
              <template v-slot:item.avg_efficiency="{ item }">
                <v-chip :color="getEfficiencyColor(item.avg_efficiency)" size="small">
                  {{ item.avg_efficiency?.toFixed(1) || 0 }}%
                </v-chip>
              </template>
              <template v-slot:item.avg_performance="{ item }">
                <v-chip :color="getPerformanceColor(item.avg_performance)" size="small">
                  {{ item.avg_performance?.toFixed(1) || 0 }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Efficiency by Shift and Product -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Efficiency by Shift</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="shiftHeaders"
              :items="efficiencyData?.by_shift || []"
              density="compact"
            >
              <template v-slot:item.efficiency="{ item }">
                <v-chip :color="getEfficiencyColor(item.efficiency)" size="small">
                  {{ item.efficiency?.toFixed(1) || 0 }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Top Products by Efficiency</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="productHeaders"
              :items="efficiencyData?.by_product || []"
              density="compact"
            >
              <template v-slot:item.efficiency="{ item }">
                <v-chip :color="getEfficiencyColor(item.efficiency)" size="small">
                  {{ item.efficiency?.toFixed(1) || 0 }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-overlay v-model="loading" class="align-center justify-center" contained>
      <v-progress-circular indeterminate size="64" color="primary" />
    </v-overlay>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
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

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const kpiStore = useKPIStore()
const loading = ref(false)
const clients = ref([])
const selectedClient = ref(null)
const startDate = ref(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
const endDate = ref(new Date().toISOString().split('T')[0])
const tableSearch = ref('')
const historicalData = ref([])
const showForecast = ref(true)
const forecastDays = ref(7)
const predictionData = ref(null)

const efficiencyData = computed(() => kpiStore.efficiency)

const statusColor = computed(() => {
  const eff = efficiencyData.value?.current || 0
  if (eff >= 85) return 'success'
  if (eff >= 70) return 'amber-darken-3'
  return 'error'
})

const gapColor = computed(() => {
  const gap = efficiencyData.value?.gap || 0
  return gap >= 0 ? 'text-success' : 'text-error'
})

const shiftHeaders = [
  { title: 'Shift', key: 'shift_name', sortable: true },
  { title: 'Output', key: 'actual_output', sortable: true },
  { title: 'Expected', key: 'expected_output', sortable: true },
  { title: 'Efficiency', key: 'efficiency', sortable: true }
]

const productHeaders = [
  { title: 'Product', key: 'product_name', sortable: true },
  { title: 'Output', key: 'actual_output', sortable: true },
  { title: 'Efficiency', key: 'efficiency', sortable: true }
]

const historyHeaders = [
  { title: 'Date', key: 'date', sortable: true },
  { title: 'Total Units', key: 'total_units', sortable: true },
  { title: 'Efficiency %', key: 'avg_efficiency', sortable: true },
  { title: 'Performance %', key: 'avg_performance', sortable: true },
  { title: 'Entry Count', key: 'entry_count', sortable: true }
]

const chartData = computed(() => {
  const trendLabels = kpiStore.trends.efficiency.map(d => format(new Date(d.date), 'MMM dd'))
  const trendData = kpiStore.trends.efficiency.map(d => d.value)

  const datasets = [
    {
      label: 'Efficiency %',
      data: trendData,
      borderColor: '#2e7d32',
      backgroundColor: 'rgba(46, 125, 50, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'Target (85%)',
      data: Array(trendLabels.length).fill(85),
      borderColor: '#f57c00',
      borderDash: [5, 5],
      pointRadius: 0
    }
  ]

  // Add forecast data if available and enabled
  if (showForecast.value && predictionData.value && predictionData.value.predictions) {
    const forecastLabels = predictionData.value.predictions.map(p => {
      const date = new Date(p.date)
      return format(date, 'MMM dd')
    })
    const forecastValues = predictionData.value.predictions.map(p => p.predicted_value)
    const upperBounds = predictionData.value.predictions.map(p => p.upper_bound)
    const lowerBounds = predictionData.value.predictions.map(p => p.lower_bound)

    // Combine labels (historical + forecast)
    const allLabels = [...trendLabels, ...forecastLabels]

    // Pad historical data with nulls for forecast period
    const paddedTrendData = [...trendData, ...Array(forecastLabels.length).fill(null)]
    const paddedTarget = Array(allLabels.length).fill(85)

    // Pad forecast data with nulls for historical period
    // Connect forecast to last historical point
    const lastHistoricalValue = trendData.length > 0 ? trendData[trendData.length - 1] : null
    const paddedForecast = [...Array(trendLabels.length - 1).fill(null), lastHistoricalValue, ...forecastValues]
    const paddedUpper = [...Array(trendLabels.length - 1).fill(null), lastHistoricalValue, ...upperBounds]
    const paddedLower = [...Array(trendLabels.length - 1).fill(null), lastHistoricalValue, ...lowerBounds]

    return {
      labels: allLabels,
      datasets: [
        {
          label: 'Efficiency %',
          data: paddedTrendData,
          borderColor: '#2e7d32',
          backgroundColor: 'rgba(46, 125, 50, 0.1)',
          tension: 0.3,
          fill: true
        },
        {
          label: 'Target (85%)',
          data: paddedTarget,
          borderColor: '#f57c00',
          borderDash: [5, 5],
          pointRadius: 0
        },
        {
          label: 'Forecast',
          data: paddedForecast,
          borderColor: '#9c27b0',
          backgroundColor: 'rgba(156, 39, 176, 0.1)',
          borderDash: [6, 4],
          tension: 0.3,
          fill: false,
          pointStyle: 'rectRot',
          pointRadius: 4,
          pointBackgroundColor: '#9c27b0'
        },
        {
          label: 'Confidence Upper',
          data: paddedUpper,
          borderColor: 'rgba(156, 39, 176, 0.3)',
          backgroundColor: 'rgba(156, 39, 176, 0.05)',
          borderDash: [2, 2],
          tension: 0.3,
          fill: '+1',
          pointRadius: 0
        },
        {
          label: 'Confidence Lower',
          data: paddedLower,
          borderColor: 'rgba(156, 39, 176, 0.3)',
          backgroundColor: 'transparent',
          borderDash: [2, 2],
          tension: 0.3,
          fill: false,
          pointRadius: 0
        }
      ]
    }
  }

  return { labels: trendLabels, datasets }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: { display: true, position: 'top' },
    tooltip: { mode: 'index', intersect: false }
  },
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      ticks: { callback: (value) => `${value}%` }
    }
  }
}

const formatValue = (value) => {
  return value !== null && value !== undefined ? Number(value).toFixed(1) : 'N/A'
}

const formatDate = (dateStr) => {
  try {
    return format(new Date(dateStr), 'MMM dd, yyyy')
  } catch {
    return dateStr
  }
}

const getEfficiencyColor = (eff) => {
  if (eff >= 85) return 'success'
  if (eff >= 70) return 'amber-darken-3'
  return 'error'
}

const getPerformanceColor = (perf) => {
  if (perf >= 95) return 'success'
  if (perf >= 80) return 'amber-darken-3'
  return 'error'
}

const getHealthColor = (score) => {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'error'
}

const getTrendColor = (trend) => {
  if (trend === 'improving') return 'success'
  if (trend === 'declining') return 'error'
  return 'grey'
}

const getTrendIcon = (trend) => {
  if (trend === 'improving') return 'mdi-trending-up'
  if (trend === 'declining') return 'mdi-trending-down'
  return 'mdi-minus'
}

const fetchPrediction = async () => {
  if (!showForecast.value) {
    predictionData.value = null
    return
  }
  try {
    const params = {
      forecast_days: forecastDays.value,
      historical_days: 30,
      method: 'auto'
    }
    if (selectedClient.value) {
      params.client_id = selectedClient.value
    }
    const response = await api.getPrediction('efficiency', params)
    predictionData.value = response.data
  } catch (error) {
    console.error('Failed to fetch prediction:', error)
    predictionData.value = null
  }
}

const onForecastToggle = () => {
  if (showForecast.value) {
    fetchPrediction()
  } else {
    predictionData.value = null
  }
}

const loadClients = async () => {
  try {
    const response = await api.getClients()
    clients.value = response.data || []
  } catch (error) {
    console.error('Failed to load clients:', error)
  }
}

const onClientChange = () => {
  kpiStore.setClient(selectedClient.value)
  refreshData()
}

const onDateChange = () => {
  kpiStore.setDateRange(startDate.value, endDate.value)
  refreshData()
}

const refreshData = async () => {
  loading.value = true
  try {
    const promises = [
      kpiStore.fetchEfficiency(),
      kpiStore.fetchDashboard()
    ]
    if (showForecast.value) {
      promises.push(fetchPrediction())
    }
    await Promise.all(promises)
    historicalData.value = kpiStore.dashboard || []
  } catch (error) {
    console.error('Failed to refresh data:', error)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await loadClients()
    kpiStore.setDateRange(startDate.value, endDate.value)
    await refreshData()
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.cursor-help {
  cursor: help;
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
