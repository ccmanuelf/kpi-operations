<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-target</v-icon>
      {{ t('capacityPlanning.kpiTracking.title') }}
      <v-spacer />
      <v-btn
        color="primary"
        size="small"
        variant="tonal"
        @click="addKPI"
      >
        <v-icon start>mdi-plus</v-icon>
        {{ t('capacityPlanning.kpiTracking.addKpi') }}
      </v-btn>
      <v-btn
        color="info"
        size="small"
        variant="outlined"
        class="ml-2"
        @click="loadActuals"
      >
        <v-icon start>mdi-refresh</v-icon>
        {{ t('capacityPlanning.kpiTracking.loadActuals') }}
      </v-btn>
    </v-card-title>
    <v-card-text>
      <!-- Summary Cards -->
      <v-row v-if="kpiData.length" class="mb-4">
        <v-col cols="3">
          <v-card variant="tonal" color="primary">
            <v-card-text class="text-center">
              <div class="text-h4">{{ kpiData.length }}</div>
              <div class="text-subtitle-1">{{ t('capacityPlanning.kpiTracking.totalKpis') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="success">
            <v-card-text class="text-center">
              <div class="text-h4">{{ onTargetCount }}</div>
              <div class="text-subtitle-1">{{ t('capacityPlanning.kpiTracking.onTarget') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="warning">
            <v-card-text class="text-center">
              <div class="text-h4">{{ offTargetCount }}</div>
              <div class="text-subtitle-1">{{ t('capacityPlanning.kpiTracking.offTarget') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="3">
          <v-card variant="tonal" color="error">
            <v-card-text class="text-center">
              <div class="text-h4">{{ criticalCount }}</div>
              <div class="text-subtitle-1">{{ t('capacityPlanning.kpiTracking.critical') }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- KPI Table -->
      <v-data-table
        v-if="kpiData.length"
        :headers="headers"
        :items="kpiData"
        :items-per-page="10"
        class="elevation-1"
        density="compact"
      >
        <template v-slot:item.kpi_name="{ item, index }">
          <v-text-field
            v-model="item.kpi_name"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.target_value="{ item, index }">
          <v-text-field
            v-model.number="item.target_value"
            type="number"
            density="compact"
            variant="plain"
            hide-details
            @update:modelValue="markDirty(index)"
          />
        </template>

        <template v-slot:item.actual_value="{ item }">
          <span v-if="item.actual_value !== null">
            {{ item.actual_value }}
          </span>
          <span v-else class="text-grey">--</span>
        </template>

        <template v-slot:item.variance_percent="{ item }">
          <v-chip
            v-if="item.variance_percent !== null"
            :color="getVarianceColor(item.variance_percent)"
            size="small"
            variant="tonal"
          >
            {{ item.variance_percent > 0 ? '+' : '' }}{{ item.variance_percent }}%
          </v-chip>
          <span v-else class="text-grey">--</span>
        </template>

        <template v-slot:item.status="{ item }">
          <v-chip
            :color="getStatusColor(item.status)"
            size="small"
            variant="tonal"
          >
            {{ item.status }}
          </v-chip>
        </template>

        <template v-slot:item.period="{ item }">
          <span v-if="item.period_start && item.period_end">
            {{ formatDate(item.period_start) }} - {{ formatDate(item.period_end) }}
          </span>
          <span v-else class="text-grey">--</span>
        </template>

        <template v-slot:item.actions="{ index }">
          <v-btn
            icon="mdi-delete"
            size="x-small"
            variant="text"
            color="error"
            @click="removeRow(index)"
          />
        </template>
      </v-data-table>

      <!-- Empty State -->
      <div v-else class="text-center pa-8 text-grey">
        <v-icon size="64" color="grey-lighten-1">mdi-target</v-icon>
        <div class="text-h6 mt-4">{{ t('capacityPlanning.kpiTracking.noCommitmentsTitle') }}</div>
        <div class="text-body-2 mt-2">
          {{ t('capacityPlanning.kpiTracking.noCommitmentsDescription') }}
        </div>
        <v-btn
          color="primary"
          variant="tonal"
          class="mt-4"
          @click="addKPI"
        >
          {{ t('capacityPlanning.kpiTracking.addKpi') }}
        </v-btn>
      </div>
    </v-card-text>

    <!-- Load Actuals Dialog -->
    <v-dialog v-model="showLoadActualsDialog" max-width="400">
      <v-card>
        <v-card-title>{{ t('capacityPlanning.kpiTracking.loadKpiActuals') }}</v-card-title>
        <v-card-text>
          <v-select
            v-model="selectedPeriod"
            :items="periodOptions"
            :label="t('common.period')"
            variant="outlined"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showLoadActualsDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-btn color="primary" @click="doLoadActuals">{{ t('capacityPlanning.kpiTracking.load') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
/**
 * KPITrackingPanel - Tracks KPI commitments with target vs actual comparison.
 *
 * Displays KPI metrics in an editable table with target values, loaded actuals,
 * variance percentages, and status chips. Summary cards show counts of on-target,
 * off-target, and critical KPIs. Supports manual KPI creation and period-based
 * actuals loading (current/last week/month).
 *
 * Store dependency: useCapacityPlanningStore (worksheets.kpiTracking)
 * No props or emits -- all state managed via store.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'

const { t } = useI18n()
const store = useCapacityPlanningStore()

const showLoadActualsDialog = ref(false)
const selectedPeriod = ref('current_week')

const headers = computed(() => [
  { title: t('capacityPlanning.kpiTracking.headers.kpiName'), key: 'kpi_name', width: '200px' },
  { title: t('capacityPlanning.kpiTracking.headers.target'), key: 'target_value', width: '100px' },
  { title: t('capacityPlanning.kpiTracking.headers.actual'), key: 'actual_value', width: '100px' },
  { title: t('capacityPlanning.kpiTracking.headers.variance'), key: 'variance_percent', width: '100px' },
  { title: t('capacityPlanning.kpiTracking.headers.status'), key: 'status', width: '100px' },
  { title: t('capacityPlanning.kpiTracking.headers.period'), key: 'period', width: '180px' },
  { title: t('capacityPlanning.kpiTracking.headers.actions'), key: 'actions', width: '80px', sortable: false }
])

const periodOptions = computed(() => [
  { title: t('capacityPlanning.kpiTracking.periods.currentWeek'), value: 'current_week' },
  { title: t('capacityPlanning.kpiTracking.periods.lastWeek'), value: 'last_week' },
  { title: t('capacityPlanning.kpiTracking.periods.currentMonth'), value: 'current_month' },
  { title: t('capacityPlanning.kpiTracking.periods.lastMonth'), value: 'last_month' }
])

const kpiData = computed(() => store.worksheets.kpiTracking.data)

const onTargetCount = computed(() =>
  kpiData.value.filter(k => Math.abs(k.variance_percent || 0) <= 5).length
)

const offTargetCount = computed(() =>
  kpiData.value.filter(k => Math.abs(k.variance_percent || 0) > 5 && Math.abs(k.variance_percent || 0) <= 10).length
)

const criticalCount = computed(() =>
  kpiData.value.filter(k => Math.abs(k.variance_percent || 0) > 10).length
)

const getVarianceColor = (variance) => {
  const abs = Math.abs(variance)
  if (abs <= 5) return 'success'
  if (abs <= 10) return 'warning'
  return 'error'
}

const getStatusColor = (status) => {
  const colors = {
    PENDING: 'grey',
    ON_TRACK: 'success',
    AT_RISK: 'warning',
    OFF_TARGET: 'error',
    ACHIEVED: 'success'
  }
  return colors[status] || 'grey'
}

const formatDate = (date) => {
  if (!date) return ''
  return new Date(date).toLocaleDateString()
}

const addKPI = () => store.addRow('kpiTracking')
const removeRow = (index) => store.removeRow('kpiTracking', index)
const markDirty = () => {
  store.worksheets.kpiTracking.dirty = true
}

const loadActuals = () => {
  showLoadActualsDialog.value = true
}

const doLoadActuals = async () => {
  showLoadActualsDialog.value = false
  try {
    await store.loadKPIActuals(selectedPeriod.value)
  } catch (error) {
    console.error('Failed to load actuals:', error)
  }
}
</script>
