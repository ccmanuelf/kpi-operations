<template>
  <v-container fluid role="main" aria-labelledby="dashboard-page-title">
    <!-- Page Header -->
    <v-row class="mb-2">
      <v-col cols="12" md="6">
        <h1 id="dashboard-page-title" class="text-h3">{{ t('dashboard.title') }}</h1>
        <p class="text-subtitle-1 text-grey-darken-1">{{ t('dashboard.overview') }}</p>
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center justify-end flex-wrap ga-3">
        <v-btn
          color="purple"
          variant="outlined"
          size="small"
          @click="showEmailDialog = true"
          aria-label="Open email reports dialog"
          prepend-icon="mdi-email-outline"
        >
          {{ t('reports.title') }}
        </v-btn>
        <v-select
          v-model="selectedClient"
          :items="clients"
          item-title="client_name"
          item-value="client_id"
          :label="t('filters.client')"
          clearable
          density="compact"
          variant="outlined"
          prepend-inner-icon="mdi-domain"
          :loading="loadingClients"
          style="max-width: 250px"
          @update:model-value="onClientChange"
          aria-label="Filter dashboard by client"
        />
      </v-col>
    </v-row>

    <!-- KPI Summary Cards with Loading State -->
    <v-row role="region" aria-label="Key Performance Indicators Summary">
      <!-- Skeleton loaders while loading -->
      <template v-if="initialLoading">
        <v-col v-for="i in 4" :key="i" cols="12" sm="6" md="3">
          <CardSkeleton variant="stats" />
        </v-col>
      </template>

      <template v-else>
        <v-col cols="12" sm="6" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" class="cursor-help" role="article" aria-labelledby="kpi-units-label">
              <v-card-text>
                <div id="kpi-units-label" class="text-overline">{{ t('dashboard.todaySummary') }}</div>
                <div class="text-h4" aria-live="polite">{{ totalUnitsToday }}</div>
                <span class="sr-only">{{ t('common.units') }}</span>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ t('common.details') }}:</div>
            <div class="tooltip-meaning">{{ t('dashboard.todaySummary') }}</div>
          </div>
        </v-tooltip>
      </v-col>

      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" class="cursor-help" role="article" aria-labelledby="kpi-efficiency-label">
              <v-card-text>
                <div id="kpi-efficiency-label" class="text-overline">{{ t('kpi.efficiency') }}</div>
                <div class="text-h4" aria-live="polite">{{ averageEfficiency }}%</div>
                <span class="sr-only">{{ t('kpi.efficiencyDesc') }}</span>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ t('kpi.efficiency') }}:</div>
            <div class="tooltip-meaning">{{ t('kpi.efficiencyDesc') }}</div>
          </div>
        </v-tooltip>
      </v-col>

      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" class="cursor-help" role="article" aria-labelledby="kpi-performance-label">
              <v-card-text>
                <div id="kpi-performance-label" class="text-overline">{{ t('kpi.performance') }}</div>
                <div class="text-h4" aria-live="polite">{{ averagePerformance }}%</div>
                <span class="sr-only">{{ t('kpi.performanceDesc') }}</span>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ t('kpi.performance') }}:</div>
            <div class="tooltip-meaning">{{ t('kpi.performanceDesc') }}</div>
          </div>
        </v-tooltip>
      </v-col>

      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" class="cursor-help" role="article" aria-labelledby="kpi-entries-label">
              <v-card-text>
                <div id="kpi-entries-label" class="text-overline">{{ t('grids.totalEntries') }}</div>
                <div class="text-h4" aria-live="polite">{{ productionEntries.length }}</div>
                <span class="sr-only">{{ t('production.title') }}</span>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ t('common.details') }}:</div>
            <div class="tooltip-meaning">{{ t('grids.totalEntries') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      </template>
    </v-row>

    <!-- Production Entries Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center flex-wrap ga-3">
            <span class="text-h6">{{ t('production.title') }}</span>
            <v-spacer />
            <v-btn
              color="success"
              variant="outlined"
              size="small"
              class="mr-2"
              @click="exportToCSV"
              :disabled="productionEntries.length === 0"
              aria-label="Export production entries to CSV file"
            >
              <v-icon start aria-hidden="true">mdi-file-delimited</v-icon>
              {{ t('reports.exportCsv') }}
            </v-btn>
            <v-btn
              color="primary"
              variant="outlined"
              size="small"
              @click="exportToExcel"
              :disabled="productionEntries.length === 0"
              aria-label="Export production entries to Excel file"
            >
              <v-icon start aria-hidden="true">mdi-file-excel</v-icon>
              {{ t('reports.exportExcel') }}
            </v-btn>
          </v-card-title>
          <v-card-text>
            <!-- Loading Skeleton -->
            <TableSkeleton v-if="initialLoading" :rows="5" :columns="7" />

            <!-- Empty State -->
            <EmptyState
              v-else-if="!loading && productionEntries.length === 0"
              variant="no-data"
              :title="t('common.noData')"
              :description="selectedClient ? t('common.noData') : t('common.noData')"
              :action-text="selectedClient ? t('common.clear') : ''"
              @action="selectedClient = null; onClientChange()"
            />

            <!-- Data Table -->
            <v-data-table
              v-else
              :headers="headers"
              :items="productionEntries"
              :loading="loading"
              :items-per-page="10"
              :items-per-page-options="[10, 25, 50, 100]"
              class="elevation-1"
              aria-label="Production entries table"
              hover
            >
              <template v-slot:item.production_date="{ item }">
                {{ formatDate(item.production_date) }}
              </template>
              <template v-slot:item.reference="{ item }">
                <div class="d-flex flex-column">
                  <span v-if="item.work_order_id" class="font-weight-medium">
                    {{ item.work_order_id }}
                  </span>
                  <span v-else-if="item.job_id" class="font-weight-medium">
                    {{ item.job_id }}
                  </span>
                  <span v-else class="text-grey-darken-1">—</span>
                </div>
              </template>
              <template v-slot:item.product_id="{ item }">
                <span>{{ getProductName(item.product_id) }}</span>
              </template>
              <template v-slot:item.shift_id="{ item }">
                <span>{{ getShiftName(item.shift_id) }}</span>
              </template>
              <template v-slot:item.efficiency_percentage="{ item }">
                <v-chip
                  :color="getEfficiencyColor(item.efficiency_percentage)"
                  size="small"
                  :aria-label="`Efficiency: ${parseFloat(item.efficiency_percentage || 0).toFixed(2)} percent, status: ${getEfficiencyColor(item.efficiency_percentage)}`"
                >
                  {{ parseFloat(item.efficiency_percentage || 0).toFixed(2) }}%
                  <span class="sr-only">({{ getEfficiencyColor(item.efficiency_percentage) === 'success' ? 'good' : getEfficiencyColor(item.efficiency_percentage) === 'warning' ? 'needs attention' : 'critical' }})</span>
                </v-chip>
              </template>
              <template v-slot:item.performance_percentage="{ item }">
                <v-chip
                  :color="getPerformanceColor(item.performance_percentage)"
                  size="small"
                  :aria-label="`Performance: ${parseFloat(item.performance_percentage || 0).toFixed(2)} percent, status: ${getPerformanceColor(item.performance_percentage)}`"
                >
                  {{ parseFloat(item.performance_percentage || 0).toFixed(2) }}%
                  <span class="sr-only">({{ getPerformanceColor(item.performance_percentage) === 'success' ? 'good' : getPerformanceColor(item.performance_percentage) === 'warning' ? 'needs attention' : 'critical' }})</span>
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Email Reports Dialog -->
    <EmailReportsDialog
      v-model="showEmailDialog"
      :client-id="selectedClient"
      @saved="onEmailConfigSaved"
    />
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useKPIStore } from '@/stores/kpiStore'
import { format } from 'date-fns'
import api from '@/services/api'
import EmailReportsDialog from '@/components/dialogs/EmailReportsDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import TableSkeleton from '@/components/ui/TableSkeleton.vue'
import CardSkeleton from '@/components/ui/CardSkeleton.vue'

const { t } = useI18n()
const kpiStore = useKPIStore()

// Loading states
const initialLoading = ref(true)

// Client filter state
const clients = ref([])
const selectedClient = ref(null)
const loadingClients = ref(false)

// Email dialog state
const showEmailDialog = ref(false)

const onEmailConfigSaved = (config) => {
  console.log('Email config saved:', config)
  // Optionally show a snackbar notification
}

const loading = computed(() => kpiStore.loading)
const productionEntries = computed(() => kpiStore.productionEntries)

// Compute card values directly from productionEntries for proper reactivity
const totalUnitsToday = computed(() => {
  const today = format(new Date(), 'yyyy-MM-dd')
  return productionEntries.value
    .filter(e => {
      // Handle both "2026-01-30" and "2026-01-30T00:00:00" formats
      const entryDate = e.production_date?.split('T')[0]
      return entryDate === today
    })
    .reduce((sum, e) => sum + (e.units_produced || 0), 0)
})

const averageEfficiency = computed(() => {
  if (productionEntries.value.length === 0) return '0.00'
  const validEntries = productionEntries.value.filter(e => e.efficiency_percentage != null)
  if (validEntries.length === 0) return '0.00'
  const sum = validEntries.reduce((acc, e) => acc + parseFloat(e.efficiency_percentage || 0), 0)
  return (sum / validEntries.length).toFixed(2)
})

const averagePerformance = computed(() => {
  if (productionEntries.value.length === 0) return '0.00'
  const validEntries = productionEntries.value.filter(e => e.performance_percentage != null)
  if (validEntries.length === 0) return '0.00'
  const sum = validEntries.reduce((acc, e) => acc + parseFloat(e.performance_percentage || 0), 0)
  return (sum / validEntries.length).toFixed(2)
})

const headers = computed(() => [
  { title: t('common.date'), key: 'production_date', sortable: true },
  { title: t('production.workOrder'), key: 'reference', sortable: false },
  { title: t('filters.product'), key: 'product_id', sortable: true },
  { title: t('production.shift'), key: 'shift_id', sortable: true },
  { title: t('common.units'), key: 'units_produced', sortable: true },
  { title: t('kpi.efficiency'), key: 'efficiency_percentage', sortable: true },
  { title: t('kpi.performance'), key: 'performance_percentage', sortable: true }
])

// Reference data for lookups
const products = ref([])
const shifts = ref([])

// Load reference data
const loadReferenceData = async () => {
  try {
    const [productsRes, shiftsRes] = await Promise.all([
      api.getProducts(),
      api.getShifts()
    ])
    products.value = productsRes.data || []
    shifts.value = shiftsRes.data || []
  } catch (error) {
    console.error('Failed to load reference data:', error)
  }
}

// Lookup functions
const getProductName = (productId) => {
  if (!productId) return '—'
  const product = products.value.find(p => p.product_id === productId)
  return product ? product.product_name : `Product #${productId}`
}

const getShiftName = (shiftId) => {
  if (!shiftId) return '—'
  const shift = shifts.value.find(s => s.shift_id === shiftId)
  return shift ? shift.shift_name : `Shift #${shiftId}`
}

const formatDate = (date) => {
  return format(new Date(date), 'MMM dd, yyyy')
}

const getEfficiencyColor = (value) => {
  const val = parseFloat(value || 0)
  if (val >= 85) return 'success'
  if (val >= 70) return 'warning'
  return 'error'
}

const getPerformanceColor = (value) => {
  const val = parseFloat(value || 0)
  if (val >= 90) return 'success'
  if (val >= 75) return 'warning'
  return 'error'
}

// Load clients from API
const loadClients = async () => {
  loadingClients.value = true
  try {
    const response = await api.getClients()
    clients.value = response.data || []
  } catch (error) {
    console.error('Failed to load clients:', error)
  } finally {
    loadingClients.value = false
  }
}

// Handle client filter change
const onClientChange = async () => {
  const params = selectedClient.value ? { client_id: selectedClient.value } : {}
  await Promise.all([
    kpiStore.fetchProductionEntries(params),
    kpiStore.fetchKPIDashboard(30, params)
  ])
}

// Refresh data with current filters
const refreshData = async () => {
  const params = selectedClient.value ? { client_id: selectedClient.value } : {}
  await Promise.all([
    kpiStore.fetchProductionEntries(params),
    kpiStore.fetchKPIDashboard(30, params)
  ])
}

// Export to CSV
const exportToCSV = () => {
  const csvHeaders = ['Date', 'Work Order', 'Job ID', 'Product', 'Shift', 'Units', 'Efficiency %', 'Performance %']
  const csvRows = productionEntries.value.map(entry => [
    entry.production_date,
    entry.work_order_id || '',
    entry.job_id || '',
    getProductName(entry.product_id),
    getShiftName(entry.shift_id),
    entry.units_produced || 0,
    parseFloat(entry.efficiency_percentage || 0).toFixed(2),
    parseFloat(entry.performance_percentage || 0).toFixed(2)
  ])

  const csvContent = [
    csvHeaders.join(','),
    ...csvRows.map(row => row.map(cell => `"${cell}"`).join(','))
  ].join('\n')

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.setAttribute('href', url)
  link.setAttribute('download', `production_entries_${format(new Date(), 'yyyy-MM-dd')}.csv`)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// Export to Excel (using XLSX format via CSV with Excel-compatible encoding)
const exportToExcel = async () => {
  try {
    const params = selectedClient.value ? { client_id: selectedClient.value } : {}
    const response = await api.exportExcel(params)
    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', `production_entries_${format(new Date(), 'yyyy-MM-dd')}.xlsx`)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  } catch (error) {
    console.error('Failed to export Excel:', error)
    // Fallback to CSV if Excel export fails
    exportToCSV()
  }
}

onMounted(async () => {
  try {
    await Promise.all([
      loadClients(),
      loadReferenceData()
    ])
    await refreshData()
  } finally {
    initialLoading.value = false
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
