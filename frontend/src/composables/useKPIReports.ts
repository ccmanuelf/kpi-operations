/**
 * Composable for KPI Dashboard report generation.
 * PDF download, Excel download, email report sending.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import api from '@/services/api'

type SnackbarFn = (message: string, color: string) => void
type SelectedClientGetter = () => string | number | null
type DateRangeGetter = () => Date[] | null | undefined

export function useKPIReports(
  showSnackbar: SnackbarFn,
  getSelectedClient: SelectedClientGetter,
  getDateRange: DateRangeGetter,
) {
  const { t } = useI18n()

  const downloadingPDF = ref(false)
  const downloadingExcel = ref(false)
  const emailDialog = ref(false)
  const emailRecipients = ref<string[]>([])
  const emailFormValid = ref(false)
  const sendingEmail = ref(false)

  const buildParams = (): URLSearchParams => {
    const params = new URLSearchParams()
    const client = getSelectedClient()
    const dateRange = getDateRange()
    if (client) params.append('client_id', String(client))
    if (dateRange && dateRange.length === 2) {
      params.append('start_date', format(dateRange[0], 'yyyy-MM-dd'))
      params.append('end_date', format(dateRange[1], 'yyyy-MM-dd'))
    }
    return params
  }

  const triggerBlobDownload = (blobData: BlobPart, filename: string): void => {
    const url = window.URL.createObjectURL(new Blob([blobData]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  const downloadPDF = async (): Promise<void> => {
    downloadingPDF.value = true
    try {
      const params = buildParams()
      const response = await api.get(`/reports/pdf?${params.toString()}`, {
        responseType: 'blob',
      })

      triggerBlobDownload(
        response.data as BlobPart,
        `KPI_Report_${format(new Date(), 'yyyyMMdd')}.pdf`,
      )

      showSnackbar(t('success.pdfDownloaded'), 'success')
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error downloading PDF:', error)
      showSnackbar(t('success.pdfDownloadFailed'), 'error')
    } finally {
      downloadingPDF.value = false
    }
  }

  const downloadExcel = async (): Promise<void> => {
    downloadingExcel.value = true
    try {
      const params = buildParams()
      const response = await api.get(`/reports/excel?${params.toString()}`, {
        responseType: 'blob',
      })

      triggerBlobDownload(
        response.data as BlobPart,
        `KPI_Report_${format(new Date(), 'yyyyMMdd')}.xlsx`,
      )

      showSnackbar(t('success.excelDownloaded'), 'success')
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error downloading Excel:', error)
      showSnackbar(t('success.excelDownloadFailed'), 'error')
    } finally {
      downloadingExcel.value = false
    }
  }

  const sendEmailReport = async (): Promise<void> => {
    if (!emailFormValid.value || emailRecipients.value.length === 0) {
      showSnackbar(t('success.pleaseAddRecipient'), 'warning')
      return
    }

    sendingEmail.value = true
    try {
      const dateRange = getDateRange()
      const payload = {
        client_id: getSelectedClient() || null,
        start_date:
          dateRange && dateRange.length === 2
            ? format(dateRange[0], 'yyyy-MM-dd')
            : format(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), 'yyyy-MM-dd'),
        end_date:
          dateRange && dateRange.length === 2
            ? format(dateRange[1], 'yyyy-MM-dd')
            : format(new Date(), 'yyyy-MM-dd'),
        recipient_emails: emailRecipients.value,
        include_excel: false,
      }

      await api.post('/reports/email', payload)

      showSnackbar(t('success.reportSent'), 'success')
      emailDialog.value = false
      emailRecipients.value = []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error sending email:', error)
      showSnackbar(t('success.reportSendFailed'), 'error')
    } finally {
      sendingEmail.value = false
    }
  }

  return {
    downloadingPDF,
    downloadingExcel,
    emailDialog,
    emailRecipients,
    emailFormValid,
    sendingEmail,
    downloadPDF,
    downloadExcel,
    sendEmailReport,
  }
}
