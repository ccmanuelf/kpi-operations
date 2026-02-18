/**
 * Composable for Quality KPI filter state and event handlers.
 * Handles: client selection, date range, search, client loading, filter change callbacks.
 */
import { ref } from 'vue'
import { useKPIStore } from '@/stores/kpi'
import api from '@/services/api'

export function useQualityFilters() {
  const kpiStore = useKPIStore()

  // --- Filter state ---
  const clients = ref([])
  const selectedClient = ref(null)
  const startDate = ref(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const endDate = ref(new Date().toISOString().split('T')[0])
  const tableSearch = ref('')

  // --- API ---
  const loadClients = async () => {
    try {
      const response = await api.getClients()
      clients.value = response.data || []
    } catch (error) {
      console.error('Failed to load clients:', error)
    }
  }

  // --- Event handlers ---
  const onClientChange = (refreshDataFn) => {
    kpiStore.setClient(selectedClient.value)
    refreshDataFn()
  }

  const onDateChange = (refreshDataFn) => {
    kpiStore.setDateRange(startDate.value, endDate.value)
    refreshDataFn()
  }

  return {
    clients,
    selectedClient,
    startDate,
    endDate,
    tableSearch,
    loadClients,
    onClientChange,
    onDateChange
  }
}
