/**
 * Composable for KPI Dashboard chart data transformation.
 * Handles: chart datasets for efficiency, quality, availability, OEE trends.
 */
import { computed } from 'vue'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'

export function useKPIChartData() {
  const kpiStore = useKPIStore()

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: {
        display: true,
        position: 'top'
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
          callback: (value) => `${value}%`
        }
      }
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false
    }
  }

  const efficiencyChartData = computed(() => ({
    labels: kpiStore.trends.efficiency.map(d => format(new Date(d.date), 'MMM dd')),
    datasets: [
      {
        label: 'Efficiency %',
        data: kpiStore.trends.efficiency.map(d => d.value),
        borderColor: '#2e7d32',
        backgroundColor: 'rgba(46, 125, 50, 0.1)',
        tension: 0.3,
        fill: true
      },
      {
        label: 'Target',
        data: Array(kpiStore.trends.efficiency.length).fill(85),
        borderColor: '#f57c00',
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
        borderColor: '#1976d2',
        backgroundColor: 'rgba(25, 118, 210, 0.1)',
        tension: 0.3,
        fill: true
      },
      {
        label: 'Target',
        data: Array(kpiStore.trends.quality.length).fill(99),
        borderColor: '#f57c00',
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
        borderColor: '#7b1fa2',
        backgroundColor: 'rgba(123, 31, 162, 0.1)',
        tension: 0.3,
        fill: true
      },
      {
        label: 'Target',
        data: Array(kpiStore.trends.availability.length).fill(90),
        borderColor: '#f57c00',
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
        borderColor: '#d32f2f',
        backgroundColor: 'rgba(211, 47, 47, 0.1)',
        tension: 0.3,
        fill: true
      },
      {
        label: 'Target',
        data: Array(kpiStore.trends.oee.length).fill(85),
        borderColor: '#f57c00',
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
