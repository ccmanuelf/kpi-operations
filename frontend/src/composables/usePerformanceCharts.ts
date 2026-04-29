/**
 * Composable for the Performance KPI chart with optional forecast
 * overlay. Mirrors the shape of useEfficiencyCharts but pulls
 * `kpi.trends.performance` and uses the dark-blue palette + 95
 * target. Series + forecast padding is built by the shared
 * `buildForecastChartData` helper.
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
import { useKPIStore } from '@/stores/kpi'
import { useChartTheme } from '@/composables/useChartTheme'
import {
  buildForecastChartData,
  type PredictionData,
  type TrendPoint,
} from '@/composables/useChartForecastDataset'

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

  const chartData = computed(() =>
    buildForecastChartData({
      trend: kpiStore.trends.performance as TrendPoint[],
      prediction: predictionData.value,
      showForecast: showForecast.value,
      target: 95,
      palette: {
        borderColor: chartColors.value.darkBlue,
        backgroundColor: chartColors.value.darkBlueFill,
        // The Performance variant uses green for the target line
        // (efficiency uses orange) — preserved per the original.
        targetBorderColor: chartColors.value.green,
        forecastBorder: chartColors.value.purple,
        forecastFill: chartColors.value.purpleFill,
        confidenceBorder: chartColors.value.purpleBorder,
        confidenceFill: chartColors.value.purpleConfidence,
      },
      labels: {
        seriesLabel: t('kpi.charts.performancePercent'),
        targetLabel: t('kpi.charts.targetValue', { value: 95 }),
        forecastLabel: t('kpi.charts.forecast'),
        confidenceUpperLabel: t('kpi.charts.confidenceUpper'),
        confidenceLowerLabel: t('kpi.charts.confidenceLower'),
      },
    }),
  )

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
