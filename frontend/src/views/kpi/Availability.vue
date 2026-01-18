<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">Equipment Availability</h1>
        <p class="text-subtitle-1 text-grey">Monitor equipment uptime and downtime patterns</p>
      </v-col>
      <v-col cols="12" md="6" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2">
          {{ formatValue(availabilityData?.percentage) }}%
        </v-chip>
        <v-chip color="grey-lighten-2">Target: 90%</v-chip>
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
        <v-card variant="outlined" color="success">
          <v-card-text>
            <div class="text-caption">Uptime (hours)</div>
            <div class="text-h4 font-weight-bold">{{ availabilityData?.uptime || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined" color="error">
          <v-card-text>
            <div class="text-caption">Downtime (hours)</div>
            <div class="text-h4 font-weight-bold">{{ availabilityData?.downtime || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Total Time</div>
            <div class="text-h4 font-weight-bold">{{ availabilityData?.total_time || 0 }}h</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">MTBF</div>
            <div class="text-h4 font-weight-bold">{{ availabilityData?.mtbf || 0 }}h</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>Availability Trend</v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
            <v-alert v-else type="info" variant="tonal">No trend data available</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Downtime History Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            Downtime Records
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
              :headers="downtimeHistoryHeaders"
              :items="downtimeHistory"
              :search="tableSearch"
              :loading="loading"
              :items-per-page="10"
              class="elevation-0"
            >
              <template v-slot:item.shift_date="{ item }">
                {{ formatDate(item.shift_date) }}
              </template>
              <template v-slot:item.duration_minutes="{ item }">
                <v-chip color="error" size="small">
                  {{ item.duration_minutes }} min
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Downtime Analysis -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Top Downtime Reasons</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="downtimeHeaders"
              :items="availabilityData?.downtime_reasons || []"
              density="compact"
            >
              <template v-slot:item.hours="{ item }">
                <v-chip color="error" size="small">{{ item.hours }}h</v-chip>
              </template>
              <template v-slot:item.percentage="{ item }">
                <v-progress-linear :model-value="item.percentage" color="error" height="20">
                  <strong>{{ item.percentage?.toFixed(1) || 0 }}%</strong>
                </v-progress-linear>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Availability by Equipment</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="equipmentHeaders"
              :items="availabilityData?.by_equipment || []"
              density="compact"
            >
              <template v-slot:item.availability="{ item }">
                <v-chip :color="getAvailabilityColor(item.availability)" size="small">
                  {{ item.availability?.toFixed(1) || 0 }}%
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
const downtimeHistory = ref([])

const availabilityData = computed(() => kpiStore.availability)

const statusColor = computed(() => {
  const avail = availabilityData.value?.percentage || 0
  if (avail >= 90) return 'success'
  if (avail >= 80) return 'warning'
  return 'error'
})

const downtimeHeaders = [
  { title: 'Reason', key: 'reason', sortable: true },
  { title: 'Hours', key: 'hours', sortable: true },
  { title: 'Percentage', key: 'percentage', sortable: true }
]

const equipmentHeaders = [
  { title: 'Equipment', key: 'equipment_name', sortable: true },
  { title: 'Uptime', key: 'uptime', sortable: true },
  { title: 'Downtime', key: 'downtime', sortable: true },
  { title: 'Availability', key: 'availability', sortable: true }
]

const downtimeHistoryHeaders = [
  { title: 'Date', key: 'shift_date', sortable: true },
  { title: 'Reason', key: 'reason_type', sortable: true },
  { title: 'Duration', key: 'duration_minutes', sortable: true },
  { title: 'Description', key: 'description', sortable: true }
]

const chartData = computed(() => ({
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
      label: 'Target (90%)',
      data: Array(kpiStore.trends.availability.length).fill(90),
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

const getAvailabilityColor = (avail) => {
  if (avail >= 90) return 'success'
  if (avail >= 80) return 'warning'
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

const loadDowntimeHistory = async () => {
  try {
    const params = {
      start_date: startDate.value,
      end_date: endDate.value
    }
    if (selectedClient.value) {
      params.client_id = selectedClient.value
    }
    const response = await api.getDowntimeEntries(params)
    downtimeHistory.value = response.data || []
  } catch (error) {
    console.error('Failed to load downtime history:', error)
    downtimeHistory.value = []
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
      kpiStore.fetchAvailability(),
      loadDowntimeHistory()
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
