/**
 * Composable for Quality KPI chart configuration and computed datasets.
 * Handles: Chart.js registration, chart data computed, chart options.
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
  Filler
} from 'chart.js'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

export function useQualityCharts() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  const chartData = computed(() => ({
    labels: kpiStore.trends.quality.map(d => format(new Date(d.date), 'MMM dd')),
    datasets: [
      {
        label: t('kpi.charts.qualityFPYPercent'),
        data: kpiStore.trends.quality.map(d => d.value),
        borderColor: '#1976d2',
        backgroundColor: 'rgba(25, 118, 210, 0.1)',
        tension: 0.3,
        fill: true
      },
      {
        label: t('kpi.charts.targetValue', { value: 99 }),
        data: Array(kpiStore.trends.quality.length).fill(99),
        borderColor: '#2e7d32',
        borderDash: [5, 5],
        pointRadius: 0
      }
    ]
  }))

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: true, position: 'top' },
      tooltip: { mode: 'index', intersect: false }
    },
    scales: {
      y: {
        beginAtZero: false,
        min: 90,
        max: 100,
        ticks: { callback: (value) => `${value}%` }
      }
    }
  }

  return {
    chartData,
    chartOptions
  }
}
