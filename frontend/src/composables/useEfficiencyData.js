/**
 * Composable for Efficiency KPI data fetching, reactive state, and calculations.
 * Handles: loading states, API calls, efficiency data, predictions, color helpers, formatters.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import api from '@/services/api'

export default function useEfficiencyData() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  // --- Reactive state ---
  const loading = ref(false)
  const clients = ref([])
  const selectedClient = ref(null)
  const startDate = ref(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const endDate = ref(new Date().toISOString().split('T')[0])
  const tableSearch = ref('')
  const historicalData = ref([])
  const showForecast = ref(true)
  const forecastDays = ref(7)
  const predictionData = ref(null)

  // --- Computed ---
  const efficiencyData = computed(() => kpiStore.efficiency)

  const statusColor = computed(() => {
    const eff = efficiencyData.value?.current || 0
    if (eff >= 85) return 'success'
    if (eff >= 70) return 'amber-darken-3'
    return 'error'
  })

  const gapColor = computed(() => {
    const gap = efficiencyData.value?.gap || 0
    return gap >= 0 ? 'text-success' : 'text-error'
  })

  // --- Table header definitions ---
  const shiftHeaders = computed(() => [
    { title: t('kpi.headers.shift'), key: 'shift_name', sortable: true },
    { title: t('kpi.headers.output'), key: 'actual_output', sortable: true },
    { title: t('kpi.headers.expected'), key: 'expected_output', sortable: true },
    { title: t('kpi.headers.efficiency'), key: 'efficiency', sortable: true }
  ])

  const productHeaders = computed(() => [
    { title: t('kpi.headers.product'), key: 'product_name', sortable: true },
    { title: t('kpi.headers.output'), key: 'actual_output', sortable: true },
    { title: t('kpi.headers.efficiency'), key: 'efficiency', sortable: true }
  ])

  const historyHeaders = computed(() => [
    { title: t('kpi.headers.date'), key: 'date', sortable: true },
    { title: t('kpi.headers.totalUnits'), key: 'total_units', sortable: true },
    { title: t('kpi.headers.efficiencyPercent'), key: 'avg_efficiency', sortable: true },
    { title: t('kpi.headers.performancePercent'), key: 'avg_performance', sortable: true },
    { title: t('kpi.headers.entryCount'), key: 'entry_count', sortable: true }
  ])

  // --- Formatting helpers ---
  const formatValue = (value) => {
    return value !== null && value !== undefined ? Number(value).toFixed(1) : t('common.na')
  }

  const formatDate = (dateStr) => {
    try {
      return format(new Date(dateStr), 'MMM dd, yyyy')
    } catch {
      return dateStr
    }
  }

  // --- Color helpers ---
  const getEfficiencyColor = (eff) => {
    if (eff >= 85) return 'success'
    if (eff >= 70) return 'amber-darken-3'
    return 'error'
  }

  const getPerformanceColor = (perf) => {
    if (perf >= 95) return 'success'
    if (perf >= 80) return 'amber-darken-3'
    return 'error'
  }

  const getHealthColor = (score) => {
    if (score >= 80) return 'success'
    if (score >= 60) return 'warning'
    return 'error'
  }

  const getTrendColor = (trend) => {
    if (trend === 'improving') return 'success'
    if (trend === 'declining') return 'error'
    return 'grey'
  }

  const getTrendIcon = (trend) => {
    if (trend === 'improving') return 'mdi-trending-up'
    if (trend === 'declining') return 'mdi-trending-down'
    return 'mdi-minus'
  }

  // --- API calls ---
  const fetchPrediction = async () => {
    if (!showForecast.value) {
      predictionData.value = null
      return
    }
    try {
      const params = {
        forecast_days: forecastDays.value,
        historical_days: 30,
        method: 'auto'
      }
      if (selectedClient.value) {
        params.client_id = selectedClient.value
      }
      const response = await api.getPrediction('efficiency', params)
      predictionData.value = response.data
    } catch (error) {
      console.error('Failed to fetch prediction:', error)
      predictionData.value = null
    }
  }

  const onForecastToggle = () => {
    if (showForecast.value) {
      fetchPrediction()
    } else {
      predictionData.value = null
    }
  }

  const loadClients = async () => {
    try {
      const response = await api.getClients()
      clients.value = response.data || []
    } catch (error) {
      console.error('Failed to load clients:', error)
    }
  }

  const onClientChange = () => {
    kpiStore.setClient(selectedClient.value)
    refreshData()
  }

  const onDateChange = () => {
    kpiStore.setDateRange(startDate.value, endDate.value)
    refreshData()
  }

  const refreshData = async () => {
    loading.value = true
    try {
      const promises = [
        kpiStore.fetchEfficiency(),
        kpiStore.fetchDashboard()
      ]
      if (showForecast.value) {
        promises.push(fetchPrediction())
      }
      await Promise.all(promises)
      historicalData.value = kpiStore.dashboard || []
    } catch (error) {
      console.error('Failed to refresh data:', error)
    } finally {
      loading.value = false
    }
  }

  const initialize = async () => {
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
    // State
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
    // Computed
    efficiencyData,
    statusColor,
    gapColor,
    // Table headers
    shiftHeaders,
    productHeaders,
    historyHeaders,
    // Formatters
    formatValue,
    formatDate,
    // Color helpers
    getEfficiencyColor,
    getPerformanceColor,
    getHealthColor,
    getTrendColor,
    getTrendIcon,
    // API / actions
    fetchPrediction,
    onForecastToggle,
    onClientChange,
    onDateChange,
    refreshData,
    initialize
  }
}
