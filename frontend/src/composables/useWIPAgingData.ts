/**
 * Composable for WIP Aging KPI data fetching, reactive state, and
 * helpers (color tokens, formatters, hold history loader).
 *
 * NOTE: thresholds are INVERTED — lower aging (in days) is better.
 * `avg <= 7` is healthy (green), `avg <= 14` is warning, else error.
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

export default function useWIPAgingData() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  const loading = ref(false)
  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const startDate = ref(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const endDate = ref(new Date().toISOString().split('T')[0])
  const tableSearch = ref('')
  const holdHistory = ref<unknown[]>([])

  const wipData = computed(() => kpiStore.wipAging)

  const statusColor = computed<string>(() => {
    const avg = (wipData.value?.average_days as number) || 0
    if (avg <= 7) return 'success'
    if (avg <= 14) return 'amber-darken-3'
    return 'error'
  })

  const agingHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.workOrder'), key: 'work_order', sortable: true },
    { title: t('kpi.headers.product'), key: 'product', sortable: true },
    { title: t('kpi.headers.age'), key: 'age', sortable: true },
    { title: t('kpi.headers.quantity'), key: 'quantity', sortable: true },
  ])

  const historyHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.holdDate'), key: 'hold_date', sortable: true },
    { title: t('kpi.headers.workOrder'), key: 'work_order_id', sortable: true },
    { title: t('kpi.headers.category'), key: 'hold_reason_category', sortable: true },
    { title: t('kpi.headers.reason'), key: 'hold_reason_description', sortable: true },
    { title: t('kpi.headers.status'), key: 'hold_status', sortable: true },
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

  // Inverted threshold — lower age (days) is better.
  const getAgeColor = (age: number): string => {
    if (age <= 7) return 'success'
    if (age <= 14) return 'amber-darken-3'
    return 'error'
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

  const loadHoldHistory = async (): Promise<void> => {
    try {
      const params: Record<string, unknown> = {
        start_date: startDate.value,
        end_date: endDate.value,
      }
      if (selectedClient.value) {
        params.client_id = selectedClient.value
      }
      const response = await api.getHoldEntries(params)
      holdHistory.value = response.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load hold history:', error)
      holdHistory.value = []
    }
  }

  const refreshData = async (): Promise<void> => {
    loading.value = true
    try {
      await Promise.all([kpiStore.fetchWIPAging(), loadHoldHistory()])
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
    holdHistory,
    wipData,
    statusColor,
    agingHeaders,
    historyHeaders,
    formatValue,
    formatDate,
    getAgeColor,
    onClientChange,
    onDateChange,
    refreshData,
    initialize,
  }
}
