/**
 * Composable for Plan vs Actual data fetching, filtering, and display helpers.
 * Handles: loading state, orders list, summary, filters, risk/variance coloring.
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getPlanVsActual, getPlanVsActualSummary } from '@/services/api/planVsActual'
import { useAuthStore } from '@/stores/authStore'
import { useNotificationStore } from '@/stores/notificationStore'

export function usePlanVsActual() {
  const { t } = useI18n()
  const authStore = useAuthStore()
  const notificationStore = useNotificationStore()

  // State
  const orders = ref([])
  const summary = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const filters = ref({
    startDate: null,
    endDate: null,
    lineId: null,
    status: null,
  })

  // Computed
  const clientId = computed(() => authStore.currentUser?.client_id)

  const statusOptions = [
    { title: 'Pending', value: 'PENDING' },
    { title: 'In Progress', value: 'IN_PROGRESS' },
    { title: 'Completed', value: 'COMPLETED' },
    { title: 'On Hold', value: 'ON_HOLD' },
    { title: 'Cancelled', value: 'CANCELLED' },
  ]

  const headers = computed(() => [
    { title: t('planVsActual.orderNumber'), key: 'order_number', sortable: true },
    { title: t('planVsActual.customer'), key: 'customer_name', sortable: true },
    { title: t('planVsActual.styleModel'), key: 'style_model', sortable: true },
    { title: t('planVsActual.plannedQty'), key: 'planned_quantity', sortable: true, align: 'end' },
    { title: t('planVsActual.actualCompleted'), key: 'actual_completed', sortable: true, align: 'end' },
    { title: t('planVsActual.variance'), key: 'variance_percentage', sortable: true, align: 'end' },
    { title: t('planVsActual.completion'), key: 'completion_percentage', sortable: true, width: '180px' },
    { title: t('planVsActual.requiredDate'), key: 'required_date', sortable: true },
    { title: t('planVsActual.risk'), key: 'on_time_risk', sortable: true },
  ])

  // Data fetching
  async function fetchData() {
    if (!clientId.value) return

    loading.value = true
    error.value = null
    try {
      const params = { client_id: clientId.value }
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
      error.value = err.response?.data?.detail || err.message || t('planVsActual.noData')
      notificationStore.showError(error.value)
    } finally {
      loading.value = false
    }
  }

  // Reset all filters and reload
  function resetFilters() {
    filters.value = {
      startDate: null,
      endDate: null,
      lineId: null,
      status: null,
    }
    fetchData()
  }

  // Display helpers
  function getRiskColor(risk) {
    const colors = {
      LOW: 'success',
      MEDIUM: 'warning',
      HIGH: 'error',
      OVERDUE: 'red-darken-3',
      COMPLETED: 'info',
      UNKNOWN: 'grey',
    }
    return colors[risk] || 'grey'
  }

  function getVarianceColor(variancePct) {
    if (variancePct >= 0) return 'success'
    if (variancePct >= -10) return 'warning'
    return 'error'
  }

  function getVarianceClass(variancePct) {
    if (variancePct >= 0) return 'text-success'
    if (variancePct >= -10) return 'text-warning'
    return 'text-error'
  }

  function getCompletionColor(completionPct) {
    if (completionPct >= 100) return 'success'
    if (completionPct >= 75) return 'info'
    if (completionPct >= 50) return 'warning'
    return 'error'
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-'
    try {
      const d = new Date(dateStr)
      return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
    } catch {
      return dateStr
    }
  }

  // Watch for client changes
  watch(clientId, (newVal) => {
    if (newVal) fetchData()
  })

  return {
    // State
    orders,
    summary,
    loading,
    error,
    filters,
    // Options
    statusOptions,
    // Computed
    headers,
    // Actions
    fetchData,
    resetFilters,
    // Display helpers
    getRiskColor,
    getVarianceColor,
    getVarianceClass,
    getCompletionColor,
    formatDate,
  }
}
