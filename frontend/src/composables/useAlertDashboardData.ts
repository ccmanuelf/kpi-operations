import { ref, computed } from 'vue'
import api from '@/services/api'

export type AlertSeverity = 'critical' | 'urgent' | 'high' | 'medium' | 'low' | string
export type AlertStatus = 'active' | 'acknowledged' | 'resolved' | string

export interface Alert {
  id?: string | number
  severity?: AlertSeverity
  status?: AlertStatus
  category?: string
  [key: string]: unknown
}

export interface AlertSummary {
  total_active: number
  by_severity: Record<string, number>
  by_category: Record<string, number>
  critical_count: number
  urgent_count: number
}

export interface AlertFilters {
  category: string
  severity: string
  status: string
}

export default function useAlertDashboardData() {
  const alerts = ref<Alert[]>([])
  const summary = ref<AlertSummary>({
    total_active: 0,
    by_severity: {},
    by_category: {},
    critical_count: 0,
    urgent_count: 0,
  })
  const loading = ref(false)

  const filters = ref<AlertFilters>({
    category: '',
    severity: '',
    status: 'active',
  })

  const urgentAlerts = computed(() =>
    alerts.value.filter((a) => a.severity === 'urgent' && a.status === 'active'),
  )

  const criticalAlerts = computed(() =>
    alerts.value.filter((a) => a.severity === 'critical' && a.status === 'active'),
  )

  async function loadAlerts(): Promise<void> {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (filters.value.category) params.append('category', filters.value.category)
      if (filters.value.severity) params.append('severity', filters.value.severity)
      if (filters.value.status) params.append('status', filters.value.status)

      const response = await api.get(`/alerts/?${params.toString()}`)
      alerts.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load alerts:', error)
    } finally {
      loading.value = false
    }
  }

  async function loadSummary(): Promise<void> {
    try {
      const response = await api.get('/alerts/summary')
      summary.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
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
    loadSummary,
  }
}
