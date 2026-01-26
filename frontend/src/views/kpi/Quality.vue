<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">{{ $t('kpi.quality') }}</h1>
        <p class="text-subtitle-1 text-grey-darken-1">{{ $t('kpi.qualityDescription') }}</p>
      </v-col>
      <v-col cols="12" md="6" class="text-right">
        <v-chip :color="fpyColor" size="large" class="mr-2 text-white" variant="flat">
          FPY: {{ formatValue(qualityData?.fpy) }}%
        </v-chip>
        <v-chip color="grey-darken-2">Target: 99%</v-chip>
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
          :label="$t('filters.client')"
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
          :label="$t('filters.startDate')"
          density="compact"
          variant="outlined"
          @change="onDateChange"
        />
      </v-col>
      <v-col cols="12" md="3">
        <v-text-field
          v-model="endDate"
          type="date"
          :label="$t('filters.endDate')"
          density="compact"
          variant="outlined"
          @change="onDateChange"
        />
      </v-col>
      <v-col cols="12" md="2">
        <v-btn color="primary" block @click="refreshData" :loading="loading">
          <v-icon left>mdi-refresh</v-icon> {{ $t('common.refresh') }}
        </v-btn>
      </v-col>
    </v-row>

    <!-- Key Quality Metrics - Yield Percentages -->
    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" :color="fpyColor" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption">{{ $t('kpi.fpy') }}</div>
                <div class="text-h3 font-weight-bold">{{ formatValue(qualityData?.fpy) }}%</div>
                <div class="text-caption text-grey-darken-1">Target: 99% | First attempt pass rate</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">Formula:</div>
            <div class="tooltip-formula">FPY = (Units Passed First Time / Total Units Inspected) × 100</div>
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">Percentage of units that pass quality inspection on the first attempt without any rework or repair needed.</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" :color="rtyColor" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption">{{ $t('kpi.rty') }}</div>
                <div class="text-h3 font-weight-bold">{{ formatValue(qualityData?.rty) }}%</div>
                <div class="text-caption text-grey-darken-1">Target: 95% | All stages combined</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">Formula:</div>
            <div class="tooltip-formula">RTY = FPY₁ × FPY₂ × FPY₃ × ... × FPYₙ</div>
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">Probability that a unit passes through ALL inspection stages (Incoming, In-Process, Final) without requiring any rework at any stage.</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" :color="finalYieldColor" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption">{{ $t('kpi.finalYield') }}</div>
                <div class="text-h3 font-weight-bold">{{ formatValue(qualityData?.final_yield) }}%</div>
                <div class="text-caption text-grey-darken-1">Target: 99% | After rework</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">Formula:</div>
            <div class="tooltip-formula">Final Yield = (Total Inspected - Scrapped) / Total Inspected × 100</div>
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">Percentage of units that ultimately passed quality (either first time or after successful rework). Only scrapped units are excluded.</div>
          </div>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- Key Quality Metrics - Counts -->
    <v-row class="mt-2">
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">{{ $t('kpi.totalUnitsInspected') }}</div>
                <div class="text-h4 font-weight-bold">{{ qualityData?.total_units || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">Total number of units that went through quality inspection during the selected period.</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">{{ $t('kpi.firstPassGood') }}</div>
                <div class="text-h4 font-weight-bold text-success">{{ qualityData?.first_pass_good || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">Number of units that passed quality inspection on the first attempt without requiring any rework.</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card variant="outlined" v-bind="props" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">{{ $t('kpi.totalScrapped') }}</div>
                <div class="text-h4 font-weight-bold text-error">{{ qualityData?.total_scrapped || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">Meaning:</div>
            <div class="tooltip-meaning">Number of units that could not be salvaged and were discarded. These units failed quality and could not be reworked successfully.</div>
          </div>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- Quality Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>{{ $t('kpi.qualityTrends') }}</v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
            <v-alert v-else type="info" variant="tonal">{{ $t('kpi.noTrendData') }}</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Quality Records Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            {{ $t('quality.inspectionRecords') }}
            <v-spacer />
            <v-text-field
              v-model="tableSearch"
              append-icon="mdi-magnify"
              :label="$t('common.search')"
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
              <template v-slot:item.inspection_stage="{ item }">
                <v-chip
                  :color="item.inspection_stage === 'Final' ? 'success' : item.inspection_stage === 'In-Process' ? 'info' : 'warning'"
                  size="small"
                  variant="tonal"
                >
                  {{ item.inspection_stage || 'N/A' }}
                </v-chip>
              </template>
              <template v-slot:item.fpy_percentage="{ item }">
                <v-chip :color="getFPYColor(calculateFPY(item))" size="small">
                  {{ formatFPY(item) }}%
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
          <v-card-title>{{ $t('quality.topDefectTypes') }}</v-card-title>
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
          <v-card-title>{{ $t('quality.byProduct') }}</v-card-title>
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
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()
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
  if (fpy >= 95) return 'amber-darken-3'
  return 'error'
})

const rtyColor = computed(() => {
  const rty = qualityData.value?.rty || 0
  if (rty >= 95) return 'success'
  if (rty >= 90) return 'amber-darken-3'
  return 'error'
})

const finalYieldColor = computed(() => {
  const fy = qualityData.value?.final_yield || 0
  if (fy >= 99) return 'success'
  if (fy >= 95) return 'amber-darken-3'
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
  { title: 'Stage', key: 'inspection_stage', sortable: true },
  { title: 'Inspected', key: 'units_inspected', sortable: true },
  { title: 'Passed', key: 'units_passed', sortable: true },
  { title: 'Defective', key: 'units_defective', sortable: true },
  { title: 'FPY %', key: 'fpy_percentage', sortable: true }
]

const chartData = computed(() => ({
  labels: kpiStore.trends.quality.map(d => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label: t('kpi.charts.qualityFPYPercent'),
      data: kpiStore.trends.quality.map(d => d.value),
      borderColor: '#1976d2',
      backgroundColor: 'rgba(25, 118, 210, 0.1)',
      tension: 0.3,
      fill: true
    },
    {
      label: t('kpi.charts.targetValue', { value: 99 }),
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
  if (fpy >= 95) return 'amber-darken-3'
  return 'error'
}

const calculateFPY = (item) => {
  // Calculate FPY from units_passed / units_inspected
  if (item.fpy_percentage) return Number(item.fpy_percentage)
  const inspected = item.units_inspected || 0
  const passed = item.units_passed || 0
  if (inspected === 0) return 0
  return (passed / inspected) * 100
}

const formatFPY = (item) => {
  const fpy = calculateFPY(item)
  return fpy.toFixed(1)
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

<style scoped>
.cursor-help {
  cursor: help;
}
</style>

<style>
/* Tooltip styling - unscoped to affect Vuetify tooltip portal */
.v-tooltip > .v-overlay__content {
  background-color: rgba(33, 33, 33, 0.95) !important;
  color: #ffffff !important;
  padding: 12px 16px !important;
  font-size: 14px !important;
  line-height: 1.5 !important;
}

.v-tooltip .tooltip-title {
  font-weight: 600;
  margin-bottom: 4px;
  color: #90caf9;
}

.v-tooltip .tooltip-formula {
  font-family: 'Courier New', monospace;
  background-color: rgba(255, 255, 255, 0.1);
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 8px;
  color: #ffffff;
}

.v-tooltip .tooltip-meaning {
  color: rgba(255, 255, 255, 0.9);
}
</style>
