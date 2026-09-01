<template>
  <v-dialog
    :model-value="modelValue"
    max-width="900"
    scrollable
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="d-flex align-center bg-info text-white">
        <v-icon start>mdi-compare</v-icon>
        {{ t('capacityPlanning.compare.title') }}
        <v-spacer />
        <v-btn
          icon="mdi-close"
          variant="text"
          size="small"
          @click="$emit('close')"
        />
      </v-card-title>

      <v-card-text v-if="rows.length" class="pa-4">
        <v-table density="compact">
          <thead>
            <tr>
              <th>{{ t('capacityPlanning.compare.metric') }}</th>
              <th v-for="row in rows" :key="row.scenario_id" class="text-center">
                {{ row.scenario_name }}
                <div v-if="row.scenario_type" class="text-caption text-medium-emphasis">
                  {{ row.scenario_type }}
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="metric in METRICS" :key="metric.field">
              <td class="font-weight-bold">{{ t(metric.label) }}</td>
              <td v-for="row in rows" :key="row.scenario_id" class="text-center">
                <span :class="highlightClass(metric, row[metric.field])">
                  {{ format(metric, row[metric.field]) }}
                </span>
              </td>
            </tr>
          </tbody>
        </v-table>

        <v-card variant="outlined" class="mt-4">
          <v-card-title class="text-subtitle-1">
            {{ t('capacityPlanning.compare.visualComparison') }}
          </v-card-title>
          <v-card-text>
            <div class="d-flex justify-space-around align-end" style="height: 200px">
              <div v-for="row in rows" :key="row.scenario_id" class="text-center">
                <div
                  :style="{
                    width: '60px',
                    height: `${Math.min(row.modified_utilization || 0, 100) * 1.5}px`,
                    backgroundColor: barColor(row.modified_utilization),
                  }"
                  class="mx-auto rounded-t"
                />
                <div class="text-caption mt-2">{{ row.scenario_name }}</div>
                <div class="text-body-2 font-weight-bold">
                  {{ (row.modified_utilization ?? 0).toFixed(1) }}%
                </div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-card-text>

      <v-card-text v-else class="text-center pa-8 text-grey">
        {{ t('capacityPlanning.compare.noResults') }}
      </v-card-text>

      <v-card-actions>
        <v-btn variant="tonal" @click="exportComparison">
          <v-icon start>mdi-download</v-icon>
          {{ t('capacityPlanning.compare.exportComparison') }}
        </v-btn>
        <v-spacer />
        <v-btn color="primary" @click="$emit('close')">{{ t('common.close') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
  // POST /api/capacity/scenarios/compare answers with a bare ARRAY of
  // comparison rows. It used to be read as `results.scenarios[]` with a nested
  // `results` object per scenario -- a shape the API has never sent -- so the
  // table's `v-if` was always false and the dialog opened empty. Typed Array
  // here so the mismatch cannot come back silently.
  results: {
    type: Array,
    default: null,
  },
})

defineEmits(['update:modelValue', 'close'])

//: The response's own field names, in the order a planner reads them:
//: what capacity was, what the plan makes it, and what that costs.
//: `better` says which direction wins, so one comparison can highlight a
//: high capacity gain and a low cost with the same code path.
const METRICS = [
  {
    field: 'original_capacity_hours',
    label: 'capacityPlanning.compare.capacityBefore',
    unit: 'hours',
    better: null,
  },
  {
    field: 'modified_capacity_hours',
    label: 'capacityPlanning.compare.capacityAfter',
    unit: 'hours',
    better: 'high',
  },
  {
    field: 'capacity_increase_percent',
    label: 'capacityPlanning.compare.capacityIncrease',
    unit: 'percent',
    better: 'high',
  },
  {
    field: 'original_utilization',
    label: 'capacityPlanning.compare.utilizationBefore',
    unit: 'percent',
    better: null,
  },
  {
    field: 'modified_utilization',
    label: 'capacityPlanning.compare.utilizationAfter',
    unit: 'percent',
    better: null,
  },
  {
    field: 'bottlenecks_resolved',
    label: 'capacityPlanning.compare.bottlenecksResolved',
    unit: 'count',
    better: 'high',
  },
  {
    field: 'cost_impact',
    label: 'capacityPlanning.compare.costImpact',
    unit: 'currency',
    better: 'low',
  },
]

const rows = computed(() => (Array.isArray(props.results) ? props.results : []))

const format = (metric, value) => {
  if (value === null || value === undefined) return t('common.na')
  if (metric.unit === 'percent') return `${Number(value).toFixed(1)}%`
  if (metric.unit === 'currency') return `$${Number(value).toLocaleString()}`
  if (metric.unit === 'count') return String(value)
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })
}

//: Only highlights when the rows actually DISAGREE. Marking a winner when
//: every scenario reports the same number -- which is what an unseeded
//: capacity module produces -- would tell a reader one plan beat another when
//: nothing distinguished them.
const highlightClass = (metric, value) => {
  if (!metric.better || value === null || value === undefined) return ''
  const values = rows.value
    .map((r) => r[metric.field])
    .filter((v) => v !== null && v !== undefined)
    .map(Number)
  if (values.length < 2) return ''
  const best = metric.better === 'high' ? Math.max(...values) : Math.min(...values)
  const worst = metric.better === 'high' ? Math.min(...values) : Math.max(...values)
  if (best === worst) return ''
  return Number(value) === best ? 'text-success font-weight-bold' : ''
}

const barColor = (utilization) => {
  if (!utilization) return '#e0e0e0'
  if (utilization >= 100) return '#f44336'
  if (utilization >= 90) return '#ff9800'
  if (utilization >= 70) return '#4caf50'
  return '#2196f3'
}

const exportComparison = () => {
  if (!rows.value.length) return
  const json = JSON.stringify(rows.value, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `scenario-comparison-${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  URL.revokeObjectURL(url)
}
</script>
