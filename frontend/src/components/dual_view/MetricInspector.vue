<template>
  <v-navigation-drawer
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    location="right"
    temporary
    width="640"
  >
    <v-card flat class="rounded-0 d-flex flex-column" style="height: 100%">
      <!-- Header -->
      <v-card-title class="d-flex justify-space-between align-center py-4 px-6 bg-primary text-white">
        <div>
          <div class="text-h6 font-weight-bold">
            {{ lineage?.metric_display_name || $t('dualView.inspector.title') }}
          </div>
          <div v-if="lineage" class="text-body-2 opacity-90">
            {{ formatPeriod(lineage.period_start, lineage.period_end) }}
          </div>
        </div>
        <v-btn icon variant="text" color="white" @click="$emit('update:modelValue', false)">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text class="pa-0 flex-grow-1 overflow-y-auto">
        <!-- Loading -->
        <div v-if="loading" class="d-flex justify-center align-center pa-8">
          <v-progress-circular indeterminate color="primary" />
        </div>

        <!-- Error -->
        <v-alert
          v-else-if="error"
          type="error"
          variant="tonal"
          class="ma-6"
        >
          {{ error }}
        </v-alert>

        <!-- Lineage details -->
        <template v-else-if="lineage">
          <!-- Standard vs Site-Adjusted values -->
          <div class="px-6 py-4 bg-surface-light">
            <v-row dense>
              <v-col cols="6" class="text-center">
                <div class="text-caption text-medium-emphasis">
                  {{ $t('dualView.inspector.standard') }}
                </div>
                <div class="text-h4 font-weight-bold">
                  {{ formatValue(lineage.standard_value) }}
                </div>
              </v-col>
              <v-col cols="6" class="text-center">
                <div class="text-caption text-medium-emphasis">
                  {{ $t('dualView.inspector.siteAdjusted') }}
                </div>
                <div class="text-h4 font-weight-bold" :class="adjustedColor">
                  {{ formatValue(lineage.site_adjusted_value) }}
                </div>
              </v-col>
            </v-row>
            <v-row v-if="lineage.delta !== null && lineage.delta !== 0" dense class="mt-2">
              <v-col cols="12" class="text-center">
                <v-chip
                  :color="lineage.delta > 0 ? 'success' : 'warning'"
                  variant="tonal"
                  size="small"
                >
                  Δ {{ lineage.delta > 0 ? '+' : '' }}{{ lineage.delta?.toFixed(2) }}
                  <span v-if="lineage.delta_pct !== null">
                    ({{ lineage.delta_pct > 0 ? '+' : '' }}{{ lineage.delta_pct.toFixed(2) }}%)
                  </span>
                </v-chip>
              </v-col>
            </v-row>
          </div>

          <v-divider />

          <!-- Formula -->
          <div class="px-6 py-4">
            <div class="text-subtitle-2 font-weight-bold mb-2">
              {{ $t('dualView.inspector.formula') }}
            </div>
            <v-card variant="outlined" class="pa-3 bg-surface">
              <code class="text-body-2">{{ lineage.formula }}</code>
            </v-card>
            <div v-if="lineage.description" class="text-caption text-medium-emphasis mt-2">
              {{ lineage.description }}
            </div>
          </div>

          <v-divider />

          <!-- Inputs table -->
          <div class="px-6 py-4">
            <div class="text-subtitle-2 font-weight-bold mb-2">
              {{ $t('dualView.inspector.inputs') }}
            </div>
            <v-table density="compact">
              <tbody>
                <tr v-for="(value, key) in lineage.inputs" :key="key">
                  <td class="text-medium-emphasis" style="width: 45%">
                    <div class="font-weight-medium">{{ key }}</div>
                    <div
                      v-if="lineage.inputs_help[key]"
                      class="text-caption text-medium-emphasis"
                      style="line-height: 1.2"
                    >
                      {{ lineage.inputs_help[key] }}
                    </div>
                  </td>
                  <td class="text-right">{{ formatInputValue(value) }}</td>
                </tr>
              </tbody>
            </v-table>
          </div>

          <v-divider />

          <!-- Assumptions applied -->
          <div class="px-6 py-4">
            <div class="text-subtitle-2 font-weight-bold mb-2">
              {{ $t('dualView.inspector.assumptions') }}
              <v-chip size="x-small" class="ml-2">
                {{ lineage.assumptions_applied.length }}
              </v-chip>
            </div>
            <div
              v-if="lineage.assumptions_applied.length === 0"
              class="text-body-2 text-medium-emphasis"
            >
              {{ $t('dualView.inspector.noAssumptions') }}
            </div>
            <v-expansion-panels
              v-else
              variant="accordion"
              multiple
            >
              <v-expansion-panel
                v-for="a in lineage.assumptions_applied"
                :key="a.assumption_id || a.name"
              >
                <v-expansion-panel-title>
                  <div class="d-flex align-center justify-space-between" style="width: 100%">
                    <div>
                      <div class="font-weight-medium">{{ a.name }}</div>
                      <div class="text-caption text-medium-emphasis">
                        {{ formatInputValue(a.value) }}
                      </div>
                    </div>
                  </div>
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <div v-if="a.description" class="text-body-2 mb-2">
                    {{ a.description }}
                  </div>
                  <div v-if="a.rationale" class="text-body-2 mb-2">
                    <span class="font-weight-medium">{{ $t('dualView.inspector.rationale') }}:</span>
                    {{ a.rationale }}
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    <div v-if="a.approved_by">
                      {{ $t('dualView.inspector.approvedBy') }}: {{ a.approved_by }}
                    </div>
                    <div v-if="a.approved_at">
                      {{ $t('dualView.inspector.approvedAt') }}: {{ formatDate(a.approved_at) }}
                    </div>
                  </div>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>

          <v-divider />

          <!-- Footer -->
          <div class="px-6 py-3 text-caption text-medium-emphasis">
            <div>
              {{ $t('dualView.inspector.calculatedAt') }}:
              {{ formatDate(lineage.calculated_at) }}
            </div>
            <div v-if="lineage.calculated_by">
              {{ $t('dualView.inspector.calculatedBy') }}: {{ lineage.calculated_by }}
            </div>
          </div>
        </template>
      </v-card-text>
    </v-card>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMetricLineage } from '@/composables/useMetricLineage'

interface Props {
  modelValue: boolean
  resultId: number | null
}

const props = defineProps<Props>()
defineEmits<{ 'update:modelValue': [value: boolean] }>()

useI18n() // template uses $t directly; keep i18n initialised
const { lineage, loading, error, load, clear } = useMetricLineage()

watch(
  () => props.resultId,
  (id) => {
    if (id !== null) {
      load(id)
    } else {
      clear()
    }
  },
  { immediate: true }
)

const adjustedColor = computed(() => {
  if (!lineage.value || lineage.value.delta === null) return ''
  return lineage.value.delta > 0 ? 'text-success' : lineage.value.delta < 0 ? 'text-warning' : ''
})

const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) return '–'
  if (typeof value === 'number') return value.toFixed(2)
  if (typeof value === 'string') {
    const num = Number(value)
    return Number.isFinite(num) ? num.toFixed(2) : value
  }
  return String(value)
}

const formatInputValue = (value: unknown): string => {
  if (value === null || value === undefined) return '–'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

const formatPeriod = (start: string, end: string): string => {
  const s = new Date(start).toLocaleDateString()
  const e = new Date(end).toLocaleDateString()
  return `${s} – ${e}`
}

const formatDate = (iso: string): string => {
  return new Date(iso).toLocaleString()
}
</script>
