/**
 * Composable for the WIP Aging KPI chart configuration. Reactive
 * Chart.js datasets and options keyed off `kpi.trends.wipAging`.
 *
 * Uses the orange palette (long-aging WIP is bad) and a 7-day target
 * line. Y-axis is open-ended (days, not %), with a `Xd` tick suffix.
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

export default function useWIPAgingCharts() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()
  const { scaleDefaults, legendDefaults, chartColors } = useChartTheme()

  const chartData = computed(() => {
    const trend = kpiStore.trends.wipAging as TrendPoint[]
    return {
      labels: trend.map((d) => format(new Date(d.date), 'MMM dd')),
      datasets: [
        {
          label: t('kpi.charts.avgWipAgeDays'),
          data: trend.map((d) => d.value),
          borderColor: chartColors.value.orange,
          backgroundColor: 'rgba(245, 124, 0, 0.1)',
          tension: 0.3,
          fill: true,
        },
        {
          label: t('kpi.charts.targetDays', { value: 7 }),
          data: Array(trend.length).fill(7),
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
        ticks: {
          callback: (value: number | string) => `${value}d`,
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
