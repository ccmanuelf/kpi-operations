/**
 * Composable for the Quality KPI chart configuration. Reactive
 * Chart.js datasets and options keyed off `kpi.trends.quality`.
 */
import { computed } from 'vue'
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

interface TrendPoint {
  date: string
  value: number
  [key: string]: unknown
}

export function useQualityCharts() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()
  const { scaleDefaults, legendDefaults, chartColors } = useChartTheme()

  const chartData = computed(() => {
    const trend = kpiStore.trends.quality as TrendPoint[]
    return {
      labels: trend.map((d) => format(new Date(d.date), 'MMM dd')),
      datasets: [
        {
          label: t('kpi.charts.qualityFPYPercent'),
          data: trend.map((d) => d.value),
          borderColor: chartColors.value.blue,
          backgroundColor: chartColors.value.blueFill,
          tension: 0.3,
          fill: true,
        },
        {
          label: t('kpi.charts.targetValue', { value: 99 }),
          data: Array(trend.length).fill(99),
          borderColor: chartColors.value.green,
          borderDash: [5, 5],
          pointRadius: 0,
        },
      ],
    }
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
        beginAtZero: false,
        min: 90,
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
