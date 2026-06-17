/**
 * Composable for KPI Dashboard display helpers — card formatting,
 * status colors, progress bars, tooltip text, summary table data.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useKPIStore, type KPISummary, type StatusColor } from '@/stores/kpi'

export interface KpiTooltip {
  title: string
  formula: string | null
  meaning: string
}

export interface SummaryItem {
  title: string
  value: string
  target: string
  status: StatusColor
  statusText: string
  trendIcon: string
  trendColor: string
  route: string
}

export interface SummaryHeader {
  title: string
  key: string
  sortable: boolean
  width?: number
}

export function useKPIDashboardHelpers() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  const kpiTooltips = computed<Record<string, KpiTooltip>>(() => ({
    efficiency: {
      title: t('kpi.tooltips.formulaLabel'),
      formula: t('kpi.tooltips.efficiency.formula'),
      meaning: t('kpi.tooltips.efficiency.meaning'),
    },
    wipAging: {
      title: t('kpi.tooltips.formulaLabel'),
      formula: t('kpi.tooltips.wipAging.formula'),
      meaning: t('kpi.tooltips.wipAging.meaning'),
    },
    onTimeDelivery: {
      title: t('kpi.tooltips.formulaLabel'),
      formula: t('kpi.tooltips.onTimeDelivery.formula'),
      meaning: t('kpi.tooltips.onTimeDelivery.meaning'),
    },
    availability: {
      title: t('kpi.tooltips.formulaLabel'),
      formula: t('kpi.tooltips.availability.formula'),
      meaning: t('kpi.tooltips.availability.meaning'),
    },
    performance: {
      title: t('kpi.tooltips.formulaLabel'),
      formula: t('kpi.tooltips.performance.formula'),
      meaning: t('kpi.tooltips.performance.meaning'),
    },
    quality: {
      title: t('kpi.tooltips.formulaLabel'),
      formula: t('kpi.tooltips.quality.formula'),
      meaning: t('kpi.tooltips.quality.meaning'),
    },
    oee: {
      title: t('kpi.tooltips.formulaLabel'),
      formula: t('kpi.tooltips.oee.formula'),
      meaning: t('kpi.tooltips.oee.meaning'),
    },
    absenteeism: {
      title: t('kpi.tooltips.formulaLabel'),
      formula: t('kpi.tooltips.absenteeism.formula'),
      meaning: t('kpi.tooltips.absenteeism.meaning'),
    },
    defectRates: {
      title: t('kpi.tooltips.formulaLabel'),
      formula: t('kpi.tooltips.defectRates.formula'),
      meaning: t('kpi.tooltips.defectRates.meaning'),
    },
    throughputTime: {
      title: t('kpi.tooltips.formulaLabel'),
      formula: t('kpi.tooltips.throughputTime.formula'),
      meaning: t('kpi.tooltips.throughputTime.meaning'),
    },
  }))

  const defaultTooltip = computed<KpiTooltip>(() => ({
    title: t('kpi.tooltips.infoLabel'),
    formula: null,
    meaning: t('kpi.tooltips.defaultMeaning'),
  }))

  const formatValue = (value: number | null | undefined, unit: string): string => {
    if (value === null || value === undefined) return t('common.na')
    return `${Number(value).toFixed(1)}${unit}`
  }

  const getCardColor = (_kpi: KPISummary): string => 'surface'

  const getStatusColor = (kpi: KPISummary): StatusColor =>
    kpiStore.kpiStatus(kpi.value, kpi.target, kpi.higherBetter)

  const getStatusText = (kpi: KPISummary): string => {
    const status = getStatusColor(kpi)
    if (status === 'success') return t('operationsHealth.onTarget')
    if (status === 'warning') return t('operationsHealth.atRisk')
    return t('operationsHealth.critical')
  }

  const getProgress = (kpi: KPISummary): number => {
    if (!kpi.value || !kpi.target) return 0
    const percentage = (kpi.value / kpi.target) * 100
    return kpi.higherBetter ? Math.min(percentage, 100) : Math.max(100 - percentage, 0)
  }

  const getTrendIcon = (_kpi: KPISummary): string => 'mdi-trending-up'
  const getTrendColor = (_kpi: KPISummary): string => 'success'

  const getConfidenceColor = (confidence: number): StatusColor => {
    if (confidence >= 0.8) return 'success'
    if (confidence >= 0.5) return 'warning'
    return 'error'
  }

  const getKpiTooltip = (key: string): KpiTooltip => kpiTooltips.value[key] || defaultTooltip.value

  const summaryHeaders = computed<SummaryHeader[]>(() => [
    { title: t('kpi.summaryHeaders.kpi'), key: 'title', sortable: true },
    { title: t('kpi.summaryHeaders.current'), key: 'value', sortable: true },
    { title: t('kpi.summaryHeaders.target'), key: 'target', sortable: true },
    { title: t('kpi.summaryHeaders.status'), key: 'status', sortable: true },
    { title: t('kpi.summaryHeaders.trend'), key: 'trend', sortable: false },
    { title: '', key: 'actions', sortable: false, width: 50 },
  ])

  const summaryItems = computed<SummaryItem[]>(() =>
    kpiStore.allKPIs.map((kpi) => ({
      title: kpi.title,
      value: formatValue(kpi.value, kpi.unit),
      target: `${kpi.target}${kpi.unit}`,
      status: getStatusColor(kpi),
      statusText: getStatusText(kpi),
      trendIcon: getTrendIcon(kpi),
      trendColor: getTrendColor(kpi),
      route: kpi.route,
    })),
  )

  return {
    formatValue,
    getCardColor,
    getStatusColor,
    getStatusText,
    getProgress,
    getTrendIcon,
    getTrendColor,
    getConfidenceColor,
    getKpiTooltip,
    summaryHeaders,
    summaryItems,
  }
}
