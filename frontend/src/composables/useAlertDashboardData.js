import { ref, computed } from 'vue'
import api from '@/services/api'

export default function useAlertDashboardData() {
  const alerts = ref([])
  const summary = ref({
    total_active: 0,
    by_severity: {},
    by_category: {},
    critical_count: 0,
    urgent_count: 0
  })
  const loading = ref(false)

  const filters = ref({
    category: '',
    severity: '',
    status: 'active'
  })

  const urgentAlerts = computed(() =>
    alerts.value.filter(a => a.severity === 'urgent' && a.status === 'active')
  )

  const criticalAlerts = computed(() =>
    alerts.value.filter(a => a.severity === 'critical' && a.status === 'active')
  )

  async function loadAlerts() {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (filters.value.category) params.append('category', filters.value.category)
      if (filters.value.severity) params.append('severity', filters.value.severity)
      if (filters.value.status) params.append('status', filters.value.status)

      const response = await api.get(`/alerts/?${params.toString()}`)
      alerts.value = response.data
    } catch (error) {
      console.error('Failed to load alerts:', error)
    } finally {
      loading.value = false
    }
  }

  async function loadSummary() {
    try {
      const response = await api.get('/alerts/summary')
      summary.value = response.data
    } catch (error) {
      console.error('Failed to load summary:', error)
    }
  }

  return {
    alerts,
    summary,
    loading,
    filters,
    urgentAlerts,
    criticalAlerts,
    loadAlerts,
    loadSummary
  }
}
