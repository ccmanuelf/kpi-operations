import { ref } from 'vue'
import api from '@/services/api/client'
import { useNotificationStore } from '@/stores/notificationStore'

export interface CSVExportParams {
  client_id?: string | number
  start_date?: string
  end_date?: string
  line_id?: string | number
  [key: string]: unknown
}

export function useCSVExport() {
  const downloading = ref(false)

  async function downloadCSV(
    entityType: string,
    params: CSVExportParams = {},
    filename: string | null = null,
  ): Promise<void> {
    const notificationStore = useNotificationStore()
    downloading.value = true

    try {
      const response = await api.get(`/export/${entityType}`, {
        params,
        responseType: 'blob',
      })

      const contentDisposition = response.headers['content-disposition'] as string | undefined
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

      const blob = new Blob([response.data as BlobPart], { type: 'text/csv' })
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
      const ax = error as { response?: { data?: { detail?: string } }; message?: string }
      const message = ax?.response?.data?.detail || ax?.message || 'CSV download failed'
      notificationStore.showError(`Export failed: ${message}`)
      throw error
    } finally {
      downloading.value = false
    }
  }

  return { downloading, downloadCSV }
}
