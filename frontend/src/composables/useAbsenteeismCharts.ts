/**
 * Composable for the Absenteeism KPI chart configuration. Reactive
 * Chart.js datasets and options keyed off `kpi.trends.absenteeism`.
 *
 * Uses the red palette (high absenteeism is bad) and target line at
 * 5%; y-axis is capped at 20% (rates rarely exceed this), not 100%.
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

export default function useAbsenteeismCharts() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()
  const { scaleDefaults, legendDefaults, chartColors } = useChartTheme()

  const chartData = computed(() => {
    const trend = kpiStore.trends.absenteeism as TrendPoint[]
    return {
      labels: trend.map((d) => format(new Date(d.date), 'MMM dd')),
      datasets: [
        {
          label: t('kpi.charts.absenteeismRatePercent'),
          data: trend.map((d) => d.value),
          borderColor: chartColors.value.red,
          backgroundColor: chartColors.value.redFill,
          tension: 0.3,
          fill: true,
        },
        {
          label: t('kpi.charts.targetValue', { value: 5 }),
          data: Array(trend.length).fill(5),
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
        beginAtZero: true,
        max: 20,
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
