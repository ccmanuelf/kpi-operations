import api from './client'

export const calculateKPIs = (entryId) => api.get(`/kpi/calculate/${entryId}`)

export const getKPIDashboard = (params) => api.get('/kpi/dashboard', { params })

export const getEfficiency = async (params) => {
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
    console.error('[KPI API] Failed to fetch efficiency:', error)
    return { data: { current: null, target: 85, actual_output: 0, expected_output: 0, gap: 0, by_shift: [], by_product: [] } }
  }
}

export const getWIPAging = async (params) => {
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
}

export const getOnTimeDelivery = async (params) => {
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
}

export const getAvailability = async (params) => {
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
}

export const getPerformance = async (params) => {
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
}

export const getQuality = async (params) => {
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
  } catch (error) {
    console.error('[KPI API] Failed to fetch quality:', error)
    return { data: { fpy: 0, rty: 0, final_yield: 0, total_units: 0, total_scrapped: 0, defects_by_type: [], by_product: [] } }
  }
}

export const getOEE = async (params) => {
  // OEE = Availability x Performance x Quality
  try {
    const [dashboardRes, qualityRes, availabilityData] = await Promise.all([
      api.get('/kpi/dashboard', { params }).catch(() => ({ data: [] })),
      api.get('/quality/kpi/fpy-rty', { params }).catch(() => ({ data: { fpy_percentage: 97 } })),
      getAvailability(params)
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
        // OEE = Availability x Performance x Quality
        const oee = (availability / 100) * (avgPerf / 100) * (quality / 100) * 100
        return { data: { percentage: parseFloat(Math.min(oee, 100).toFixed(2)) } }
      }
    }
    return { data: { percentage: null } }
  } catch (error) {
    console.error('[KPI API] Failed to fetch OEE:', error)
    return { data: { percentage: null } }
  }
}

export const getAbsenteeism = (params) => {
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
  })).catch((error) => {
    console.error('[KPI API] Failed to fetch absenteeism:', error)
    return {
      data: {
        rate: 0,
        total_employees: 0,
        total_absences: 0,
        by_reason: [],
        by_department: [],
        high_absence_employees: []
      }
    }
  })
}

export const getDefectRates = (params) => {
  return api.get('/quality/kpi/ppm', { params }).then(res => ({
    data: {
      ppm: res.data?.ppm ?? null,
      defect_rate_percentage: res.data?.defect_rate_percentage ?? null
    }
  })).catch((error) => {
    console.error('[KPI API] Failed to fetch defect rates:', error)
    return { data: { ppm: null, defect_rate_percentage: null } }
  })
}

export const getThroughputTime = async (params) => {
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
    console.error('[KPI API] Failed to fetch throughput time:', error)
    return { data: { average_hours: null } }
  }
}

// KPI Trends (fallback to empty arrays if endpoints don't exist)
export const getEfficiencyTrend = (params) => api.get('/kpi/efficiency/trend', { params }).catch((error) => { console.error('[KPI API] Failed to fetch efficiency trend:', error); return { data: [] } })

export const getWIPAgingTrend = (params) => api.get('/kpi/wip-aging/trend', { params }).catch((error) => { console.error('[KPI API] Failed to fetch WIP aging trend:', error); return { data: [] } })

export const getOnTimeDeliveryTrend = (params) => api.get('/kpi/on-time-delivery/trend', { params }).catch((error) => { console.error('[KPI API] Failed to fetch OTD trend:', error); return { data: [] } })

export const getAvailabilityTrend = (params) => api.get('/kpi/availability/trend', { params }).catch((error) => { console.error('[KPI API] Failed to fetch availability trend:', error); return { data: [] } })

export const getPerformanceTrend = (params) => api.get('/kpi/performance/trend', { params }).catch((error) => { console.error('[KPI API] Failed to fetch performance trend:', error); return { data: [] } })

export const getQualityTrend = (params) => api.get('/kpi/quality/trend', { params }).catch((error) => { console.error('[KPI API] Failed to fetch quality trend:', error); return { data: [] } })

export const getOEETrend = (params) => api.get('/kpi/oee/trend', { params }).catch((error) => { console.error('[KPI API] Failed to fetch OEE trend:', error); return { data: [] } })

export const getAbsenteeismTrend = (params) => api.get('/attendance/kpi/absenteeism/trend', { params }).catch((error) => { console.error('[KPI API] Failed to fetch absenteeism trend:', error); return { data: [] } })
