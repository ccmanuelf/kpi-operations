/**
 * Composable for Availability KPI data fetching, reactive state,
 * and helpers (color tokens, formatters, downtime history loader).
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

export default function useAvailabilityData() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  const loading = ref(false)
  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const startDate = ref(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const endDate = ref(new Date().toISOString().split('T')[0])
  const tableSearch = ref('')
  const downtimeHistory = ref<unknown[]>([])

  const availabilityData = computed(() => kpiStore.availability)

  const statusColor = computed<string>(() => {
    const avail = (availabilityData.value?.percentage as number) || 0
    if (avail >= 90) return 'success'
    if (avail >= 80) return 'amber-darken-3'
    return 'error'
  })

  const downtimeHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.reason'), key: 'reason', sortable: true },
    { title: t('kpi.headers.hours'), key: 'hours', sortable: true },
    { title: t('kpi.headers.percentage'), key: 'percentage', sortable: true },
  ])

  const equipmentHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.equipment'), key: 'equipment_name', sortable: true },
    { title: t('kpi.headers.uptime'), key: 'uptime', sortable: true },
    { title: t('kpi.headers.downtime'), key: 'downtime', sortable: true },
    { title: t('kpi.headers.availability'), key: 'availability', sortable: true },
  ])

  const downtimeHistoryHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.date'), key: 'shift_date', sortable: true },
    { title: t('kpi.headers.reason'), key: 'downtime_reason', sortable: true },
    { title: t('kpi.headers.duration'), key: 'downtime_duration_minutes', sortable: true },
    { title: t('kpi.headers.notes'), key: 'notes', sortable: true },
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

  const getAvailabilityColor = (avail: number): string => {
    if (avail >= 90) return 'success'
    if (avail >= 80) return 'amber-darken-3'
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

  const loadDowntimeHistory = async (): Promise<void> => {
    try {
      const params: Record<string, unknown> = {
        start_date: startDate.value,
        end_date: endDate.value,
      }
      if (selectedClient.value) {
        params.client_id = selectedClient.value
      }
      const response = await api.getDowntimeEntries(params)
      downtimeHistory.value = response.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load downtime history:', error)
      downtimeHistory.value = []
    }
  }

  const refreshData = async (): Promise<void> => {
    loading.value = true
    try {
      await Promise.all([kpiStore.fetchAvailability(), loadDowntimeHistory()])
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
    downtimeHistory,
    availabilityData,
    statusColor,
    downtimeHeaders,
    equipmentHeaders,
    downtimeHistoryHeaders,
    formatValue,
    formatDate,
    getAvailabilityColor,
    onClientChange,
    onDateChange,
    refreshData,
    initialize,
  }
}
