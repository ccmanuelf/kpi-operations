<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="8">
        <h1 class="text-h3">On-Time Delivery Performance</h1>
        <p class="text-subtitle-1 text-grey">Monitor delivery performance against customer commitments</p>
      </v-col>
      <v-col cols="12" md="4" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2">
          {{ formatValue(otdData?.percentage) }}%
        </v-chip>
        <v-chip color="grey-lighten-2">Target: 95%</v-chip>
      </v-col>
    </v-row>

    <!-- Summary Cards -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Total Deliveries</div>
            <div class="text-h4 font-weight-bold">{{ otdData?.total_deliveries || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined" color="success">
          <v-card-text>
            <div class="text-caption">On Time</div>
            <div class="text-h4 font-weight-bold">{{ otdData?.on_time || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined" color="error">
          <v-card-text>
            <div class="text-caption">Late</div>
            <div class="text-h4 font-weight-bold">{{ otdData?.late || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Avg Delay</div>
            <div class="text-h4 font-weight-bold">{{ otdData?.avg_delay || 0 }}h</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>On-Time Delivery Trend</v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
            <v-alert v-else type="info" variant="tonal">No trend data available</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Performance by Client -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Performance by Client</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="clientHeaders"
              :items="otdData?.by_client || []"
              density="compact"
            >
              <template v-slot:item.otd_percentage="{ item }">
                <v-chip :color="getOTDColor(item.otd_percentage)" size="small">
                  {{ item.otd_percentage.toFixed(1) }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Late Deliveries -->
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Recent Late Deliveries</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="lateHeaders"
              :items="otdData?.late_deliveries || []"
              density="compact"
              :items-per-page="10"
            >
              <template v-slot:item.delay_hours="{ item }">
                <v-chip color="error" size="small">
                  {{ item.delay_hours }}h late
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
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

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const kpiStore = useKPIStore()
const loading = ref(false)
const otdData = computed(() => kpiStore.onTimeDelivery)

const statusColor = computed(() => {
  const percentage = otdData.value?.percentage || 0
  if (percentage >= 95) return 'success'
  if (percentage >= 85) return 'warning'
  return 'error'
})

const clientHeaders = [
  { title: 'Client', key: 'client_name', sortable: true },
  { title: 'Total', key: 'total_deliveries', sortable: true },
  { title: 'On Time', key: 'on_time', sortable: true },
  { title: 'OTD %', key: 'otd_percentage', sortable: true }
]

const lateHeaders = [
  { title: 'Date', key: 'delivery_date', sortable: true },
  { title: 'Work Order', key: 'work_order', sortable: true },
  { title: 'Client', key: 'client', sortable: true },
  { title: 'Delay', key: 'delay_hours', sortable: true }
]

const chartData = computed(() => ({
  labels: kpiStore.trends.onTimeDelivery.map(d => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label: 'On-Time Delivery %',
      data: kpiStore.trends.onTimeDelivery.map(d => d.value),
      borderColor: '#1976d2',
      backgroundColor: 'rgba(25, 118, 210, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'Target (95%)',
      data: Array(kpiStore.trends.onTimeDelivery.length).fill(95),
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

const getOTDColor = (percentage) => {
  if (percentage >= 95) return 'success'
  if (percentage >= 85) return 'warning'
  return 'error'
}

onMounted(async () => {
  loading.value = true
  try {
    await kpiStore.fetchOnTimeDelivery()
  } finally {
    loading.value = false
  }
})
</script>
