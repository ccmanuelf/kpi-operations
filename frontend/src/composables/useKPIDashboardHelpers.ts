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

const kpiTooltips: Record<string, KpiTooltip> = {
  efficiency: {
    title: 'Formula:',
    formula: 'Efficiency = (Actual Output / Expected Output) x 100',
    meaning:
      'Measures how well resources are utilized to produce output. Higher efficiency means more output with the same resources.',
  },
  wipAging: {
    title: 'Formula:',
    formula: 'WIP Age = Days Since Work Order Started',
    meaning:
      'Average time work-in-process items spend in production. Lower is better - indicates faster throughput and fewer bottlenecks.',
  },
  onTimeDelivery: {
    title: 'Formula:',
    formula: 'OTD = (Orders Delivered On Time / Total Orders) x 100',
    meaning:
      'Percentage of orders delivered by the promised date. Critical for customer satisfaction and reliability.',
  },
  availability: {
    title: 'Formula:',
    formula: 'Availability = (Uptime / Planned Production Time) x 100',
    meaning:
      'Percentage of scheduled time that equipment is available for production. Accounts for breakdowns and changeovers.',
  },
  performance: {
    title: 'Formula:',
    formula: 'Performance = (Actual Rate / Ideal Rate) x 100',
    meaning:
      'Measures production speed relative to the designed capacity. Accounts for slow cycles and minor stoppages.',
  },
  quality: {
    title: 'Formula:',
    formula: 'FPY = (Good Units First Pass / Total Units) x 100',
    meaning:
      'First Pass Yield - percentage of units that pass inspection on the first attempt without rework or repair.',
  },
  oee: {
    title: 'Formula:',
    formula: 'OEE = Availability x Performance x Quality',
    meaning:
      'Overall Equipment Effectiveness - comprehensive metric combining availability, performance, and quality to measure manufacturing productivity.',
  },
  absenteeism: {
    title: 'Formula:',
    formula: 'Absenteeism = (Absent Hours / Scheduled Hours) x 100',
    meaning:
      'Percentage of scheduled work hours lost due to employee absence. Lower is better for workforce planning and productivity.',
  },
  defectRates: {
    title: 'Formula:',
    formula: 'PPM = (Defective Units / Total Units) x 1,000,000',
    meaning:
      'Parts Per Million - number of defective parts per million produced. Industry standard for measuring quality at scale.',
  },
  throughputTime: {
    title: 'Formula:',
    formula: 'Throughput = Total Time from Start to Completion',
    meaning:
      'Average time to complete a production order from start to finish. Lower times indicate more efficient processes.',
  },
}

const defaultTooltip: KpiTooltip = {
  title: 'Info:',
  formula: null,
  meaning: 'Key performance indicator tracking operational metrics.',
}

export function useKPIDashboardHelpers() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

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

  const getKpiTooltip = (key: string): KpiTooltip => kpiTooltips[key] || defaultTooltip

  const summaryHeaders: SummaryHeader[] = [
    { title: 'KPI', key: 'title', sortable: true },
    { title: 'Current', key: 'value', sortable: true },
    { title: 'Target', key: 'target', sortable: true },
    { title: 'Status', key: 'status', sortable: true },
    { title: 'Trend', key: 'trend', sortable: false },
    { title: '', key: 'actions', sortable: false, width: 50 },
  ]

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
