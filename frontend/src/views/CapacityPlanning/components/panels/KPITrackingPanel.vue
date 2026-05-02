<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon start>mdi-target</v-icon>
      {{ t('capacityPlanning.kpiTracking.title') }}
      <v-spacer />
      <v-btn color="primary" size="small" variant="tonal" @click="addRow">
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

      <!-- KPI Grid -->
      <AGGridBase
        v-if="kpiData.length"
        :columnDefs="columnDefs"
        :rowData="kpiData"
        height="500px"
        :pagination="true"
        :paginationPageSize="20"
        :enableExcelPaste="false"
        entry-type="production"
        @cell-value-changed="onCellValueChanged"
      />

      <!-- Empty State -->
      <div v-else class="text-center pa-8 text-grey">
        <v-icon size="64" color="grey-lighten-1">mdi-target</v-icon>
        <div class="text-h6 mt-4">{{ t('capacityPlanning.kpiTracking.noCommitmentsTitle') }}</div>
        <div class="text-body-2 mt-2">
          {{ t('capacityPlanning.kpiTracking.noCommitmentsDescription') }}
        </div>
        <v-btn color="primary" variant="tonal" class="mt-4" @click="addRow">
          {{ t('capacityPlanning.kpiTracking.addKpi') }}
        </v-btn>
      </div>
    </v-card-text>

    <!-- Load Actuals Dialog (Exception 3 — parameter dialog) -->
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
 * KPITrackingPanel - AG Grid surface for KPI commitment tracking
 * (target vs actual + variance + status).
 *
 * Migrated 2026-05-01 from v-data-table + v-text-field slots to
 * AGGridBase as part of Group G Surface #18 (final Group G surface)
 * of the entry-interface audit.
 *
 * Editable fields: kpi_name (text), target_value (numeric).
 * Read-only display fields with chip renderers: actual_value,
 * variance_percent, status, period (formatted date range).
 * actual_value/variance_percent/status are populated by the store's
 * loadKPIActuals() action against backend KPI actuals data.
 *
 * The "Load Actuals" period-picker dialog remains as a parameter
 * dialog (Exception 3).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from '@/components/grids/AGGridBase.vue'
import { useCapacityPlanningStore } from '@/stores/capacityPlanningStore'
import useKPITrackingGridData from '@/composables/useKPITrackingGridData'

const { t } = useI18n()
const store = useCapacityPlanningStore()

const showLoadActualsDialog = ref(false)
const selectedPeriod = ref('current_week')

const periodOptions = computed(() => [
  { title: t('capacityPlanning.kpiTracking.periods.currentWeek'), value: 'current_week' },
  { title: t('capacityPlanning.kpiTracking.periods.lastWeek'), value: 'last_week' },
  { title: t('capacityPlanning.kpiTracking.periods.currentMonth'), value: 'current_month' },
  { title: t('capacityPlanning.kpiTracking.periods.lastMonth'), value: 'last_month' },
])

const {
  kpiData,
  onTargetCount,
  offTargetCount,
  criticalCount,
  columnDefs,
  addRow,
  onCellValueChanged,
} = useKPITrackingGridData()

const loadActuals = () => {
  showLoadActualsDialog.value = true
}

const doLoadActuals = async () => {
  showLoadActualsDialog.value = false
  try {
    await store.loadKPIActuals(selectedPeriod.value)
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('Failed to load actuals:', error)
  }
}
</script>
