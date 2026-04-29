/**
 * Composable for the Performance KPI chart with optional forecast
 * overlay. Mirrors the shape of useEfficiencyCharts but pulls
 * `kpi.trends.performance` and uses the dark-blue palette + 95
 * target.
 */
import { computed, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import { useChartTheme } from '@/composables/useChartTheme'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
)

interface PredictionPoint {
  date: string
  predicted_value: number
  upper_bound: number
  lower_bound: number
  [key: string]: unknown
}

interface PredictionData {
  predictions?: PredictionPoint[]
  [key: string]: unknown
}

interface TrendPoint {
  date: string
  value: number
  [key: string]: unknown
}

export interface ForecastChartOptions {
  showForecast: Ref<boolean>
  predictionData: Ref<PredictionData | null>
}

export default function usePerformanceCharts({
  showForecast,
  predictionData,
}: ForecastChartOptions) {
  const { t } = useI18n()
  const kpiStore = useKPIStore()
  const { scaleDefaults, legendDefaults, chartColors } = useChartTheme()

  const chartData = computed(() => {
    const trend = kpiStore.trends.performance as TrendPoint[]
    const trendLabels = trend.map((d) => format(new Date(d.date), 'MMM dd'))
    const trendData = trend.map((d) => d.value)

    const datasets: Array<Record<string, unknown>> = [
      {
        label: t('kpi.charts.performancePercent'),
        data: trendData,
        borderColor: chartColors.value.darkBlue,
        backgroundColor: chartColors.value.darkBlueFill,
        tension: 0.3,
        fill: true,
      },
      {
        label: t('kpi.charts.targetValue', { value: 95 }),
        data: Array(trendLabels.length).fill(95),
        borderColor: chartColors.value.green,
        borderDash: [5, 5],
        pointRadius: 0,
      },
    ]

    if (showForecast.value && predictionData.value?.predictions) {
      const forecastLabels = predictionData.value.predictions.map((p) =>
        format(new Date(p.date), 'MMM dd'),
      )
      const forecastValues = predictionData.value.predictions.map((p) => p.predicted_value)
      const upperBounds = predictionData.value.predictions.map((p) => p.upper_bound)
      const lowerBounds = predictionData.value.predictions.map((p) => p.lower_bound)

      const allLabels = [...trendLabels, ...forecastLabels]
      const paddedTrendData: (number | null)[] = [
        ...trendData,
        ...Array(forecastLabels.length).fill(null),
      ]
      const paddedTarget = Array(allLabels.length).fill(95)

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
            label: t('kpi.charts.performancePercent'),
            data: paddedTrendData,
            borderColor: chartColors.value.darkBlue,
            backgroundColor: chartColors.value.darkBlueFill,
            tension: 0.3,
            fill: true,
          },
          {
            label: t('kpi.charts.targetValue', { value: 95 }),
            data: paddedTarget,
            borderColor: chartColors.value.green,
            borderDash: [5, 5],
            pointRadius: 0,
          },
          {
            label: t('kpi.charts.forecast'),
            data: paddedForecast,
            borderColor: chartColors.value.purple,
            backgroundColor: chartColors.value.purpleFill,
            borderDash: [6, 4],
            tension: 0.3,
            fill: false,
            pointStyle: 'rectRot',
            pointRadius: 4,
            pointBackgroundColor: chartColors.value.purple,
          },
          {
            label: t('kpi.charts.confidenceUpper'),
            data: paddedUpper,
            borderColor: chartColors.value.purpleBorder,
            backgroundColor: chartColors.value.purpleConfidence,
            borderDash: [2, 2],
            tension: 0.3,
            fill: '+1',
            pointRadius: 0,
          },
          {
            label: t('kpi.charts.confidenceLower'),
            data: paddedLower,
            borderColor: chartColors.value.purpleBorder,
            backgroundColor: 'transparent',
            borderDash: [2, 2],
            tension: 0.3,
            fill: false,
            pointRadius: 0,
          },
        ],
      }
    }

    return { labels: trendLabels, datasets }
  })

  const chartOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: true, position: 'top' as const, ...legendDefaults.value },
      tooltip: { mode: 'index' as const, intersect: false },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        ticks: {
          callback: (value: number | string) => `${value}%`,
          ...scaleDefaults.value.ticks,
        },
        grid: scaleDefaults.value.grid,
      },
      x: { ticks: scaleDefaults.value.ticks, grid: scaleDefaults.value.grid },
    },
  }))

  return {
    chartData,
    chartOptions,
  }
}
