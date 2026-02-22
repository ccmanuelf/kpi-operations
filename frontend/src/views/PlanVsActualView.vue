<template>
  <v-container fluid>
    <!-- Page Title -->
    <v-row>
      <v-col>
        <h1 class="text-h4 mb-4">{{ t('planVsActual.title') }}</h1>
      </v-col>
    </v-row>

    <!-- Summary Cards -->
    <v-row v-if="summary">
      <v-col cols="12" sm="6" md="3">
        <v-card variant="elevated">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ summary.total_orders }}</div>
            <div class="text-subtitle-1 text-medium-emphasis">{{ t('planVsActual.totalOrders') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card variant="elevated">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ formatNumber(summary.total_planned_quantity) }}</div>
            <div class="text-subtitle-1 text-medium-emphasis">{{ t('planVsActual.totalPlanned') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card variant="elevated">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold">{{ formatNumber(summary.total_actual_completed) }}</div>
            <div class="text-subtitle-1 text-medium-emphasis">{{ t('planVsActual.totalActual') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-card variant="elevated">
          <v-card-text class="text-center">
            <div class="text-h4 font-weight-bold" :class="getVarianceClass(summary.overall_completion_pct - 100)">
              {{ summary.overall_completion_pct?.toFixed(1) }}%
            </div>
            <div class="text-subtitle-1 text-medium-emphasis">{{ t('planVsActual.overallCompletion') }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Risk Distribution -->
    <v-row v-if="summary?.risk_distribution" class="mb-2">
      <v-col cols="12">
        <v-card variant="elevated">
          <v-card-text>
            <div class="text-subtitle-1 font-weight-medium mb-2">{{ t('planVsActual.riskDistribution') }}</div>
            <div class="d-flex flex-wrap ga-2">
              <v-chip
                v-for="(count, risk) in summary.risk_distribution"
                :key="risk"
                :color="getRiskColor(risk)"
                variant="flat"
                size="small"
              >
                {{ getRiskLabel(risk) }}: {{ count }}
              </v-chip>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Filters -->
    <v-row class="mb-2">
      <v-col cols="12" sm="6" md="3">
        <v-text-field
          v-model="filters.startDate"
          type="date"
          :label="t('planVsActual.startDate')"
          clearable
          density="compact"
          variant="outlined"
          hide-details
        />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-text-field
          v-model="filters.endDate"
          type="date"
          :label="t('planVsActual.endDate')"
          clearable
          density="compact"
          variant="outlined"
          hide-details
        />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <v-select
          v-model="filters.status"
          :items="statusOptions"
          :label="t('planVsActual.status')"
          clearable
          density="compact"
          variant="outlined"
          hide-details
        />
      </v-col>
      <v-col cols="12" sm="6" md="3" class="d-flex align-center ga-2">
        <v-btn color="primary" variant="elevated" @click="fetchData" :loading="loading">
          {{ t('planVsActual.refresh') }}
        </v-btn>
        <v-btn variant="outlined" @click="resetFilters">
          {{ t('common.reset') }}
        </v-btn>
      </v-col>
    </v-row>

    <!-- Data Table -->
    <v-row>
      <v-col>
        <v-card variant="elevated">
          <v-data-table
            :headers="headers"
            :items="orders"
            :loading="loading"
            item-value="capacity_order_id"
            show-expand
            :no-data-text="t('planVsActual.noData')"
            hover
          >
            <!-- Variance slot -->
            <template #item.variance_percentage="{ item }">
              <span class="font-weight-medium" :class="getVarianceClass(item.variance_percentage)">
                {{ item.variance_percentage > 0 ? '+' : '' }}{{ item.variance_percentage?.toFixed(1) }}%
              </span>
            </template>

            <!-- Completion progress bar -->
            <template #item.completion_percentage="{ item }">
              <v-progress-linear
                :model-value="Math.min(item.completion_percentage, 100)"
                :color="getCompletionColor(item.completion_percentage)"
                height="20"
                rounded
              >
                <template #default>
                  <span class="text-caption font-weight-medium">{{ item.completion_percentage?.toFixed(1) }}%</span>
                </template>
              </v-progress-linear>
            </template>

            <!-- Required date slot -->
            <template #item.required_date="{ item }">
              {{ formatDate(item.required_date) }}
            </template>

            <!-- Risk chip slot -->
            <template #item.on_time_risk="{ item }">
              <v-chip :color="getRiskColor(item.on_time_risk)" size="small" variant="flat">
                {{ getRiskLabel(item.on_time_risk) }}
              </v-chip>
            </template>

            <!-- Planned quantity formatting -->
            <template #item.planned_quantity="{ item }">
              {{ formatNumber(item.planned_quantity) }}
            </template>

            <!-- Actual completed formatting -->
            <template #item.actual_completed="{ item }">
              {{ formatNumber(item.actual_completed) }}
            </template>

            <!-- Expanded row for drill-down -->
            <template #expanded-row="{ columns, item }">
              <tr>
                <td :colspan="columns.length" class="pa-4 bg-grey-lighten-5">
                  <v-row>
                    <v-col cols="12" md="6">
                      <h4 class="text-subtitle-1 font-weight-bold mb-2">{{ t('planVsActual.orderDetails') }}</h4>
                      <div class="mb-1">
                        <strong>{{ t('common.status') }}:</strong> {{ item.status }}
                      </div>
                      <div class="mb-1">
                        <strong>{{ t('planVsActual.priority') }}:</strong> {{ item.priority }}
                      </div>
                      <div class="mb-1">
                        <strong>{{ t('planVsActual.linkedWorkOrders') }}:</strong> {{ item.linked_work_orders }}
                      </div>
                      <div v-if="item.projected_completion" class="mb-1">
                        <strong>{{ t('planVsActual.projectedCompletion') }}:</strong> {{ formatDate(item.projected_completion) }}
                      </div>
                      <div v-if="item.planned_start_date" class="mb-1">
                        <strong>{{ t('planVsActual.plannedStart') }}:</strong> {{ formatDate(item.planned_start_date) }}
                      </div>
                      <div v-if="item.planned_end_date" class="mb-1">
                        <strong>{{ t('planVsActual.plannedEnd') }}:</strong> {{ formatDate(item.planned_end_date) }}
                      </div>
                      <div class="mb-1">
                        <strong>{{ t('planVsActual.varianceQty') }}:</strong>
                        <span :class="getVarianceClass(item.variance_percentage)">
                          {{ item.variance_quantity > 0 ? '+' : '' }}{{ formatNumber(item.variance_quantity) }}
                        </span>
                      </div>
                    </v-col>
                    <v-col cols="12" md="6" v-if="item.line_breakdown && item.line_breakdown.length">
                      <h4 class="text-subtitle-1 font-weight-bold mb-2">{{ t('planVsActual.lineBreakdown') }}</h4>
                      <v-table density="compact">
                        <thead>
                          <tr>
                            <th>{{ t('planVsActual.lineId') }}</th>
                            <th class="text-end">{{ t('planVsActual.unitsProduced') }}</th>
                            <th class="text-end">{{ t('planVsActual.entries') }}</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="lb in item.line_breakdown" :key="lb.line_id">
                            <td>{{ lb.line_id }}</td>
                            <td class="text-end">{{ formatNumber(lb.units_produced) }}</td>
                            <td class="text-end">{{ lb.entry_count }}</td>
                          </tr>
                        </tbody>
                      </v-table>
                    </v-col>
                  </v-row>
                </td>
              </tr>
            </template>
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePlanVsActual } from '@/composables/usePlanVsActual'

const { t } = useI18n()

const {
  orders,
  summary,
  loading,
  filters,
  statusOptions,
  headers,
  fetchData,
  resetFilters,
  getRiskColor,
  getVarianceColor,
  getVarianceClass,
  getCompletionColor,
  formatDate,
} = usePlanVsActual()

/**
 * Map risk keys to localized labels
 */
function getRiskLabel(risk) {
  const labels = {
    LOW: t('planVsActual.riskLow'),
    MEDIUM: t('planVsActual.riskMedium'),
    HIGH: t('planVsActual.riskHigh'),
    OVERDUE: t('planVsActual.riskOverdue'),
    COMPLETED: t('planVsActual.riskCompleted'),
    UNKNOWN: t('planVsActual.riskUnknown'),
  }
  return labels[risk] || risk
}

/**
 * Format large numbers with locale separators
 */
function formatNumber(value) {
  if (value == null) return '-'
  return Number(value).toLocaleString()
}

onMounted(() => {
  fetchData()
})
</script>
