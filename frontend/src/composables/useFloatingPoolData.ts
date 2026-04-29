/**
 * Composable for Floating Pool reactive state, data fetching,
 * computed summaries, and display helpers.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import api from '@/services/api'
import { getFloatingPoolSimulationInsights } from '@/services/api/simulation'

export interface PoolEntry {
  pool_id?: string | number | null
  employee_id?: string | number
  employee_code?: string
  employee_name?: string
  position?: string
  current_assignment?: string | number | null
  available_from?: string | null
  available_to?: string | null
  notes?: string | null
  [key: string]: unknown
}

export interface PoolClient {
  client_id: string | number
  name?: string
  [key: string]: unknown
}

export interface PoolSummary {
  total_floating_pool_employees: number
  currently_available: number
  currently_assigned: number
  available_employees?: PoolEntry[]
}

export interface SimulationInsights {
  current_status: Record<string, unknown>
  staffing_scenarios: unknown[]
  recommendations: unknown[]
  [key: string]: unknown
}

export interface SnackbarState {
  show: boolean
  message: string
  color: string
}

export interface AvailableEmployee {
  employee_id: string | number
  employee_name: string
}

export interface StatusOption {
  title: string
  value: 'available' | 'assigned'
}

export interface TableHeader {
  title: string
  key: string
  sortable?: boolean
  width?: string
}

export default function useFloatingPoolData() {
  const { t } = useI18n()

  const loading = ref(false)
  const loadingInsights = ref(false)
  const entries = ref<PoolEntry[]>([])
  const clients = ref<PoolClient[]>([])
  const statusFilter = ref<'available' | 'assigned' | null>(null)
  const clientFilter = ref<string | number | null>(null)
  const snackbar = ref<SnackbarState>({ show: false, message: '', color: 'success' })
  const insightsPanel = ref<unknown>(null)
  const insights = ref<SimulationInsights>({
    current_status: {},
    staffing_scenarios: [],
    recommendations: [],
  })

  const poolSummary = ref<PoolSummary>({
    total_floating_pool_employees: 0,
    currently_available: 0,
    currently_assigned: 0,
    available_employees: [],
  })

  const summary = computed(() => {
    if (poolSummary.value.total_floating_pool_employees > 0) {
      return {
        total: poolSummary.value.total_floating_pool_employees,
        available: poolSummary.value.currently_available,
        assigned: poolSummary.value.currently_assigned,
      }
    }
    const total = entries.value.length
    const assigned = entries.value.filter((e) => e.current_assignment).length
    return {
      total,
      available: total - assigned,
      assigned,
    }
  })

  const utilizationPercent = computed(() => {
    if (summary.value.total === 0) return 0
    return Math.round((summary.value.assigned / summary.value.total) * 100)
  })

  const statusOptions = computed<StatusOption[]>(() => [
    { title: t('admin.floatingPool.available'), value: 'available' },
    { title: t('admin.floatingPool.assigned'), value: 'assigned' },
  ])

  const clientOptions = computed(() => clients.value)

  const availableEmployees = computed<AvailableEmployee[]>(() => {
    const fromSummary = poolSummary.value.available_employees
    if (fromSummary && fromSummary.length > 0) {
      return fromSummary.map((e) => ({
        employee_id: e.employee_id ?? '',
        employee_name: e.employee_name || `Employee #${e.employee_id}`,
      }))
    }
    return entries.value
      .filter((e) => !e.current_assignment)
      .map((e) => ({
        employee_id: e.employee_id ?? '',
        employee_name: e.employee_name || `Employee #${e.employee_id}`,
      }))
  })

  const filteredEntries = computed<PoolEntry[]>(() => {
    let result = [...entries.value]

    if (statusFilter.value === 'available') {
      result = result.filter((e) => !e.current_assignment)
    } else if (statusFilter.value === 'assigned') {
      result = result.filter((e) => e.current_assignment)
    }

    if (clientFilter.value) {
      result = result.filter((e) => e.current_assignment === clientFilter.value)
    }

    return result
  })

  const tableHeaders = computed<TableHeader[]>(() => [
    { title: t('admin.floatingPool.employeeId'), key: 'employee_id', width: '100px' },
    { title: t('admin.floatingPool.employeeName'), key: 'employee_name' },
    { title: t('admin.floatingPool.status'), key: 'status', width: '120px' },
    { title: t('admin.floatingPool.assignedTo'), key: 'current_assignment' },
    {
      title: t('admin.floatingPool.availableFrom'),
      key: 'available_from',
      width: '150px',
    },
    {
      title: t('admin.floatingPool.availableTo'),
      key: 'available_to',
      width: '150px',
    },
    { title: t('common.actions'), key: 'actions', sortable: false, width: '200px' },
  ])

  const showSnackbar = (message: string, color: string = 'success'): void => {
    snackbar.value = { show: true, message, color }
  }

  const getClientName = (clientId: string | number): string | number => {
    const client = clients.value.find((c) => c.client_id === clientId)
    return client?.name || clientId
  }

  const formatDate = (dateStr: string | null | undefined): string => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'MMM dd, yyyy HH:mm')
    } catch {
      return dateStr
    }
  }

  const fetchData = async (): Promise<void> => {
    loading.value = true
    try {
      const [poolResponse, summaryResponse, clientsResponse] = await Promise.all([
        api.get('/floating-pool'),
        api.get('/floating-pool/summary'),
        api.get('/clients'),
      ])
      entries.value = poolResponse.data || []
      clients.value = clientsResponse.data || []

      if (summaryResponse.data) {
        poolSummary.value = summaryResponse.data as PoolSummary

        if (
          entries.value.length === 0 &&
          (summaryResponse.data as PoolSummary).available_employees?.length
        ) {
          entries.value = (summaryResponse.data as PoolSummary).available_employees!.map(
            (emp): PoolEntry => ({
              pool_id: null,
              employee_id: emp.employee_id,
              employee_code: emp.employee_code,
              employee_name: emp.employee_name,
              position: emp.position,
              current_assignment: null,
              available_from: null,
              available_to: null,
              notes: null,
            }),
          )
        }
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error fetching floating pool data:', error)
      const ax = error as { response?: { data?: { detail?: string } }; message?: string }
      showSnackbar(
        t('common.error') + ': ' + (ax?.response?.data?.detail || ax?.message || ''),
        'error',
      )
    } finally {
      loading.value = false
    }
  }

  const fetchInsights = async (): Promise<void> => {
    loadingInsights.value = true
    try {
      const response = await getFloatingPoolSimulationInsights({})
      insights.value = (response.data as SimulationInsights) || {
        current_status: {},
        staffing_scenarios: [],
        recommendations: [],
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error fetching simulation insights:', error)
    } finally {
      loadingInsights.value = false
    }
  }

  return {
    loading,
    loadingInsights,
    entries,
    clients,
    statusFilter,
    clientFilter,
    snackbar,
    insightsPanel,
    insights,
    poolSummary,
    summary,
    utilizationPercent,
    statusOptions,
    clientOptions,
    availableEmployees,
    filteredEntries,
    tableHeaders,
    showSnackbar,
    getClientName,
    formatDate,
    fetchData,
    fetchInsights,
  }
}
