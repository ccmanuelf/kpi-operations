<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">Overall Equipment Effectiveness (OEE)</h1>
        <p class="text-subtitle-1 text-grey">Comprehensive productivity metric combining Availability, Performance, and Quality</p>
      </v-col>
      <v-col cols="12" md="6" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2">
          {{ formatValue(oeeData?.percentage) }}%
        </v-chip>
        <v-chip color="grey-lighten-2">Target: 85%</v-chip>
      </v-col>
    </v-row>

    <!-- Client Filter -->
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

    <!-- OEE Formula Display -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card color="primary" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h6 mb-2">OEE = Availability x Performance x Quality</div>
            <div class="text-h4 font-weight-bold">
              {{ formatValue(components.availability) }}% x
              {{ formatValue(components.performance) }}% x
              {{ formatValue(components.quality) }}% =
              <span :class="statusColor + '--text'">{{ formatValue(oeeData?.percentage) }}%</span>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Component Cards -->
    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-card variant="outlined" @click="$router.push('/kpi/availability')" style="cursor:pointer">
          <v-card-text>
            <div class="d-flex align-center justify-space-between">
              <div>
                <div class="text-caption text-grey-darken-1">Availability</div>
                <div class="text-h4 font-weight-bold">{{ formatValue(components.availability) }}%</div>
                <div class="text-caption">Equipment uptime</div>
              </div>
              <v-icon size="48" color="blue">mdi-server</v-icon>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="4">
        <v-card variant="outlined" @click="$router.push('/kpi/performance')" style="cursor:pointer">
          <v-card-text>
            <div class="d-flex align-center justify-space-between">
              <div>
                <div class="text-caption text-grey-darken-1">Performance</div>
                <div class="text-h4 font-weight-bold">{{ formatValue(components.performance) }}%</div>
                <div class="text-caption">Speed efficiency</div>
              </div>
              <v-icon size="48" color="orange">mdi-speedometer</v-icon>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="4">
        <v-card variant="outlined" @click="$router.push('/kpi/quality')" style="cursor:pointer">
          <v-card-text>
            <div class="d-flex align-center justify-space-between">
              <div>
                <div class="text-caption text-grey-darken-1">Quality (FPY)</div>
                <div class="text-h4 font-weight-bold">{{ formatValue(components.quality) }}%</div>
                <div class="text-caption">First pass yield</div>
              </div>
              <v-icon size="48" color="green">mdi-star-circle</v-icon>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- OEE Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>OEE Trend</v-card-title>
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

const oeeData = computed(() => kpiStore.oee)
const components = computed(() => ({
  availability: kpiStore.availability?.percentage || 91.5,
  performance: kpiStore.performance?.percentage || 92,
  quality: kpiStore.quality?.fpy || 97
}))

const statusColor = computed(() => {
  const oee = oeeData.value?.percentage || 0
  if (oee >= 85) return 'success'
  if (oee >= 65) return 'warning'
  return 'error'
})

const historyHeaders = [
  { title: 'Date', key: 'date', sortable: true },
  { title: 'Total Units', key: 'total_units', sortable: true },
  { title: 'Efficiency %', key: 'avg_efficiency', sortable: true },
  { title: 'Performance %', key: 'avg_performance', sortable: true },
  { title: 'Entry Count', key: 'entry_count', sortable: true }
]

const chartData = computed(() => ({
  labels: kpiStore.trends.oee.map(d => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label: 'OEE %',
      data: kpiStore.trends.oee.map(d => d.value),
      borderColor: '#1976d2',
      backgroundColor: 'rgba(25, 118, 210, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'World Class (85%)',
      data: Array(kpiStore.trends.oee.length).fill(85),
      borderColor: '#2e7d32',
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
  if (eff >= 70) return 'warning'
  return 'error'
}

const getPerformanceColor = (perf) => {
  if (perf >= 95) return 'success'
  if (perf >= 80) return 'warning'
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
      kpiStore.fetchOEE(),
      kpiStore.fetchAvailability(),
      kpiStore.fetchPerformance(),
      kpiStore.fetchQuality(),
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
