/**
 * Composable for Work Order data fetching, filtering, and display
 * helpers (progress/status/priority colors, overdue check, headers).
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { format, parseISO, isAfter, startOfDay } from 'date-fns'
import api from '@/services/api'
import { getClients } from '@/services/api/reference'
import { useNotificationStore } from '@/stores/notificationStore'
import { useKPIStore } from '@/stores/kpi'
import { useAuthStore } from '@/stores/authStore'
import type { WorkOrder } from './useWorkOrderForms'

export interface ClientOption {
  client_id: string
  client_name?: string
  name?: string
  [key: string]: unknown
}

export interface WorkOrderFilters {
  search: string
  status: string | null
  priority: string | null
  startDate: string
  endDate: string
}

export interface StatusOption {
  title: string
  value: string
}

interface TableHeader {
  title: string
  key: string
  sortable: boolean
  width?: string
}

interface SummaryStats {
  total: number
  active: number
  onHold: number
  completed: number
}

const debounce = <TArgs extends unknown[]>(
  fn: (...args: TArgs) => void,
  delay: number,
): ((...args: TArgs) => void) => {
  let timeoutId: ReturnType<typeof setTimeout> | undefined
  return (...args: TArgs) => {
    if (timeoutId) clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn(...args), delay)
  }
}

export function useWorkOrderData() {
  const { t } = useI18n()
  const notificationStore = useNotificationStore()
  const kpiStore = useKPIStore()
  const authStore = useAuthStore()

  const initialLoading = ref(true)
  const loading = ref(false)

  const workOrders = ref<WorkOrder[]>([])
  const clients = ref<ClientOption[]>([])

  const selectedWorkOrder = ref<WorkOrder | null>(null)
  const detailDrawerOpen = ref(false)

  // Active client for both filtering and addRow's payload. Operators
  // pinned to a single tenant default to their own client_id_assigned;
  // admins / power users with `client_id_assigned: null` follow the
  // shared kpi store's selectedClient so a single picker drives both
  // KPI dashboards and operational views (matches the Capacity
  // Planning pattern).
  const selectedClient = computed<string | null>({
    get() {
      // The legacy kpi store types selectedClient as `string | number | null`
      // (numeric IDs from the pre-string-PK era); we coerce to string at this
      // boundary so downstream consumers see only string | null.
      const raw =
        (authStore.user?.client_id_assigned as string | null | undefined)
        ?? kpiStore.selectedClient
        ?? null
      return raw == null ? null : String(raw)
    },
    set(value) {
      kpiStore.setClient(value)
    },
  })

  const filters = ref<WorkOrderFilters>({
    search: '',
    status: null,
    priority: null,
    startDate: '',
    endDate: '',
  })

  const statusOptions: StatusOption[] = [
    { title: 'Active', value: 'ACTIVE' },
    { title: 'On Hold', value: 'ON_HOLD' },
    { title: 'Completed', value: 'COMPLETED' },
    { title: 'Rejected', value: 'REJECTED' },
    { title: 'Cancelled', value: 'CANCELLED' },
  ]

  const priorityOptions: StatusOption[] = [
    { title: 'Urgent', value: 'URGENT' },
    { title: 'High', value: 'HIGH' },
    { title: 'Normal', value: 'NORMAL' },
    { title: 'Medium', value: 'MEDIUM' },
    { title: 'Low', value: 'LOW' },
  ]

  const headers = computed<TableHeader[]>(() => [
    { title: t('workOrders.workOrderId'), key: 'work_order_id', sortable: true },
    { title: t('production.style'), key: 'style_model', sortable: true },
    { title: t('jobs.progress'), key: 'progress', sortable: false, width: '200px' },
    { title: '%', key: 'progress_pct', sortable: true, width: '80px' },
    { title: t('common.status'), key: 'status', sortable: true },
    { title: t('workOrders.priority'), key: 'priority', sortable: true },
    { title: t('workOrders.dueDate'), key: 'planned_ship_date', sortable: true },
    { title: t('common.actions'), key: 'actions', sortable: false, width: '140px' },
  ])

  // "Active" rolls up the running-state enum values (ACTIVE +
  // IN_PROGRESS + RECEIVED + RELEASED) — backend WorkOrderStatusEnum
  // distinguishes those, but operators reading the dashboard care
  // about "is this WO in flight". Counting ACTIVE alone showed 0
  // even on a populated grid because seed data lands in IN_PROGRESS.
  const ACTIVE_STATUSES = new Set([
    'ACTIVE',
    'IN_PROGRESS',
    'RECEIVED',
    'RELEASED',
  ])

  const summaryStats = computed<SummaryStats>(() => {
    const stats: SummaryStats = {
      total: workOrders.value.length,
      active: 0,
      onHold: 0,
      completed: 0,
    }
    workOrders.value.forEach((wo) => {
      if (ACTIVE_STATUSES.has(wo.status)) stats.active++
      else if (wo.status === 'ON_HOLD') stats.onHold++
      else if (wo.status === 'COMPLETED' || wo.status === 'SHIPPED' || wo.status === 'CLOSED') {
        stats.completed++
      }
    })
    return stats
  })

  const loadClients = async (): Promise<void> => {
    try {
      const response = await getClients()
      clients.value = (response.data as ClientOption[]) || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading clients:', error)
    }
  }

  const loadWorkOrders = async (): Promise<void> => {
    loading.value = true
    try {
      const params: Record<string, unknown> = {}
      if (filters.value.status) params.status_filter = filters.value.status
      if (filters.value.search) params.style_model = filters.value.search
      if (selectedClient.value) params.client_id = selectedClient.value

      const response = await api.getWorkOrders(params)
      workOrders.value = response.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading work orders:', error)
      notificationStore.showError(t('notifications.workOrders.loadFailed'))
    } finally {
      loading.value = false
      initialLoading.value = false
    }
  }

  // Re-fetch work orders when the active client changes (e.g. via
  // dropdown or via another view's client picker shared through the
  // kpi store).
  watch(selectedClient, () => {
    loadWorkOrders()
  })

  const debouncedSearch = debounce(() => {
    loadWorkOrders()
  }, 300)

  const resetFilters = (): void => {
    filters.value = {
      search: '',
      status: null,
      priority: null,
      startDate: '',
      endDate: '',
    }
    loadWorkOrders()
  }

  const calculateProgress = (item: WorkOrder): number => {
    if (!item.planned_quantity || item.planned_quantity === 0) return 0
    return (item.actual_quantity / item.planned_quantity) * 100
  }

  const getProgressColor = (item: WorkOrder): string => {
    const progress = calculateProgress(item)
    if (progress >= 100) return 'success'
    if (progress >= 75) return 'info'
    if (progress >= 50) return 'warning'
    return 'error'
  }

  const getStatusColor = (status: string): string => {
    const colors: Record<string, string> = {
      ACTIVE: 'info',
      ON_HOLD: 'warning',
      COMPLETED: 'success',
      REJECTED: 'error',
      CANCELLED: 'grey',
    }
    return colors[status] || 'grey'
  }

  const formatStatus = (status: string): string => {
    const labels: Record<string, string> = {
      ACTIVE: 'Active',
      ON_HOLD: 'On Hold',
      COMPLETED: 'Completed',
      REJECTED: 'Rejected',
      CANCELLED: 'Cancelled',
    }
    return labels[status] || status
  }

  const getPriorityColor = (priority: string | null): string => {
    if (!priority) return 'grey'
    const colors: Record<string, string> = {
      URGENT: 'purple',
      HIGH: 'error',
      NORMAL: 'grey',
      MEDIUM: 'warning',
      LOW: 'success',
    }
    return colors[priority] || 'grey'
  }

  const formatDate = (dateStr: string | null | undefined): string => {
    if (!dateStr) return ''
    try {
      return format(parseISO(dateStr), 'MMM dd, yyyy')
    } catch {
      return dateStr
    }
  }

  const isOverdue = (item: WorkOrder): boolean => {
    if (!item.planned_ship_date || item.status === 'COMPLETED') return false
    const dueDate = parseISO(item.planned_ship_date)
    return isAfter(startOfDay(new Date()), dueDate)
  }

  const onRowClick = (
    _event: Event,
    payload: { item: WorkOrder },
  ): void => {
    openDetailDrawer(payload.item)
  }

  const openDetailDrawer = (workOrder: WorkOrder): void => {
    selectedWorkOrder.value = workOrder
    detailDrawerOpen.value = true
  }

  return {
    initialLoading,
    loading,
    workOrders,
    clients,
    selectedClient,
    selectedWorkOrder,
    detailDrawerOpen,
    filters,
    statusOptions,
    priorityOptions,
    headers,
    summaryStats,
    loadClients,
    loadWorkOrders,
    debouncedSearch,
    resetFilters,
    calculateProgress,
    getProgressColor,
    getStatusColor,
    formatStatus,
    getPriorityColor,
    formatDate,
    isOverdue,
    onRowClick,
    openDetailDrawer,
  }
}
