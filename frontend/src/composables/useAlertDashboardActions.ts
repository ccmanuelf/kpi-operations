import { ref } from 'vue'
import api from '@/services/api'
import type { Alert } from './useAlertDashboardData'

export interface AlertDashboardActionsOptions {
  loadAlerts: () => Promise<void>
  loadSummary: () => Promise<void>
}

export interface ResolvableAlert extends Alert {
  alert_id: string | number
}

export default function useAlertDashboardActions({
  loadAlerts,
  loadSummary,
}: AlertDashboardActionsOptions) {
  const generating = ref(false)

  const showResolveDialog = ref(false)
  const resolvingAlert = ref<ResolvableAlert | null>(null)
  const resolutionNotes = ref('')

  async function generateAlerts(): Promise<void> {
    generating.value = true
    try {
      await api.post('/alerts/generate/check-all')
      await loadAlerts()
      await loadSummary()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to generate alerts:', error)
    } finally {
      generating.value = false
    }
  }

  async function handleAcknowledge(alertId: string | number): Promise<void> {
    try {
      await api.post(`/alerts/${alertId}/acknowledge`, {})
      await loadAlerts()
      await loadSummary()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to acknowledge alert:', error)
    }
  }

  function handleResolve(alert: ResolvableAlert): void {
    resolvingAlert.value = alert
    resolutionNotes.value = ''
    showResolveDialog.value = true
  }

  async function confirmResolve(): Promise<void> {
    if (!resolvingAlert.value || !resolutionNotes.value.trim()) return

    try {
      await api.post(`/alerts/${resolvingAlert.value.alert_id}/resolve`, {
        resolution_notes: resolutionNotes.value,
      })
      closeResolveDialog()
      await loadAlerts()
      await loadSummary()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to resolve alert:', error)
    }
  }

  function closeResolveDialog(): void {
    showResolveDialog.value = false
    resolvingAlert.value = null
    resolutionNotes.value = ''
  }

  async function handleDismiss(alertId: string | number): Promise<void> {
    if (!confirm('Are you sure you want to dismiss this alert?')) return

    try {
      await api.post(`/alerts/${alertId}/dismiss`)
      await loadAlerts()
      await loadSummary()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to dismiss alert:', error)
    }
  }

  return {
    generating,
    showResolveDialog,
    resolvingAlert,
    resolutionNotes,
    generateAlerts,
    handleAcknowledge,
    handleResolve,
    confirmResolve,
    closeResolveDialog,
    handleDismiss,
  }
}
