/**
 * Composable for Floating Pool reactive state, data fetching, computed properties,
 * and display helpers (summary, filtering, table headers, date formatting, client lookup).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import api from '@/services/api'
import { getFloatingPoolSimulationInsights } from '@/services/api/simulation'

export default function useFloatingPoolData() {
  const { t } = useI18n()

  // --- Reactive State ---
  const loading = ref(false)
  const loadingInsights = ref(false)
  const entries = ref([])
  const clients = ref([])
  const statusFilter = ref(null)
  const clientFilter = ref(null)
  const snackbar = ref({ show: false, message: '', color: 'success' })
  const insightsPanel = ref(null)
  const insights = ref({
    current_status: {},
    staffing_scenarios: [],
    recommendations: []
  })

  // Floating pool summary from API
  const poolSummary = ref({
    total_floating_pool_employees: 0,
    currently_available: 0,
    currently_assigned: 0,
    available_employees: []
  })

  // --- Computed ---
  const summary = computed(() => {
    if (poolSummary.value.total_floating_pool_employees > 0) {
      return {
        total: poolSummary.value.total_floating_pool_employees,
        available: poolSummary.value.currently_available,
        assigned: poolSummary.value.currently_assigned
      }
    }
    const total = entries.value.length
    const assigned = entries.value.filter(e => e.current_assignment).length
    return {
      total,
      available: total - assigned,
      assigned
    }
  })

  const utilizationPercent = computed(() => {
    if (summary.value.total === 0) return 0
    return Math.round((summary.value.assigned / summary.value.total) * 100)
  })

  const statusOptions = computed(() => [
    { title: t('admin.floatingPool.available'), value: 'available' },
    { title: t('admin.floatingPool.assigned'), value: 'assigned' }
  ])

  const clientOptions = computed(() => clients.value)

  const availableEmployees = computed(() => {
    if (poolSummary.value.available_employees?.length > 0) {
      return poolSummary.value.available_employees.map(e => ({
        employee_id: e.employee_id,
        employee_name: e.employee_name || `Employee #${e.employee_id}`
      }))
    }
    return entries.value.filter(e => !e.current_assignment).map(e => ({
      employee_id: e.employee_id,
      employee_name: e.employee_name || `Employee #${e.employee_id}`
    }))
  })

  const filteredEntries = computed(() => {
    let result = [...entries.value]

    if (statusFilter.value === 'available') {
      result = result.filter(e => !e.current_assignment)
    } else if (statusFilter.value === 'assigned') {
      result = result.filter(e => e.current_assignment)
    }

    if (clientFilter.value) {
      result = result.filter(e => e.current_assignment === clientFilter.value)
    }

    return result
  })

  const tableHeaders = computed(() => [
    { title: t('admin.floatingPool.employeeId'), key: 'employee_id', width: '100px' },
    { title: t('admin.floatingPool.employeeName'), key: 'employee_name' },
    { title: t('admin.floatingPool.status'), key: 'status', width: '120px' },
    { title: t('admin.floatingPool.assignedTo'), key: 'current_assignment' },
    { title: t('admin.floatingPool.availableFrom'), key: 'available_from', width: '150px' },
    { title: t('admin.floatingPool.availableTo'), key: 'available_to', width: '150px' },
    { title: t('common.actions'), key: 'actions', sortable: false, width: '200px' }
  ])

  // --- Methods ---
  const showSnackbar = (message, color = 'success') => {
    snackbar.value = { show: true, message, color }
  }

  const getClientName = (clientId) => {
    const client = clients.value.find(c => c.client_id === clientId)
    return client?.name || clientId
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    try {
      return format(new Date(dateStr), 'MMM dd, yyyy HH:mm')
    } catch {
      return dateStr
    }
  }

  const fetchData = async () => {
    loading.value = true
    try {
      const [poolResponse, summaryResponse, clientsResponse] = await Promise.all([
        api.get('/floating-pool'),
        api.get('/floating-pool/summary'),
        api.get('/clients')
      ])
      entries.value = poolResponse.data || []
      clients.value = clientsResponse.data || []

      if (summaryResponse.data) {
        poolSummary.value = summaryResponse.data

        if (entries.value.length === 0 && summaryResponse.data.available_employees?.length > 0) {
          entries.value = summaryResponse.data.available_employees.map(emp => ({
            pool_id: null,
            employee_id: emp.employee_id,
            employee_code: emp.employee_code,
            employee_name: emp.employee_name,
            position: emp.position,
            current_assignment: null,
            available_from: null,
            available_to: null,
            notes: null
          }))
        }
      }
    } catch (error) {
      console.error('Error fetching floating pool data:', error)
      showSnackbar(t('common.error') + ': ' + (error.response?.data?.detail || error.message), 'error')
    } finally {
      loading.value = false
    }
  }

  const fetchInsights = async () => {
    loadingInsights.value = true
    try {
      const response = await getFloatingPoolSimulationInsights({})
      insights.value = response.data || {
        current_status: {},
        staffing_scenarios: [],
        recommendations: []
      }
    } catch (error) {
      console.error('Error fetching simulation insights:', error)
    } finally {
      loadingInsights.value = false
    }
  }

  return {
    // State
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
    // Computed
    summary,
    utilizationPercent,
    statusOptions,
    clientOptions,
    availableEmployees,
    filteredEntries,
    tableHeaders,
    // Methods
    showSnackbar,
    getClientName,
    formatDate,
    fetchData,
    fetchInsights
  }
}
