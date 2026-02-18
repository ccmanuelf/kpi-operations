<template>
  <v-container fluid class="pa-4" role="main" aria-labelledby="kpi-dashboard-title">
    <!-- Header -->
    <v-row class="mb-2">
      <v-col cols="12" md="6">
        <h1 id="kpi-dashboard-title" class="text-h3">{{ t('navigation.kpiDashboard') }}</h1>
        <p class="text-subtitle-1 text-grey">{{ t('kpi.title') }}</p>
      </v-col>
      <v-col cols="12" md="6" class="d-flex align-center justify-end ga-2">
        <v-tooltip location="bottom">
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" color="secondary" variant="tonal" prepend-icon="mdi-qrcode-scan"
              @click="showQRScanner = true" :aria-label="t('kpi.ariaOpenQrScanner')">
              {{ t('common.search') }}
            </v-btn>
          </template>
          <span>{{ t('filters.scanQrForQuickEntry') }}</span>
        </v-tooltip>
        <v-menu v-if="filtersStore.savedFilters.length > 0" offset-y>
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" variant="tonal" prepend-icon="mdi-filter-check"
              :color="filtersStore.hasActiveFilter ? 'primary' : undefined">
              {{ filtersStore.hasActiveFilter ? filtersStore.activeFilter.filter_name : t('filters.savedFilters') }}
              <v-icon end>mdi-chevron-down</v-icon>
            </v-btn>
          </template>
          <v-list density="compact" max-width="300">
            <v-list-subheader>
              <v-icon start size="small">mdi-bookmark-multiple</v-icon>
              {{ t('filters.quickApplyFilter') }}
            </v-list-subheader>
            <v-list-item v-for="filter in filtersStore.savedFilters.slice(0, 5)" :key="filter.filter_id"
              :active="filtersStore.activeFilter?.filter_id === filter.filter_id"
              @click="applyQuickSavedFilter(filter)">
              <template v-slot:prepend>
                <v-icon :color="filter.is_default ? 'primary' : undefined">
                  {{ filter.is_default ? 'mdi-star' : 'mdi-filter-outline' }}
                </v-icon>
              </template>
              <v-list-item-title>{{ filter.filter_name }}</v-list-item-title>
              <v-list-item-subtitle>{{ filter.filter_type }}</v-list-item-subtitle>
            </v-list-item>
            <v-divider v-if="filtersStore.savedFilters.length > 5" />
            <v-list-item @click="showFilterManager = true">
              <template v-slot:prepend><v-icon>mdi-cog-outline</v-icon></template>
              <v-list-item-title>{{ t('filters.manageAllFilters') }}</v-list-item-title>
            </v-list-item>
            <v-list-item v-if="filtersStore.hasActiveFilter" @click="filtersStore.clearActiveFilter()">
              <template v-slot:prepend><v-icon color="error">mdi-filter-off</v-icon></template>
              <v-list-item-title class="text-error">{{ t('filters.clearActiveFilter') }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
        <v-tooltip location="bottom">
          <template v-slot:activator="{ props }">
            <v-btn v-bind="props" icon variant="text" @click="showSaveFilterDialog = true">
              <v-icon>mdi-content-save-outline</v-icon>
            </v-btn>
          </template>
          <span>{{ t('filters.saveFilterConfig') }}</span>
        </v-tooltip>
        <v-btn variant="outlined" prepend-icon="mdi-view-dashboard-edit" @click="showCustomizer = true">
          {{ t('common.edit') }}
        </v-btn>
        <v-menu>
          <template v-slot:activator="{ props }">
            <v-btn color="primary" variant="flat" v-bind="props" prepend-icon="mdi-file-download">
              {{ t('reports.title') }}
            </v-btn>
          </template>
          <v-list>
            <v-list-item @click="downloadPDF" :loading="downloadingPDF">
              <template v-slot:prepend><v-icon>mdi-file-pdf-box</v-icon></template>
              <v-list-item-title>{{ t('reports.exportPdf') }}</v-list-item-title>
            </v-list-item>
            <v-list-item @click="downloadExcel" :loading="downloadingExcel">
              <template v-slot:prepend><v-icon>mdi-file-excel</v-icon></template>
              <v-list-item-title>{{ t('reports.exportExcel') }}</v-list-item-title>
            </v-list-item>
            <v-list-item @click="emailDialog = true">
              <template v-slot:prepend><v-icon>mdi-email</v-icon></template>
              <v-list-item-title>{{ t('reports.title') }}</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
        <v-btn icon="mdi-refresh" variant="text" @click="refreshData" :loading="loading"
          :aria-label="t('kpi.ariaRefreshDashboard')" :aria-busy="loading" />
      </v-col>
    </v-row>

    <!-- Filter Bar -->
    <v-row class="mb-4">
      <v-col cols="12">
        <FilterBar filter-type="dashboard" :clients="clients" @filter-change="handleFilterChange" />
      </v-col>
    </v-row>

    <!-- KPI Cards Grid -->
    <v-row>
      <v-col v-for="kpi in kpiStore.allKPIs" :key="kpi.key" cols="12" sm="6" md="4" lg="3">
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props: tooltipProps }">
            <v-card v-bind="tooltipProps" :color="getCardColor(kpi)" variant="outlined" class="kpi-card"
              :class="{ 'estimated-card': kpi.inference?.is_estimated }"
              @click="navigateToDetail(kpi.route)" hover>
              <v-card-text>
                <div class="d-flex justify-space-between align-start mb-3">
                  <div>
                    <div class="d-flex align-center">
                      <span class="text-caption text-grey-darken-1">{{ kpi.title }}</span>
                      <InferenceIndicator v-if="kpi.inference" :is-estimated="kpi.inference.is_estimated"
                        :confidence-score="kpi.inference.confidence_score" :inference-details="kpi.inference.details" />
                    </div>
                    <div class="text-h4 font-weight-bold mt-1" :class="{ 'text-estimated': kpi.inference?.is_estimated }">
                      {{ formatValue(kpi.value, kpi.unit) }}
                    </div>
                    <div v-if="kpi.subtitle" class="text-caption text-grey-darken-2 mt-1">{{ kpi.subtitle }}</div>
                  </div>
                  <v-icon :color="getStatusColor(kpi)" size="40">
                    {{ kpiStore.kpiIcon(kpi.value, kpi.target, kpi.higherBetter) }}
                  </v-icon>
                </div>
                <v-progress-linear :model-value="getProgress(kpi)" :color="getStatusColor(kpi)"
                  height="8" rounded class="mb-2" />
                <div class="d-flex justify-space-between text-caption">
                  <span class="text-grey-darken-1">{{ t('kpi.target') }}: {{ kpi.target }}{{ kpi.unit }}</span>
                  <span :class="`text-${getStatusColor(kpi)}`">{{ getStatusText(kpi) }}</span>
                </div>
                <div v-if="kpi.inference?.is_estimated" class="confidence-bar mt-2">
                  <v-tooltip location="bottom">
                    <template v-slot:activator="{ props }">
                      <v-progress-linear v-bind="props" :model-value="kpi.inference.confidence_score * 100"
                        :color="getConfidenceColor(kpi.inference.confidence_score)"
                        height="3" rounded bg-opacity="0.2" />
                    </template>
                    <span>{{ $t('kpi.confidence') }}: {{ Math.round(kpi.inference.confidence_score * 100) }}%</span>
                  </v-tooltip>
                </div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ getKpiTooltip(kpi.key).title }}</div>
            <div v-if="getKpiTooltip(kpi.key).formula" class="tooltip-formula">{{ getKpiTooltip(kpi.key).formula }}</div>
            <div class="tooltip-title">{{ t('common.details') }}:</div>
            <div class="tooltip-meaning">{{ getKpiTooltip(kpi.key).meaning }}</div>
            <div v-if="kpi.inference?.is_estimated" class="tooltip-inference mt-2">
              <v-divider class="my-2" />
              <div class="tooltip-title">{{ t('quality.title') }}:</div>
              <div class="tooltip-meaning">
                {{ $t('kpi.estimated') }} - {{ Math.round(kpi.inference.confidence_score * 100) }}% {{ $t('kpi.confidence') }}
              </div>
            </div>
          </div>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- Trend Charts -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card role="region" aria-labelledby="trends-title">
          <v-card-title class="d-flex justify-space-between align-center">
            <span id="trends-title">{{ t('kpi.performanceTrend') }}</span>
            <v-btn-toggle v-model="trendPeriod" mandatory density="compact"
              @update:model-value="refreshData" :aria-label="t('kpi.ariaSelectTrendPeriod')">
              <v-btn value="7" size="small">7 {{ t('common.days') }}</v-btn>
              <v-btn value="30" size="small">30 {{ t('common.days') }}</v-btn>
              <v-btn value="90" size="small">90 {{ t('common.days') }}</v-btn>
            </v-btn-toggle>
          </v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="12" md="6">
                <Line v-if="efficiencyChartData.labels.length" :data="efficiencyChartData" :options="chartOptions" />
              </v-col>
              <v-col cols="12" md="6">
                <Line v-if="qualityChartData.labels.length" :data="qualityChartData" :options="chartOptions" />
              </v-col>
              <v-col cols="12" md="6">
                <Line v-if="availabilityChartData.labels.length" :data="availabilityChartData" :options="chartOptions" />
              </v-col>
              <v-col cols="12" md="6">
                <Line v-if="oeeChartData.labels.length" :data="oeeChartData" :options="chartOptions" />
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Summary Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>{{ t('reports.summary') }}</v-card-title>
          <v-card-text>
            <v-data-table :headers="summaryHeaders" :items="summaryItems" :loading="loading"
              density="comfortable" class="elevation-0">
              <template v-slot:item.status="{ item }">
                <v-chip :color="item.status" size="small" variant="flat">{{ item.statusText }}</v-chip>
              </template>
              <template v-slot:item.trend="{ item }">
                <v-icon :color="item.trendColor" size="small">{{ item.trendIcon }}</v-icon>
              </template>
              <template v-slot:item.actions="{ item }">
                <v-btn icon="mdi-chevron-right" size="small" variant="text" @click="navigateToDetail(item.route)" />
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Loading overlay -->
    <v-overlay v-model="loading" class="align-center justify-center" contained>
      <v-progress-circular indeterminate size="64" color="primary" />
    </v-overlay>

    <!-- Email Report Dialog -->
    <v-dialog v-model="emailDialog" max-width="500px" role="dialog" aria-modal="true" aria-labelledby="email-dialog-title">
      <v-card>
        <v-card-title id="email-dialog-title" class="text-h5">{{ t('reports.title') }}</v-card-title>
        <v-card-text>
          <v-form ref="emailForm" v-model="emailFormValid">
            <v-combobox v-model="emailRecipients" :label="t('filters.recipients')" chips multiple
              variant="outlined" :hint="t('filters.pressEnterToAdd')" persistent-hint
              :rules="[v => (v && v.length > 0) || t('filters.atLeastOneRecipient')]">
              <template v-slot:chip="{ item, props }">
                <v-chip v-bind="props" closable>{{ item }}</v-chip>
              </template>
            </v-combobox>
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="grey" variant="text" @click="emailDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" variant="flat" @click="sendEmailReport"
            :loading="sendingEmail" :disabled="!emailFormValid">{{ t('common.submit') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :color="snackbarColor" :timeout="4000" role="alert"
      :aria-live="snackbarColor === 'error' ? 'assertive' : 'polite'">
      {{ snackbarMessage }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar = false" :aria-label="t('kpi.ariaCloseNotification')">{{ t('common.close') }}</v-btn>
      </template>
    </v-snackbar>

    <!-- Dashboard Customizer & Filter Manager -->
    <DashboardCustomizer v-model="showCustomizer" @saved="onCustomizerSaved" />
    <FilterManager v-model="showFilterManager" />

    <!-- QR Scanner Dialog -->
    <v-dialog v-model="showQRScanner" max-width="500px" role="dialog" aria-modal="true" aria-labelledby="qr-scanner-title">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" aria-hidden="true">mdi-qrcode-scan</v-icon>
          <span id="qr-scanner-title">{{ t('filters.quickQrScanner') }}</span>
          <v-spacer />
          <v-btn icon variant="text" @click="showQRScanner = false" :aria-label="t('kpi.ariaCloseQrScanner')">
            <v-icon aria-hidden="true">mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text class="pa-0">
          <QRCodeScanner @auto-fill="handleQRAutoFill" @scanned="handleQRScanned" />
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Save Filter Dialog -->
    <v-dialog v-model="showSaveFilterDialog" max-width="450px" role="dialog" aria-modal="true" aria-labelledby="save-filter-title">
      <v-card>
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" aria-hidden="true">mdi-content-save</v-icon>
          <span id="save-filter-title">{{ t('filters.saveCurrentFilter') }}</span>
        </v-card-title>
        <v-card-text>
          <v-form ref="saveFilterForm" v-model="saveFilterFormValid">
            <v-text-field v-model="newFilterName" :label="t('filters.filterName')"
              :placeholder="t('filters.filterNamePlaceholder')" variant="outlined"
              :rules="[v => !!v || t('filters.nameRequired')]" class="mb-3" />
            <v-select v-model="newFilterType" :items="filterTypeOptions"
              :label="t('filters.filterType')" variant="outlined" class="mb-3" />
            <v-checkbox v-model="newFilterIsDefault" :label="t('filters.setAsDefault')" hide-details />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="grey" variant="text" @click="showSaveFilterDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" variant="flat" @click="saveCurrentFilter"
            :loading="savingFilter" :disabled="!saveFilterFormValid">{{ t('filters.saveFilter') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
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
  Legend,
  Filler
} from 'chart.js'
import { useKPIStore } from '@/stores/kpi'

// Components
import FilterBar from '@/components/filters/FilterBar.vue'
import DashboardCustomizer from '@/components/dashboard/DashboardCustomizer.vue'
import FilterManager from '@/components/filters/FilterManager.vue'
import QRCodeScanner from '@/components/QRCodeScanner.vue'
import InferenceIndicator from '@/components/kpi/InferenceIndicator.vue'

// Composables
import { useKPIDashboardData } from '@/composables/useKPIDashboardData'
import { useKPIReports } from '@/composables/useKPIReports'
import { useKPIFilters } from '@/composables/useKPIFilters'
import { useKPIChartData } from '@/composables/useKPIChartData'
import { useKPIDashboardHelpers } from '@/composables/useKPIDashboardHelpers'
import { useKPIDashboardActions } from '@/composables/useKPIDashboardActions'

ChartJS.register(
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler
)

const { t } = useI18n()
const kpiStore = useKPIStore()

// UI actions & snackbar (shared across composables)
const {
  snackbar, snackbarMessage, snackbarColor, showSnackbar,
  showCustomizer, showQRScanner,
  navigateToDetail, onCustomizerSaved,
  handleQRScanned, handleQRAutoFill
} = useKPIDashboardActions()

// Data & filter composable
const {
  loading, selectedClient, dateRange, trendPeriod, clients,
  filtersStore, refreshData, handleFilterChange, initialize
} = useKPIDashboardData(showSnackbar)

// Report composable
const {
  downloadingPDF, downloadingExcel,
  emailDialog, emailRecipients, emailFormValid, sendingEmail,
  downloadPDF, downloadExcel, sendEmailReport
} = useKPIReports(showSnackbar, () => selectedClient.value, () => dateRange.value)

// Filter management composable
const {
  showSaveFilterDialog, saveFilterForm, saveFilterFormValid,
  newFilterName, newFilterType, newFilterIsDefault,
  savingFilter, filterTypeOptions, showFilterManager,
  applyQuickSavedFilter, saveCurrentFilter
} = useKPIFilters(showSnackbar, handleFilterChange, () => selectedClient.value, () => dateRange.value)

// Chart data composable
const {
  chartOptions, efficiencyChartData, qualityChartData,
  availabilityChartData, oeeChartData
} = useKPIChartData()

// KPI display helpers & summary table
const {
  formatValue, getCardColor, getStatusColor, getStatusText,
  getProgress, getConfidenceColor, getKpiTooltip,
  summaryHeaders, summaryItems
} = useKPIDashboardHelpers()

// Template refs
const emailForm = ref(null)

onMounted(async () => {
  await initialize()
})
</script>

<style scoped>
.kpi-card {
  cursor: pointer;
  transition: all 0.2s ease;
  border-width: 2px !important;
}

.kpi-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

/* Phase 7.3: Estimated card styling */
.estimated-card {
  border-style: dashed !important;
  border-color: rgba(var(--v-theme-warning), 0.4) !important;
}

.text-estimated {
  opacity: 0.9;
}

.confidence-bar {
  opacity: 0.7;
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
