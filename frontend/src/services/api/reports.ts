import api from './client'

export const getDailyReport = (date: string) => {
  return api.get(`/reports/daily/${date}`, {
    responseType: 'blob',
  })
}

export const getWeeklyReport = (startDate: string, endDate: string) => {
  return api.get('/reports/weekly', {
    params: { start_date: startDate, end_date: endDate },
    responseType: 'blob',
  })
}

export const getMonthlyReport = (month: number, year: number) => {
  return api.get('/reports/monthly', {
    params: { month, year },
    responseType: 'blob',
  })
}

export const exportExcel = (params?: Record<string, unknown>) => {
  return api.get('/reports/excel', {
    params,
    responseType: 'blob',
  })
}

export const exportPDF = (params?: Record<string, unknown>) => {
  return api.get('/reports/pdf', {
    params,
    responseType: 'blob',
  })
}

export interface EmailReportConfig {
  enabled: boolean
  frequency: 'daily' | 'weekly' | 'monthly'
  recipients: string[]
  report_time: string
}

export const getEmailReportConfig = (clientId: string | number) => {
  return api
    .get('/reports/email-config', { params: { client_id: clientId } })
    .catch(() => ({
      data: {
        enabled: false,
        frequency: 'daily',
        recipients: [],
        report_time: '06:00',
      } as EmailReportConfig,
    }))
}

export const saveEmailReportConfig = (data: EmailReportConfig) =>
  api.post('/reports/email-config', data)

export const updateEmailReportConfig = (data: Partial<EmailReportConfig>) =>
  api.put('/reports/email-config', data)

export const sendTestEmail = (email: string) => api.post('/reports/email-config/test', { email })

export const triggerManualReport = (data: Record<string, unknown>) =>
  api.post('/reports/send-manual', data)
