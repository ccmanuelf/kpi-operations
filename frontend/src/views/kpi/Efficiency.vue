<template>
  <v-container fluid class="pa-4">
    <v-btn icon="mdi-arrow-left" variant="text" @click="$router.back()" class="mb-4" />

    <v-row>
      <v-col cols="12" md="6">
        <h1 class="text-h3">{{ $t('kpi.efficiency') }}</h1>
        <p class="text-subtitle-1 text-grey-darken-1">{{ $t('kpi.efficiencyDescription') }}</p>
      </v-col>
      <v-col cols="12" md="6" class="text-right">
        <v-chip :color="statusColor" size="large" class="mr-2 text-white" variant="flat">
          {{ formatValue(efficiencyData?.current) }}%
        </v-chip>
        <v-chip color="grey-darken-2">{{ $t('kpi.targetPercent', { value: 85 }) }}</v-chip>
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
                <div class="text-caption text-grey-darken-1">{{ $t('kpi.currentEfficiency') }}</div>
                <div class="text-h4 font-weight-bold">{{ formatValue(efficiencyData?.current) }}%</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.formula') }}:</div>
            <div class="tooltip-formula">{{ $t('kpi.tooltips.efficiencyFormula') }}</div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.efficiencyMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">{{ $t('kpi.actualOutput') }}</div>
                <div class="text-h4 font-weight-bold">{{ efficiencyData?.actual_output || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.actualOutputMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">{{ $t('kpi.expectedOutput') }}</div>
                <div class="text-h4 font-weight-bold">{{ efficiencyData?.expected_output || 0 }}</div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.expectedOutputMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
      <v-col cols="12" md="3">
        <v-tooltip location="bottom" max-width="300">
          <template v-slot:activator="{ props }">
            <v-card v-bind="props" variant="outlined" class="cursor-help">
              <v-card-text>
                <div class="text-caption text-grey-darken-1">{{ $t('kpi.gap') }}</div>
                <div class="text-h4 font-weight-bold" :class="gapColor">
                  {{ $t('kpi.unitsCount', { count: efficiencyData?.gap || 0 }) }}
                </div>
              </v-card-text>
            </v-card>
          </template>
          <div>
            <div class="tooltip-title">{{ $t('common.formula') }}:</div>
            <div class="tooltip-formula">{{ $t('kpi.tooltips.gapFormula') }}</div>
            <div class="tooltip-title">{{ $t('common.meaning') }}:</div>
            <div class="tooltip-meaning">{{ $t('kpi.tooltips.gapMeaning') }}</div>
          </div>
        </v-tooltip>
      </v-col>
    </v-row>

    <!-- Efficiency Trend Chart -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center">
            <span>{{ $t('kpi.efficiencyTrend') }}</span>
            <v-spacer />
            <v-switch
              v-model="showForecast"
              :label="$t('kpi.showForecast')"
              color="purple"
              density="compact"
              hide-details
              class="mr-4"
              @change="onForecastToggle"
            />
            <v-select
              v-if="showForecast"
              v-model="forecastDays"
              :items="[3, 7, 14, 21, 30]"
              :label="$t('kpi.forecastDays')"
              density="compact"
              variant="outlined"
              style="max-width: 120px"
              hide-details
              @update:model-value="fetchPrediction"
            />
          </v-card-title>
          <v-card-text>
            <Line v-if="chartData.labels.length" :data="chartData" :options="chartOptions" />
            <v-alert v-else type="info" variant="tonal">{{ $t('kpi.noTrendData') }}</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Prediction Details Card -->
    <v-row v-if="showForecast && predictionData" class="mt-4">
      <v-col cols="12" md="4">
        <v-card variant="outlined" class="border-purple">
          <v-card-title class="text-purple-darken-1">
            <v-icon start>mdi-crystal-ball</v-icon>
            {{ $t('kpi.predictionSummary') }}
          </v-card-title>
          <v-card-text>
            <div class="d-flex justify-space-between mb-2">
              <span class="text-grey-darken-1">{{ $t('kpi.predictedAverage') }}</span>
              <span class="font-weight-bold">{{ predictionData.predicted_average?.toFixed(1) }}%</span>
            </div>
            <div class="d-flex justify-space-between mb-2">
              <span class="text-grey-darken-1">{{ $t('kpi.currentValue') }}</span>
              <span>{{ predictionData.current_value?.toFixed(1) }}%</span>
            </div>
            <div class="d-flex justify-space-between mb-2">
              <span class="text-grey-darken-1">{{ $t('kpi.expectedChange') }}</span>
              <v-chip :color="predictionData.expected_change_percent >= 0 ? 'success' : 'error'" size="small">
                {{ predictionData.expected_change_percent >= 0 ? '+' : '' }}{{ predictionData.expected_change_percent?.toFixed(1) }}%
              </v-chip>
            </div>
            <div class="d-flex justify-space-between mb-2">
              <span class="text-grey-darken-1">{{ $t('kpi.modelAccuracy') }}</span>
              <span>{{ predictionData.model_accuracy?.toFixed(0) }}%</span>
            </div>
            <div class="d-flex justify-space-between">
              <span class="text-grey-darken-1">{{ $t('kpi.method') }}</span>
              <v-chip size="x-small" color="purple" variant="outlined">
                {{ predictionData.prediction_method?.replace(/_/g, ' ') }}
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card variant="outlined">
          <v-card-title>
            <v-icon start>mdi-heart-pulse</v-icon>
            {{ $t('kpi.healthAssessment') }}
          </v-card-title>
          <v-card-text v-if="predictionData.health_assessment">
            <div class="d-flex align-center mb-3">
              <v-progress-circular
                :model-value="predictionData.health_assessment.health_score"
                :color="getHealthColor(predictionData.health_assessment.health_score)"
                :size="60"
                :width="6"
              >
                {{ predictionData.health_assessment.health_score?.toFixed(0) }}
              </v-progress-circular>
              <div class="ml-3">
                <div class="text-body-2 text-grey-darken-1">{{ $t('kpi.healthScore') }}</div>
                <v-chip :color="getTrendColor(predictionData.health_assessment.trend)" size="small">
                  <v-icon start size="small">{{ getTrendIcon(predictionData.health_assessment.trend) }}</v-icon>
                  {{ predictionData.health_assessment.trend }}
                </v-chip>
              </div>
            </div>
            <div class="text-caption text-grey-darken-1">
              {{ predictionData.health_assessment.current_vs_target }}
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card variant="outlined">
          <v-card-title>
            <v-icon start>mdi-lightbulb</v-icon>
            {{ $t('kpi.recommendations') }}
          </v-card-title>
          <v-card-text v-if="predictionData.health_assessment?.recommendations">
            <v-list density="compact" class="pa-0">
              <v-list-item
                v-for="(rec, index) in predictionData.health_assessment.recommendations.slice(0, 3)"
                :key="index"
                class="px-0"
              >
                <template v-slot:prepend>
                  <v-icon size="small" color="amber-darken-2">mdi-arrow-right</v-icon>
                </template>
                <v-list-item-title class="text-body-2">{{ rec }}</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Historical Data Table -->
    <v-row class="mt-4">
      <v-col cols="12">
        <v-card>
          <v-card-title>
            {{ $t('kpi.historicalData') }}
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

    <!-- Efficiency by Shift and Product -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>{{ $t('kpi.efficiencyByShift') }}</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="shiftHeaders"
              :items="efficiencyData?.by_shift || []"
              density="compact"
            >
              <template v-slot:item.efficiency="{ item }">
                <v-chip :color="getEfficiencyColor(item.efficiency)" size="small">
                  {{ item.efficiency?.toFixed(1) || 0 }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>{{ $t('kpi.topProductsByEfficiency') }}</v-card-title>
          <v-card-text>
            <v-data-table
              :headers="productHeaders"
              :items="efficiencyData?.by_product || []"
              density="compact"
            >
              <template v-slot:item.efficiency="{ item }">
                <v-chip :color="getEfficiencyColor(item.efficiency)" size="small">
                  {{ item.efficiency?.toFixed(1) || 0 }}%
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
import useEfficiencyData from '@/composables/useEfficiencyData'
import useEfficiencyCharts from '@/composables/useEfficiencyCharts'

const {
  loading, clients, selectedClient, startDate, endDate, tableSearch,
  historicalData, showForecast, forecastDays, predictionData,
  efficiencyData, statusColor, gapColor,
  shiftHeaders, productHeaders, historyHeaders,
  formatValue, formatDate,
  getEfficiencyColor, getPerformanceColor, getHealthColor, getTrendColor, getTrendIcon,
  fetchPrediction, onForecastToggle, onClientChange, onDateChange, refreshData, initialize
} = useEfficiencyData()

const { chartData, chartOptions } = useEfficiencyCharts({ showForecast, predictionData })

onMounted(() => initialize())
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
