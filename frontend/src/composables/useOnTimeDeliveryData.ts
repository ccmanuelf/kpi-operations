/**
 * Composable for On-Time Delivery KPI data fetching, reactive state,
 * and helpers (color tokens, formatters).
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

export default function useOnTimeDeliveryData() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  const loading = ref(false)
  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const startDate = ref(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const endDate = ref(new Date().toISOString().split('T')[0])
  const tableSearch = ref('')
  const historicalData = ref<unknown[]>([])

  const otdData = computed(() => kpiStore.onTimeDelivery)

  const statusColor = computed<string>(() => {
    const percentage = (otdData.value?.percentage as number) || 0
    if (percentage >= 95) return 'success'
    if (percentage >= 85) return 'amber-darken-3'
    return 'error'
  })

  const clientHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.client'), key: 'client_name', sortable: true },
    { title: t('kpi.headers.total'), key: 'total_deliveries', sortable: true },
    { title: t('kpi.headers.onTime'), key: 'on_time', sortable: true },
    { title: t('kpi.headers.otdPercent'), key: 'otd_percentage', sortable: true },
  ])

  const lateHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.date'), key: 'delivery_date', sortable: true },
    { title: t('kpi.headers.workOrder'), key: 'work_order', sortable: true },
    { title: t('kpi.headers.client'), key: 'client', sortable: true },
    { title: t('kpi.headers.delay'), key: 'delay_hours', sortable: true },
  ])

  const historyHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.date'), key: 'date', sortable: true },
    { title: t('kpi.headers.totalUnits'), key: 'total_units', sortable: true },
    { title: t('kpi.headers.efficiencyPercent'), key: 'avg_efficiency', sortable: true },
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

  const getOTDColor = (percentage: number): string => {
    if (percentage >= 95) return 'success'
    if (percentage >= 85) return 'amber-darken-3'
    return 'error'
  }

  const getEfficiencyColor = (eff: number): string => {
    if (eff >= 85) return 'success'
    if (eff >= 70) return 'amber-darken-3'
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

  const refreshData = async (): Promise<void> => {
    loading.value = true
    try {
      await Promise.all([kpiStore.fetchOnTimeDelivery(), kpiStore.fetchDashboard()])
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
    otdData,
    statusColor,
    clientHeaders,
    lateHeaders,
    historyHeaders,
    formatValue,
    formatDate,
    getOTDColor,
    getEfficiencyColor,
    onClientChange,
    onDateChange,
    refreshData,
    initialize,
  }
}
