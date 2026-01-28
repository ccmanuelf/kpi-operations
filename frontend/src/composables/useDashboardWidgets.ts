/**
 * Dashboard Widgets Composables
 * Provides reactive data fetching for dashboard widgets
 */
import { ref, computed, watch } from 'vue'
import axios from 'axios'

const API_BASE = '/api'

// Types
export interface DowntimeImpactData {
  category: string
  totalHours: number
  oeeImpact: number
  eventCount: number
  severity: 'critical' | 'high' | 'medium' | 'low'
}

export interface BradfordFactorData {
  employeeId: number
  employeeName: string
  score: number
  spells: number
  totalDays: number
  riskLevel: 'low' | 'monitor' | 'action' | 'critical'
}

export interface OperatorQualityData {
  operatorId: string
  operatorName: string
  unitsInspected: number
  defects: number
  fpy: number
  trend: 'up' | 'down' | 'stable'
}

export interface ReworkOperationData {
  operation: string
  reworkUnits: number
  reworkHours: number
  reworkRate: number
  estimatedCost: number
}

export interface AbsenteeismAlertData {
  rate: number
  threshold: number
  scheduledHours: number
  absentHours: number
  affectedEmployees: number
  trend: number
}

// Downtime Impact Composable
export function useDowntimeImpact(clientId?: string, dateRange?: string) {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const data = ref<DowntimeImpactData[]>([])

  const totalDowntime = computed(() =>
    data.value.reduce((sum, item) => sum + item.totalHours, 0)
  )

  const totalOeeImpact = computed(() =>
    data.value.reduce((sum, item) => sum + item.oeeImpact, 0)
  )

  const fetchData = async (startDate?: string, endDate?: string) => {
    loading.value = true
    error.value = null

    try {
      // Try dedicated endpoint first
      const response = await axios.get(`${API_BASE}/kpi/downtime-impact`, {
        params: { client_id: clientId, start_date: startDate, end_date: endDate }
      })

      if (response.data?.categories) {
        data.value = response.data.categories.map((cat: any, index: number) => ({
          category: cat.category || cat.downtime_category,
          totalHours: parseFloat(cat.total_hours || 0),
          oeeImpact: parseFloat(cat.oee_impact || 0),
          eventCount: cat.event_count || 0,
          severity: determineSeverity(parseFloat(cat.oee_impact || 0))
        }))
      }
    } catch {
      // Fallback to downtime events
      try {
        const response = await axios.get(`${API_BASE}/downtime`, {
          params: { start_date: startDate, end_date: endDate, limit: 1000 }
        })

        if (Array.isArray(response.data)) {
          const categoryMap = new Map<string, { hours: number; count: number }>()

          response.data.forEach((event: any) => {
            const category = event.downtime_category || 'Unknown'
            const hours = parseFloat(event.duration_hours || 0)

            if (categoryMap.has(category)) {
              const existing = categoryMap.get(category)!
              existing.hours += hours
              existing.count += 1
            } else {
              categoryMap.set(category, { hours, count: 1 })
            }
          })

          const totalScheduled = 480 // Default estimate
          data.value = Array.from(categoryMap.entries())
            .sort((a, b) => b[1].hours - a[1].hours)
            .slice(0, 10)
            .map(([category, info]) => ({
              category,
              totalHours: parseFloat(info.hours.toFixed(1)),
              oeeImpact: parseFloat(((info.hours / totalScheduled) * 100).toFixed(1)),
              eventCount: info.count,
              severity: determineSeverity((info.hours / totalScheduled) * 100)
            }))
        }
      } catch (err: any) {
        error.value = err.response?.data?.detail || 'Failed to load downtime data'
      }
    } finally {
      loading.value = false
    }
  }

  const determineSeverity = (impact: number): 'critical' | 'high' | 'medium' | 'low' => {
    if (impact >= 10) return 'critical'
    if (impact >= 5) return 'high'
    if (impact >= 2) return 'medium'
    return 'low'
  }

  return {
    loading,
    error,
    data,
    totalDowntime,
    totalOeeImpact,
    fetchData
  }
}

// Bradford Factor Composable
export function useBradfordFactor() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const data = ref<BradfordFactorData[]>([])

  const fetchData = async (employeeId?: number, startDate?: string, endDate?: string) => {
    loading.value = true
    error.value = null

    try {
      const response = await axios.get(`${API_BASE}/kpi/bradford-factor`, {
        params: { employee_id: employeeId, start_date: startDate, end_date: endDate }
      })

      if (Array.isArray(response.data)) {
        data.value = response.data.map((emp: any) => ({
          employeeId: emp.employee_id,
          employeeName: emp.employee_name || `Employee ${emp.employee_id}`,
          score: emp.bradford_score || 0,
          spells: emp.spells || 0,
          totalDays: emp.total_days || 0,
          riskLevel: getRiskLevel(emp.bradford_score || 0)
        }))
      } else if (response.data) {
        data.value = [{
          employeeId: response.data.employee_id || employeeId || 0,
          employeeName: response.data.employee_name || 'Selected Employee',
          score: response.data.bradford_score || response.data.score || 0,
          spells: response.data.spells || 0,
          totalDays: response.data.total_days || 0,
          riskLevel: getRiskLevel(response.data.bradford_score || response.data.score || 0)
        }]
      }
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to load Bradford Factor data'
    } finally {
      loading.value = false
    }
  }

  const getRiskLevel = (score: number): 'low' | 'monitor' | 'action' | 'critical' => {
    if (score <= 50) return 'low'
    if (score <= 200) return 'monitor'
    if (score <= 400) return 'action'
    return 'critical'
  }

  return {
    loading,
    error,
    data,
    fetchData
  }
}

// Quality by Operator Composable
export function useQualityByOperator() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const data = ref<OperatorQualityData[]>([])

  const averageFPY = computed(() => {
    if (!data.value.length) return 0
    return data.value.reduce((sum, op) => sum + op.fpy, 0) / data.value.length
  })

  const topPerformers = computed(() =>
    data.value.filter(op => op.fpy >= 98).length
  )

  const needsAttention = computed(() =>
    data.value.filter(op => op.fpy < 95).length
  )

  const fetchData = async (clientId?: string, productId?: number, startDate?: string, endDate?: string) => {
    loading.value = true
    error.value = null

    try {
      const response = await axios.get(`${API_BASE}/kpi/quality/by-operator`, {
        params: { client_id: clientId, product_id: productId, start_date: startDate, end_date: endDate }
      })

      if (Array.isArray(response.data)) {
        data.value = response.data.map((op: any) => ({
          operatorId: op.operator_id || op.employee_id || 'N/A',
          operatorName: op.operator_name || op.employee_name || `Operator ${op.operator_id}`,
          unitsInspected: op.units_inspected || 0,
          defects: op.defects || 0,
          fpy: parseFloat(op.fpy || 100),
          trend: op.trend || 'stable'
        }))
      }
    } catch {
      // Fallback to quality inspections
      try {
        const response = await axios.get(`${API_BASE}/quality`, {
          params: { start_date: startDate, end_date: endDate, limit: 1000 }
        })

        if (Array.isArray(response.data)) {
          const operatorMap = new Map<string, { name: string; inspected: number; defects: number }>()

          response.data.forEach((inspection: any) => {
            const id = inspection.inspector_id || inspection.operator_id || 'unknown'
            const name = inspection.inspector_name || inspection.operator_name || `Operator ${id}`

            if (operatorMap.has(id)) {
              const existing = operatorMap.get(id)!
              existing.inspected += inspection.units_inspected || 0
              existing.defects += inspection.defects_found || 0
            } else {
              operatorMap.set(id, {
                name,
                inspected: inspection.units_inspected || 0,
                defects: inspection.defects_found || 0
              })
            }
          })

          data.value = Array.from(operatorMap.entries())
            .map(([id, info]) => {
              const fpy = info.inspected > 0
                ? ((info.inspected - info.defects) / info.inspected) * 100
                : 100
              return {
                operatorId: id,
                operatorName: info.name,
                unitsInspected: info.inspected,
                defects: info.defects,
                fpy: parseFloat(fpy.toFixed(1)),
                trend: 'stable' as const
              }
            })
            .sort((a, b) => b.fpy - a.fpy)
            .slice(0, 20)
        }
      } catch (err: any) {
        error.value = err.response?.data?.detail || 'Failed to load quality data'
      }
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    data,
    averageFPY,
    topPerformers,
    needsAttention,
    fetchData
  }
}

// Rework by Operation Composable
export function useReworkByOperation() {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const data = ref<ReworkOperationData[]>([])
  const totalUnitsProduced = ref(10000)

  const totalReworkUnits = computed(() =>
    data.value.reduce((sum, op) => sum + op.reworkUnits, 0)
  )

  const totalReworkCost = computed(() =>
    data.value.reduce((sum, op) => sum + op.estimatedCost, 0)
  )

  const overallReworkRate = computed(() => {
    if (totalUnitsProduced.value === 0) return 0
    return (totalReworkUnits.value / totalUnitsProduced.value) * 100
  })

  const fetchData = async (clientId?: string, productId?: number, startDate?: string, endDate?: string) => {
    loading.value = true
    error.value = null

    try {
      const response = await axios.get(`${API_BASE}/kpi/quality/rework-by-operation`, {
        params: { client_id: clientId, product_id: productId, start_date: startDate, end_date: endDate }
      })

      const operations = response.data?.operations || response.data
      if (Array.isArray(operations)) {
        totalUnitsProduced.value = response.data?.total_units_produced || 10000

        data.value = operations.map((op: any) => ({
          operation: op.operation || op.inspection_stage || 'Unknown',
          reworkUnits: op.rework_units || 0,
          reworkHours: parseFloat(op.rework_hours || 0),
          reworkRate: parseFloat(op.rework_rate || 0),
          estimatedCost: op.estimated_cost || (op.rework_units * 15)
        }))
      }
    } catch {
      // Fallback to quality inspections
      try {
        const response = await axios.get(`${API_BASE}/quality`, {
          params: { start_date: startDate, end_date: endDate, limit: 1000 }
        })

        if (Array.isArray(response.data)) {
          const operationMap = new Map<string, { rework: number; total: number }>()
          let totalProduced = 0

          response.data.forEach((inspection: any) => {
            const operation = inspection.inspection_stage || 'General'
            const rework = inspection.rework_units || 0
            const total = inspection.units_inspected || 0

            totalProduced += total

            if (operationMap.has(operation)) {
              const existing = operationMap.get(operation)!
              existing.rework += rework
              existing.total += total
            } else {
              operationMap.set(operation, { rework, total })
            }
          })

          totalUnitsProduced.value = totalProduced

          data.value = Array.from(operationMap.entries())
            .filter(([_, info]) => info.rework > 0)
            .map(([operation, info]) => ({
              operation,
              reworkUnits: info.rework,
              reworkHours: info.rework * 0.5,
              reworkRate: info.total > 0 ? (info.rework / info.total) * 100 : 0,
              estimatedCost: info.rework * 15
            }))
            .sort((a, b) => b.reworkUnits - a.reworkUnits)
            .slice(0, 10)
        }
      } catch (err: any) {
        error.value = err.response?.data?.detail || 'Failed to load rework data'
      }
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    data,
    totalUnitsProduced,
    totalReworkUnits,
    totalReworkCost,
    overallReworkRate,
    fetchData
  }
}

// Absenteeism Alert Composable
export function useAbsenteeismAlert(threshold = 5) {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const data = ref<AbsenteeismAlertData>({
    rate: 0,
    threshold,
    scheduledHours: 0,
    absentHours: 0,
    affectedEmployees: 0,
    trend: 0
  })

  const shouldShowAlert = computed(() => data.value.rate > data.value.threshold)

  const alertSeverity = computed(() => {
    if (data.value.rate > threshold * 2) return 'error'
    if (data.value.rate > threshold) return 'warning'
    return 'info'
  })

  const fetchData = async (clientId?: string, startDate?: string, endDate?: string) => {
    loading.value = true
    error.value = null

    try {
      const response = await axios.get(`${API_BASE}/kpi/absenteeism`, {
        params: { client_id: clientId, start_date: startDate, end_date: endDate }
      })

      if (response.data) {
        data.value = {
          rate: parseFloat(response.data.absenteeism_rate || 0),
          threshold,
          scheduledHours: response.data.total_scheduled_hours || 0,
          absentHours: response.data.total_absent_hours || 0,
          affectedEmployees: response.data.affected_employees || response.data.employee_count || 0,
          trend: response.data.trend || 0
        }
      }
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to load absenteeism data'
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    error,
    data,
    shouldShowAlert,
    alertSeverity,
    fetchData
  }
}

// Export all composables
export default {
  useDowntimeImpact,
  useBradfordFactor,
  useQualityByOperator,
  useReworkByOperation,
  useAbsenteeismAlert
}
