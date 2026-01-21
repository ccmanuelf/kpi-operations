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

  // KPIs - Individual Metrics (using backend endpoints)
  // The /kpi/dashboard endpoint returns an array of daily summaries with avg_efficiency, avg_performance
  async getEfficiency(params) {
    try {
      // Fetch all efficiency data in parallel
      const [dashboardRes, byShiftRes, byProductRes] = await Promise.all([
        api.get('/kpi/dashboard', { params }).catch(() => ({ data: [] })),
        api.get('/kpi/efficiency/by-shift', { params }).catch(() => ({ data: [] })),
        api.get('/kpi/efficiency/by-product', { params }).catch(() => ({ data: [] }))
      ])

      // Calculate average efficiency from dashboard data
      const data = dashboardRes.data || []
      let avgEfficiency = null
      if (Array.isArray(data) && data.length > 0) {
        const validEntries = data.filter(d => d.avg_efficiency != null)
        avgEfficiency = validEntries.length > 0
          ? validEntries.reduce((sum, d) => sum + d.avg_efficiency, 0) / validEntries.length
          : null
      }

      // Calculate total actual_output, expected_output, and gap from by-shift data
      const byShiftData = byShiftRes.data || []
      let totalActualOutput = 0
      let totalExpectedOutput = 0

      byShiftData.forEach(shift => {
        totalActualOutput += shift.actual_output || 0
        totalExpectedOutput += shift.expected_output || 0
      })

      // Gap = difference between expected and actual (positive = under target)
      const gap = totalExpectedOutput - totalActualOutput

      return {
        data: {
          current: avgEfficiency,
          target: 85,
          actual_output: totalActualOutput,
          expected_output: totalExpectedOutput,
          gap: gap,
          by_shift: byShiftData,
          by_product: byProductRes.data || []
        }
      }
    } catch (error) {
      return { data: { current: null, target: 85, actual_output: 0, expected_output: 0, gap: 0, by_shift: [], by_product: [] } }
    }
  },
  async getWIPAging(params) {
    try {
      // Fetch WIP aging data and top aging items in parallel
      const [agingRes, topRes] = await Promise.all([
        api.get('/kpi/wip-aging', { params }).catch(() => ({ data: {} })),
        api.get('/kpi/wip-aging/top', { params }).catch(() => ({ data: [] }))
      ])

      const data = agingRes.data || {}
      const topAgingItems = Array.isArray(topRes.data) ? topRes.data : []
      const aging_15_30 = data.aging_15_30_days || 0
      const aging_over_30 = data.aging_over_30_days || 0

      // Calculate actual max_days from top aging items (first item is oldest)
      const maxDays = topAgingItems.length > 0 ? Math.max(...topAgingItems.map(item => item.age || 0)) : 0

      return {
        data: {
          average_days: parseFloat(data.average_aging_days) || data.average_age || data.avg_hold_duration || 0,
          total_held: data.total_held_quantity || 0,
          total_units: data.total_held_quantity || 0,
          aging_0_7: data.aging_0_7_days || 0,
          age_0_7: data.aging_0_7_days || 0,
          aging_8_14: data.aging_8_14_days || 0,
          age_8_14: data.aging_8_14_days || 0,
          aging_15_30: aging_15_30,
          aging_over_30: aging_over_30,
          age_15_plus: aging_15_30 + aging_over_30,
          critical_count: aging_15_30 + aging_over_30,
          max_days: maxDays,
          total_hold_events: data.total_hold_events || 0,
          top_aging: topAgingItems
        }
      }
    } catch (error) {
      console.error('WIP Aging fetch error:', error)
      return { data: { average_days: 0, total_held: 0, total_units: 0, max_days: 0, top_aging: [] } }
    }
  },
  async getOnTimeDelivery(params) {
    try {
      // Fetch OTD data, by-client breakdown, and late deliveries in parallel
      const [otdRes, byClientRes, lateDeliveriesRes] = await Promise.all([
        api.get('/kpi/otd', { params }).catch(() => ({ data: {} })),
        api.get('/kpi/otd/by-client', { params }).catch(() => ({ data: [] })),
        api.get('/kpi/otd/late-deliveries', { params }).catch(() => ({ data: [] }))
      ])

      const otdData = otdRes.data || {}
      const byClientData = byClientRes.data || []
      const lateDeliveriesData = lateDeliveriesRes.data || []

      return {
        data: {
          percentage: otdData.otd_percentage || otdData.otd_rate || otdData.percentage || 0,
          on_time_count: otdData.on_time_count || 0,
          total_orders: otdData.total_orders || 0,
          by_client: byClientData,
          late_deliveries: lateDeliveriesData
        }
      }
    } catch (error) {
      console.error('OTD fetch error:', error)
      return { data: { percentage: 0, on_time_count: 0, total_orders: 0, by_client: [], late_deliveries: [] } }
    }
  },
  async getAvailability(params) {
    try {
      // Fetch production entries and downtime data to calculate actual availability
      const [productionRes, downtimeRes] = await Promise.all([
        api.get('/production', { params }).catch(() => ({ data: [] })),
        api.get('/downtime', { params }).catch(() => ({ data: [] }))
      ])

      const productionData = productionRes.data || []
      const downtimeData = downtimeRes.data || []

      // Calculate total scheduled hours from actual production run_time_hours
      let totalScheduledHours = 0
      productionData.forEach(p => {
        totalScheduledHours += parseFloat(p.run_time_hours || 0)
      })

      // If no production data, use a reasonable default based on date range
      if (totalScheduledHours === 0 && productionData.length === 0) {
        // Fallback: estimate based on 8 hours/day for the date range
        const startDate = params?.start_date ? new Date(params.start_date) : new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
        const endDate = params?.end_date ? new Date(params.end_date) : new Date()
        const days = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24)) || 30
        totalScheduledHours = days * 8
      }

      // Calculate total downtime hours
      let totalDowntimeHours = 0
      let totalDowntimeEvents = downtimeData.length

      // Aggregate downtime by reason
      const reasonsMap = {}
      // Aggregate downtime by equipment
      const equipmentMap = {}

      // Sum up downtime - backend returns downtime_duration_minutes
      downtimeData.forEach(d => {
        // Convert minutes to hours
        const minutes = parseFloat(d.downtime_duration_minutes || d.duration_hours * 60 || 0)
        const hours = minutes / 60
        totalDowntimeHours += hours

        // Aggregate by reason
        const reason = d.downtime_reason || d.reason_type || 'Unknown'
        if (!reasonsMap[reason]) {
          reasonsMap[reason] = { reason, hours: 0, count: 0 }
        }
        reasonsMap[reason].hours += hours
        reasonsMap[reason].count += 1

        // Aggregate by equipment
        const equipment = d.machine_id || d.equipment_code || 'Unknown Equipment'
        if (!equipmentMap[equipment]) {
          equipmentMap[equipment] = { equipment_name: equipment, uptime: 0, downtime: 0 }
        }
        equipmentMap[equipment].downtime += hours
      })

      // Calculate uptime
      const uptimeHours = Math.max(0, totalScheduledHours - totalDowntimeHours)

      // Calculate availability: (Scheduled - Downtime) / Scheduled * 100
      const availability = totalScheduledHours > 0
        ? Math.max(0, Math.min(100, (uptimeHours / totalScheduledHours) * 100))
        : 0

      // Calculate MTBF (Mean Time Between Failures)
      // MTBF = Total Operating Time / Number of Failures
      const mtbf = totalDowntimeEvents > 0
        ? parseFloat((uptimeHours / totalDowntimeEvents).toFixed(1))
        : parseFloat(uptimeHours.toFixed(1))

      // Convert reasons map to array with percentages
      const downtimeReasons = Object.values(reasonsMap).map(r => ({
        reason: r.reason,
        hours: parseFloat(r.hours.toFixed(1)),
        count: r.count,
        percentage: totalDowntimeHours > 0 ? (r.hours / totalDowntimeHours) * 100 : 0
      })).sort((a, b) => b.hours - a.hours)

      // Convert equipment map to array with availability
      const equipmentCount = Object.keys(equipmentMap).length || 1
      const byEquipment = Object.values(equipmentMap).map(e => {
        const equipScheduled = totalScheduledHours / equipmentCount
        const equipUptime = equipScheduled - e.downtime
        return {
          equipment_name: e.equipment_name,
          uptime: parseFloat(Math.max(0, equipUptime).toFixed(1)),
          downtime: parseFloat(e.downtime.toFixed(1)),
          availability: parseFloat((Math.max(0, equipUptime) / equipScheduled * 100).toFixed(1))
        }
      }).sort((a, b) => a.availability - b.availability)

      return {
        data: {
          percentage: availability > 0 ? parseFloat(availability.toFixed(2)) : null,
          uptime: parseFloat(uptimeHours.toFixed(1)),
          downtime: parseFloat(totalDowntimeHours.toFixed(1)),
          total_time: parseFloat(totalScheduledHours.toFixed(1)),
          mtbf: mtbf,
          scheduled_hours: totalScheduledHours,
          downtime_hours: totalDowntimeHours,
          downtime_events: totalDowntimeEvents,
          downtime_reasons: downtimeReasons,
          by_equipment: byEquipment
        }
      }
    } catch (error) {
      console.error('Availability fetch error:', error)
      return { data: { percentage: null, uptime: 0, downtime: 0, total_time: 0, mtbf: 0, downtime_reasons: [], by_equipment: [] } }
    }
  },
  async getPerformance(params) {
    try {
      // Fetch all performance data in parallel
      const [dashboardRes, productionRes, byShiftRes, byProductRes] = await Promise.all([
        api.get('/kpi/dashboard', { params }).catch(() => ({ data: [] })),
        api.get('/production', { params }).catch(() => ({ data: [] })),
        api.get('/kpi/performance/by-shift', { params }).catch(() => ({ data: [] })),
        api.get('/kpi/performance/by-product', { params }).catch(() => ({ data: [] }))
      ])

      // Calculate average performance from dashboard data
      const dashboardData = dashboardRes.data || []
      let avgPerformance = null
      if (Array.isArray(dashboardData) && dashboardData.length > 0) {
        const validEntries = dashboardData.filter(d => d.avg_performance != null)
        avgPerformance = validEntries.length > 0
          ? validEntries.reduce((sum, d) => sum + d.avg_performance, 0) / validEntries.length
          : null
      }

      // Calculate totals from production entries
      const productionData = productionRes.data || []
      let totalUnits = 0
      let totalHours = 0
      let totalExpectedOutput = 0

      productionData.forEach(entry => {
        totalUnits += parseInt(entry.units_produced || 0)
        totalHours += parseFloat(entry.run_time_hours || 0)
        // Expected output based on ideal cycle time: run_time_hours * 60 / ideal_cycle_time_minutes
        if (entry.ideal_cycle_time_minutes && entry.ideal_cycle_time_minutes > 0) {
          totalExpectedOutput += (parseFloat(entry.run_time_hours || 0) * 60) / parseFloat(entry.ideal_cycle_time_minutes)
        }
      })

      // Actual Rate = Total Units / Production Hours (units per hour)
      const actualRate = totalHours > 0 ? Math.round(totalUnits / totalHours) : 0

      // Standard Rate = Expected Output / Production Hours
      // If no expected output data, estimate based on typical target (95% of actual as baseline)
      let standardRate = 0
      if (totalExpectedOutput > 0 && totalHours > 0) {
        standardRate = Math.round(totalExpectedOutput / totalHours)
      } else if (avgPerformance && avgPerformance > 0 && actualRate > 0) {
        // Estimate: if actual_rate is X% of standard, then standard = actual / (performance/100)
        standardRate = Math.round(actualRate / (avgPerformance / 100))
      } else if (actualRate > 0) {
        // Fallback: assume 95% target means actual = 95% of standard
        standardRate = Math.round(actualRate / 0.95)
      }

      return {
        data: {
          percentage: avgPerformance ? parseFloat(avgPerformance.toFixed(1)) : null,
          target: 95,
          actual_rate: actualRate,
          standard_rate: standardRate,
          total_units: totalUnits,
          production_hours: parseFloat(totalHours.toFixed(1)),
          by_shift: byShiftRes.data || [],
          by_product: byProductRes.data || []
        }
      }
    } catch (error) {
      console.error('Performance fetch error:', error)
      return { data: { percentage: null, target: 95, actual_rate: 0, standard_rate: 0, total_units: 0, production_hours: 0, by_shift: [], by_product: [] } }
    }
  },
  async getQuality(params) {
    try {
      const [fpyRtyRes, defectsRes, byProductRes] = await Promise.all([
        api.get('/quality/kpi/fpy-rty', { params }),
        api.get('/quality/kpi/defects-by-type', { params }).catch(() => ({ data: [] })),
        api.get('/quality/kpi/by-product', { params }).catch(() => ({ data: [] }))
      ])
      return {
        data: {
          fpy: parseFloat(fpyRtyRes.data?.fpy_percentage) || fpyRtyRes.data?.fpy || fpyRtyRes.data?.first_pass_yield || 0,
          rty: parseFloat(fpyRtyRes.data?.rty_percentage) || 0,
          final_yield: parseFloat(fpyRtyRes.data?.final_yield_percentage) || 0,
          total_units: fpyRtyRes.data?.total_units || 0,
          first_pass_good: fpyRtyRes.data?.first_pass_good || 0,
          total_scrapped: fpyRtyRes.data?.total_scrapped || 0,
          defects_by_type: defectsRes.data || [],
          by_product: byProductRes.data || []
        }
      }
    } catch {
      return { data: { fpy: 0, rty: 0, final_yield: 0, total_units: 0, total_scrapped: 0, defects_by_type: [], by_product: [] } }
    }
  },
  async getOEE(params) {
    // OEE = Availability x Performance x Quality
    try {
      const [dashboardRes, qualityRes, availabilityData] = await Promise.all([
        api.get('/kpi/dashboard', { params }).catch(() => ({ data: [] })),
        api.get('/quality/kpi/fpy-rty', { params }).catch(() => ({ data: { fpy_percentage: 97 } })),
        this.getAvailability(params)
      ])

      const data = dashboardRes.data || []
      const quality = parseFloat(qualityRes.data?.fpy_percentage || qualityRes.data?.fpy || 97)
      const availability = availabilityData.data?.percentage || 90

      if (Array.isArray(data) && data.length > 0) {
        // Calculate OEE from efficiency, performance, and actual quality data
        const validEntries = data.filter(d => d.avg_efficiency != null && d.avg_performance != null)
        if (validEntries.length > 0) {
          const avgEff = validEntries.reduce((sum, d) => sum + d.avg_efficiency, 0) / validEntries.length
          const avgPerf = validEntries.reduce((sum, d) => sum + d.avg_performance, 0) / validEntries.length
          // OEE = Availability × Performance × Quality
          const oee = (availability / 100) * (avgPerf / 100) * (quality / 100) * 100
          return { data: { percentage: parseFloat(Math.min(oee, 100).toFixed(2)) } }
        }
      }
      return { data: { percentage: null } }
    } catch (error) {
      return { data: { percentage: null } }
    }
  },
  getAbsenteeism(params) {
    return api.get('/attendance/kpi/absenteeism', { params }).then(res => ({
      data: {
        rate: parseFloat(res.data?.absenteeism_rate) || res.data?.rate || 0,
        total_scheduled_hours: parseFloat(res.data?.total_scheduled_hours) || 0,
        total_hours_absent: parseFloat(res.data?.total_hours_absent) || 0,
        total_employees: res.data?.total_employees || 0,
        total_absences: res.data?.total_absences || 0,
        // Include breakdown data for tables
        by_reason: res.data?.by_reason || [],
        by_department: res.data?.by_department || [],
        high_absence_employees: res.data?.high_absence_employees || []
      }
    })).catch(() => ({
      data: {
        rate: 0,
        total_employees: 0,
        total_absences: 0,
        by_reason: [],
        by_department: [],
        high_absence_employees: []
      }
    }))
  },
  getDefectRates(params) {
    return api.get('/quality/kpi/ppm', { params }).then(res => ({
      data: {
        ppm: res.data?.ppm ?? null,
        defect_rate_percentage: res.data?.defect_rate_percentage ?? null
      }
    })).catch(() => ({ data: { ppm: null, defect_rate_percentage: null } }))
  },
  async getThroughputTime(params) {
    try {
      // Calculate throughput time from production entries
      const response = await api.get('/production', { params })
      const entries = response.data || []

      if (entries.length > 0) {
        // Throughput time = total run time / total units produced (averaged across entries)
        let totalRunHours = 0
        let totalUnits = 0

        entries.forEach(entry => {
          totalRunHours += parseFloat(entry.run_time_hours || 0)
          totalUnits += parseInt(entry.units_produced || 0)
        })

        // Average throughput time per unit in hours
        const avgThroughput = totalUnits > 0 ? (totalRunHours / totalUnits) * 100 : 0
        // Cap at reasonable value (24 hours max for display)
        const displayValue = Math.min(avgThroughput, 24)

        return { data: { average_hours: parseFloat(displayValue.toFixed(2)) || null } }
      }
      return { data: { average_hours: null } }
    } catch (error) {
      return { data: { average_hours: null } }
    }
  },

  // KPI Trends (fallback to empty arrays if endpoints don't exist)
  getEfficiencyTrend(params) {
    return api.get('/kpi/efficiency/trend', { params }).catch(() => ({ data: [] }))
  },
  getWIPAgingTrend(params) {
    return api.get('/kpi/wip-aging/trend', { params }).catch(() => ({ data: [] }))
  },
  getOnTimeDeliveryTrend(params) {
    return api.get('/kpi/on-time-delivery/trend', { params }).catch(() => ({ data: [] }))
  },
  getAvailabilityTrend(params) {
    return api.get('/kpi/availability/trend', { params }).catch(() => ({ data: [] }))
  },
  getPerformanceTrend(params) {
    return api.get('/kpi/performance/trend', { params }).catch(() => ({ data: [] }))
  },
  getQualityTrend(params) {
    return api.get('/kpi/quality/trend', { params }).catch(() => ({ data: [] }))
  },
  getOEETrend(params) {
    return api.get('/kpi/oee/trend', { params }).catch(() => ({ data: [] }))
  },
  getAbsenteeismTrend(params) {
    return api.get('/attendance/kpi/absenteeism/trend', { params }).catch(() => ({ data: [] }))
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
  // Clients CRUD
  getClients() {
    return api.get('/clients')
  },
  getClient(clientId) {
    return api.get(`/clients/${clientId}`)
  },
  createClient(data) {
    return api.post('/clients', data)
  },
  updateClient(clientId, data) {
    return api.put(`/clients/${clientId}`, data)
  },
  deleteClient(clientId) {
    return api.delete(`/clients/${clientId}`)
  },

  // Users CRUD (Admin)
  getUsers() {
    return api.get('/users')
  },
  getUser(userId) {
    return api.get(`/users/${userId}`)
  },
  createUser(data) {
    return api.post('/users', data)
  },
  updateUser(userId, data) {
    return api.put(`/users/${userId}`, data)
  },
  deleteUser(userId) {
    return api.delete(`/users/${userId}`)
  },

  // KPI Thresholds
  getKPIThresholds(clientId = null) {
    const params = clientId ? { client_id: clientId } : {}
    return api.get('/kpi-thresholds', { params })
  },
  updateKPIThresholds(data) {
    return api.put('/kpi-thresholds', data)
  },
  deleteClientThreshold(clientId, kpiKey) {
    return api.delete(`/kpi-thresholds/${clientId}/${kpiKey}`)
  },

  getDowntimeReasons() {
    return api.get('/downtime-reasons')
  },

  // ============================================
  // Defect Type Catalog (Client-specific)
  // ============================================
  getDefectTypes(clientId) {
    // If clientId provided, get client-specific defect types
    if (clientId) {
      return api.get(`/defect-types/client/${clientId}`)
    }
    // Fallback: try to get from user's assigned client or return empty
    return api.get('/defect-types/client/default').catch(() => ({ data: [] }))
  },
  getDefectTypesByClient(clientId, includeInactive = false, includeGlobal = true) {
    return api.get(`/defect-types/client/${clientId}`, {
      params: {
        include_inactive: includeInactive,
        include_global: includeGlobal
      }
    })
  },
  getGlobalDefectTypes(includeInactive = false) {
    return api.get('/defect-types/global', {
      params: { include_inactive: includeInactive }
    })
  },
  createDefectType(data) {
    return api.post('/defect-types', data)
  },
  updateDefectType(defectTypeId, data) {
    return api.put(`/defect-types/${defectTypeId}`, data)
  },
  deleteDefectType(defectTypeId) {
    return api.delete(`/defect-types/${defectTypeId}`)
  },
  uploadDefectTypes(clientId, file, replaceExisting = false) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('replace_existing', replaceExisting)
    return api.post(`/defect-types/upload/${clientId}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },
  getDefectTypeTemplate() {
    return api.get('/defect-types/template/download')
  },

  // ============================================
  // Dashboard Preferences
  // ============================================
  getDashboardPreferences() {
    return api.get('/preferences/dashboard')
  },
  saveDashboardPreferences(data) {
    return api.put('/preferences/dashboard', data)
  },
  updateDashboardPreferences(data) {
    return api.patch('/preferences/dashboard', data)
  },
  getDashboardDefaults(role) {
    return api.get(`/preferences/defaults/${role}`)
  },
  resetDashboardPreferences() {
    return api.post('/preferences/reset')
  },

  // ============================================
  // Saved Filters
  // ============================================
  getSavedFilters(params) {
    return api.get('/filters', { params })
  },
  createSavedFilter(data) {
    return api.post('/filters', data)
  },
  getSavedFilter(filterId) {
    return api.get(`/filters/${filterId}`)
  },
  updateSavedFilter(filterId, data) {
    return api.put(`/filters/${filterId}`, data)
  },
  deleteSavedFilter(filterId) {
    return api.delete(`/filters/${filterId}`)
  },
  applyFilter(filterId) {
    return api.post(`/filters/${filterId}/apply`)
  },
  setDefaultFilter(filterId) {
    return api.post(`/filters/${filterId}/set-default`)
  },
  duplicateFilter(filterId, newName) {
    return api.post(`/filters/${filterId}/duplicate`, { new_name: newName })
  },
  getFilterHistory() {
    return api.get('/filters/history/recent')
  },
  clearFilterHistory() {
    return api.delete('/filters/history')
  },

  // ============================================
  // QR Code
  // ============================================
  lookupQR(data) {
    return api.get('/qr/lookup', { params: { data } })
  },
  getWorkOrderQR(workOrderId) {
    return api.get(`/qr/work-order/${workOrderId}/image`, { responseType: 'blob' })
  },
  getProductQR(productId) {
    return api.get(`/qr/product/${productId}/image`, { responseType: 'blob' })
  },
  getJobQR(jobId) {
    return api.get(`/qr/job/${jobId}/image`, { responseType: 'blob' })
  },
  getEmployeeQR(employeeId) {
    return api.get(`/qr/employee/${employeeId}/image`, { responseType: 'blob' })
  },
  generateQR(entityType, entityId) {
    return api.post('/qr/generate', { entity_type: entityType, entity_id: entityId })
  },
  generateQRImage(entityType, entityId) {
    return api.post('/qr/generate/image', { entity_type: entityType, entity_id: entityId }, { responseType: 'blob' })
  },

  // ============================================
  // Predictions API (Forecasting)
  // ============================================

  /**
   * Get prediction for a single KPI with confidence intervals
   * @param {string} kpiType - Type of KPI (efficiency, performance, availability, oee, ppm, dpmo, fpy, rty, absenteeism, otd)
   * @param {Object} params - Query params: client_id, forecast_days (1-30), historical_days (7-90), method (auto|simple|double|linear)
   */
  getPrediction(kpiType, params) {
    return api.get(`/predictions/${kpiType}`, { params })
  },

  /**
   * Get predictions for all KPIs in a single dashboard response
   * @param {Object} params - Query params: client_id, forecast_days (1-30), historical_days (7-90)
   */
  getAllPredictions(params) {
    return api.get('/predictions/dashboard/all', { params })
  },

  /**
   * Get KPI benchmarks for all metrics
   */
  getPredictionBenchmarks() {
    return api.get('/predictions/benchmarks')
  },

  /**
   * Get quick health assessment for a specific KPI
   * @param {string} kpiType - Type of KPI
   * @param {Object} params - Query params: client_id
   */
  getKPIHealth(kpiType, params) {
    return api.get(`/predictions/health/${kpiType}`, { params })
  },

  // ============================================
  // Email Report Configuration
  // ============================================

  /**
   * Get email report configuration for a client
   * @param {string|number} clientId - Client ID
   */
  getEmailReportConfig(clientId) {
    return api.get('/reports/email-config', { params: { client_id: clientId } }).catch(() => ({
      data: {
        enabled: false,
        frequency: 'daily',
        recipients: [],
        report_time: '06:00'
      }
    }))
  },

  /**
   * Save email report configuration
   * @param {Object} data - Configuration: enabled, frequency, recipients[], report_time
   */
  saveEmailReportConfig(data) {
    return api.post('/reports/email-config', data)
  },

  /**
   * Update email report configuration
   * @param {Object} data - Configuration updates
   */
  updateEmailReportConfig(data) {
    return api.put('/reports/email-config', data)
  },

  /**
   * Send test email to verify configuration
   * @param {string} email - Email address to test
   */
  sendTestEmail(email) {
    return api.post('/reports/email-config/test', { email })
  },

  /**
   * Manually trigger a report for specific client
   * @param {Object} data - client_id, start_date, end_date, recipient_emails[]
   */
  triggerManualReport(data) {
    return api.post('/reports/send-manual', data)
  }
}
