<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="8">
        <h1 class="text-h3">Equipment Availability</h1>
        <p class="text-subtitle-1 text-grey">Monitor equipment uptime and downtime patterns</p>
      </v-col>
      <v-col cols="12" md="4" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2">
          {{ formatValue(availabilityData?.percentage) }}%
        </v-chip>
        <v-chip color="grey-lighten-2">Target: 90%</v-chip>
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
                  <strong>{{ item.percentage.toFixed(1) }}%</strong>
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
                  {{ item.availability.toFixed(1) }}%
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

const getAvailabilityColor = (avail) => {
  if (avail >= 90) return 'success'
  if (avail >= 80) return 'warning'
  return 'error'
}

onMounted(async () => {
  loading.value = true
  try {
    await kpiStore.fetchAvailability()
  } finally {
    loading.value = false
  }
})
</script>
