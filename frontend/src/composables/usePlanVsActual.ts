/**
 * Composable for the Plan-vs-Actual variance dashboard. Loading,
 * orders list, summary, filters, and risk/variance/completion
 * coloring helpers.
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getPlanVsActual, getPlanVsActualSummary } from '@/services/api/planVsActual'
import { useAuthStore } from '@/stores/authStore'
import { useNotificationStore } from '@/stores/notificationStore'

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'OVERDUE' | 'COMPLETED' | 'UNKNOWN'
export type OrderStatus =
  | 'PENDING'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'ON_HOLD'
  | 'CANCELLED'

export interface PlanVsActualOrder {
  order_number?: string
  customer_name?: string
  style_model?: string
  planned_quantity?: number
  actual_completed?: number
  variance_percentage?: number
  completion_percentage?: number
  required_date?: string
  on_time_risk?: RiskLevel
  [key: string]: unknown
}

export interface PlanVsActualSummary {
  total_orders?: number
  on_track?: number
  at_risk?: number
  overdue?: number
  [key: string]: unknown
}

export interface PlanVsActualFilters {
  startDate: string | null
  endDate: string | null
  lineId: string | number | null
  status: OrderStatus | null
}

export interface StatusOption {
  title: string
  value: OrderStatus
}

export interface TableHeader {
  title: string
  key: string
  sortable: boolean
  align?: 'start' | 'center' | 'end'
  width?: string
}

export function usePlanVsActual() {
  const { t } = useI18n()
  const authStore = useAuthStore()
  const notificationStore = useNotificationStore()

  const orders = ref<PlanVsActualOrder[]>([])
  const summary = ref<PlanVsActualSummary | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const filters = ref<PlanVsActualFilters>({
    startDate: null,
    endDate: null,
    lineId: null,
    status: null,
  })

  const clientId = computed<string | number | null>(
    () => (authStore.currentUser?.client_id_assigned as string | number | null) ?? null,
  )

  const statusOptions: StatusOption[] = [
    { title: 'Pending', value: 'PENDING' },
    { title: 'In Progress', value: 'IN_PROGRESS' },
    { title: 'Completed', value: 'COMPLETED' },
    { title: 'On Hold', value: 'ON_HOLD' },
    { title: 'Cancelled', value: 'CANCELLED' },
  ]

  const headers = computed<TableHeader[]>(() => [
    { title: t('planVsActual.orderNumber'), key: 'order_number', sortable: true },
    { title: t('planVsActual.customer'), key: 'customer_name', sortable: true },
    { title: t('planVsActual.styleModel'), key: 'style_model', sortable: true },
    {
      title: t('planVsActual.plannedQty'),
      key: 'planned_quantity',
      sortable: true,
      align: 'end',
    },
    {
      title: t('planVsActual.actualCompleted'),
      key: 'actual_completed',
      sortable: true,
      align: 'end',
    },
    {
      title: t('planVsActual.variance'),
      key: 'variance_percentage',
      sortable: true,
      align: 'end',
    },
    {
      title: t('planVsActual.completion'),
      key: 'completion_percentage',
      sortable: true,
      width: '180px',
    },
    { title: t('planVsActual.requiredDate'), key: 'required_date', sortable: true },
    { title: t('planVsActual.risk'), key: 'on_time_risk', sortable: true },
  ])

  async function fetchData(): Promise<void> {
    if (!clientId.value) return

    loading.value = true
    error.value = null
    try {
      const params: Record<string, unknown> = { client_id: clientId.value }
      if (filters.value.startDate) params.start_date = filters.value.startDate
      if (filters.value.endDate) params.end_date = filters.value.endDate
      if (filters.value.lineId) params.line_id = filters.value.lineId
      if (filters.value.status) params.status = filters.value.status

      const [detailRes, summaryRes] = await Promise.all([
        getPlanVsActual(params),
        getPlanVsActualSummary({ client_id: clientId.value }),
      ])

      orders.value = detailRes.data
      summary.value = summaryRes.data
    } catch (err) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      error.value = ax?.response?.data?.detail || ax?.message || t('planVsActual.noData')
      notificationStore.showError(error.value)
    } finally {
      loading.value = false
    }
  }

  function resetFilters(): void {
    filters.value = {
      startDate: null,
      endDate: null,
      lineId: null,
      status: null,
    }
    fetchData()
  }

  function getRiskColor(risk: RiskLevel | string | undefined): string {
    const colors: Record<string, string> = {
      LOW: 'success',
      MEDIUM: 'warning',
      HIGH: 'error',
      OVERDUE: 'red-darken-3',
      COMPLETED: 'info',
      UNKNOWN: 'grey',
    }
    return (risk && colors[risk]) || 'grey'
  }

  function getVarianceColor(variancePct: number): string {
    if (variancePct >= 0) return 'success'
    if (variancePct >= -10) return 'warning'
    return 'error'
  }

  function getVarianceClass(variancePct: number): string {
    if (variancePct >= 0) return 'text-success'
    if (variancePct >= -10) return 'text-warning'
    return 'text-error'
  }

  function getCompletionColor(completionPct: number): string {
    if (completionPct >= 100) return 'success'
    if (completionPct >= 75) return 'info'
    if (completionPct >= 50) return 'warning'
    return 'error'
  }

  function formatDate(dateStr: string | null | undefined): string {
    if (!dateStr) return '-'
    try {
      const d = new Date(dateStr)
      return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      })
    } catch {
      return dateStr
    }
  }

  watch(clientId, (newVal) => {
    if (newVal) fetchData()
  })

  return {
    orders,
    summary,
    loading,
    error,
    filters,
    statusOptions,
    headers,
    fetchData,
    resetFilters,
    getRiskColor,
    getVarianceColor,
    getVarianceClass,
    getCompletionColor,
    formatDate,
  }
}
