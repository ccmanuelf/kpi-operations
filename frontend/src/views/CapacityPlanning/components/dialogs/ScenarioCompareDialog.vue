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
        Scenario Comparison
        <v-spacer />
        <v-btn
          icon="mdi-close"
          variant="text"
          size="small"
          @click="$emit('close')"
        />
      </v-card-title>
      <v-card-text v-if="results" class="pa-4">
        <!-- Comparison Table -->
        <v-table v-if="results.scenarios?.length" density="compact">
          <thead>
            <tr>
              <th>Metric</th>
              <th
                v-for="scenario in results.scenarios"
                :key="scenario.id"
                class="text-center"
              >
                {{ scenario.name }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="font-weight-bold">Total Output</td>
              <td
                v-for="scenario in results.scenarios"
                :key="scenario.id"
                class="text-center"
              >
                <span :class="getBestClass('total_output', scenario.results?.total_output)">
                  {{ scenario.results?.total_output?.toLocaleString() || 'N/A' }}
                </span>
              </td>
            </tr>
            <tr>
              <td class="font-weight-bold">Avg Utilization</td>
              <td
                v-for="scenario in results.scenarios"
                :key="scenario.id"
                class="text-center"
              >
                <span :class="getBestClass('avg_utilization', scenario.results?.avg_utilization)">
                  {{ scenario.results?.avg_utilization?.toFixed(1) || 'N/A' }}%
                </span>
              </td>
            </tr>
            <tr>
              <td class="font-weight-bold">On-Time Delivery</td>
              <td
                v-for="scenario in results.scenarios"
                :key="scenario.id"
                class="text-center"
              >
                <span :class="getBestClass('on_time_rate', scenario.results?.on_time_rate)">
                  {{ scenario.results?.on_time_rate?.toFixed(1) || 'N/A' }}%
                </span>
              </td>
            </tr>
            <tr>
              <td class="font-weight-bold">Total Hours</td>
              <td
                v-for="scenario in results.scenarios"
                :key="scenario.id"
                class="text-center"
              >
                {{ scenario.results?.total_hours?.toFixed(1) || 'N/A' }}
              </td>
            </tr>
            <tr>
              <td class="font-weight-bold">Overtime Hours</td>
              <td
                v-for="scenario in results.scenarios"
                :key="scenario.id"
                class="text-center"
              >
                {{ scenario.results?.overtime_hours?.toFixed(1) || '0' }}
              </td>
            </tr>
            <tr>
              <td class="font-weight-bold">Estimated Cost</td>
              <td
                v-for="scenario in results.scenarios"
                :key="scenario.id"
                class="text-center"
              >
                <span :class="getLowestClass('estimated_cost', scenario.results?.estimated_cost)">
                  ${{ scenario.results?.estimated_cost?.toLocaleString() || 'N/A' }}
                </span>
              </td>
            </tr>
          </tbody>
        </v-table>

        <!-- Recommendation -->
        <v-alert
          v-if="results.recommendation"
          type="info"
          variant="tonal"
          class="mt-4"
        >
          <strong>Recommendation:</strong> {{ results.recommendation }}
        </v-alert>

        <!-- Chart Placeholder -->
        <v-card variant="outlined" class="mt-4">
          <v-card-title class="text-subtitle-1">Visual Comparison</v-card-title>
          <v-card-text>
            <div class="d-flex justify-space-around align-end" style="height: 200px">
              <div
                v-for="scenario in results.scenarios"
                :key="scenario.id"
                class="text-center"
              >
                <div
                  :style="{
                    width: '60px',
                    height: `${Math.min(scenario.results?.avg_utilization || 0, 100) * 1.5}px`,
                    backgroundColor: getBarColor(scenario.results?.avg_utilization)
                  }"
                  class="mx-auto rounded-t"
                />
                <div class="text-caption mt-2">{{ scenario.name }}</div>
                <div class="text-body-2 font-weight-bold">
                  {{ scenario.results?.avg_utilization?.toFixed(1) || 0 }}%
                </div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-card-text>
      <v-card-text v-else class="text-center pa-8 text-grey">
        No comparison results available.
      </v-card-text>
      <v-card-actions>
        <v-btn variant="tonal" @click="exportComparison">
          <v-icon start>mdi-download</v-icon>
          Export Comparison
        </v-btn>
        <v-spacer />
        <v-btn color="primary" @click="$emit('close')">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  results: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'close'])

// Find the best (highest) value for a metric
const getBestValue = (metric) => {
  if (!props.results?.scenarios) return null
  const values = props.results.scenarios
    .map(s => s.results?.[metric])
    .filter(v => v !== null && v !== undefined)
  return values.length > 0 ? Math.max(...values) : null
}

// Find the lowest value for a metric (for cost)
const getLowestValue = (metric) => {
  if (!props.results?.scenarios) return null
  const values = props.results.scenarios
    .map(s => s.results?.[metric])
    .filter(v => v !== null && v !== undefined)
  return values.length > 0 ? Math.min(...values) : null
}

const getBestClass = (metric, value) => {
  const best = getBestValue(metric)
  if (best !== null && value === best) {
    return 'text-success font-weight-bold'
  }
  return ''
}

const getLowestClass = (metric, value) => {
  const lowest = getLowestValue(metric)
  if (lowest !== null && value === lowest) {
    return 'text-success font-weight-bold'
  }
  return ''
}

const getBarColor = (utilization) => {
  if (!utilization) return '#e0e0e0'
  if (utilization >= 100) return '#f44336'
  if (utilization >= 90) return '#ff9800'
  if (utilization >= 70) return '#4caf50'
  return '#2196f3'
}

const exportComparison = () => {
  if (!props.results) return

  const json = JSON.stringify(props.results, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `scenario-comparison-${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  URL.revokeObjectURL(url)
}
</script>
