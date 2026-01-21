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
          <v-card-title>Efficiency Trend</v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
            <v-alert v-else type="info" variant="tonal">No trend data available</v-alert>
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

const chartData = computed(() => ({
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
      label: 'Target (85%)',
      data: Array(kpiStore.trends.efficiency.length).fill(85),
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
    await Promise.all([
      kpiStore.fetchEfficiency(),
      kpiStore.fetchDashboard()
    ])
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
