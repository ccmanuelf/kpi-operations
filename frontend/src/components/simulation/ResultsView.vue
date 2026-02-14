<template>
  <v-dialog
    v-model="dialogModel"
    fullscreen
    :scrim="false"
    transition="dialog-bottom-transition"
  >
    <v-card>
      <v-toolbar dark color="primary">
        <v-btn icon dark @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
        <v-toolbar-title>Simulation Results</v-toolbar-title>
        <v-spacer />
        <v-toolbar-items>
          <v-btn variant="text" @click="exportToExcel">
            <v-icon left>mdi-microsoft-excel</v-icon>
            Export to Excel
          </v-btn>
        </v-toolbar-items>
      </v-toolbar>

      <v-container fluid v-if="results">
        <!-- Summary Header -->
        <v-row class="mb-4">
          <v-col cols="12">
            <v-alert :type="summaryAlertType" variant="tonal">
              <div class="d-flex align-center justify-space-between">
                <div>
                  <strong>{{ summaryText }}</strong>
                  <div class="text-caption">
                    Simulated {{ results.daily_summary.daily_throughput_pcs }} pieces/day vs
                    {{ results.daily_summary.daily_demand_pcs }} demand
                  </div>
                </div>
                <div class="text-right">
                  <div class="text-h4">{{ results.daily_summary.daily_coverage_pct }}%</div>
                  <div class="text-caption">Coverage</div>
                </div>
              </div>
            </v-alert>
          </v-col>
        </v-row>

        <!-- Tabs -->
        <v-tabs v-model="activeTab" bg-color="primary" show-arrows>
          <v-tab value="summary">Summary</v-tab>
          <v-tab value="weekly">Weekly Capacity</v-tab>
          <v-tab value="stations">Station Performance</v-tab>
          <v-tab value="products">Per Product</v-tab>
          <v-tab value="bundles">Bundle Metrics</v-tab>
          <v-tab value="rebalancing">Rebalancing</v-tab>
          <v-tab value="assumptions">Assumptions</v-tab>
        </v-tabs>

        <v-window v-model="activeTab" class="mt-4">
          <!-- Summary Tab -->
          <v-window-item value="summary">
            <v-row>
              <v-col cols="12" md="4">
                <v-card variant="outlined">
                  <v-card-title class="text-subtitle-1">Daily Summary</v-card-title>
                  <v-card-text>
                    <v-list density="compact">
                      <v-list-item>
                        <template v-slot:prepend><v-icon>mdi-clock</v-icon></template>
                        <v-list-item-title>{{ results.daily_summary.total_shifts_per_day }} shifts, {{ results.daily_summary.daily_planned_hours }}h/day</v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <template v-slot:prepend><v-icon>mdi-package-variant</v-icon></template>
                        <v-list-item-title>{{ results.daily_summary.bundles_processed_per_day }} bundles/day (size: {{ results.daily_summary.bundle_size_pcs }})</v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <template v-slot:prepend><v-icon>mdi-timer-sand</v-icon></template>
                        <v-list-item-title>Avg cycle time: {{ results.daily_summary.avg_cycle_time_min }} min</v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <template v-slot:prepend><v-icon>mdi-layers-outline</v-icon></template>
                        <v-list-item-title>Avg WIP: {{ results.daily_summary.avg_wip_pcs }} pieces</v-list-item-title>
                      </v-list-item>
                    </v-list>
                  </v-card-text>
                </v-card>
              </v-col>

              <v-col cols="12" md="4">
                <v-card variant="outlined">
                  <v-card-title class="text-subtitle-1">Free Capacity</v-card-title>
                  <v-card-text>
                    <v-list density="compact">
                      <v-list-item>
                        <template v-slot:prepend><v-icon>mdi-speedometer</v-icon></template>
                        <v-list-item-title>Max capacity: {{ results.free_capacity.daily_max_capacity_pcs }} pcs/day</v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <template v-slot:prepend><v-icon>mdi-percent</v-icon></template>
                        <v-list-item-title>Usage: {{ results.free_capacity.demand_usage_pct }}%</v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <template v-slot:prepend><v-icon>mdi-clock-plus</v-icon></template>
                        <v-list-item-title>Free line hours: {{ results.free_capacity.free_line_hours_per_day.toFixed(1) }}h/day</v-list-item-title>
                      </v-list-item>
                      <v-list-item>
                        <template v-slot:prepend><v-icon>mdi-account-plus</v-icon></template>
                        <v-list-item-title>Equiv. free operators: {{ results.free_capacity.equivalent_free_operators_full_shift.toFixed(1) }}</v-list-item-title>
                      </v-list-item>
                    </v-list>
                  </v-card-text>
                </v-card>
              </v-col>

              <v-col cols="12" md="4">
                <v-card variant="outlined">
                  <v-card-title class="text-subtitle-1">Bottlenecks</v-card-title>
                  <v-card-text>
                    <div v-if="bottlenecks.length > 0">
                      <v-chip
                        v-for="bn in bottlenecks"
                        :key="bn.machine_tool"
                        color="error"
                        variant="tonal"
                        size="small"
                        class="ma-1"
                      >
                        {{ bn.operation }} ({{ bn.util_pct }}%)
                      </v-chip>
                    </div>
                    <div v-else class="text-success">
                      <v-icon>mdi-check-circle</v-icon>
                      No bottlenecks detected
                    </div>

                    <div v-if="donors.length > 0" class="mt-3">
                      <div class="text-caption text-medium-emphasis mb-1">Potential Donors:</div>
                      <v-chip
                        v-for="dn in donors"
                        :key="dn.machine_tool"
                        color="success"
                        variant="tonal"
                        size="small"
                        class="ma-1"
                      >
                        {{ dn.operation }} ({{ dn.util_pct }}%)
                      </v-chip>
                    </div>
                  </v-card-text>
                </v-card>
              </v-col>
            </v-row>
          </v-window-item>

          <!-- Weekly Capacity Tab -->
          <v-window-item value="weekly">
            <v-data-table
              :headers="weeklyHeaders"
              :items="results.weekly_demand_capacity"
              density="compact"
              class="elevation-1"
            >
              <template v-slot:item.status="{ item }">
                <v-chip
                  :color="getStatusColor(item.status)"
                  size="small"
                  variant="tonal"
                >
                  {{ item.status }}
                </v-chip>
              </template>
              <template v-slot:item.demand_coverage_pct="{ item }">
                {{ item.demand_coverage_pct.toFixed(1) }}%
              </template>
            </v-data-table>
          </v-window-item>

          <!-- Station Performance Tab -->
          <v-window-item value="stations">
            <v-data-table
              :headers="stationHeaders"
              :items="results.station_performance"
              density="compact"
              class="elevation-1"
              :sort-by="[{ key: 'util_pct', order: 'desc' }]"
            >
              <template v-slot:item.is_bottleneck="{ item }">
                <v-icon v-if="item.is_bottleneck" color="error">mdi-alert-circle</v-icon>
              </template>
              <template v-slot:item.is_donor="{ item }">
                <v-icon v-if="item.is_donor" color="success">mdi-account-arrow-right</v-icon>
              </template>
              <template v-slot:item.util_pct="{ item }">
                <v-progress-linear
                  :model-value="item.util_pct"
                  :color="getUtilColor(item.util_pct)"
                  height="20"
                  rounded
                >
                  <template v-slot:default>
                    <span class="text-caption">{{ item.util_pct.toFixed(1) }}%</span>
                  </template>
                </v-progress-linear>
              </template>
            </v-data-table>
          </v-window-item>

          <!-- Per Product Tab -->
          <v-window-item value="products">
            <v-data-table
              :headers="productHeaders"
              :items="results.per_product_summary"
              density="compact"
              class="elevation-1"
            >
              <template v-slot:item.daily_coverage_pct="{ item }">
                <v-chip
                  :color="getCoverageColor(item.daily_coverage_pct)"
                  size="small"
                  variant="tonal"
                >
                  {{ item.daily_coverage_pct.toFixed(1) }}%
                </v-chip>
              </template>
            </v-data-table>
          </v-window-item>

          <!-- Bundle Metrics Tab -->
          <v-window-item value="bundles">
            <v-data-table
              :headers="bundleHeaders"
              :items="results.bundle_metrics"
              density="compact"
              class="elevation-1"
            />
          </v-window-item>

          <!-- Rebalancing Tab -->
          <v-window-item value="rebalancing">
            <v-alert v-if="results.rebalancing_suggestions.length === 0" type="success" variant="tonal">
              No rebalancing needed - line is well balanced.
            </v-alert>
            <v-data-table
              v-else
              :headers="rebalanceHeaders"
              :items="results.rebalancing_suggestions"
              density="compact"
              class="elevation-1"
            >
              <template v-slot:item.role="{ item }">
                <v-chip
                  :color="item.role === 'Bottleneck' ? 'error' : 'success'"
                  size="small"
                  variant="tonal"
                >
                  {{ item.role }}
                </v-chip>
              </template>
            </v-data-table>
          </v-window-item>

          <!-- Assumptions Tab -->
          <v-window-item value="assumptions">
            <v-card variant="outlined">
              <v-card-text>
                <v-row>
                  <v-col cols="12" md="6">
                    <h4 class="mb-2">Configuration</h4>
                    <v-list density="compact">
                      <v-list-item>
                        <v-list-item-title>Engine Version</v-list-item-title>
                        <v-list-item-subtitle>{{ results.assumption_log.simulation_engine_version }}</v-list-item-subtitle>
                      </v-list-item>
                      <v-list-item>
                        <v-list-item-title>Mode</v-list-item-title>
                        <v-list-item-subtitle>{{ results.assumption_log.configuration_mode }}</v-list-item-subtitle>
                      </v-list-item>
                      <v-list-item>
                        <v-list-item-title>Timestamp</v-list-item-title>
                        <v-list-item-subtitle>{{ formatTimestamp(results.assumption_log.timestamp) }}</v-list-item-subtitle>
                      </v-list-item>
                    </v-list>
                  </v-col>
                  <v-col cols="12" md="6">
                    <h4 class="mb-2">Formulas Used</h4>
                    <v-list density="compact">
                      <v-list-item v-for="(formula, key) in results.assumption_log.formula_implementations" :key="key">
                        <v-list-item-title>{{ key }}</v-list-item-title>
                        <v-list-item-subtitle class="text-wrap">{{ formula }}</v-list-item-subtitle>
                      </v-list-item>
                    </v-list>
                  </v-col>
                </v-row>

                <h4 class="mt-4 mb-2">Limitations & Caveats</h4>
                <v-list density="compact">
                  <v-list-item v-for="(caveat, idx) in results.assumption_log.limitations_and_caveats" :key="idx">
                    <template v-slot:prepend>
                      <v-icon size="small" color="warning">mdi-information</v-icon>
                    </template>
                    <v-list-item-title class="text-body-2">{{ caveat }}</v-list-item-title>
                  </v-list-item>
                </v-list>
              </v-card-text>
            </v-card>
          </v-window-item>
        </v-window>

        <!-- Footer -->
        <v-divider class="my-4" />
        <div class="text-caption text-medium-emphasis text-center">
          Simulation completed in {{ results.simulation_duration_seconds.toFixed(2) }} seconds
        </div>
      </v-container>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { format } from 'date-fns'
import { exportSimulationToExcel } from '@/utils/excelExport'

const props = defineProps({
  modelValue: Boolean,
  results: Object
})

const emit = defineEmits(['update:modelValue'])

const dialogModel = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const activeTab = ref('summary')

const close = () => {
  emit('update:modelValue', false)
}

const summaryAlertType = computed(() => {
  const coverage = props.results?.daily_summary?.daily_coverage_pct || 0
  if (coverage >= 100) return 'success'
  if (coverage >= 90) return 'warning'
  return 'error'
})

const summaryText = computed(() => {
  const coverage = props.results?.daily_summary?.daily_coverage_pct || 0
  if (coverage >= 100) return 'Demand can be fully met'
  if (coverage >= 90) return 'Slight shortfall expected'
  return 'Significant shortfall - action needed'
})

const bottlenecks = computed(() => {
  return props.results?.station_performance?.filter(s => s.is_bottleneck) || []
})

const donors = computed(() => {
  return props.results?.station_performance?.filter(s => s.is_donor) || []
})

// Table headers
const weeklyHeaders = [
  { title: 'Product', key: 'product' },
  { title: 'Weekly Demand', key: 'weekly_demand_pcs' },
  { title: 'Weekly Capacity', key: 'max_weekly_capacity_pcs' },
  { title: 'Coverage', key: 'demand_coverage_pct' },
  { title: 'Status', key: 'status' }
]

const stationHeaders = [
  { title: 'Product', key: 'product', width: 100 },
  { title: 'Step', key: 'step', width: 60 },
  { title: 'Operation', key: 'operation' },
  { title: 'Machine/Tool', key: 'machine_tool' },
  { title: 'Operators', key: 'operators', width: 80 },
  { title: 'Utilization', key: 'util_pct', width: 150 },
  { title: 'Queue Wait', key: 'queue_wait_time_min', width: 100 },
  { title: 'BN', key: 'is_bottleneck', width: 50 },
  { title: 'DN', key: 'is_donor', width: 50 }
]

const productHeaders = [
  { title: 'Product', key: 'product' },
  { title: 'Bundle Size', key: 'bundle_size_pcs' },
  { title: 'Mix %', key: 'mix_share_pct' },
  { title: 'Daily Demand', key: 'daily_demand_pcs' },
  { title: 'Daily Output', key: 'daily_throughput_pcs' },
  { title: 'Coverage', key: 'daily_coverage_pct' },
  { title: 'Weekly Demand', key: 'weekly_demand_pcs' },
  { title: 'Weekly Output', key: 'weekly_throughput_pcs' }
]

const bundleHeaders = [
  { title: 'Product', key: 'product' },
  { title: 'Bundle Size', key: 'bundle_size_pcs' },
  { title: 'Bundles/Day', key: 'bundles_arriving_per_day' },
  { title: 'Avg in System', key: 'avg_bundles_in_system' },
  { title: 'Max in System', key: 'max_bundles_in_system' },
  { title: 'Avg Cycle Time', key: 'avg_bundle_cycle_time_min' }
]

const rebalanceHeaders = [
  { title: 'Product', key: 'product' },
  { title: 'Step', key: 'step' },
  { title: 'Operation', key: 'operation' },
  { title: 'Machine', key: 'machine_tool' },
  { title: 'Ops Before', key: 'operators_before' },
  { title: 'Ops After', key: 'operators_after' },
  { title: 'Util Before', key: 'util_before_pct' },
  { title: 'Util After', key: 'util_after_pct' },
  { title: 'Role', key: 'role' },
  { title: 'Action', key: 'comment' }
]

// Helper functions
const getStatusColor = (status) => {
  switch (status) {
    case 'OK': return 'success'
    case 'Tight': return 'warning'
    case 'Shortfall': return 'error'
    default: return 'grey'
  }
}

const getUtilColor = (util) => {
  if (util >= 95) return 'error'
  if (util >= 80) return 'warning'
  if (util <= 50) return 'info'
  return 'success'
}

const getCoverageColor = (coverage) => {
  if (coverage >= 100) return 'success'
  if (coverage >= 90) return 'warning'
  return 'error'
}

const formatTimestamp = (ts) => {
  try {
    return format(new Date(ts), 'PPpp')
  } catch {
    return ts
  }
}

const exportToExcel = async () => {
  if (props.results) {
    await exportSimulationToExcel(props.results, {
      includeAssumptions: true
    })
  }
}
</script>
