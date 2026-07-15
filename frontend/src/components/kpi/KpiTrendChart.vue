<template>
  <v-card>
    <v-card-title class="d-flex align-center flex-wrap ga-2">
      <span>{{ title }}</span>
      <v-spacer />
      <v-select
        :model-value="rangeKey"
        :items="options"
        item-title="title"
        item-value="value"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width: 160px"
        @update:model-value="onRangeChange"
      />
    </v-card-title>
    <v-card-text>
      <v-alert v-if="error" type="error" variant="tonal" density="compact">
        {{ $t('common.loadError') }}
      </v-alert>
      <v-alert v-else-if="!loading && points.length === 0" type="info" variant="tonal" density="compact">
        {{ $t('kpi.noTrendData') }}
      </v-alert>
      <Line v-else :data="chartData" :options="chartOptions" />
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend,
  LineController,
  type ChartData,
  type ChartDataset,
  type ChartOptions,
  type TooltipItem,
} from 'chart.js'
import { computeKpiRange, useKpiChartRange, type KpiRangeKey } from '@/composables/useKpiChartRange'
import { useChartTheme } from '@/composables/useChartTheme'
import { computeOutOfControl, type OocPoint, type OocThreshold } from '@/utils/outOfControl'
import { fetchActiveAlertsForKpi } from '@/services/api/kpi'
import { unwrapTrend } from './kpiChartConfig'

ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, LineController)

interface Props {
  metricKey: string
  title: string
  threshold: OocThreshold | null
  clientId?: string | null
  unit?: string
  fetchTrend: (_params: Record<string, unknown>) => Promise<unknown>
  alertKey?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  clientId: null,
  unit: '',
  alertKey: null,
})

const { t } = useI18n()
const { options } = useKpiChartRange()
const { chartColors, scaleDefaults, legendDefaults } = useChartTheme()

const rangeKey = ref<KpiRangeKey>('last90Days')
const rawPoints = ref<{ date: string; value: number }[]>([])
const points = ref<OocPoint[]>([])
const oocMeta = ref<{ ucl: number | null; lcl: number | null; target: number | null; critical: number | null }>({
  ucl: null,
  lcl: null,
  target: null,
  critical: null,
})
const alertMessage = ref<string | null>(null)
const loading = ref(false)
const error = ref(false)

// Recompute the OOC result (and hence chart datasets) whenever the fetched
// series OR the threshold changes. The threshold typically arrives after
// this component has already mounted and fetched (the parent loads it
// asynchronously), so this must NOT depend solely on load()'s fetch path.
watch(
  [rawPoints, () => props.threshold],
  ([raw, threshold]) => {
    const result = computeOutOfControl(raw, threshold)
    points.value = result.points
    oocMeta.value = { ucl: result.ucl, lcl: result.lcl, target: result.target, critical: result.critical }
  },
  { immediate: true },
)

const load = async () => {
  loading.value = true
  error.value = false
  alertMessage.value = null
  try {
    const { start, end } = computeKpiRange(rangeKey.value)
    const res = await props.fetchTrend({
      start_date: start,
      end_date: end,
      client_id: props.clientId ?? undefined,
    })
    rawPoints.value = unwrapTrend(res)

    if (props.alertKey && rawPoints.value.length > 0) {
      try {
        const alerts = await fetchActiveAlertsForKpi(props.alertKey, props.clientId ?? null)
        const latest = Array.isArray(alerts) ? alerts[0] : null
        if (latest) {
          alertMessage.value = latest.recommendation ? `${latest.message} — ${latest.recommendation}` : latest.message
        }
      } catch {
        // Alert enrichment is best-effort — the chart still renders without it.
      }
    }
  } catch {
    rawPoints.value = []
    error.value = true
  } finally {
    loading.value = false
  }
}

const onRangeChange = (key: KpiRangeKey) => {
  rangeKey.value = key
  void load()
}

onMounted(load)
watch(() => props.clientId, load)

defineExpose({ onRangeChange })

const buildFlatDataset = (value: number, label: string, color: string, length: number) => ({
  label,
  data: Array(length).fill(value),
  borderColor: color,
  borderDash: [6, 4],
  pointRadius: 0,
  fill: false,
})

const chartData = computed<ChartData<'line'>>(() => {
  const pts = points.value
  const mainColor = chartColors.value.blue
  const oocColor = chartColors.value.red

  const dataset = {
    label: props.title,
    data: pts.map((p) => p.value),
    borderColor: mainColor,
    backgroundColor: chartColors.value.blueFill,
    tension: 0.25,
    fill: true,
    spanGaps: true,
    pointRadius: pts.map((p) => (p.ooc ? 7 : 3)),
    pointBackgroundColor: pts.map(() => mainColor),
    pointBorderColor: pts.map((p) => (p.ooc ? oocColor : mainColor)),
    pointBorderWidth: pts.map((p) => (p.ooc ? 3 : 1)),
  }

  const datasets: ChartDataset<'line'>[] = [dataset]
  const { target, critical, ucl, lcl } = oocMeta.value
  if (target !== null) datasets.push(buildFlatDataset(target, t('kpi.target'), chartColors.value.orange, pts.length))
  if (critical !== null) datasets.push(buildFlatDataset(critical, t('kpi.criticalLine'), oocColor, pts.length))
  if (ucl !== null) datasets.push(buildFlatDataset(ucl, t('kpi.controlLimit'), chartColors.value.purple, pts.length))
  if (lcl !== null) datasets.push(buildFlatDataset(lcl, t('kpi.controlLimit'), chartColors.value.purple, pts.length))

  return {
    labels: pts.map((p) => format(new Date(p.date), 'MMM dd')),
    datasets,
  }
})

const tooltipLabel = (ctx: TooltipItem<'line'>): string | string[] => {
  const unitSuffix = props.unit ? ` ${props.unit}` : ''
  const base = `${ctx.dataset.label}: ${ctx.formattedValue}${unitSuffix}`
  if (ctx.datasetIndex !== 0) return base

  const lines = [base]
  const point: OocPoint | undefined = points.value[ctx.dataIndex]
  if (point?.ooc) {
    for (const reason of point.reasons) lines.push(t(reason.key, reason.args))
  }
  if (alertMessage.value && ctx.dataIndex === points.value.length - 1) {
    lines.push(alertMessage.value)
  }
  return lines
}

const chartOptions = computed<ChartOptions<'line'>>(() => ({
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: { display: true, position: 'top', labels: legendDefaults.value.labels },
    tooltip: {
      mode: 'index',
      intersect: false,
      callbacks: { label: tooltipLabel },
    },
  },
  scales: {
    y: { ticks: scaleDefaults.value.ticks, grid: scaleDefaults.value.grid },
    x: { ticks: scaleDefaults.value.ticks, grid: scaleDefaults.value.grid },
  },
  interaction: { mode: 'nearest', axis: 'x', intersect: false },
}))
</script>
