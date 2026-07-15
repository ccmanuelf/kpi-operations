/**
 * Config table for the reusable KpiTrendChart component. Each entry maps a
 * dashboard KPI card to its trend fetcher, threshold key, and (optional)
 * alert key so the chart/threshold/alert keys never diverge across cards.
 */
import {
  getEfficiencyTrend,
  getPerformanceTrend,
  getQualityTrend,
  getAvailabilityTrend,
  getOEETrend,
  getWIPAgingTrend,
  getOnTimeDeliveryTrend,
  getAbsenteeismTrend,
  getPpmTrend,
  getThroughputTrend,
} from '@/services/api/kpi'

export interface KpiTrendPoint {
  date: string
  value: number
}

export interface KpiChartConfigItem {
  metricKey: string // stable id for the chart
  titleKey: string // i18n key for the card title
  thresholdKey: string // KPIThreshold.kpi_key
  alertKey: string | null // Alert.kpi_key for latest-point enrichment (null if none)
  unit: string
  fetchTrend: (_params: Record<string, unknown>) => Promise<unknown>
}

// unwrap the api `{ data: [...] }` (or `[...]`) into a plain points array
export const unwrapTrend = (res: unknown): KpiTrendPoint[] => {
  const d = (res as { data?: unknown })?.data ?? res
  return Array.isArray(d)
    ? d.map((r: { date: unknown; value: unknown }) => ({ date: String(r.date), value: Number(r.value) }))
    : []
}

export const KPI_CHART_CONFIG: KpiChartConfigItem[] = [
  { metricKey: 'efficiency', titleKey: 'kpi.efficiency', thresholdKey: 'efficiency', alertKey: 'efficiency', unit: '%', fetchTrend: getEfficiencyTrend },
  { metricKey: 'performance', titleKey: 'kpi.performance', thresholdKey: 'performance', alertKey: null, unit: '%', fetchTrend: getPerformanceTrend },
  { metricKey: 'quality', titleKey: 'kpi.quality', thresholdKey: 'quality_rate', alertKey: 'quality', unit: '%', fetchTrend: getQualityTrend },
  { metricKey: 'availability', titleKey: 'kpi.availability', thresholdKey: 'availability', alertKey: null, unit: '%', fetchTrend: getAvailabilityTrend },
  { metricKey: 'oee', titleKey: 'kpi.oee', thresholdKey: 'oee', alertKey: null, unit: '%', fetchTrend: getOEETrend },
  { metricKey: 'wipAging', titleKey: 'kpi.wipAging', thresholdKey: 'wip_aging', alertKey: 'hold_approval', unit: 'd', fetchTrend: getWIPAgingTrend },
  // NOTE: brief's sample used titleKey 'kpi.onTimeDelivery', which does not exist in the
  // locale files — 'kpi.otd' is the key the OTD dashboard card actually uses.
  { metricKey: 'otd', titleKey: 'kpi.otd', thresholdKey: 'otd', alertKey: 'otd', unit: '%', fetchTrend: getOnTimeDeliveryTrend },
  { metricKey: 'absenteeism', titleKey: 'kpi.absenteeism', thresholdKey: 'absenteeism', alertKey: null, unit: '%', fetchTrend: getAbsenteeismTrend },
  { metricKey: 'ppm', titleKey: 'kpi.ppm', thresholdKey: 'ppm', alertKey: null, unit: 'ppm', fetchTrend: getPpmTrend },
  { metricKey: 'throughput', titleKey: 'kpi.throughputTime', thresholdKey: 'throughput', alertKey: null, unit: 'h', fetchTrend: getThroughputTrend },
]
