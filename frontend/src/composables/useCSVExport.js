import { ref } from 'vue'
import api from '@/services/api/client'
import { useNotificationStore } from '@/stores/notificationStore'

/**
 * Composable for downloading CSV exports from the backend.
 *
 * Usage:
 *   const { downloading, downloadCSV } = useCSVExport()
 *   await downloadCSV('production-entries', { client_id: 'ABC', start_date: '2026-01-01' })
 */
export function useCSVExport() {
  const downloading = ref(false)

  /**
   * Download a CSV export for the given entity type.
   *
   * @param {string} entityType - The entity endpoint name (e.g. 'production-entries', 'work-orders')
   * @param {Object} params - Optional query parameters (client_id, start_date, end_date, line_id)
   * @param {string|null} filename - Optional custom filename; auto-generated if null
   */
  async function downloadCSV(entityType, params = {}, filename = null) {
    const notificationStore = useNotificationStore()
    downloading.value = true

    try {
      const response = await api.get(`/export/${entityType}`, {
        params,
        responseType: 'blob',
      })

      // Extract filename from Content-Disposition header or use provided/default
      const contentDisposition = response.headers['content-disposition']
      let resolvedFilename = filename
      if (!resolvedFilename && contentDisposition) {
        const match = contentDisposition.match(/filename="?([^";\n]+)"?/)
        if (match) {
          resolvedFilename = match[1]
        }
      }
      if (!resolvedFilename) {
        resolvedFilename = `${entityType}_export.csv`
      }

      // Create blob download link and trigger browser download
      const blob = new Blob([response.data], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', resolvedFilename)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)

      notificationStore.showSuccess(`${entityType} CSV downloaded successfully`)
    } catch (error) {
      const message = error.response?.data?.detail || error.message || 'CSV download failed'
      notificationStore.showError(`Export failed: ${message}`)
      throw error
    } finally {
      downloading.value = false
    }
  }

  return { downloading, downloadCSV }
}
