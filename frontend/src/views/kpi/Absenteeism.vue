<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">Workforce Absenteeism</h1>
        <p class="text-subtitle-1 text-grey">Track employee attendance patterns and absence rates</p>
      </v-col>
      <v-col cols="12" md="6" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2">
          {{ formatValue(absenteeismData?.rate) }}%
        </v-chip>
        <v-chip color="grey-lighten-2">Target: &lt; 5%</v-chip>
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
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Total Employees</div>
            <div class="text-h4 font-weight-bold">{{ absenteeismData?.total_employees || 0 }}</div>
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
            <div class="text-caption text-grey-darken-1">Scheduled Hours</div>
            <div class="text-h4 font-weight-bold">{{ absenteeismData?.total_scheduled_hours || 0 }}h</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="3">
        <v-card variant="outlined">
          <v-card-text>
            <div class="text-caption text-grey-darken-1">Absent Hours</div>
            <div class="text-h4 font-weight-bold text-error">{{ absenteeismData?.total_hours_absent || 0 }}h</div>
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
            <v-alert v-else type="info" variant="tonal">No trend data available</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Attendance Records Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            Attendance Records
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
              :headers="attendanceHistoryHeaders"
              :items="attendanceHistory"
              :search="tableSearch"
              :loading="loading"
              :items-per-page="10"
              class="elevation-0"
            >
              <template v-slot:item.shift_date="{ item }">
                {{ formatDate(item.shift_date) }}
              </template>
              <template v-slot:item.status="{ item }">
                <v-chip :color="item.status === 'PRESENT' ? 'success' : 'error'" size="small">
                  {{ item.status }}
                </v-chip>
              </template>
            </v-data-table>
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
                  <strong>{{ item.percentage?.toFixed(1) || 0 }}%</strong>
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
                  {{ item.rate?.toFixed(1) || 0 }}%
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
const attendanceHistory = ref([])

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

const attendanceHistoryHeaders = [
  { title: 'Date', key: 'shift_date', sortable: true },
  { title: 'Employee ID', key: 'employee_id', sortable: true },
  { title: 'Hours Scheduled', key: 'hours_scheduled', sortable: true },
  { title: 'Hours Worked', key: 'hours_worked', sortable: true },
  { title: 'Status', key: 'status', sortable: true }
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

const formatDate = (dateStr) => {
  try {
    return format(new Date(dateStr), 'MMM dd, yyyy')
  } catch {
    return dateStr
  }
}

const getAbsenteeismColor = (rate) => {
  if (rate <= 5) return 'success'
  if (rate <= 10) return 'warning'
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

const loadAttendanceHistory = async () => {
  try {
    const params = {
      start_date: startDate.value,
      end_date: endDate.value
    }
    if (selectedClient.value) {
      params.client_id = selectedClient.value
    }
    const response = await api.getAttendanceEntries(params)
    attendanceHistory.value = response.data || []
  } catch (error) {
    console.error('Failed to load attendance history:', error)
    attendanceHistory.value = []
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
      kpiStore.fetchAbsenteeism(),
      loadAttendanceHistory()
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
