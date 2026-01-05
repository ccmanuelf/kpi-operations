import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor for adding auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for handling errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default {
  // Auth
  login(credentials) {
    return api.post('/auth/login', credentials)
  },
  register(userData) {
    return api.post('/auth/register', userData)
  },
  getCurrentUser() {
    return api.get('/auth/me')
  },

  // Production entries
  createProductionEntry(data) {
    return api.post('/production', data)
  },
  getProductionEntries(params) {
    return api.get('/production', { params })
  },
  getProductionEntry(id) {
    return api.get(`/production/${id}`)
  },
  updateProductionEntry(id, data) {
    return api.put(`/production/${id}`, data)
  },
  deleteProductionEntry(id) {
    return api.delete(`/production/${id}`)
  },

  // CSV Upload
  uploadCSV(file) {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/production/upload/csv', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  // Batch Import Production Entries
  batchImportProduction(entries) {
    return api.post('/production/batch-import', { entries })
  },

  // KPIs - Dashboard
  calculateKPIs(entryId) {
    return api.get(`/kpi/calculate/${entryId}`)
  },
  getKPIDashboard(params) {
    return api.get('/kpi/dashboard', { params })
  },

  // KPIs - Individual Metrics
  getEfficiency(params) {
    return api.get('/kpi/efficiency', { params })
  },
  getWIPAging(params) {
    return api.get('/kpi/wip-aging', { params })
  },
  getOnTimeDelivery(params) {
    return api.get('/kpi/on-time-delivery', { params })
  },
  getAvailability(params) {
    return api.get('/kpi/availability', { params })
  },
  getPerformance(params) {
    return api.get('/kpi/performance', { params })
  },
  getQuality(params) {
    return api.get('/kpi/quality', { params })
  },
  getOEE(params) {
    return api.get('/kpi/oee', { params })
  },
  getAbsenteeism(params) {
    return api.get('/kpi/absenteeism', { params })
  },
  getDefectRates(params) {
    return api.get('/kpi/defect-rates', { params })
  },
  getThroughputTime(params) {
    return api.get('/kpi/throughput-time', { params })
  },

  // KPI Trends
  getEfficiencyTrend(params) {
    return api.get('/kpi/efficiency/trend', { params })
  },
  getWIPAgingTrend(params) {
    return api.get('/kpi/wip-aging/trend', { params })
  },
  getOnTimeDeliveryTrend(params) {
    return api.get('/kpi/on-time-delivery/trend', { params })
  },
  getAvailabilityTrend(params) {
    return api.get('/kpi/availability/trend', { params })
  },
  getPerformanceTrend(params) {
    return api.get('/kpi/performance/trend', { params })
  },
  getQualityTrend(params) {
    return api.get('/kpi/quality/trend', { params })
  },
  getOEETrend(params) {
    return api.get('/kpi/oee/trend', { params })
  },
  getAbsenteeismTrend(params) {
    return api.get('/kpi/absenteeism/trend', { params })
  },

  // Data Entry - Downtime
  createDowntimeEntry(data) {
    return api.post('/downtime', data)
  },
  getDowntimeEntries(params) {
    return api.get('/downtime', { params })
  },
  updateDowntimeEntry(id, data) {
    return api.put(`/downtime/${id}`, data)
  },
  deleteDowntimeEntry(id) {
    return api.delete(`/downtime/${id}`)
  },

  // Data Entry - Attendance
  createAttendanceEntry(data) {
    return api.post('/attendance', data)
  },
  getAttendanceEntries(params) {
    return api.get('/attendance', { params })
  },
  updateAttendanceEntry(id, data) {
    return api.put(`/attendance/${id}`, data)
  },
  deleteAttendanceEntry(id) {
    return api.delete(`/attendance/${id}`)
  },

  // Data Entry - Quality
  createQualityEntry(data) {
    return api.post('/quality', data)
  },
  getQualityEntries(params) {
    return api.get('/quality', { params })
  },
  updateQualityEntry(id, data) {
    return api.put(`/quality/${id}`, data)
  },
  deleteQualityEntry(id) {
    return api.delete(`/quality/${id}`)
  },

  // Data Entry - Hold/Resume
  createHoldEntry(data) {
    return api.post('/holds', data)
  },
  updateHoldEntry(id, data) {
    return api.put(`/holds/${id}`, data)
  },
  deleteHoldEntry(id) {
    return api.delete(`/holds/${id}`)
  },
  resumeHold(id, data) {
    return api.post(`/holds/${id}/resume`, data)
  },
  getHoldEntries(params) {
    return api.get('/holds', { params })
  },
  getActiveHolds(params) {
    return api.get('/holds/active', { params })
  },

  // Reports - PDF & Excel
  getDailyReport(date) {
    return api.get(`/reports/daily/${date}`, {
      responseType: 'blob'
    })
  },
  getWeeklyReport(startDate, endDate) {
    return api.get('/reports/weekly', {
      params: { start_date: startDate, end_date: endDate },
      responseType: 'blob'
    })
  },
  getMonthlyReport(month, year) {
    return api.get('/reports/monthly', {
      params: { month, year },
      responseType: 'blob'
    })
  },
  exportExcel(params) {
    return api.get('/reports/excel', {
      params,
      responseType: 'blob'
    })
  },
  exportPDF(params) {
    return api.get('/reports/pdf', {
      params,
      responseType: 'blob'
    })
  },

  // Reference data
  getProducts() {
    return api.get('/products')
  },
  getShifts() {
    return api.get('/shifts')
  },
  getClients() {
    return api.get('/clients')
  },
  getDowntimeReasons() {
    return api.get('/downtime-reasons')
  },
  getDefectTypes() {
    return api.get('/defect-types')
  }
}
