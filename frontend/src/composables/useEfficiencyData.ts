/**
 * Composable for Efficiency KPI data fetching, reactive state,
 * and helpers (color tokens, formatters, prediction loader).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import api from '@/services/api'

interface ClientOption {
  client_id?: string | number
  [key: string]: unknown
}

interface TableHeader {
  title: string
  key: string
  sortable: boolean
}

type Trend = 'improving' | 'declining' | 'stable' | string

export default function useEfficiencyData() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  const loading = ref(false)
  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const startDate = ref(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const endDate = ref(new Date().toISOString().split('T')[0])
  const tableSearch = ref('')
  const historicalData = ref<unknown[]>([])
  const showForecast = ref(true)
  const forecastDays = ref(7)
  const predictionData = ref<unknown | null>(null)

  const efficiencyData = computed(() => kpiStore.efficiency)

  const statusColor = computed<string>(() => {
    const eff = (efficiencyData.value?.current as number) || 0
    if (eff >= 85) return 'success'
    if (eff >= 70) return 'amber-darken-3'
    return 'error'
  })

  const gapColor = computed<string>(() => {
    const gap = ((efficiencyData.value as { gap?: number } | null)?.gap as number) || 0
    return gap >= 0 ? 'text-success' : 'text-error'
  })

  const shiftHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.shift'), key: 'shift_name', sortable: true },
    { title: t('kpi.headers.output'), key: 'actual_output', sortable: true },
    { title: t('kpi.headers.expected'), key: 'expected_output', sortable: true },
    { title: t('kpi.headers.efficiency'), key: 'efficiency', sortable: true },
  ])

  const productHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.product'), key: 'product_name', sortable: true },
    { title: t('kpi.headers.output'), key: 'actual_output', sortable: true },
    { title: t('kpi.headers.efficiency'), key: 'efficiency', sortable: true },
  ])

  const historyHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.date'), key: 'date', sortable: true },
    { title: t('kpi.headers.totalUnits'), key: 'total_units', sortable: true },
    { title: t('kpi.headers.efficiencyPercent'), key: 'avg_efficiency', sortable: true },
    { title: t('kpi.headers.performancePercent'), key: 'avg_performance', sortable: true },
    { title: t('kpi.headers.entryCount'), key: 'entry_count', sortable: true },
  ])

  const formatValue = (value: number | null | undefined): string =>
    value !== null && value !== undefined ? Number(value).toFixed(1) : t('common.na')

  const formatDate = (dateStr: string): string => {
    try {
      return format(new Date(dateStr), 'MMM dd, yyyy')
    } catch {
      return dateStr
    }
  }

  const getEfficiencyColor = (eff: number): string => {
    if (eff >= 85) return 'success'
    if (eff >= 70) return 'amber-darken-3'
    return 'error'
  }

  const getPerformanceColor = (perf: number): string => {
    if (perf >= 95) return 'success'
    if (perf >= 80) return 'amber-darken-3'
    return 'error'
  }

  const getHealthColor = (score: number): string => {
    if (score >= 80) return 'success'
    if (score >= 60) return 'warning'
    return 'error'
  }

  const getTrendColor = (trend: Trend): string => {
    if (trend === 'improving') return 'success'
    if (trend === 'declining') return 'error'
    return 'grey'
  }

  const getTrendIcon = (trend: Trend): string => {
    if (trend === 'improving') return 'mdi-trending-up'
    if (trend === 'declining') return 'mdi-trending-down'
    return 'mdi-minus'
  }

  const fetchPrediction = async (): Promise<void> => {
    if (!showForecast.value) {
      predictionData.value = null
      return
    }
    try {
      const params: Record<string, unknown> = {
        forecast_days: forecastDays.value,
        historical_days: 30,
        method: 'auto',
      }
      if (selectedClient.value) {
        params.client_id = selectedClient.value
      }
      const response = await api.getPrediction('efficiency', params)
      predictionData.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to fetch prediction:', error)
      predictionData.value = null
    }
  }

  const onForecastToggle = (): void => {
    if (showForecast.value) {
      fetchPrediction()
    } else {
      predictionData.value = null
    }
  }

  const loadClients = async (): Promise<void> => {
    try {
      const response = await api.getClients()
      clients.value = response.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load clients:', error)
    }
  }

  const refreshData = async (): Promise<void> => {
    loading.value = true
    try {
      const promises: Promise<unknown>[] = [
        kpiStore.fetchEfficiency(),
        kpiStore.fetchDashboard(),
      ]
      if (showForecast.value) {
        promises.push(fetchPrediction())
      }
      await Promise.all(promises)
      historicalData.value = (kpiStore.dashboard as unknown[]) || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to refresh data:', error)
    } finally {
      loading.value = false
    }
  }

  const onClientChange = (): void => {
    kpiStore.setClient(selectedClient.value)
    refreshData()
  }

  const onDateChange = (): void => {
    kpiStore.setDateRange(startDate.value, endDate.value)
    refreshData()
  }

  const initialize = async (): Promise<void> => {
    loading.value = true
    try {
      await loadClients()
      kpiStore.setDateRange(startDate.value, endDate.value)
      await refreshData()
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    clients,
    selectedClient,
    startDate,
    endDate,
    tableSearch,
    historicalData,
    showForecast,
    forecastDays,
    predictionData,
    efficiencyData,
    statusColor,
    gapColor,
    shiftHeaders,
    productHeaders,
    historyHeaders,
    formatValue,
    formatDate,
    getEfficiencyColor,
    getPerformanceColor,
    getHealthColor,
    getTrendColor,
    getTrendIcon,
    fetchPrediction,
    onForecastToggle,
    onClientChange,
    onDateChange,
    refreshData,
    initialize,
  }
}
