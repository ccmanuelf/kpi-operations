/**
 * Composable for the Efficiency KPI chart with optional forecast
 * overlay. Series + forecast padding is built by the shared
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

export default function useEfficiencyCharts({
  showForecast,
  predictionData,
}: ForecastChartOptions) {
  const { t } = useI18n()
  const kpiStore = useKPIStore()
  const { scaleDefaults, legendDefaults, chartColors } = useChartTheme()

  const chartData = computed(() =>
    buildForecastChartData({
      trend: kpiStore.trends.efficiency as TrendPoint[],
      prediction: predictionData.value,
      showForecast: showForecast.value,
      target: 85,
      palette: {
        borderColor: chartColors.value.green,
        backgroundColor: chartColors.value.greenFill,
        targetBorderColor: chartColors.value.orange,
        forecastBorder: chartColors.value.purple,
        forecastFill: chartColors.value.purpleFill,
        confidenceBorder: chartColors.value.purpleBorder,
        confidenceFill: chartColors.value.purpleConfidence,
      },
      labels: {
        seriesLabel: t('kpi.charts.efficiencyPercent'),
        targetLabel: t('kpi.charts.targetValue', { value: 85 }),
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
