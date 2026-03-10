/**
 * Composable for Efficiency KPI chart configuration and computed datasets.
 * Handles: Chart.js registration, chart data computed (with forecast overlay), chart options.
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
import { useChartTheme } from '@/composables/useChartTheme'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

export default function useEfficiencyCharts({ showForecast, predictionData }) {
  const { t } = useI18n()
  const kpiStore = useKPIStore()
  const { scaleDefaults, legendDefaults, chartColors } = useChartTheme()

  const chartData = computed(() => {
    const trendLabels = kpiStore.trends.efficiency.map(d => format(new Date(d.date), 'MMM dd'))
    const trendData = kpiStore.trends.efficiency.map(d => d.value)

    const datasets = [
      {
        label: t('kpi.charts.efficiencyPercent'),
        data: trendData,
        borderColor: chartColors.value.green,
        backgroundColor: chartColors.value.greenFill,
        tension: 0.3,
        fill: true
      },
      {
        label: t('kpi.charts.targetValue', { value: 85 }),
        data: Array(trendLabels.length).fill(85),
        borderColor: chartColors.value.orange,
        borderDash: [5, 5],
        pointRadius: 0
      }
    ]

    // Add forecast data if available and enabled
    if (showForecast.value && predictionData.value && predictionData.value.predictions) {
      const forecastLabels = predictionData.value.predictions.map(p => {
        const date = new Date(p.date)
        return format(date, 'MMM dd')
      })
      const forecastValues = predictionData.value.predictions.map(p => p.predicted_value)
      const upperBounds = predictionData.value.predictions.map(p => p.upper_bound)
      const lowerBounds = predictionData.value.predictions.map(p => p.lower_bound)

      const allLabels = [...trendLabels, ...forecastLabels]
      const paddedTrendData = [...trendData, ...Array(forecastLabels.length).fill(null)]
      const paddedTarget = Array(allLabels.length).fill(85)

      const lastHistoricalValue = trendData.length > 0 ? trendData[trendData.length - 1] : null
      const paddedForecast = [...Array(trendLabels.length - 1).fill(null), lastHistoricalValue, ...forecastValues]
      const paddedUpper = [...Array(trendLabels.length - 1).fill(null), lastHistoricalValue, ...upperBounds]
      const paddedLower = [...Array(trendLabels.length - 1).fill(null), lastHistoricalValue, ...lowerBounds]

      return {
        labels: allLabels,
        datasets: [
          {
            label: t('kpi.charts.efficiencyPercent'),
            data: paddedTrendData,
            borderColor: chartColors.value.green,
            backgroundColor: chartColors.value.greenFill,
            tension: 0.3,
            fill: true
          },
          {
            label: t('kpi.charts.targetValue', { value: 85 }),
            data: paddedTarget,
            borderColor: chartColors.value.orange,
            borderDash: [5, 5],
            pointRadius: 0
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
            pointBackgroundColor: chartColors.value.purple
          },
          {
            label: t('kpi.charts.confidenceUpper'),
            data: paddedUpper,
            borderColor: chartColors.value.purpleBorder,
            backgroundColor: chartColors.value.purpleConfidence,
            borderDash: [2, 2],
            tension: 0.3,
            fill: '+1',
            pointRadius: 0
          },
          {
            label: t('kpi.charts.confidenceLower'),
            data: paddedLower,
            borderColor: chartColors.value.purpleBorder,
            backgroundColor: 'transparent',
            borderDash: [2, 2],
            tension: 0.3,
            fill: false,
            pointRadius: 0
          }
        ]
      }
    }

    return { labels: trendLabels, datasets }
  })

  const chartOptions = computed(() => ({
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: true, position: 'top', ...legendDefaults.value },
      tooltip: { mode: 'index', intersect: false }
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        ticks: { callback: (value) => `${value}%`, ...scaleDefaults.value.ticks },
        grid: scaleDefaults.value.grid
      },
      x: { ticks: scaleDefaults.value.ticks, grid: scaleDefaults.value.grid }
    }
  }))

  return {
    chartData,
    chartOptions
  }
}
