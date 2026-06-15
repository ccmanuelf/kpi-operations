/**
 * Composable for OEE KPI data fetching, reactive state, and helpers
 * (color tokens, formatters, component breakdown). OEE pulls
 * availability/performance/quality alongside its own value to drive
 * the formula card.
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

export default function useOEEData() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  const loading = ref(false)
  const clients = ref<ClientOption[]>([])
  const selectedClient = ref<string | number | null>(null)
  const startDate = ref(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0])
  const endDate = ref(new Date().toISOString().split('T')[0])
  const tableSearch = ref('')
  const historicalData = ref<unknown[]>([])

  const oeeData = computed(() => kpiStore.oee)

  const components = computed(() => ({
    availability: (kpiStore.availability?.percentage as number | undefined) ?? 91.5,
    performance: (kpiStore.performance?.percentage as number | undefined) ?? 92,
    quality: ((kpiStore.quality as { fpy?: number } | null)?.fpy as number | undefined) ?? 97,
  }))

  const statusColor = computed<string>(() => {
    const oee = (oeeData.value?.percentage as number) || 0
    if (oee >= 85) return 'var(--cds-support-success)'
    if (oee >= 65) return '#b45309'
    return 'var(--cds-support-error)'
  })

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
      await Promise.all([
        kpiStore.fetchOEE(),
        kpiStore.fetchAvailability(),
        kpiStore.fetchPerformance(),
        kpiStore.fetchQuality(),
        kpiStore.fetchDashboard(),
      ])
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
    oeeData,
    components,
    statusColor,
    historyHeaders,
    formatValue,
    formatDate,
    getEfficiencyColor,
    getPerformanceColor,
    onClientChange,
    onDateChange,
    refreshData,
    initialize,
  }
}
