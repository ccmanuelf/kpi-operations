/**
 * Composable for KPI Dashboard data fetching and filter state.
 * Loading state, clients list, date range, per-KPI thresholds, refresh.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import { useDashboardStore } from '@/stores/dashboardStore'
import { useFiltersStore, type FilterConfig } from '@/stores/filtersStore'
import api from '@/services/api'

interface ClientOption {
  id: string | number | null
  name: string
  [key: string]: unknown
}

interface KPIThresholdRow {
  threshold_id?: string
  kpi_key?: string
  target_value: number
  warning_threshold: number | null
  critical_threshold: number | null
  unit?: string
  higher_is_better: 'Y' | 'N'
  is_global?: boolean
}

export interface KpiThreshold {
  target: number
  warning: number | null
  critical: number | null
  higher_is_better: boolean
}

type SnackbarFn = (_message: string, _color: string) => void

export function useKPIDashboardData(showSnackbar: SnackbarFn) {
  const { t } = useI18n()
  const kpiStore = useKPIStore()
  const dashboardStore = useDashboardStore()
  const filtersStore = useFiltersStore()

  const loading = ref(false)
  const selectedClient = ref<string | number | null>(null)
  const selectedLineId = ref<string | number | null>(null)
  const dateRange = ref<Date[]>([
    new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
    new Date(),
  ])
  const clients = ref<ClientOption[]>([{ id: null, name: 'All Clients' }])
  const kpiThresholds = ref<Record<string, KPIThresholdRow>>({})

  const loadClients = async (): Promise<void> => {
    try {
      const response = await api.getClients()
      clients.value = [
        { id: null, name: 'All Clients' },
        ...((response.data as ClientOption[]) || []),
      ]
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading clients:', error)
      showSnackbar(t('errors.loadClientsFailed') || 'Failed to load clients', 'error')
    }
  }

  const loadThresholds = async (): Promise<void> => {
    try {
      const response = await api.getKPIThresholds(selectedClient.value)
      kpiThresholds.value =
        (response.data?.thresholds as Record<string, KPIThresholdRow>) || {}
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading KPI thresholds:', error)
    }
  }

  // Per-KPI target/warning/critical/direction for the diagnostic trend
  // charts' OOC engine. Returns null when the KPI has no threshold row
  // (e.g. wip_aging, throughput) — the OOC engine correctly falls back
  // to SPC-only control limits in that case.
  const thresholdFor = (thresholdKey: string): KpiThreshold | null => {
    const row = kpiThresholds.value[thresholdKey]
    if (!row) return null
    return {
      target: row.target_value,
      warning: row.warning_threshold ?? null,
      critical: row.critical_threshold ?? null,
      higher_is_better: row.higher_is_better === 'Y',
    }
  }

  const refreshData = async (): Promise<void> => {
    loading.value = true
    try {
      // The kpiStore.fetchAllKPIs signature takes no arguments;
      // line filtering is applied at the per-KPI level by the
      // store using its `selectedClient` state. Preserved a no-op
      // params accumulator for callsite parity.
      void selectedLineId.value
      await Promise.all([kpiStore.fetchAllKPIs(), loadThresholds()])
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error refreshing data:', error)
      showSnackbar(t('errors.refreshFailed') || 'Failed to refresh data', 'error')
    } finally {
      loading.value = false
    }
  }

  const onLineFilterChange = (lineId: string | number | null): void => {
    selectedLineId.value = lineId
    refreshData()
  }

  const handleClientChange = (): void => {
    kpiStore.setClient(selectedClient.value)
    refreshData()
  }

  const handleDateChange = (): void => {
    if (dateRange.value && dateRange.value.length === 2) {
      kpiStore.setDateRange(
        format(dateRange.value[0], 'yyyy-MM-dd'),
        format(dateRange.value[1], 'yyyy-MM-dd'),
      )
      refreshData()
    }
  }

  type FilterParamsLike = FilterConfig & {
    start_date?: string
    end_date?: string
  }

  const handleFilterChange = (filterParams: FilterParamsLike): void => {
    if (filterParams.client_id !== undefined) {
      selectedClient.value = (filterParams.client_id as string | number | null) ?? null
      kpiStore.setClient(selectedClient.value)
    }

    if (filterParams.date_range) {
      const filterDateRange = filterParams.date_range
      if (
        filterDateRange.type === 'absolute' &&
        filterDateRange.start_date &&
        filterDateRange.end_date
      ) {
        kpiStore.setDateRange(filterDateRange.start_date, filterDateRange.end_date)
        dateRange.value = [
          new Date(filterDateRange.start_date),
          new Date(filterDateRange.end_date),
        ]
      } else if (
        filterDateRange.type === 'relative' &&
        filterDateRange.relative_days !== undefined
      ) {
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

  const initialize = async (): Promise<void> => {
    await loadClients()
    await dashboardStore.initializePreferences()
    await filtersStore.initializeFilters()
    await refreshData()
  }

  return {
    loading,
    selectedClient,
    selectedLineId,
    dateRange,
    clients,
    kpiStore,
    dashboardStore,
    filtersStore,
    loadClients,
    refreshData,
    handleClientChange,
    handleDateChange,
    handleFilterChange,
    onLineFilterChange,
    initialize,
    thresholdFor,
  }
}
