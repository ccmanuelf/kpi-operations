import api from './client'

export const getDailyReport = (date) => {
  return api.get(`/reports/daily/${date}`, {
    responseType: 'blob'
  })
}

export const getWeeklyReport = (startDate, endDate) => {
  return api.get('/reports/weekly', {
    params: { start_date: startDate, end_date: endDate },
    responseType: 'blob'
  })
}

export const getMonthlyReport = (month, year) => {
  return api.get('/reports/monthly', {
    params: { month, year },
    responseType: 'blob'
  })
}

export const exportExcel = (params) => {
  return api.get('/reports/excel', {
    params,
    responseType: 'blob'
  })
}

export const exportPDF = (params) => {
  return api.get('/reports/pdf', {
    params,
    responseType: 'blob'
  })
}

// Email Report Configuration
export const getEmailReportConfig = (clientId) => {
  return api.get('/reports/email-config', { params: { client_id: clientId } }).catch(() => ({
    data: {
      enabled: false,
      frequency: 'daily',
      recipients: [],
      report_time: '06:00'
    }
  }))
}

export const saveEmailReportConfig = (data) => api.post('/reports/email-config', data)

export const updateEmailReportConfig = (data) => api.put('/reports/email-config', data)

export const sendTestEmail = (email) => api.post('/reports/email-config/test', { email })

export const triggerManualReport = (data) => api.post('/reports/send-manual', data)
