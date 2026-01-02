<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="8">
        <h1 class="text-h3">WIP Aging Analysis</h1>
        <p class="text-subtitle-1 text-grey">Track work-in-process aging and identify bottlenecks</p>
      </v-col>
      <v-col cols="12" md="4" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2">
          {{ formatValue(wipData?.average_days) }} days avg
        </v-chip>
        <v-chip color="grey-lighten-2">Target: 7 days</v-chip>
      </v-col>
    </v-row>

    <!-- Summary Cards -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Total WIP Units</div>
            <div class="text-h4 font-weight-bold">{{ wipData?.total_units || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Average Age</div>
            <div class="text-h4 font-weight-bold">{{ formatValue(wipData?.average_days) }} days</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Oldest Item</div>
            <div class="text-h4 font-weight-bold">{{ wipData?.max_days || 0 }} days</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Critical Items (>14d)</div>
            <div class="text-h4 font-weight-bold text-error">{{ wipData?.critical_count || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>WIP Aging Trend</v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
            <v-alert v-else type="info" variant="tonal">No trend data available</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Age Distribution -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Age Distribution</v-card-title>
          <v-card-text>
            <v-list>
              <v-list-item>
                <template v-slot:prepend>
                  <v-icon color="success">mdi-check-circle</v-icon>
                </template>
                <v-list-item-title>0-7 days (On Track)</v-list-item-title>
                <v-list-item-subtitle>{{ wipData?.age_0_7 || 0 }} units</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template v-slot:prepend>
                  <v-icon color="warning">mdi-alert-circle</v-icon>
                </template>
                <v-list-item-title>8-14 days (At Risk)</v-list-item-title>
                <v-list-item-subtitle>{{ wipData?.age_8_14 || 0 }} units</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template v-slot:prepend>
                  <v-icon color="error">mdi-close-circle</v-icon>
                </template>
                <v-list-item-title>15+ days (Critical)</v-list-item-title>
                <v-list-item-subtitle>{{ wipData?.age_15_plus || 0 }} units</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Top Aging Items -->
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Top 10 Aging Items</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="agingHeaders"
              :items="wipData?.top_aging || []"
              density="compact"
              :items-per-page="10"
            >
              <template v-slot:item.age="{ item }">
                <v-chip :color="getAgeColor(item.age)" size="small">
                  {{ item.age }} days
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

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const kpiStore = useKPIStore()
const loading = ref(false)
const wipData = computed(() => kpiStore.wipAging)

const statusColor = computed(() => {
  const avg = wipData.value?.average_days || 0
  if (avg <= 7) return 'success'
  if (avg <= 14) return 'warning'
  return 'error'
})

const agingHeaders = [
  { title: 'Work Order', key: 'work_order', sortable: true },
  { title: 'Product', key: 'product', sortable: true },
  { title: 'Age', key: 'age', sortable: true },
  { title: 'Quantity', key: 'quantity', sortable: true }
]

const chartData = computed(() => ({
  labels: kpiStore.trends.wipAging.map(d => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label: 'Average WIP Age (days)',
      data: kpiStore.trends.wipAging.map(d => d.value),
      borderColor: '#f57c00',
      backgroundColor: 'rgba(245, 124, 0, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'Target (7 days)',
      data: Array(kpiStore.trends.wipAging.length).fill(7),
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
      ticks: { callback: (value) => `${value}d` }
    }
  }
}

const formatValue = (value) => {
  return value !== null && value !== undefined ? Number(value).toFixed(1) : 'N/A'
}

const getAgeColor = (age) => {
  if (age <= 7) return 'success'
  if (age <= 14) return 'warning'
  return 'error'
}

onMounted(async () => {
  loading.value = true
  try {
    await kpiStore.fetchWIPAging()
  } finally {
    loading.value = false
  }
})
</script>
