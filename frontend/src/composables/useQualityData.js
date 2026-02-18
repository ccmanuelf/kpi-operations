/**
 * Composable for Quality KPI data fetching, reactive state, and calculations.
 * Handles: loading states, API calls, quality/repair/job data, color helpers, formatters.
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import api from '@/services/api'

export function useQualityData() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  // --- Reactive state ---
  const loading = ref(false)
  const loadingJobRty = ref(false)
  const qualityHistory = ref([])
  const repairBreakdown = ref(null)
  const jobRtySummary = ref(null)

  // --- Computed ---
  const qualityData = computed(() => kpiStore.quality)

  const fpyColor = computed(() => {
    const fpy = qualityData.value?.fpy || 0
    if (fpy >= 99) return 'success'
    if (fpy >= 95) return 'amber-darken-3'
    return 'error'
  })

  const rtyColor = computed(() => {
    const rty = qualityData.value?.rty || 0
    if (rty >= 95) return 'success'
    if (rty >= 90) return 'amber-darken-3'
    return 'error'
  })

  const finalYieldColor = computed(() => {
    const fy = qualityData.value?.final_yield || 0
    if (fy >= 99) return 'success'
    if (fy >= 95) return 'amber-darken-3'
    return 'error'
  })

  // --- Table header definitions ---
  const defectHeaders = computed(() => [
    { title: t('kpi.headers.defectType'), key: 'defect_type', sortable: true },
    { title: t('kpi.headers.count'), key: 'count', sortable: true },
    { title: t('kpi.headers.percentage'), key: 'percentage', sortable: true }
  ])

  const productHeaders = computed(() => [
    { title: t('kpi.headers.product'), key: 'product_name', sortable: true },
    { title: t('kpi.headers.inspected'), key: 'inspected', sortable: true },
    { title: t('kpi.headers.defects'), key: 'defects', sortable: true },
    { title: t('kpi.headers.fpy'), key: 'fpy', sortable: true }
  ])

  const qualityHistoryHeaders = computed(() => [
    { title: t('kpi.headers.date'), key: 'shift_date', sortable: true },
    { title: t('kpi.headers.workOrder'), key: 'work_order_id', sortable: true },
    { title: t('kpi.headers.stage'), key: 'inspection_stage', sortable: true },
    { title: t('kpi.headers.inspected'), key: 'units_inspected', sortable: true },
    { title: t('kpi.headers.passed'), key: 'units_passed', sortable: true },
    { title: t('kpi.headers.defective'), key: 'units_defective', sortable: true },
    { title: t('kpi.headers.fpyPercent'), key: 'fpy_percentage', sortable: true }
  ])

  // --- Formatting helpers ---
  const formatValue = (value) => {
    return value !== null && value !== undefined ? Number(value).toFixed(2) : t('common.na')
  }

  const formatDate = (dateStr) => {
    try {
      return format(new Date(dateStr), 'MMM dd, yyyy')
    } catch {
      return dateStr
    }
  }

  // --- Color helpers ---
  const getFPYColor = (fpy) => {
    if (fpy >= 99) return 'success'
    if (fpy >= 95) return 'amber-darken-3'
    return 'error'
  }

  const getInterpretationColor = (interpretation) => {
    if (!interpretation) return 'grey'
    const lower = interpretation.toLowerCase()
    if (lower.includes('excellent')) return 'success'
    if (lower.includes('good')) return 'light-green'
    if (lower.includes('acceptable')) return 'amber'
    if (lower.includes('warning')) return 'orange'
    if (lower.includes('critical') || lower.includes('poor')) return 'error'
    return 'info'
  }

  const getStageColor = (stage) => {
    if (stage === 'Final') return 'success'
    if (stage === 'In-Process') return 'info'
    if (stage === 'Incoming') return 'warning'
    return 'grey'
  }

  const getYieldColor = (yieldPct) => {
    if (yieldPct >= 99) return 'success'
    if (yieldPct >= 95) return 'amber-darken-3'
    return 'error'
  }

  // --- FPY calculation ---
  const calculateFPY = (item) => {
    if (item.fpy_percentage) return Number(item.fpy_percentage)
    const inspected = item.units_inspected || 0
    const passed = item.units_passed || 0
    if (inspected === 0) return 0
    return (passed / inspected) * 100
  }

  const formatFPY = (item) => {
    const fpy = calculateFPY(item)
    return fpy.toFixed(1)
  }

  // --- API calls ---
  const loadJobRtySummary = async (selectedClient, startDate, endDate) => {
    loadingJobRty.value = true
    try {
      const params = {
        start_date: startDate,
        end_date: endDate
      }
      if (selectedClient) {
        params.client_id = selectedClient
      }
      const response = await api.get('/jobs/kpi/rty-summary', { params })
      jobRtySummary.value = response.data
    } catch (error) {
      console.error('Failed to load job RTY summary:', error)
      jobRtySummary.value = null
    } finally {
      loadingJobRty.value = false
    }
  }

  const loadRepairBreakdown = async (selectedClient, startDate, endDate) => {
    try {
      const params = {
        start_date: startDate,
        end_date: endDate
      }
      if (selectedClient) {
        params.client_id = selectedClient
      }
      const response = await api.get('/quality/kpi/fpy-rty-breakdown', { params })
      repairBreakdown.value = response.data
    } catch (error) {
      console.error('Failed to load repair breakdown:', error)
      repairBreakdown.value = null
    }
  }

  const loadQualityHistory = async (selectedClient, startDate, endDate) => {
    try {
      const params = {
        start_date: startDate,
        end_date: endDate
      }
      if (selectedClient) {
        params.client_id = selectedClient
      }
      const response = await api.getQualityEntries(params)
      qualityHistory.value = response.data || []
    } catch (error) {
      console.error('Failed to load quality history:', error)
      qualityHistory.value = []
    }
  }

  const refreshData = async (selectedClient, startDate, endDate) => {
    loading.value = true
    try {
      await Promise.all([
        kpiStore.fetchQuality(),
        loadQualityHistory(selectedClient, startDate, endDate),
        loadRepairBreakdown(selectedClient, startDate, endDate),
        loadJobRtySummary(selectedClient, startDate, endDate)
      ])
    } catch (error) {
      console.error('Failed to refresh data:', error)
    } finally {
      loading.value = false
    }
  }

  return {
    // State
    loading,
    loadingJobRty,
    qualityHistory,
    repairBreakdown,
    jobRtySummary,
    qualityData,
    // Computed colors
    fpyColor,
    rtyColor,
    finalYieldColor,
    // Table headers
    defectHeaders,
    productHeaders,
    qualityHistoryHeaders,
    // Formatters
    formatValue,
    formatDate,
    formatFPY,
    // Color helpers
    getFPYColor,
    getInterpretationColor,
    getStageColor,
    getYieldColor,
    // Calculations
    calculateFPY,
    // API
    loadJobRtySummary,
    loadRepairBreakdown,
    loadQualityHistory,
    refreshData
  }
}
