<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="8">
        <h1 class="text-h3">Operational Efficiency</h1>
        <p class="text-subtitle-1 text-grey">Monitor resource utilization and productivity metrics</p>
      </v-col>
      <v-col cols="12" md="4" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2">
          {{ formatValue(efficiencyData?.current) }}%
        </v-chip>
        <v-chip color="grey-lighten-2">Target: 85%</v-chip>
      </v-col>
    </v-row>

    <!-- Summary Cards -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Current Efficiency</div>
            <div class="text-h4 font-weight-bold">{{ formatValue(efficiencyData?.current) }}%</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Actual Output</div>
            <div class="text-h4 font-weight-bold">{{ efficiencyData?.actual_output || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Expected Output</div>
            <div class="text-h4 font-weight-bold">{{ efficiencyData?.expected_output || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Gap</div>
            <div class="text-h4 font-weight-bold" :class="gapColor">
              {{ efficiencyData?.gap || 0 }} units
            </div>
          </v-card-text>
        </v-card>
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
                  {{ item.efficiency.toFixed(1) }}%
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
                  {{ item.efficiency.toFixed(1) }}%
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
const efficiencyData = computed(() => kpiStore.efficiency)

const statusColor = computed(() => {
  const eff = efficiencyData.value?.current || 0
  if (eff >= 85) return 'success'
  if (eff >= 70) return 'warning'
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

const getEfficiencyColor = (eff) => {
  if (eff >= 85) return 'success'
  if (eff >= 70) return 'warning'
  return 'error'
}

onMounted(async () => {
  loading.value = true
  try {
    await kpiStore.fetchEfficiency()
  } finally {
    loading.value = false
  }
})
</script>
