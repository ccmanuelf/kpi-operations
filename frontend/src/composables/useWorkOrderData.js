/**
 * Composable for Work Order data fetching, filtering, and display helpers.
 * Handles: loading state, work orders list, filters, summary stats,
 *          table headers, progress/status/priority formatting.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format, parseISO, isAfter, startOfDay } from 'date-fns'
import api from '@/services/api'
import { useNotificationStore } from '@/stores/notificationStore'

// Simple debounce utility
const debounce = (fn, delay) => {
  let timeoutId
  return (...args) => {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn(...args), delay)
  }
}

export function useWorkOrderData() {
  const { t } = useI18n()
  const notificationStore = useNotificationStore()

  // Loading state
  const initialLoading = ref(true)
  const loading = ref(false)

  // Data
  const workOrders = ref([])

  // Drawer state
  const selectedWorkOrder = ref(null)
  const detailDrawerOpen = ref(false)

  // Filters
  const filters = ref({
    search: '',
    status: null,
    priority: null,
    startDate: '',
    endDate: ''
  })

  // Options
  const statusOptions = [
    { title: 'Active', value: 'ACTIVE' },
    { title: 'On Hold', value: 'ON_HOLD' },
    { title: 'Completed', value: 'COMPLETED' },
    { title: 'Rejected', value: 'REJECTED' },
    { title: 'Cancelled', value: 'CANCELLED' }
  ]

  const priorityOptions = [
    { title: 'High', value: 'HIGH' },
    { title: 'Medium', value: 'MEDIUM' },
    { title: 'Low', value: 'LOW' }
  ]

  // Table headers
  const headers = computed(() => [
    { title: t('workOrders.workOrderId'), key: 'work_order_id', sortable: true },
    { title: t('production.style'), key: 'style_model', sortable: true },
    { title: t('jobs.progress'), key: 'progress', sortable: false, width: '200px' },
    { title: '%', key: 'progress_pct', sortable: true, width: '80px' },
    { title: t('common.status'), key: 'status', sortable: true },
    { title: t('workOrders.priority'), key: 'priority', sortable: true },
    { title: t('workOrders.dueDate'), key: 'planned_ship_date', sortable: true },
    { title: t('common.actions'), key: 'actions', sortable: false, width: '140px' }
  ])

  // Summary stats
  const summaryStats = computed(() => {
    const stats = {
      total: workOrders.value.length,
      active: 0,
      onHold: 0,
      completed: 0
    }
    workOrders.value.forEach(wo => {
      if (wo.status === 'ACTIVE') stats.active++
      else if (wo.status === 'ON_HOLD') stats.onHold++
      else if (wo.status === 'COMPLETED') stats.completed++
    })
    return stats
  })

  // Data fetching
  const loadWorkOrders = async () => {
    loading.value = true
    try {
      const params = {}
      if (filters.value.status) params.status_filter = filters.value.status
      if (filters.value.search) params.style_model = filters.value.search

      const response = await api.getWorkOrders(params)
      workOrders.value = response.data || []
    } catch (error) {
      console.error('Error loading work orders:', error)
      notificationStore.showError('Failed to load work orders')
    } finally {
      loading.value = false
      initialLoading.value = false
    }
  }

  const debouncedSearch = debounce(() => {
    loadWorkOrders()
  }, 300)

  const resetFilters = () => {
    filters.value = {
      search: '',
      status: null,
      priority: null,
      startDate: '',
      endDate: ''
    }
    loadWorkOrders()
  }

  // Display helpers
  const calculateProgress = (item) => {
    if (!item.planned_quantity || item.planned_quantity === 0) return 0
    return (item.actual_quantity / item.planned_quantity) * 100
  }

  const getProgressColor = (item) => {
    const progress = calculateProgress(item)
    if (progress >= 100) return 'success'
    if (progress >= 75) return 'info'
    if (progress >= 50) return 'warning'
    return 'error'
  }

  const getStatusColor = (status) => {
    const colors = {
      ACTIVE: 'info',
      ON_HOLD: 'warning',
      COMPLETED: 'success',
      REJECTED: 'error',
      CANCELLED: 'grey'
    }
    return colors[status] || 'grey'
  }

  const formatStatus = (status) => {
    const labels = {
      ACTIVE: 'Active',
      ON_HOLD: 'On Hold',
      COMPLETED: 'Completed',
      REJECTED: 'Rejected',
      CANCELLED: 'Cancelled'
    }
    return labels[status] || status
  }

  const getPriorityColor = (priority) => {
    const colors = {
      HIGH: 'error',
      MEDIUM: 'warning',
      LOW: 'success'
    }
    return colors[priority] || 'grey'
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    try {
      return format(parseISO(dateStr), 'MMM dd, yyyy')
    } catch {
      return dateStr
    }
  }

  const isOverdue = (item) => {
    if (!item.planned_ship_date || item.status === 'COMPLETED') return false
    const dueDate = parseISO(item.planned_ship_date)
    return isAfter(startOfDay(new Date()), dueDate)
  }

  // Drawer / row interactions
  const onRowClick = (event, { item }) => {
    openDetailDrawer(item)
  }

  const openDetailDrawer = (workOrder) => {
    selectedWorkOrder.value = workOrder
    detailDrawerOpen.value = true
  }

  return {
    // State
    initialLoading,
    loading,
    workOrders,
    selectedWorkOrder,
    detailDrawerOpen,
    filters,
    // Options
    statusOptions,
    priorityOptions,
    // Computed
    headers,
    summaryStats,
    // Data fetching
    loadWorkOrders,
    debouncedSearch,
    resetFilters,
    // Display helpers
    calculateProgress,
    getProgressColor,
    getStatusColor,
    formatStatus,
    getPriorityColor,
    formatDate,
    isOverdue,
    // Interactions
    onRowClick,
    openDetailDrawer
  }
}
