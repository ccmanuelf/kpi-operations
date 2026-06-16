<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">{{ $t('kpi.oee') }}</h1>
        <p class="text-subtitle-1 text-medium-emphasis">{{ $t('kpi.oeeDescription') }}</p>
      </v-col>
      <v-col cols="12" md="6" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2 text-white" variant="flat">
          {{ formatValue(oeeData?.percentage) }}%
        </v-chip>
        <v-chip variant="text" style="color: var(--cds-text-secondary)">{{ $t('kpi.targetPercent', { value: 85 }) }}</v-chip>
      </v-col>
    </v-row>

    <!-- Client Filter -->
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

    <!-- OEE Formula Display -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card color="primary" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h6 mb-2">{{ $t('kpi.oeeFormula') }}</div>
            <!-- Math formula display (Availability% × Performance% × Quality% = OEE%); not UI copy. -->
            <!-- eslint-disable @intlify/vue-i18n/no-raw-text -->
            <div class="text-h4 font-weight-bold">
              {{ formatValue(components.availability) }}% x
              {{ formatValue(components.performance) }}% x
              {{ formatValue(components.quality) }}% =
              <!-- Inherit the tonal card's (AA) text color; the status color is
                   already conveyed by the chip above and is not AA as text on
                   this surface across themes. -->
              <span>{{ formatValue(oeeData?.percentage) }}%</span>
            </div>
            <!-- eslint-enable @intlify/vue-i18n/no-raw-text -->
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Component Cards -->
    <v-row class="mt-4">
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" @click="$router.push('/kpi/availability')" style="cursor:pointer">
              <v-card-text>
                <div class="d-flex align-center justify-space-between">
                  <div>
                    <div class="text-caption text-medium-emphasis">{{ $t('kpi.availability') }}</div>
                    <div class="text-h4 font-weight-bold">{{ formatValue(components.availability) }}%</div>
                    <div class="text-caption">{{ $t('kpi.equipmentUptime') }}</div>
                  </div>
                  <v-icon size="48" color="blue">mdi-server</v-icon>
                </div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.formula') }}:</div>
            <div class="tooltip-formula">{{ $t('kpi.tooltips.availabilityFormula') }}</div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.availabilityMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" @click="$router.push('/kpi/performance')" style="cursor:pointer">
              <v-card-text>
                <div class="d-flex align-center justify-space-between">
                  <div>
                    <div class="text-caption text-medium-emphasis">{{ $t('kpi.performance') }}</div>
                    <div class="text-h4 font-weight-bold">{{ formatValue(components.performance) }}%</div>
                    <div class="text-caption">{{ $t('kpi.speedEfficiency') }}</div>
                  </div>
                  <v-icon size="48" color="orange">mdi-speedometer</v-icon>
                </div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.formula') }}:</div>
            <div class="tooltip-formula">{{ $t('kpi.tooltips.performanceFormula') }}</div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.performanceMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="4">
        <v-tooltip location="bottom" max-width="350">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" @click="$router.push('/kpi/quality')" style="cursor:pointer">
              <v-card-text>
                <div class="d-flex align-center justify-space-between">
                  <div>
                    <div class="text-caption text-medium-emphasis">{{ $t('kpi.qualityFPY') }}</div>
                    <div class="text-h4 font-weight-bold">{{ formatValue(components.quality) }}%</div>
                    <div class="text-caption">{{ $t('kpi.firstPassYield') }}</div>
                  </div>
                  <v-icon size="48" color="green">mdi-star-circle</v-icon>
                </div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.formula') }}:</div>
            <div class="tooltip-formula">{{ $t('kpi.tooltips.qualityFormula') }}</div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.qualityMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- OEE Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>{{ $t('kpi.oeeTrend') }}</v-card-title>
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
              <template v-slot:item.avg_performance="{ item }">
                <v-chip :color="getPerformanceColor(item.avg_performance)" size="small">
                  {{ item.avg_performance?.toFixed(1) || 0 }}%
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
import useOEEData from '@/composables/useOEEData'
import useOEECharts from '@/composables/useOEECharts'

const {
  loading, clients, selectedClient, startDate, endDate, tableSearch,
  historicalData, oeeData, components, statusColor,
  historyHeaders, formatValue, formatDate,
  getEfficiencyColor, getPerformanceColor,
  onClientChange, onDateChange, refreshData, initialize
} = useOEEData()

const { chartData, chartOptions } = useOEECharts()

onMounted(() => initialize())
</script>

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
