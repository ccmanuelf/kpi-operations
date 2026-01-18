<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">Quality Metrics Dashboard</h1>
        <p class="text-subtitle-1 text-grey">Comprehensive quality analysis: PPM, DPMO, FPY, RTY</p>
      </v-col>
      <v-col cols="12" md="6" class="text-right">
        <v-chip :color="fpyColor" size="large" class="mr-2">
          FPY: {{ formatValue(qualityData?.fpy) }}%
        </v-chip>
        <v-chip color="grey-lighten-2">Target: 99%</v-chip>
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

    <!-- Key Quality Metrics -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-card variant="outlined" :color="fpyColor">
          <v-card-text>
            <div class="text-caption">First Pass Yield (FPY)</div>
            <div class="text-h3 font-weight-bold">{{ formatValue(qualityData?.fpy) }}%</div>
            <div class="text-caption text-grey-darken-1">Target: 99%</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined" :color="rtyColor">
          <v-card-text>
            <div class="text-caption">Rolled Throughput Yield (RTY)</div>
            <div class="text-h3 font-weight-bold">{{ formatValue(qualityData?.rty) }}%</div>
            <div class="text-caption text-grey-darken-1">Target: 95%</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Total Units Inspected</div>
            <div class="text-h3 font-weight-bold">{{ qualityData?.total_units || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">First Pass Good</div>
            <div class="text-h3 font-weight-bold">{{ qualityData?.first_pass_good || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Quality Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>Quality Trends</v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
            <v-alert v-else type="info" variant="tonal">No trend data available</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Quality Records Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            Quality Inspection Records
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
              :headers="qualityHistoryHeaders"
              :items="qualityHistory"
              :search="tableSearch"
              :loading="loading"
              :items-per-page="10"
              class="elevation-0"
            >
              <template v-slot:item.shift_date="{ item }">
                {{ formatDate(item.shift_date) }}
              </template>
              <template v-slot:item.inspection_result="{ item }">
                <v-chip :color="item.inspection_result === 'PASS' ? 'success' : 'error'" size="small">
                  {{ item.inspection_result }}
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Defect Analysis -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Top Defect Types</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="defectHeaders"
              :items="qualityData?.defects_by_type || []"
              density="compact"
            >
              <template v-slot:item.count="{ item }">
                <v-chip color="error" size="small">{{ item.count }}</v-chip>
              </template>
              <template v-slot:item.percentage="{ item }">
                <v-progress-linear
                  :model-value="item.percentage"
                  color="error"
                  height="20"
                >
                  <strong>{{ item.percentage?.toFixed(1) || 0 }}%</strong>
                </v-progress-linear>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Quality by Product</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="productHeaders"
              :items="qualityData?.by_product || []"
              density="compact"
            >
              <template v-slot:item.fpy="{ item }">
                <v-chip :color="getFPYColor(item.fpy)" size="small">
                  {{ item.fpy?.toFixed(1) || 0 }}%
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
const qualityHistory = ref([])

const qualityData = computed(() => kpiStore.quality)

const fpyColor = computed(() => {
  const fpy = qualityData.value?.fpy || 0
  if (fpy >= 99) return 'success'
  if (fpy >= 95) return 'warning'
  return 'error'
})

const rtyColor = computed(() => {
  const rty = qualityData.value?.rty || 0
  if (rty >= 95) return 'success'
  if (rty >= 90) return 'warning'
  return 'error'
})

const defectHeaders = [
  { title: 'Defect Type', key: 'defect_type', sortable: true },
  { title: 'Count', key: 'count', sortable: true },
  { title: 'Percentage', key: 'percentage', sortable: true }
]

const productHeaders = [
  { title: 'Product', key: 'product_name', sortable: true },
  { title: 'Inspected', key: 'inspected', sortable: true },
  { title: 'Defects', key: 'defects', sortable: true },
  { title: 'FPY', key: 'fpy', sortable: true }
]

const qualityHistoryHeaders = [
  { title: 'Date', key: 'shift_date', sortable: true },
  { title: 'Work Order', key: 'work_order_id', sortable: true },
  { title: 'Units Inspected', key: 'units_inspected', sortable: true },
  { title: 'Defects Found', key: 'defects_found', sortable: true },
  { title: 'Result', key: 'inspection_result', sortable: true }
]

const chartData = computed(() => ({
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
      label: 'Target (99%)',
      data: Array(kpiStore.trends.quality.length).fill(99),
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
      beginAtZero: false,
      min: 90,
      max: 100,
      ticks: { callback: (value) => `${value}%` }
    }
  }
}

const formatValue = (value) => {
  return value !== null && value !== undefined ? Number(value).toFixed(2) : 'N/A'
}

const formatDate = (dateStr) => {
  try {
    return format(new Date(dateStr), 'MMM dd, yyyy')
  } catch {
    return dateStr
  }
}

const getFPYColor = (fpy) => {
  if (fpy >= 99) return 'success'
  if (fpy >= 95) return 'warning'
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

const loadQualityHistory = async () => {
  try {
    const params = {
      start_date: startDate.value,
      end_date: endDate.value
    }
    if (selectedClient.value) {
      params.client_id = selectedClient.value
    }
    const response = await api.getQualityEntries(params)
    qualityHistory.value = response.data || []
  } catch (error) {
    console.error('Failed to load quality history:', error)
    qualityHistory.value = []
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
      kpiStore.fetchQuality(),
      loadQualityHistory()
    ])
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
