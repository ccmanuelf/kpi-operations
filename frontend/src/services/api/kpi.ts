import api from './client'

type Params = Record<string, unknown>

export const calculateKPIs = (entryId: string | number) => api.get(`/kpi/calculate/${entryId}`)

export const getKPIDashboard = (params?: Params) => api.get('/kpi/dashboard', { params })

export const getEfficiency = async (params?: Params) => {
  try {
    const [dashboardRes, byShiftRes, byProductRes] = await Promise.all([
      api.get('/kpi/dashboard', { params }).catch(() => ({ data: [] })),
      api.get('/kpi/efficiency/by-shift', { params }).catch(() => ({ data: [] })),
      api.get('/kpi/efficiency/by-product', { params }).catch(() => ({ data: [] })),
    ])

    const data = dashboardRes.data || []
    let avgEfficiency: number | null = null
    if (Array.isArray(data) && data.length > 0) {
      const validEntries = data.filter((d: any) => d.avg_efficiency != null)
      avgEfficiency =
        validEntries.length > 0
          ? validEntries.reduce((sum: number, d: any) => sum + d.avg_efficiency, 0) /
            validEntries.length
          : null
    }

    const byShiftData = byShiftRes.data || []
    let totalActualOutput = 0
    let totalExpectedOutput = 0

    byShiftData.forEach((shift: any) => {
      totalActualOutput += shift.actual_output || 0
      totalExpectedOutput += shift.expected_output || 0
    })

    const gap = totalExpectedOutput - totalActualOutput

    return {
      data: {
        current: avgEfficiency,
        target: 85,
        actual_output: totalActualOutput,
        expected_output: totalExpectedOutput,
        gap: gap,
        by_shift: byShiftData,
        by_product: byProductRes.data || [],
      },
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('[KPI API] Failed to fetch efficiency:', error)
    return {
      data: {
        current: null,
        target: 85,
        actual_output: 0,
        expected_output: 0,
        gap: 0,
        by_shift: [],
        by_product: [],
      },
    }
  }
}

export const getWIPAging = async (params?: Params) => {
  try {
    const [agingRes, topRes] = await Promise.all([
      api.get('/kpi/wip-aging', { params }).catch(() => ({ data: {} })),
      api.get('/kpi/wip-aging/top', { params }).catch(() => ({ data: [] })),
    ])

    const data: any = agingRes.data || {}
    const topAgingItems: any[] = Array.isArray(topRes.data) ? topRes.data : []
    const aging_15_30 = data.aging_15_30_days || 0
    const aging_over_30 = data.aging_over_30_days || 0

    const maxDays =
      topAgingItems.length > 0 ? Math.max(...topAgingItems.map((item: any) => item.age || 0)) : 0

    return {
      data: {
        average_days:
          parseFloat(data.average_aging_days) || data.average_age || data.avg_hold_duration || 0,
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
        top_aging: topAgingItems,
      },
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('WIP Aging fetch error:', error)
    return {
      data: { average_days: 0, total_held: 0, total_units: 0, max_days: 0, top_aging: [] },
    }
  }
}

export const getOnTimeDelivery = async (params?: Params) => {
  try {
    const [otdRes, byClientRes, lateDeliveriesRes] = await Promise.all([
      api.get('/kpi/otd', { params }).catch(() => ({ data: {} })),
      api.get('/kpi/otd/by-client', { params }).catch(() => ({ data: [] })),
      api.get('/kpi/otd/late-deliveries', { params }).catch(() => ({ data: [] })),
    ])

    const otdData: any = otdRes.data || {}
    const byClientData = byClientRes.data || []
    const lateDeliveriesData = lateDeliveriesRes.data || []

    return {
      data: {
        percentage: otdData.otd_percentage || otdData.otd_rate || otdData.percentage || 0,
        on_time_count: otdData.on_time_count || 0,
        total_orders: otdData.total_orders || 0,
        by_client: byClientData,
        late_deliveries: lateDeliveriesData,
      },
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('OTD fetch error:', error)
    return {
      data: { percentage: 0, on_time_count: 0, total_orders: 0, by_client: [], late_deliveries: [] },
    }
  }
}

export const getAvailability = async (params?: Params) => {
  try {
    const [productionRes, downtimeRes] = await Promise.all([
      api.get('/production', { params }).catch(() => ({ data: [] })),
      api.get('/downtime', { params }).catch(() => ({ data: [] })),
    ])

    const productionData: any[] = productionRes.data || []
    const downtimeData: any[] = downtimeRes.data || []

    let totalScheduledHours = 0
    productionData.forEach((p: any) => {
      totalScheduledHours += parseFloat(p.run_time_hours || 0)
    })

    if (totalScheduledHours === 0 && productionData.length === 0) {
      const startDate = params?.start_date
        ? new Date(params.start_date as string)
        : new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
      const endDate = params?.end_date ? new Date(params.end_date as string) : new Date()
      const days =
        Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)) || 30
      totalScheduledHours = days * 8
    }

    let totalDowntimeHours = 0
    const totalDowntimeEvents = downtimeData.length

    const reasonsMap: Record<string, { reason: string; hours: number; count: number }> = {}
    const equipmentMap: Record<
      string,
      { equipment_name: string; uptime: number; downtime: number }
    > = {}

    downtimeData.forEach((d: any) => {
      const minutes = parseFloat(d.downtime_duration_minutes || d.duration_hours * 60 || 0)
      const hours = minutes / 60
      totalDowntimeHours += hours

      const reason = d.downtime_reason || d.reason_type || 'Unknown'
      if (!reasonsMap[reason]) {
        reasonsMap[reason] = { reason, hours: 0, count: 0 }
      }
      reasonsMap[reason].hours += hours
      reasonsMap[reason].count += 1

      const equipment = d.machine_id || d.equipment_code || 'Unknown Equipment'
      if (!equipmentMap[equipment]) {
        equipmentMap[equipment] = { equipment_name: equipment, uptime: 0, downtime: 0 }
      }
      equipmentMap[equipment].downtime += hours
    })

    const uptimeHours = Math.max(0, totalScheduledHours - totalDowntimeHours)

    const availability =
      totalScheduledHours > 0
        ? Math.max(0, Math.min(100, (uptimeHours / totalScheduledHours) * 100))
        : 0

    const mtbf =
      totalDowntimeEvents > 0
        ? parseFloat((uptimeHours / totalDowntimeEvents).toFixed(1))
        : parseFloat(uptimeHours.toFixed(1))

    const downtimeReasons = Object.values(reasonsMap)
      .map((r) => ({
        reason: r.reason,
        hours: parseFloat(r.hours.toFixed(1)),
        count: r.count,
        percentage: totalDowntimeHours > 0 ? (r.hours / totalDowntimeHours) * 100 : 0,
      }))
      .sort((a, b) => b.hours - a.hours)

    const equipmentCount = Object.keys(equipmentMap).length || 1
    const byEquipment = Object.values(equipmentMap)
      .map((e) => {
        const equipScheduled = totalScheduledHours / equipmentCount
        const equipUptime = equipScheduled - e.downtime
        return {
          equipment_name: e.equipment_name,
          uptime: parseFloat(Math.max(0, equipUptime).toFixed(1)),
          downtime: parseFloat(e.downtime.toFixed(1)),
          availability: parseFloat(((Math.max(0, equipUptime) / equipScheduled) * 100).toFixed(1)),
        }
      })
      .sort((a, b) => a.availability - b.availability)

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
        by_equipment: byEquipment,
      },
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('Availability fetch error:', error)
    return {
      data: {
        percentage: null,
        uptime: 0,
        downtime: 0,
        total_time: 0,
        mtbf: 0,
        downtime_reasons: [],
        by_equipment: [],
      },
    }
  }
}

export const getPerformance = async (params?: Params) => {
  try {
    const [dashboardRes, productionRes, byShiftRes, byProductRes] = await Promise.all([
      api.get('/kpi/dashboard', { params }).catch(() => ({ data: [] })),
      api.get('/production', { params }).catch(() => ({ data: [] })),
      api.get('/kpi/performance/by-shift', { params }).catch(() => ({ data: [] })),
      api.get('/kpi/performance/by-product', { params }).catch(() => ({ data: [] })),
    ])

    const dashboardData = dashboardRes.data || []
    let avgPerformance: number | null = null
    if (Array.isArray(dashboardData) && dashboardData.length > 0) {
      const validEntries = dashboardData.filter((d: any) => d.avg_performance != null)
      avgPerformance =
        validEntries.length > 0
          ? validEntries.reduce((sum: number, d: any) => sum + d.avg_performance, 0) /
            validEntries.length
          : null
    }

    const productionData: any[] = productionRes.data || []
    let totalUnits = 0
    let totalHours = 0
    let totalExpectedOutput = 0

    productionData.forEach((entry: any) => {
      totalUnits += parseInt(entry.units_produced || 0)
      totalHours += parseFloat(entry.run_time_hours || 0)
      if (entry.ideal_cycle_time_minutes && entry.ideal_cycle_time_minutes > 0) {
        totalExpectedOutput +=
          (parseFloat(entry.run_time_hours || 0) * 60) / parseFloat(entry.ideal_cycle_time_minutes)
      }
    })

    const actualRate = totalHours > 0 ? Math.round(totalUnits / totalHours) : 0

    let standardRate = 0
    if (totalExpectedOutput > 0 && totalHours > 0) {
      standardRate = Math.round(totalExpectedOutput / totalHours)
    } else if (avgPerformance && avgPerformance > 0 && actualRate > 0) {
      standardRate = Math.round(actualRate / (avgPerformance / 100))
    } else if (actualRate > 0) {
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
        by_product: byProductRes.data || [],
      },
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('Performance fetch error:', error)
    return {
      data: {
        percentage: null,
        target: 95,
        actual_rate: 0,
        standard_rate: 0,
        total_units: 0,
        production_hours: 0,
        by_shift: [],
        by_product: [],
      },
    }
  }
}

export const getQuality = async (params?: Params) => {
  try {
    const [fpyRtyRes, defectsRes, byProductRes] = await Promise.all([
      api.get('/quality/kpi/fpy-rty', { params }),
      api.get('/quality/kpi/defects-by-type', { params }).catch(() => ({ data: [] })),
      api.get('/quality/kpi/by-product', { params }).catch(() => ({ data: [] })),
    ])
    const fpyData: any = fpyRtyRes.data ?? {}
    return {
      data: {
        fpy:
          parseFloat(fpyData?.fpy_percentage) || fpyData?.fpy || fpyData?.first_pass_yield || 0,
        rty: parseFloat(fpyData?.rty_percentage) || 0,
        final_yield: parseFloat(fpyData?.final_yield_percentage) || 0,
        total_units: fpyData?.total_units || 0,
        first_pass_good: fpyData?.first_pass_good || 0,
        total_scrapped: fpyData?.total_scrapped || 0,
        defects_by_type: defectsRes.data || [],
        by_product: byProductRes.data || [],
      },
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('[KPI API] Failed to fetch quality:', error)
    return {
      data: {
        fpy: 0,
        rty: 0,
        final_yield: 0,
        total_units: 0,
        total_scrapped: 0,
        defects_by_type: [],
        by_product: [],
      },
    }
  }
}

export const getOEE = async (params?: Params) => {
  try {
    const [dashboardRes, qualityRes, availabilityData] = await Promise.all([
      api.get('/kpi/dashboard', { params }).catch(() => ({ data: [] })),
      api.get('/quality/kpi/fpy-rty', { params }).catch(() => ({ data: { fpy_percentage: 97 } })),
      getAvailability(params),
    ])

    const data = dashboardRes.data || []
    const qualityPayload: any = qualityRes.data ?? {}
    const quality = parseFloat(qualityPayload?.fpy_percentage || qualityPayload?.fpy || 97)
    const availability = availabilityData.data?.percentage || 90

    if (Array.isArray(data) && data.length > 0) {
      const validEntries = data.filter(
        (d: any) => d.avg_efficiency != null && d.avg_performance != null,
      )
      if (validEntries.length > 0) {
        const avgPerf =
          validEntries.reduce((sum: number, d: any) => sum + d.avg_performance, 0) /
          validEntries.length
        const oee = (availability / 100) * (avgPerf / 100) * (quality / 100) * 100
        return { data: { percentage: parseFloat(Math.min(oee, 100).toFixed(2)) } }
      }
    }
    return { data: { percentage: null } }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('[KPI API] Failed to fetch OEE:', error)
    return { data: { percentage: null } }
  }
}

export const getAbsenteeism = (params?: Params) => {
  return api
    .get('/attendance/kpi/absenteeism', { params })
    .then((res) => {
      const d: any = res.data ?? {}
      return {
        data: {
          rate: parseFloat(d?.absenteeism_rate) || d?.rate || 0,
          total_scheduled_hours: parseFloat(d?.total_scheduled_hours) || 0,
          total_hours_absent: parseFloat(d?.total_hours_absent) || 0,
          total_employees: d?.total_employees || 0,
          total_absences: d?.total_absences || 0,
          by_reason: d?.by_reason || [],
          by_department: d?.by_department || [],
          high_absence_employees: d?.high_absence_employees || [],
        },
      }
    })
    .catch((error) => {
      // eslint-disable-next-line no-console
      console.error('[KPI API] Failed to fetch absenteeism:', error)
      return {
        data: {
          rate: 0,
          total_employees: 0,
          total_absences: 0,
          by_reason: [],
          by_department: [],
          high_absence_employees: [],
        },
      }
    })
}

export const getDefectRates = (params?: Params) => {
  return api
    .get('/quality/kpi/ppm', { params })
    .then((res) => {
      const d: any = res.data ?? {}
      return {
        data: {
          ppm: d?.ppm ?? null,
          defect_rate_percentage: d?.defect_rate_percentage ?? null,
        },
      }
    })
    .catch((error) => {
      // eslint-disable-next-line no-console
      console.error('[KPI API] Failed to fetch defect rates:', error)
      return { data: { ppm: null, defect_rate_percentage: null } }
    })
}

export const getThroughputTime = async (params?: Params) => {
  try {
    const response = await api.get('/production', { params })
    const entries: any[] = response.data || []

    if (entries.length > 0) {
      let totalRunHours = 0
      let totalUnits = 0

      entries.forEach((entry: any) => {
        totalRunHours += parseFloat(entry.run_time_hours || 0)
        totalUnits += parseInt(entry.units_produced || 0)
      })

      const avgThroughput = totalUnits > 0 ? (totalRunHours / totalUnits) * 100 : 0
      const displayValue = Math.min(avgThroughput, 24)

      return { data: { average_hours: parseFloat(displayValue.toFixed(2)) || null } }
    }
    return { data: { average_hours: null } }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('[KPI API] Failed to fetch throughput time:', error)
    return { data: { average_hours: null } }
  }
}

const trendCatch = (label: string) => (error: unknown) => {
  // eslint-disable-next-line no-console
  console.error(`[KPI API] Failed to fetch ${label} trend:`, error)
  return { data: [] }
}

export const getEfficiencyTrend = (params?: Params) =>
  api.get('/kpi/efficiency/trend', { params }).catch(trendCatch('efficiency'))

export const getWIPAgingTrend = (params?: Params) =>
  api.get('/kpi/wip-aging/trend', { params }).catch(trendCatch('WIP aging'))

export const getOnTimeDeliveryTrend = (params?: Params) =>
  api.get('/kpi/on-time-delivery/trend', { params }).catch(trendCatch('OTD'))

export const getAvailabilityTrend = (params?: Params) =>
  api.get('/kpi/availability/trend', { params }).catch(trendCatch('availability'))

export const getPerformanceTrend = (params?: Params) =>
  api.get('/kpi/performance/trend', { params }).catch(trendCatch('performance'))

export const getQualityTrend = (params?: Params) =>
  api.get('/kpi/quality/trend', { params }).catch(trendCatch('quality'))

export const getOEETrend = (params?: Params) =>
  api.get('/kpi/oee/trend', { params }).catch(trendCatch('OEE'))

export const getAbsenteeismTrend = (params?: Params) =>
  api.get('/attendance/kpi/absenteeism/trend', { params }).catch(trendCatch('absenteeism'))
