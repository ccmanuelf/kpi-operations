/**
 * Composable for KPI Dashboard chart data transformation.
 * Handles: chart datasets for efficiency, quality, availability, OEE trends.
 */
import { computed } from 'vue'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import { useChartTheme } from '@/composables/useChartTheme'

export function useKPIChartData() {
  const kpiStore = useKPIStore()
  const { scaleDefaults, legendDefaults, chartColors } = useChartTheme()

  const chartOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        display: true,
        position: 'top',
        ...legendDefaults.value
      },
      tooltip: {
        mode: 'index',
        intersect: false
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        ticks: {
          callback: (value) => `${value}%`,
          ...scaleDefaults.value.ticks
        },
        grid: scaleDefaults.value.grid
      },
      x: {
        ticks: scaleDefaults.value.ticks,
        grid: scaleDefaults.value.grid
      }
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false
    }
  }))

  const efficiencyChartData = computed(() => ({
    labels: kpiStore.trends.efficiency.map(d => format(new Date(d.date), 'MMM dd')),
    datasets: [
      {
        label: 'Efficiency %',
        data: kpiStore.trends.efficiency.map(d => d.value),
        borderColor: chartColors.value.green,
        backgroundColor: chartColors.value.greenFill,
        tension: 0.3,
        fill: true
      },
      {
        label: 'Target',
        data: Array(kpiStore.trends.efficiency.length).fill(85),
        borderColor: chartColors.value.orange,
        borderDash: [5, 5],
        pointRadius: 0
      }
    ]
  }))

  const qualityChartData = computed(() => ({
    labels: kpiStore.trends.quality.map(d => format(new Date(d.date), 'MMM dd')),
    datasets: [
      {
        label: 'FPY %',
        data: kpiStore.trends.quality.map(d => d.value),
        borderColor: chartColors.value.blue,
        backgroundColor: chartColors.value.blueFill,
        tension: 0.3,
        fill: true
      },
      {
        label: 'Target',
        data: Array(kpiStore.trends.quality.length).fill(99),
        borderColor: chartColors.value.orange,
        borderDash: [5, 5],
        pointRadius: 0
      }
    ]
  }))

  const availabilityChartData = computed(() => ({
    labels: kpiStore.trends.availability.map(d => format(new Date(d.date), 'MMM dd')),
    datasets: [
      {
        label: 'Availability %',
        data: kpiStore.trends.availability.map(d => d.value),
        borderColor: chartColors.value.purple,
        backgroundColor: chartColors.value.purpleFill,
        tension: 0.3,
        fill: true
      },
      {
        label: 'Target',
        data: Array(kpiStore.trends.availability.length).fill(90),
        borderColor: chartColors.value.orange,
        borderDash: [5, 5],
        pointRadius: 0
      }
    ]
  }))

  const oeeChartData = computed(() => ({
    labels: kpiStore.trends.oee.map(d => format(new Date(d.date), 'MMM dd')),
    datasets: [
      {
        label: 'OEE %',
        data: kpiStore.trends.oee.map(d => d.value),
        borderColor: chartColors.value.red,
        backgroundColor: chartColors.value.redFill,
        tension: 0.3,
        fill: true
      },
      {
        label: 'Target',
        data: Array(kpiStore.trends.oee.length).fill(85),
        borderColor: chartColors.value.orange,
        borderDash: [5, 5],
        pointRadius: 0
      }
    ]
  }))

  return {
    chartOptions,
    efficiencyChartData,
    qualityChartData,
    availabilityChartData,
    oeeChartData
  }
}
