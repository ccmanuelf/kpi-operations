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
  Filler,
  type ChartData,
  type ChartDataset,
  type ChartOptions,
  type TooltipItem,
} from 'chart.js'
import { computeKpiRange, useKpiChartRange, type KpiRangeKey } from '@/composables/useKpiChartRange'
import { useChartTheme } from '@/composables/useChartTheme'
import { computeOutOfControl, type OocPoint, type OocThreshold } from '@/utils/outOfControl'
import { fetchActiveAlertsForKpi, fetchKpiCauses, type KpiCause } from '@/services/api/kpi'
import { unwrapTrend } from './kpiChartConfig'

// Filler is required whenever a dataset sets `fill: true` (the main series
// below does) — without it Chart.js silently no-ops the fill and logs
// "Tried to use the 'fill' option without the 'Filler' plugin enabled"
// on every render (ISSUE 005; 10x per KPI Dashboard load, one per card).
ChartJS.register(LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Legend, LineController, Filler)

// Percentage metrics can never fall outside 0-100; clamping control limits
// to this domain before charting keeps a sigma-inflated UCL/LCL from
// dragging the y-axis out to absurd values (ISSUE 004).
const PERCENT_DOMAIN: [number, number] = [0, 100]

interface Props {
  metricKey: string
  title: string
  threshold: OocThreshold | null
  clientId?: string | null
  unit?: string
  fetchTrend: (_params: Record<string, unknown>) => Promise<unknown>
  alertKey?: string | null
  causeDriven?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  clientId: null,
  unit: '',
  alertKey: null,
  causeDriven: false,
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
    const result = computeOutOfControl(raw, threshold, {
      domain: props.unit === '%' ? PERCENT_DOMAIN : undefined,
    })
    points.value = result.points
    oocMeta.value = { ucl: result.ucl, lcl: result.lcl, target: result.target, critical: result.critical }
  },
  { immediate: true },
)

const causes = ref<Record<string, KpiCause>>({})
let causeSeq = 0

// After OOC points are (re)computed, fetch causes for the sparse OOC dates.
// Guarded so a stale response cannot overwrite a newer one; best-effort.
watch(
  points,
  async (pts) => {
    if (!props.causeDriven) return
    const oocDates = pts.filter((p) => p.ooc).map((p) => p.date)
    if (oocDates.length === 0) {
      causeSeq++ // invalidate any in-flight cause fetch
      causes.value = {}
      return
    }
    const seq = ++causeSeq
    try {
      const map = await fetchKpiCauses(props.metricKey, oocDates, props.clientId ?? null)
      if (seq !== causeSeq) return
      causes.value = map
    } catch {
      // best-effort — SP1 tooltip remains
    }
  },
  { immediate: true },
)

// Monotonic request id: a rapid range/client change can start a second load()
// while the first is in flight; without this guard an earlier fetch resolving
// AFTER a later one would overwrite rawPoints with stale data (chart shows the
// wrong range). Each load() claims the next seq; a resolved fetch only applies
// if it is still the latest request.
let loadSeq = 0

const load = async () => {
  const seq = ++loadSeq
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
    if (seq !== loadSeq) return // superseded by a newer load() — discard this stale response
    rawPoints.value = unwrapTrend(res)

    if (props.alertKey && rawPoints.value.length > 0) {
      try {
        const alerts = await fetchActiveAlertsForKpi(props.alertKey, props.clientId ?? null)
        if (seq !== loadSeq) return
        const latest = Array.isArray(alerts) ? alerts[0] : null
        if (latest) {
          alertMessage.value = latest.recommendation ? `${latest.message} — ${latest.recommendation}` : latest.message
        }
      } catch {
        // Alert enrichment is best-effort — the chart still renders without it.
      }
    }
  } catch {
    if (seq === loadSeq) {
      rawPoints.value = []
      error.value = true
    }
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

const onRangeChange = (key: KpiRangeKey) => {
  rangeKey.value = key
  void load()
}

onMounted(load)
watch(() => props.clientId, load)

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
  const cause = point?.ooc ? causes.value[point.date] : undefined
  if (cause?.factor) {
    const factorLabel =
      cause.kind === 'component' ? t(`kpi.${cause.factor}`) : cause.factor
    lines.push(
      t(`kpi.cause.${cause.kind}`, {
        factor: factorLabel,
        value: cause.value ?? '',
        unit: cause.unit,
        share: cause.share != null ? Math.round(cause.share * 100) : '',
      }),
    )
  }
  if (alertMessage.value && ctx.dataIndex === points.value.length - 1) {
    lines.push(alertMessage.value)
  }
  return lines
}

defineExpose({ onRangeChange, tooltipLabel })

// Chart.js auto-scales the y-axis tightly around whatever datasets are
// rendered. With no control limits present (SPC arm didn't trigger — too
// few points, or zero variance) a near-constant metric like Quality
// (99.16-99.18%) gets an axis spanning only that sliver, exaggerating
// noise-level movement (over-zoom observation). Padding the observed range
// by a fixed fraction keeps small series readable without re-widening the
// axis the way the (now-clamped) control limits used to.
const yAxisRange = computed<{ min: number | undefined; max: number | undefined }>(() => {
  const values = points.value.map((p) => p.value).filter((v) => Number.isFinite(v))
  const { target, critical, ucl, lcl } = oocMeta.value
  for (const v of [target, critical, ucl, lcl]) {
    if (v !== null) values.push(v)
  }
  if (values.length === 0) return { min: undefined, max: undefined }

  let min = Math.min(...values)
  let max = Math.max(...values)
  const range = max - min
  const pad = range > 0 ? range * 0.15 : Math.max(Math.abs(max) * 0.05, 1)
  min -= pad
  max += pad

  // No KPI rendered by this chart can legitimately be negative — floor the
  // padded min at 0 for every metric. Percentage metrics already got this
  // via PERCENT_DOMAIN[0] below; non-percentage-but-still-non-negative
  // metrics (e.g. PPM) previously had no floor at all, so heavy
  // proportional padding on a small series could push the axis well below
  // zero (live-VM evidence: a PPM chart padded to a min of -687).
  min = Math.max(min, 0)

  if (props.unit === '%') {
    min = Math.max(min, PERCENT_DOMAIN[0])
    max = Math.min(max, PERCENT_DOMAIN[1])
  }
  return { min, max }
})

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
    y: {
      ticks: scaleDefaults.value.ticks,
      grid: scaleDefaults.value.grid,
      min: yAxisRange.value.min,
      max: yAxisRange.value.max,
    },
    x: { ticks: scaleDefaults.value.ticks, grid: scaleDefaults.value.grid },
  },
  interaction: { mode: 'nearest', axis: 'x', intersect: false },
}))
</script>
