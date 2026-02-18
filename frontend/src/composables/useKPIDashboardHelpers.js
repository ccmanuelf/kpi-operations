/**
 * Composable for KPI Dashboard display helpers.
 * Handles: KPI card formatting, status colors, progress, tooltips, summary table data.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useKPIStore } from '@/stores/kpi'

/**
 * KPI tooltip descriptions keyed by KPI identifier.
 * Static data — defined outside the composable to avoid re-creation per instance.
 */
const kpiTooltips = {
  efficiency: {
    title: 'Formula:',
    formula: 'Efficiency = (Actual Output / Expected Output) x 100',
    meaning: 'Measures how well resources are utilized to produce output. Higher efficiency means more output with the same resources.'
  },
  wipAging: {
    title: 'Formula:',
    formula: 'WIP Age = Days Since Work Order Started',
    meaning: 'Average time work-in-process items spend in production. Lower is better - indicates faster throughput and fewer bottlenecks.'
  },
  onTimeDelivery: {
    title: 'Formula:',
    formula: 'OTD = (Orders Delivered On Time / Total Orders) x 100',
    meaning: 'Percentage of orders delivered by the promised date. Critical for customer satisfaction and reliability.'
  },
  availability: {
    title: 'Formula:',
    formula: 'Availability = (Uptime / Planned Production Time) x 100',
    meaning: 'Percentage of scheduled time that equipment is available for production. Accounts for breakdowns and changeovers.'
  },
  performance: {
    title: 'Formula:',
    formula: 'Performance = (Actual Rate / Ideal Rate) x 100',
    meaning: 'Measures production speed relative to the designed capacity. Accounts for slow cycles and minor stoppages.'
  },
  quality: {
    title: 'Formula:',
    formula: 'FPY = (Good Units First Pass / Total Units) x 100',
    meaning: 'First Pass Yield - percentage of units that pass inspection on the first attempt without rework or repair.'
  },
  oee: {
    title: 'Formula:',
    formula: 'OEE = Availability x Performance x Quality',
    meaning: 'Overall Equipment Effectiveness - comprehensive metric combining availability, performance, and quality to measure manufacturing productivity.'
  },
  absenteeism: {
    title: 'Formula:',
    formula: 'Absenteeism = (Absent Hours / Scheduled Hours) x 100',
    meaning: 'Percentage of scheduled work hours lost due to employee absence. Lower is better for workforce planning and productivity.'
  },
  defectRates: {
    title: 'Formula:',
    formula: 'PPM = (Defective Units / Total Units) x 1,000,000',
    meaning: 'Parts Per Million - number of defective parts per million produced. Industry standard for measuring quality at scale.'
  },
  throughputTime: {
    title: 'Formula:',
    formula: 'Throughput = Total Time from Start to Completion',
    meaning: 'Average time to complete a production order from start to finish. Lower times indicate more efficient processes.'
  }
}

const defaultTooltip = {
  title: 'Info:',
  formula: null,
  meaning: 'Key performance indicator tracking operational metrics.'
}

export function useKPIDashboardHelpers() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  // --- KPI card display helpers ---

  const formatValue = (value, unit) => {
    if (value === null || value === undefined) return t('common.na')
    return `${Number(value).toFixed(1)}${unit}`
  }

  const getCardColor = (_kpi) => {
    return 'surface'
  }

  const getStatusColor = (kpi) => {
    return kpiStore.kpiStatus(kpi.value, kpi.target, kpi.higherBetter)
  }

  const getStatusText = (kpi) => {
    const status = getStatusColor(kpi)
    if (status === 'success') return t('operationsHealth.onTarget')
    if (status === 'warning') return t('operationsHealth.atRisk')
    return t('operationsHealth.critical')
  }

  const getProgress = (kpi) => {
    if (!kpi.value || !kpi.target) return 0
    const percentage = (kpi.value / kpi.target) * 100
    return kpi.higherBetter ? Math.min(percentage, 100) : Math.max(100 - percentage, 0)
  }

  const getTrendIcon = (_kpi) => {
    return 'mdi-trending-up'
  }

  const getTrendColor = (_kpi) => {
    return 'success'
  }

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'success'
    if (confidence >= 0.5) return 'warning'
    return 'error'
  }

  const getKpiTooltip = (key) => {
    return kpiTooltips[key] || defaultTooltip
  }

  // --- Summary table ---

  const summaryHeaders = [
    { title: 'KPI', key: 'title', sortable: true },
    { title: 'Current', key: 'value', sortable: true },
    { title: 'Target', key: 'target', sortable: true },
    { title: 'Status', key: 'status', sortable: true },
    { title: 'Trend', key: 'trend', sortable: false },
    { title: '', key: 'actions', sortable: false, width: 50 }
  ]

  const summaryItems = computed(() => {
    return kpiStore.allKPIs.map(kpi => ({
      title: kpi.title,
      value: formatValue(kpi.value, kpi.unit),
      target: `${kpi.target}${kpi.unit}`,
      status: getStatusColor(kpi),
      statusText: getStatusText(kpi),
      trendIcon: getTrendIcon(kpi),
      trendColor: getTrendColor(kpi),
      route: kpi.route
    }))
  })

  return {
    // KPI card helpers
    formatValue,
    getCardColor,
    getStatusColor,
    getStatusText,
    getProgress,
    getTrendIcon,
    getTrendColor,
    getConfidenceColor,
    getKpiTooltip,
    // Summary table
    summaryHeaders,
    summaryItems
  }
}
