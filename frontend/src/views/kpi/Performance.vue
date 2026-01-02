<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="8">
        <h1 class="text-h3">Production Performance</h1>
        <p class="text-subtitle-1 text-grey">Monitor production speed and throughput efficiency</p>
      </v-col>
      <v-col cols="12" md="4" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2">
          {{ formatValue(performanceData?.percentage) }}%
        </v-chip>
        <v-chip color="grey-lighten-2">Target: 95%</v-chip>
      </v-col>
    </v-row>

    <!-- Summary Cards -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Actual Rate</div>
            <div class="text-h4 font-weight-bold">{{ performanceData?.actual_rate || 0 }} u/h</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Standard Rate</div>
            <div class="text-h4 font-weight-bold">{{ performanceData?.standard_rate || 0 }} u/h</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Total Units</div>
            <div class="text-h4 font-weight-bold">{{ performanceData?.total_units || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Production Hours</div>
            <div class="text-h4 font-weight-bold">{{ performanceData?.production_hours || 0 }}h</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>Performance Trend</v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Performance Analysis -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Performance by Shift</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="shiftHeaders"
              :items="performanceData?.by_shift || []"
              density="compact"
            >
              <template v-slot:item.performance="{ item }">
                <v-chip :color="getPerformanceColor(item.performance)" size="small">
                  {{ item.performance.toFixed(1) }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Performance by Product</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="productHeaders"
              :items="performanceData?.by_product || []"
              density="compact"
            >
              <template v-slot:item.performance="{ item }">
                <v-chip :color="getPerformanceColor(item.performance)" size="small">
                  {{ item.performance.toFixed(1) }}%
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
const performanceData = computed(() => kpiStore.performance)

const statusColor = computed(() => {
  const perf = performanceData.value?.percentage || 0
  if (perf >= 95) return 'success'
  if (perf >= 85) return 'warning'
  return 'error'
})

const shiftHeaders = [
  { title: 'Shift', key: 'shift_name', sortable: true },
  { title: 'Units', key: 'units', sortable: true },
  { title: 'Rate', key: 'rate', sortable: true },
  { title: 'Performance', key: 'performance', sortable: true }
]

const productHeaders = [
  { title: 'Product', key: 'product_name', sortable: true },
  { title: 'Units', key: 'units', sortable: true },
  { title: 'Rate', key: 'rate', sortable: true },
  { title: 'Performance', key: 'performance', sortable: true }
]

const chartData = computed(() => ({
  labels: kpiStore.trends.performance.map(d => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label: 'Performance %',
      data: kpiStore.trends.performance.map(d => d.value),
      borderColor: '#0d47a1',
      backgroundColor: 'rgba(13, 71, 161, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'Target (95%)',
      data: Array(kpiStore.trends.performance.length).fill(95),
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

const getPerformanceColor = (perf) => {
  if (perf >= 95) return 'success'
  if (perf >= 85) return 'warning'
  return 'error'
}

onMounted(async () => {
  loading.value = true
  try {
    await kpiStore.fetchPerformance()
  } finally {
    loading.value = false
  }
})
</script>
