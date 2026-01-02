<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="8">
        <h1 class="text-h3">Workforce Absenteeism</h1>
        <p class="text-subtitle-1 text-grey">Track employee attendance patterns and absence rates</p>
      </v-col>
      <v-col cols="12" md="4" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2">
          {{ formatValue(absenteeismData?.rate) }}%
        </v-chip>
        <v-chip color="grey-lighten-2">Target: < 5%</v-chip>
      </v-col>
    </v-row>

    <!-- Summary Cards -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Total Workforce</div>
            <div class="text-h4 font-weight-bold">{{ absenteeismData?.total_workforce || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined" color="error">
          <v-card-text>
            <div class="text-caption">Total Absences</div>
            <div class="text-h4 font-weight-bold">{{ absenteeismData?.total_absences || 0 }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Expected Hours</div>
            <div class="text-h4 font-weight-bold">{{ absenteeismData?.expected_hours || 0 }}h</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Absence Hours</div>
            <div class="text-h4 font-weight-bold text-error">{{ absenteeismData?.absence_hours || 0 }}h</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>Absenteeism Trend</v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Absenteeism Analysis -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>Absence Reasons</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="reasonHeaders"
              :items="absenteeismData?.by_reason || []"
              density="compact"
            >
              <template v-slot:item.count="{ item }">
                <v-chip color="error" size="small">{{ item.count }}</v-chip>
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
          <v-card-title>Absenteeism by Department</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="deptHeaders"
              :items="absenteeismData?.by_department || []"
              density="compact"
            >
              <template v-slot:item.rate="{ item }">
                <v-chip :color="getAbsenteeismColor(item.rate)" size="small">
                  {{ item.rate.toFixed(1) }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- High Absence Alerts -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>High Absence Alerts</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="alertHeaders"
              :items="absenteeismData?.high_absence_employees || []"
              density="compact"
            >
              <template v-slot:item.absence_count="{ item }">
                <v-chip color="warning" size="small">{{ item.absence_count }} days</v-chip>
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
const absenteeismData = computed(() => kpiStore.absenteeism)

const statusColor = computed(() => {
  const rate = absenteeismData.value?.rate || 0
  if (rate <= 5) return 'success'
  if (rate <= 10) return 'warning'
  return 'error'
})

const reasonHeaders = [
  { title: 'Reason', key: 'reason', sortable: true },
  { title: 'Count', key: 'count', sortable: true },
  { title: 'Percentage', key: 'percentage', sortable: true }
]

const deptHeaders = [
  { title: 'Department', key: 'department', sortable: true },
  { title: 'Workforce', key: 'workforce', sortable: true },
  { title: 'Absences', key: 'absences', sortable: true },
  { title: 'Rate', key: 'rate', sortable: true }
]

const alertHeaders = [
  { title: 'Employee ID', key: 'employee_id', sortable: true },
  { title: 'Department', key: 'department', sortable: true },
  { title: 'Absence Days', key: 'absence_count', sortable: true },
  { title: 'Last Absence', key: 'last_absence', sortable: true }
]

const chartData = computed(() => ({
  labels: kpiStore.trends.absenteeism.map(d => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label: 'Absenteeism Rate %',
      data: kpiStore.trends.absenteeism.map(d => d.value),
      borderColor: '#d32f2f',
      backgroundColor: 'rgba(211, 47, 47, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: 'Target (5%)',
      data: Array(kpiStore.trends.absenteeism.length).fill(5),
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
      max: 20,
      ticks: { callback: (value) => `${value}%` }
    }
  }
}

const formatValue = (value) => {
  return value !== null && value !== undefined ? Number(value).toFixed(1) : 'N/A'
}

const getAbsenteeismColor = (rate) => {
  if (rate <= 5) return 'success'
  if (rate <= 10) return 'warning'
  return 'error'
}

onMounted(async () => {
  loading.value = true
  try {
    await kpiStore.fetchAbsenteeism()
  } finally {
    loading.value = false
  }
})
</script>
