/**
 * Composable for KPI Dashboard chart data transformation.
 * Reactive Chart.js datasets for efficiency, quality, availability,
 * and OEE trend lines, plus shared options.
 */
import { computed } from 'vue'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import { useChartTheme } from '@/composables/useChartTheme'

interface TrendPoint {
  date: string
  value: number
  [key: string]: unknown
}

const buildTrendDataset = (
  trend: TrendPoint[],
  label: string,
  borderColor: string,
  backgroundColor: string,
  target: number,
  targetColor: string,
) => ({
  labels: trend.map((d) => format(new Date(d.date), 'MMM dd')),
  datasets: [
    {
      label,
      data: trend.map((d) => d.value),
      borderColor,
      backgroundColor,
      tension: 0.3,
      fill: true,
    },
    {
      label: 'Target',
      data: Array(trend.length).fill(target),
      borderColor: targetColor,
      borderDash: [5, 5],
      pointRadius: 0,
    },
  ],
})

export function useKPIChartData() {
  const kpiStore = useKPIStore()
  const { scaleDefaults, legendDefaults, chartColors } = useChartTheme()

  const chartOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        ...legendDefaults.value,
      },
      tooltip: {
        mode: 'index' as const,
        intersect: false,
      },
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
      x: {
        ticks: scaleDefaults.value.ticks,
        grid: scaleDefaults.value.grid,
      },
    },
    interaction: {
      mode: 'nearest' as const,
      axis: 'x' as const,
      intersect: false,
    },
  }))

  const efficiencyChartData = computed(() =>
    buildTrendDataset(
      kpiStore.trends.efficiency as TrendPoint[],
      'Efficiency %',
      chartColors.value.green,
      chartColors.value.greenFill,
      85,
      chartColors.value.orange,
    ),
  )

  const qualityChartData = computed(() =>
    buildTrendDataset(
      kpiStore.trends.quality as TrendPoint[],
      'FPY %',
      chartColors.value.blue,
      chartColors.value.blueFill,
      99,
      chartColors.value.orange,
    ),
  )

  const availabilityChartData = computed(() =>
    buildTrendDataset(
      kpiStore.trends.availability as TrendPoint[],
      'Availability %',
      chartColors.value.purple,
      chartColors.value.purpleFill,
      90,
      chartColors.value.orange,
    ),
  )

  const oeeChartData = computed(() =>
    buildTrendDataset(
      kpiStore.trends.oee as TrendPoint[],
      'OEE %',
      chartColors.value.red,
      chartColors.value.redFill,
      85,
      chartColors.value.orange,
    ),
  )

  return {
    chartOptions,
    efficiencyChartData,
    qualityChartData,
    availabilityChartData,
    oeeChartData,
  }
}
