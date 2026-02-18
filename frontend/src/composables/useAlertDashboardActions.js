import { ref } from 'vue'
import api from '@/services/api'

export default function useAlertDashboardActions({ loadAlerts, loadSummary }) {
  const generating = ref(false)

  const showResolveDialog = ref(false)
  const resolvingAlert = ref(null)
  const resolutionNotes = ref('')

  async function generateAlerts() {
    generating.value = true
    try {
      await api.post('/alerts/generate/check-all')
      await loadAlerts()
      await loadSummary()
    } catch (error) {
      console.error('Failed to generate alerts:', error)
    } finally {
      generating.value = false
    }
  }

  async function handleAcknowledge(alertId) {
    try {
      await api.post(`/alerts/${alertId}/acknowledge`, {})
      await loadAlerts()
      await loadSummary()
    } catch (error) {
      console.error('Failed to acknowledge alert:', error)
    }
  }

  function handleResolve(alert) {
    resolvingAlert.value = alert
    resolutionNotes.value = ''
    showResolveDialog.value = true
  }

  async function confirmResolve() {
    if (!resolvingAlert.value || !resolutionNotes.value.trim()) return

    try {
      await api.post(`/alerts/${resolvingAlert.value.alert_id}/resolve`, {
        resolution_notes: resolutionNotes.value
      })
      closeResolveDialog()
      await loadAlerts()
      await loadSummary()
    } catch (error) {
      console.error('Failed to resolve alert:', error)
    }
  }

  function closeResolveDialog() {
    showResolveDialog.value = false
    resolvingAlert.value = null
    resolutionNotes.value = ''
  }

  async function handleDismiss(alertId) {
    if (!confirm('Are you sure you want to dismiss this alert?')) return

    try {
      await api.post(`/alerts/${alertId}/dismiss`)
      await loadAlerts()
      await loadSummary()
    } catch (error) {
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
    handleDismiss
  }
}
