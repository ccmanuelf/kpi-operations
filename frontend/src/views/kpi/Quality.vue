<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12">
        <h1 class="text-h3">Quality Metrics Dashboard</h1>
        <p class="text-subtitle-1 text-grey">Comprehensive quality analysis: PPM, DPMO, FPY, RTY</p>
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
        <v-card variant="outlined" :color="ppmColor">
          <v-card-text>
            <div class="text-caption">PPM (Parts Per Million)</div>
            <div class="text-h3 font-weight-bold">{{ qualityData?.ppm || 0 }}</div>
            <div class="text-caption text-grey-darken-1">Target: < 500</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined" :color="dpmoColor">
          <v-card-text>
            <div class="text-caption">DPMO (Defects Per Million)</div>
            <div class="text-h3 font-weight-bold">{{ qualityData?.dpmo || 0 }}</div>
            <div class="text-caption text-grey-darken-1">Target: < 1000</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Defect Summary -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Total Inspected</div>
            <div class="text-h4 font-weight-bold">{{ qualityData?.total_inspected || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Total Defects</div>
            <div class="text-h4 font-weight-bold text-error">{{ qualityData?.total_defects || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Rejected</div>
            <div class="text-h4 font-weight-bold text-warning">{{ qualityData?.rejected || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Reworked</div>
            <div class="text-h4 font-weight-bold">{{ qualityData?.reworked || 0 }}</div>
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
                  <strong>{{ item.percentage.toFixed(1) }}%</strong>
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
                  {{ item.fpy.toFixed(1) }}%
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

const ppmColor = computed(() => {
  const ppm = qualityData.value?.ppm || 0
  if (ppm <= 500) return 'success'
  if (ppm <= 1000) return 'warning'
  return 'error'
})

const dpmoColor = computed(() => {
  const dpmo = qualityData.value?.dpmo || 0
  if (dpmo <= 1000) return 'success'
  if (dpmo <= 3000) return 'warning'
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

const getFPYColor = (fpy) => {
  if (fpy >= 99) return 'success'
  if (fpy >= 95) return 'warning'
  return 'error'
}

onMounted(async () => {
  loading.value = true
  try {
    await kpiStore.fetchQuality()
  } finally {
    loading.value = false
  }
})
</script>
