<template>
  <v-card variant="outlined" class="dual-view-kpi-panel">
    <v-card-title v-if="title || $slots.actions" class="d-flex align-center pa-3">
      <span class="text-subtitle-1 font-weight-bold">{{ title || $t('dualView.panel.title') }}</span>
      <v-spacer />
      <slot name="actions">
        <DualViewToggle />
      </slot>
    </v-card-title>

    <v-card-text class="pa-3">
      <v-alert v-if="error" type="error" density="compact" variant="tonal" class="mb-3" closable @click:close="error = null">
        {{ error }}
      </v-alert>

      <v-row dense>
        <v-col v-for="metric in METRICS" :key="metric.kpiKey" cols="12" sm="4">
          <v-card
            variant="outlined"
            class="kpi-tile h-100"
            :class="{ clickable: !!getResult(metric.kpiKey) }"
            hover
            @click="handleTileClick(metric.kpiKey)"
          >
            <v-card-text class="pa-3 text-center">
              <div class="d-flex align-center justify-center mb-1">
                <v-icon :color="metric.color" class="mr-2">{{ metric.icon }}</v-icon>
                <span class="text-caption text-medium-emphasis">{{ $t(metric.labelKey) }}</span>
                <v-icon
                  v-if="getResult(metric.kpiKey)?.assumptions_applied_count"
                  size="x-small"
                  color="warning"
                  class="ml-1"
                >
                  mdi-tune
                </v-icon>
              </div>

              <div v-if="loading[metric.kpiKey]" class="d-flex justify-center pa-2">
                <v-progress-circular indeterminate size="24" :color="metric.color" />
              </div>

              <div v-else-if="getResult(metric.kpiKey)" class="text-h4 font-weight-bold" :class="`text-${metric.color}`">
                {{ formatValue(getResult(metric.kpiKey)) }}
              </div>

              <div v-else class="text-h4 text-medium-emphasis">—</div>

              <div
                v-if="getResult(metric.kpiKey)?.delta !== null && getResult(metric.kpiKey)?.delta !== 0"
                class="text-caption mt-1"
                :class="deltaColor(getResult(metric.kpiKey))"
              >
                Δ {{ formatDelta(getResult(metric.kpiKey)) }}
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <div class="text-caption text-medium-emphasis mt-2 d-flex align-center ga-2">
        <v-icon size="x-small">{{ dualViewStore.isStandard ? 'mdi-book-open-outline' : 'mdi-tune' }}</v-icon>
        <span>{{ dualViewStore.isStandard ? $t('dualView.panel.showingStandard') : $t('dualView.panel.showingSiteAdjusted') }}</span>
      </div>
    </v-card-text>

    <MetricInspector v-model="inspectorOpen" :result-id="inspectorResultId" />
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import DualViewToggle from '@/components/dual_view/DualViewToggle.vue'
import MetricInspector from '@/components/dual_view/MetricInspector.vue'
import { useDualViewStore } from '@/stores/dualViewStore'
import {
  calculateFPYFromPeriod,
  calculateOEEFromPeriod,
  calculateOTDFromPeriod,
  type DualViewCalculateResponse,
} from '@/services/api/dualViewCalc'

interface Props {
  clientId: string | null
  periodStart: string | Date | null
  periodEnd: string | Date | null
  title?: string | null
  // Optional partition filters passed through to the aggregator. Filters
  // not applicable to a metric's source tables are silently ignored
  // server-side.
  lineId?: number | null
  shiftId?: number | null
  productId?: number | null
  workOrderId?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  title: null,
  lineId: null,
  shiftId: null,
  productId: null,
  workOrderId: null,
})

useI18n() // template uses $t directly
const dualViewStore = useDualViewStore()

const METRICS = [
  { kpiKey: 'oee', labelKey: 'kpi.oee', icon: 'mdi-factory', color: 'primary' },
  { kpiKey: 'otd', labelKey: 'kpi.otd', icon: 'mdi-truck-delivery', color: 'info' },
  { kpiKey: 'fpy', labelKey: 'kpi.fpy', icon: 'mdi-star-circle', color: 'success' },
] as const

type MetricKey = (typeof METRICS)[number]['kpiKey']

const results = reactive<Record<MetricKey, DualViewCalculateResponse | null>>({
  oee: null,
  otd: null,
  fpy: null,
})
const loading = reactive<Record<MetricKey, boolean>>({
  oee: false,
  otd: false,
  fpy: false,
})
const error = ref<string | null>(null)

const inspectorOpen = ref(false)
const inspectorResultId = ref<number | null>(null)

const getResult = (key: MetricKey) => results[key]

const toIso = (value: string | Date | null): string | null => {
  if (!value) return null
  if (value instanceof Date) return value.toISOString()
  try {
    return new Date(value).toISOString()
  } catch {
    return null
  }
}

const buildBody = computed(() => {
  const start = toIso(props.periodStart)
  const end = toIso(props.periodEnd)
  if (!props.clientId || !start || !end) return null
  return {
    client_id: props.clientId,
    period_start: start,
    period_end: end,
    line_id: props.lineId ?? undefined,
    shift_id: props.shiftId ?? undefined,
    product_id: props.productId ?? undefined,
    work_order_id: props.workOrderId ?? undefined,
  }
})

const fetchAll = async () => {
  const body = buildBody.value
  if (!body) {
    error.value = null
    return
  }

  error.value = null
  const tasks: Array<[MetricKey, ReturnType<typeof calculateOEEFromPeriod>]> = [
    ['oee', calculateOEEFromPeriod(body)],
    ['otd', calculateOTDFromPeriod(body)],
    ['fpy', calculateFPYFromPeriod(body)],
  ]
  for (const [key] of tasks) loading[key] = true

  for (const [key, promise] of tasks) {
    try {
      const response = await promise
      results[key] = response.data
    } catch (err) {
      results[key] = null
      error.value = err instanceof Error ? err.message : `Failed to load ${key}`
    } finally {
      loading[key] = false
    }
  }
}

const handleTileClick = (key: MetricKey) => {
  const result = results[key]
  if (!result) return
  inspectorResultId.value = result.result_id
  inspectorOpen.value = true
}

const formatValue = (result: DualViewCalculateResponse | null): string => {
  if (!result) return '—'
  const raw = dualViewStore.isStandard ? result.standard_value : result.site_adjusted_value
  const num = Number(raw)
  if (!Number.isFinite(num)) return String(raw)
  return `${num.toFixed(2)}%`
}

const formatDelta = (result: DualViewCalculateResponse | null): string => {
  if (!result?.delta) return ''
  const sign = result.delta > 0 ? '+' : ''
  const pct =
    result.delta_pct !== null && result.delta_pct !== undefined
      ? ` (${result.delta_pct > 0 ? '+' : ''}${result.delta_pct.toFixed(2)}%)`
      : ''
  return `${sign}${result.delta.toFixed(2)}${pct}`
}

const deltaColor = (result: DualViewCalculateResponse | null): string => {
  if (!result?.delta) return 'text-medium-emphasis'
  return result.delta > 0 ? 'text-success' : 'text-warning'
}

// Initial fetch + auto-refetch when client/period/filters change
watch(
  () => [
    props.clientId,
    toIso(props.periodStart),
    toIso(props.periodEnd),
    props.lineId,
    props.shiftId,
    props.productId,
    props.workOrderId,
  ],
  () => {
    fetchAll()
  },
  { immediate: false }
)

onMounted(() => {
  fetchAll()
})
</script>

<style scoped>
.kpi-tile.clickable {
  cursor: pointer;
  transition: transform 80ms ease-out;
}
.kpi-tile.clickable:hover {
  transform: translateY(-1px);
}
.dual-view-kpi-panel {
  /* Keeps the panel visually distinct from native v-cards */
}
</style>
