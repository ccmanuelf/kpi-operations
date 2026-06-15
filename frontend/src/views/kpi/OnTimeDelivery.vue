<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">{{ $t('kpi.otd') }}</h1>
        <p class="text-subtitle-1 text-medium-emphasis">{{ $t('kpi.otdDescription') }}</p>
      </v-col>
      <v-col cols="12" md="6" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2 text-white" variant="flat">
          {{ formatValue(otdData?.percentage) }}%
        </v-chip>
        <v-chip variant="text" style="color: var(--cds-text-secondary)">{{ $t('kpi.targetPercent', { value: 95 }) }}</v-chip>
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

    <!-- Summary Cards -->
    <v-row class="mt-4">
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-medium-emphasis">{{ $t('kpi.totalDeliveries') }}</div>
                <div class="text-h4 font-weight-bold">{{ otdData?.total_orders || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.totalDeliveriesMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" color="success" class="cursor-help">
              <v-card-text>
                <div class="text-caption">{{ $t('kpi.onTime') }}</div>
                <div class="text-h4 font-weight-bold">{{ otdData?.on_time_count || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.onTimeMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" color="error" class="cursor-help">
              <v-card-text>
                <div class="text-caption">{{ $t('kpi.late') }}</div>
                <div class="text-h4 font-weight-bold">{{ (otdData?.total_orders || 0) - (otdData?.on_time_count || 0) }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.formula') }}:</div>
            <div class="tooltip-formula">{{ $t('kpi.tooltips.lateFormula') }}</div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.lateMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-medium-emphasis">{{ $t('kpi.otdRate') }}</div>
                <div class="text-h4 font-weight-bold">{{ formatValue(otdData?.percentage) }}%</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.formula') }}:</div>
            <div class="tooltip-formula">{{ $t('kpi.tooltips.otdRateFormula') }}</div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.otdRateMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>{{ $t('kpi.otdTrend') }}</v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
            <v-alert v-else type="info" variant="tonal">{{ $t('kpi.noTrendData') }}</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Historical Data Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            {{ $t('kpi.productionHistory') }}
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
              :headers="historyHeaders"
              :items="historicalData"
              :search="tableSearch"
              :loading="loading"
              :items-per-page="10"
              class="elevation-0"
              :no-data-text="$t('common.noData')"
            >
              <template v-slot:item.date="{ item }">
                {{ formatDate(item.date) }}
              </template>
              <template v-slot:item.avg_efficiency="{ item }">
                <v-chip :color="getEfficiencyColor(item.avg_efficiency)" size="small">
                  {{ item.avg_efficiency?.toFixed(1) || 0 }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Performance by Client -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>{{ $t('kpi.performanceByClient') }}</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="clientHeaders"
              :items="otdData?.by_client || []"
              density="compact"
              :no-data-text="$t('common.noData')"
            >
              <template v-slot:item.otd_percentage="{ item }">
                <v-chip :color="getOTDColor(item.otd_percentage)" size="small">
                  {{ item.otd_percentage?.toFixed(1) || 0 }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Late Deliveries -->
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>{{ $t('kpi.recentLateDeliveries') }}</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="lateHeaders"
              :items="otdData?.late_deliveries || []"
              density="compact"
              :items-per-page="10"
              :no-data-text="$t('common.noData')"
            >
              <template v-slot:item.delay_hours="{ item }">
                <v-chip color="error" size="small">
                  {{ $t('kpi.hLate', { hours: item.delay_hours }) }}
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
import { onMounted } from 'vue'
import { Line } from 'vue-chartjs'
import useOnTimeDeliveryData from '@/composables/useOnTimeDeliveryData'
import useOnTimeDeliveryCharts from '@/composables/useOnTimeDeliveryCharts'

const {
  loading, clients, selectedClient, startDate, endDate, tableSearch,
  historicalData, otdData, statusColor,
  clientHeaders, lateHeaders, historyHeaders,
  formatValue, formatDate, getOTDColor, getEfficiencyColor,
  onClientChange, onDateChange, refreshData, initialize
} = useOnTimeDeliveryData()

const { chartData, chartOptions } = useOnTimeDeliveryCharts()

onMounted(() => initialize())
</script>

<style scoped>
.cursor-help {
  cursor: help;
}
</style>

<style>
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
