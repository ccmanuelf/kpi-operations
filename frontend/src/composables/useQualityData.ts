/**
 * Composable for Quality KPI data fetching, reactive state, and
 * helpers (color tokens, formatters, FPY calculation, repair
 * breakdown, job-level RTY summary).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useKPIStore } from '@/stores/kpi'
import api from '@/services/api'

export interface QualityHistoryItem {
  shift_date?: string
  work_order_id?: string | number
  inspection_stage?: string
  units_inspected?: number
  units_passed?: number
  units_defective?: number
  fpy_percentage?: number | string
  [key: string]: unknown
}

interface TableHeader {
  title: string
  key: string
  sortable: boolean
}

export function useQualityData() {
  const { t } = useI18n()
  const kpiStore = useKPIStore()

  const loading = ref(false)
  const loadingJobRty = ref(false)
  const qualityHistory = ref<QualityHistoryItem[]>([])
  const repairBreakdown = ref<unknown | null>(null)
  const jobRtySummary = ref<unknown | null>(null)

  const qualityData = computed(() => kpiStore.quality)

  const fpyColor = computed<string>(() => {
    const fpy = (qualityData.value?.fpy as number) || 0
    if (fpy >= 99) return 'success'
    if (fpy >= 95) return 'amber-darken-3'
    return 'error'
  })

  const rtyColor = computed<string>(() => {
    const rty = ((qualityData.value as { rty?: number } | null)?.rty as number) || 0
    if (rty >= 95) return 'success'
    if (rty >= 90) return 'amber-darken-3'
    return 'error'
  })

  const finalYieldColor = computed<string>(() => {
    const fy =
      ((qualityData.value as { final_yield?: number } | null)?.final_yield as number) || 0
    if (fy >= 99) return 'success'
    if (fy >= 95) return 'amber-darken-3'
    return 'error'
  })

  const defectHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.defectType'), key: 'defect_type', sortable: true },
    { title: t('kpi.headers.count'), key: 'count', sortable: true },
    { title: t('kpi.headers.percentage'), key: 'percentage', sortable: true },
  ])

  const productHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.product'), key: 'product_name', sortable: true },
    { title: t('kpi.headers.inspected'), key: 'inspected', sortable: true },
    { title: t('kpi.headers.defects'), key: 'defects', sortable: true },
    { title: t('kpi.headers.fpy'), key: 'fpy', sortable: true },
  ])

  const qualityHistoryHeaders = computed<TableHeader[]>(() => [
    { title: t('kpi.headers.date'), key: 'shift_date', sortable: true },
    { title: t('kpi.headers.workOrder'), key: 'work_order_id', sortable: true },
    { title: t('kpi.headers.stage'), key: 'inspection_stage', sortable: true },
    { title: t('kpi.headers.inspected'), key: 'units_inspected', sortable: true },
    { title: t('kpi.headers.passed'), key: 'units_passed', sortable: true },
    { title: t('kpi.headers.defective'), key: 'units_defective', sortable: true },
    { title: t('kpi.headers.fpyPercent'), key: 'fpy_percentage', sortable: true },
  ])

  const formatValue = (value: number | null | undefined): string =>
    value !== null && value !== undefined ? Number(value).toFixed(2) : t('common.na')

  const formatDate = (dateStr: string): string => {
    try {
      return format(new Date(dateStr), 'MMM dd, yyyy')
    } catch {
      return dateStr
    }
  }

  const getFPYColor = (fpy: number): string => {
    if (fpy >= 99) return 'success'
    if (fpy >= 95) return 'amber-darken-3'
    return 'error'
  }

  const getInterpretationColor = (interpretation: string | null | undefined): string => {
    if (!interpretation) return 'grey'
    const lower = interpretation.toLowerCase()
    if (lower.includes('excellent')) return 'success'
    if (lower.includes('good')) return 'light-green'
    if (lower.includes('acceptable')) return 'amber'
    if (lower.includes('warning')) return 'orange'
    if (lower.includes('critical') || lower.includes('poor')) return 'error'
    return 'info'
  }

  const getStageColor = (stage: string | null | undefined): string => {
    if (stage === 'Final') return 'success'
    if (stage === 'In-Process') return 'info'
    if (stage === 'Incoming') return 'warning'
    return 'grey'
  }

  const getYieldColor = (yieldPct: number): string => {
    if (yieldPct >= 99) return 'success'
    if (yieldPct >= 95) return 'amber-darken-3'
    return 'error'
  }

  const calculateFPY = (item: QualityHistoryItem): number => {
    if (item.fpy_percentage) return Number(item.fpy_percentage)
    const inspected = item.units_inspected || 0
    const passed = item.units_passed || 0
    if (inspected === 0) return 0
    return (passed / inspected) * 100
  }

  const formatFPY = (item: QualityHistoryItem): string => {
    const fpy = calculateFPY(item)
    return fpy.toFixed(1)
  }

  type ClientId = string | number | null

  const loadJobRtySummary = async (
    selectedClient: ClientId,
    startDate: string,
    endDate: string,
  ): Promise<void> => {
    loadingJobRty.value = true
    try {
      const params: Record<string, unknown> = {
        start_date: startDate,
        end_date: endDate,
      }
      if (selectedClient) {
        params.client_id = selectedClient
      }
      const response = await api.get('/jobs/kpi/rty-summary', { params })
      jobRtySummary.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load job RTY summary:', error)
      jobRtySummary.value = null
    } finally {
      loadingJobRty.value = false
    }
  }

  const loadRepairBreakdown = async (
    selectedClient: ClientId,
    startDate: string,
    endDate: string,
  ): Promise<void> => {
    try {
      const params: Record<string, unknown> = {
        start_date: startDate,
        end_date: endDate,
      }
      if (selectedClient) {
        params.client_id = selectedClient
      }
      const response = await api.get('/quality/kpi/fpy-rty-breakdown', { params })
      repairBreakdown.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load repair breakdown:', error)
      repairBreakdown.value = null
    }
  }

  const loadQualityHistory = async (
    selectedClient: ClientId,
    startDate: string,
    endDate: string,
  ): Promise<void> => {
    try {
      const params: Record<string, unknown> = {
        start_date: startDate,
        end_date: endDate,
      }
      if (selectedClient) {
        params.client_id = selectedClient
      }
      const response = await api.getQualityEntries(params)
      qualityHistory.value = response.data || []
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load quality history:', error)
      qualityHistory.value = []
    }
  }

  const refreshData = async (
    selectedClient: ClientId,
    startDate: string,
    endDate: string,
  ): Promise<void> => {
    loading.value = true
    try {
      await Promise.all([
        kpiStore.fetchQuality(),
        loadQualityHistory(selectedClient, startDate, endDate),
        loadRepairBreakdown(selectedClient, startDate, endDate),
        loadJobRtySummary(selectedClient, startDate, endDate),
      ])
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to refresh data:', error)
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    loadingJobRty,
    qualityHistory,
    repairBreakdown,
    jobRtySummary,
    qualityData,
    fpyColor,
    rtyColor,
    finalYieldColor,
    defectHeaders,
    productHeaders,
    qualityHistoryHeaders,
    formatValue,
    formatDate,
    formatFPY,
    getFPYColor,
    getInterpretationColor,
    getStageColor,
    getYieldColor,
    calculateFPY,
    loadJobRtySummary,
    loadRepairBreakdown,
    loadQualityHistory,
    refreshData,
  }
}
