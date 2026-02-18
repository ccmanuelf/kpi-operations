/**
 * Composable for KPI Dashboard data fetching and filter state.
 * Handles: loading state, clients list, date range, trend period, refresh.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import { useDashboardStore } from '@/stores/dashboardStore'
import { useFiltersStore } from '@/stores/filtersStore'
import api from '@/services/api'

export function useKPIDashboardData(showSnackbar) {
  const { t } = useI18n()
  const kpiStore = useKPIStore()
  const dashboardStore = useDashboardStore()
  const filtersStore = useFiltersStore()

  // State
  const loading = ref(false)
  const selectedClient = ref(null)
  const dateRange = ref([
    new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
    new Date()
  ])
  const trendPeriod = ref('30')
  const clients = ref([{ id: null, name: 'All Clients' }])

  const loadClients = async () => {
    try {
      const response = await api.getClients()
      clients.value = [
        { id: null, name: 'All Clients' },
        ...response.data
      ]
    } catch (error) {
      console.error('Error loading clients:', error)
      showSnackbar(t('errors.loadClientsFailed') || 'Failed to load clients', 'error')
    }
  }

  const refreshData = async () => {
    loading.value = true
    try {
      await kpiStore.fetchAllKPIs()
    } catch (error) {
      console.error('Error refreshing data:', error)
      showSnackbar(t('errors.refreshFailed') || 'Failed to refresh data', 'error')
    } finally {
      loading.value = false
    }
  }

  const handleClientChange = () => {
    kpiStore.setClient(selectedClient.value)
    refreshData()
  }

  const handleDateChange = () => {
    if (dateRange.value && dateRange.value.length === 2) {
      kpiStore.setDateRange(
        format(dateRange.value[0], 'yyyy-MM-dd'),
        format(dateRange.value[1], 'yyyy-MM-dd')
      )
      refreshData()
    }
  }

  const handleFilterChange = (filterParams) => {
    if (filterParams.client_id !== undefined) {
      selectedClient.value = filterParams.client_id
      kpiStore.setClient(filterParams.client_id)
    }

    if (filterParams.date_range) {
      const filterDateRange = filterParams.date_range
      if (filterDateRange.type === 'absolute' && filterDateRange.start_date && filterDateRange.end_date) {
        kpiStore.setDateRange(filterDateRange.start_date, filterDateRange.end_date)
        dateRange.value = [new Date(filterDateRange.start_date), new Date(filterDateRange.end_date)]
      } else if (filterDateRange.type === 'relative' && filterDateRange.relative_days !== undefined) {
        const end = new Date()
        const start = new Date()
        start.setDate(start.getDate() - filterDateRange.relative_days)
        const startStr = format(start, 'yyyy-MM-dd')
        const endStr = format(end, 'yyyy-MM-dd')
        kpiStore.setDateRange(startStr, endStr)
        dateRange.value = [start, end]
      }
    } else if (filterParams.start_date && filterParams.end_date) {
      kpiStore.setDateRange(filterParams.start_date, filterParams.end_date)
      dateRange.value = [new Date(filterParams.start_date), new Date(filterParams.end_date)]
    }

    refreshData()
  }

  const initialize = async () => {
    await loadClients()
    await dashboardStore.initializePreferences()
    await filtersStore.initializeFilters()
    await refreshData()
  }

  return {
    // State
    loading,
    selectedClient,
    dateRange,
    trendPeriod,
    clients,
    // Stores (exposed for template use)
    kpiStore,
    dashboardStore,
    filtersStore,
    // Methods
    loadClients,
    refreshData,
    handleClientChange,
    handleDateChange,
    handleFilterChange,
    initialize
  }
}
