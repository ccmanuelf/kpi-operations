/**
 * Shared helper for KPI chart datasets that overlay a forecast on
 * a historical trend. Both `useEfficiencyCharts` and
 * `usePerformanceCharts` derived ~150 lines of identical
 * forecast-padding logic from this shape; this module extracts
 * the common builder.
 */
import { format } from 'date-fns'

export interface PredictionPoint {
  date: string
  predicted_value: number
  upper_bound: number
  lower_bound: number
  [key: string]: unknown
}

export interface PredictionData {
  predictions?: PredictionPoint[]
  [key: string]: unknown
}

export interface TrendPoint {
  date: string
  value: number
  [key: string]: unknown
}

export interface ChartDatasetEntry {
  label: string
  data: (number | null)[]
  borderColor: string
  backgroundColor?: string
  borderDash?: number[]
  tension?: number
  fill?: boolean | string
  pointStyle?: string
  pointRadius?: number
  pointBackgroundColor?: string
}

export interface ChartData {
  labels: string[]
  datasets: ChartDatasetEntry[]
}

export interface ForecastPalette {
  // Series colors (the historical trend line + fill)
  borderColor: string
  backgroundColor: string
  // Target line color
  targetBorderColor: string
  // Forecast palette
  forecastBorder: string
  forecastFill: string
  confidenceBorder: string
  confidenceFill: string
}

export interface ForecastChartLabels {
  // Localized "Series" label (e.g. "Efficiency %")
  seriesLabel: string
  // Localized "Target: 85" label
  targetLabel: string
  // Localized "Forecast" / "Confidence Upper" / "Confidence Lower"
  forecastLabel: string
  confidenceUpperLabel: string
  confidenceLowerLabel: string
}

export interface BuildForecastChartOptions {
  trend: TrendPoint[]
  prediction: PredictionData | null
  showForecast: boolean
  target: number
  palette: ForecastPalette
  labels: ForecastChartLabels
}

/**
 * Build the historical-trend chart data, with an optional forecast
 * overlay padded so the forecast segment starts at the last
 * historical value (visually continuous).
 */
export function buildForecastChartData({
  trend,
  prediction,
  showForecast,
  target,
  palette,
  labels,
}: BuildForecastChartOptions): ChartData {
  const trendLabels = trend.map((d) => format(new Date(d.date), 'MMM dd'))
  const trendData: number[] = trend.map((d) => d.value)

  // No forecast: just the historical trend + flat target line.
  if (!showForecast || !prediction?.predictions) {
    return {
      labels: trendLabels,
      datasets: [
        {
          label: labels.seriesLabel,
          data: trendData,
          borderColor: palette.borderColor,
          backgroundColor: palette.backgroundColor,
          tension: 0.3,
          fill: true,
        },
        {
          label: labels.targetLabel,
          data: Array(trendLabels.length).fill(target),
          borderColor: palette.targetBorderColor,
          borderDash: [5, 5],
          pointRadius: 0,
        },
      ],
    }
  }

  // Forecast overlay: extend labels with the forecast dates and
  // pad each series so they line up.
  const forecastLabels = prediction.predictions.map((p) =>
    format(new Date(p.date), 'MMM dd'),
  )
  const forecastValues = prediction.predictions.map((p) => p.predicted_value)
  const upperBounds = prediction.predictions.map((p) => p.upper_bound)
  const lowerBounds = prediction.predictions.map((p) => p.lower_bound)

  const allLabels = [...trendLabels, ...forecastLabels]
  const paddedTrendData: (number | null)[] = [
    ...trendData,
    ...Array(forecastLabels.length).fill(null),
  ]
  const paddedTarget = Array(allLabels.length).fill(target)

  // Bridge the historical series into the forecast at the last
  // historical sample so the line is visually continuous.
  const lastHistoricalValue: number | null =
    trendData.length > 0 ? trendData[trendData.length - 1] : null
  const padding = Array(trendLabels.length - 1).fill(null)
  const paddedForecast = [...padding, lastHistoricalValue, ...forecastValues]
  const paddedUpper = [...padding, lastHistoricalValue, ...upperBounds]
  const paddedLower = [...padding, lastHistoricalValue, ...lowerBounds]

  return {
    labels: allLabels,
    datasets: [
      {
        label: labels.seriesLabel,
        data: paddedTrendData,
        borderColor: palette.borderColor,
        backgroundColor: palette.backgroundColor,
        tension: 0.3,
        fill: true,
      },
      {
        label: labels.targetLabel,
        data: paddedTarget,
        borderColor: palette.targetBorderColor,
        borderDash: [5, 5],
        pointRadius: 0,
      },
      {
        label: labels.forecastLabel,
        data: paddedForecast,
        borderColor: palette.forecastBorder,
        backgroundColor: palette.forecastFill,
        borderDash: [6, 4],
        tension: 0.3,
        fill: false,
        pointStyle: 'rectRot',
        pointRadius: 4,
        pointBackgroundColor: palette.forecastBorder,
      },
      {
        label: labels.confidenceUpperLabel,
        data: paddedUpper,
        borderColor: palette.confidenceBorder,
        backgroundColor: palette.confidenceFill,
        borderDash: [2, 2],
        tension: 0.3,
        fill: '+1',
        pointRadius: 0,
      },
      {
        label: labels.confidenceLowerLabel,
        data: paddedLower,
        borderColor: palette.confidenceBorder,
        backgroundColor: 'transparent',
        borderDash: [2, 2],
        tension: 0.3,
        fill: false,
        pointRadius: 0,
      },
    ],
  }
}
