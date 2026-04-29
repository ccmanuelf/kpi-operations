/**
 * Composable for Quality KPI filter state and event handlers.
 * Client selection, date range, search box, client loading, and
 * filter-change callbacks that drive a refresh function the
 * caller provides.
 */
import { ref } from 'vue'
import { useKPIStore } from '@/stores/kpi'
import api from '@/services/api'

interface ClientOption {
  client_id?: string | number
  name?: string
  [key: string]: unknown
}

type RefreshFn = () => void | Promise<void>

export function useQualityFilters() {
  const kpiStore = useKPIStore()

  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const startDate = ref(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const endDate = ref(new Date().toISOString().split('T')[0])
  const tableSearch = ref('')

  const loadClients = async (): Promise<void> => {
    try {
      const response = await api.getClients()
      clients.value = response.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load clients:', error)
    }
  }

  const onClientChange = (refreshDataFn: RefreshFn): void => {
    kpiStore.setClient(selectedClient.value)
    refreshDataFn()
  }

  const onDateChange = (refreshDataFn: RefreshFn): void => {
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
    onDateChange,
  }
}
