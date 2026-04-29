/**
 * Composable for DashboardOverview data fetching, computed date
 * range, navigation handlers, and shift-workflow triggers.
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useWorkflowStore } from '@/stores/workflowStore'

export type DateRangeOption = '7d' | '30d' | '90d' | string

export interface DashboardOverviewProps {
  dateRange?: DateRangeOption
  [key: string]: unknown
}

export interface DashboardKPIData {
  efficiency: number
  performance: number
  wipAging: number
  otd: number
  availability: number
  absenteeism: number
  ppm: number
  dpmo: number
  fpy: number
  rty: number
}

export function useDashboardOverviewData(props: DashboardOverviewProps) {
  const router = useRouter()
  const workflowStore = useWorkflowStore()

  const startDate = computed<string>(() => {
    const today = new Date()
    const days = props.dateRange === '7d' ? 7 : props.dateRange === '90d' ? 90 : 30
    const start = new Date(today.getTime() - days * 24 * 60 * 60 * 1000)
    return start.toISOString().split('T')[0]
  })

  const endDate = computed<string>(() => new Date().toISOString().split('T')[0])

  const kpiData = ref<DashboardKPIData>({
    efficiency: 0,
    performance: 0,
    wipAging: 0,
    otd: 0,
    availability: 0,
    absenteeism: 0,
    ppm: 0,
    dpmo: 0,
    fpy: 0,
    rty: 0,
  })

  const fetchKPIData = async (): Promise<void> => {
    try {
      const [
        efficiencyRes,
        performanceRes,
        wipRes,
        otdRes,
        availabilityRes,
        absenteeismRes,
        ppmRes,
        dpmoRes,
        fpyRes,
        rtyRes,
      ] = await Promise.all([
        axios.get('/api/kpi/efficiency/trend'),
        axios.get('/api/kpi/performance/trend'),
        axios.get('/api/kpi/wip-aging'),
        axios.get('/api/kpi/otd'),
        axios.get('/api/kpi/availability'),
        axios.get('/api/attendance/kpi/absenteeism'),
        axios.get('/api/quality/kpi/ppm'),
        axios.get('/api/quality/kpi/dpmo'),
        axios.get('/api/quality/kpi/fpy-rty'),
        axios.get('/api/quality/kpi/fpy-rty'),
      ])

      kpiData.value = {
        efficiency: parseFloat(efficiencyRes.data.value.toFixed(1)),
        performance: parseFloat(performanceRes.data.value.toFixed(1)),
        wipAging: parseFloat(wipRes.data.average_aging_days.toFixed(1)),
        otd: parseFloat(otdRes.data.otd_percentage.toFixed(1)),
        availability: parseFloat(availabilityRes.data.average_availability.toFixed(1)),
        absenteeism: parseFloat(absenteeismRes.data.absenteeism_rate.toFixed(1)),
        ppm: parseInt(ppmRes.data.ppm),
        dpmo: parseInt(dpmoRes.data.dpmo),
        fpy: parseFloat(fpyRes.data.fpy.toFixed(1)),
        rty: parseFloat(rtyRes.data.rty.toFixed(1)),
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error fetching KPI data:', error)
    }
  }

  onMounted(() => {
    fetchKPIData()
  })

  const navigateToAbsenteeism = (): void => {
    router.push('/kpi/absenteeism')
  }

  const navigateToDowntimeAnalysis = (): void => {
    router.push('/kpi/availability')
  }

  const navigateToAttendance = (): void => {
    router.push('/kpi/absenteeism')
  }

  const navigateToQualityTrends = (): void => {
    router.push('/kpi/quality')
  }

  const navigateToReworkAnalysis = (): void => {
    router.push('/kpi/quality')
  }

  const openScheduleDialog = (): void => {
    // eslint-disable-next-line no-console
    console.log('Opening schedule review dialog')
  }

  const handleAbsenteeismAction = (actionId: string | number): void => {
    // eslint-disable-next-line no-console
    console.log('Handling absenteeism action:', actionId)
  }

  const exportQualityReport = (): void => {
    // eslint-disable-next-line no-console
    console.log('Exporting quality by operator report')
  }

  const openActionDialog = (): void => {
    // eslint-disable-next-line no-console
    console.log('Opening corrective action dialog')
  }

  const handleCompletenessNavigate = (categoryId: string, route: string): void => {
    // eslint-disable-next-line no-console
    console.log(`Navigating to ${categoryId} at ${route}`)
  }

  const handleStartShift = (): void => {
    workflowStore.startWorkflow('shift-start')
  }

  const handleEndShift = (): void => {
    workflowStore.startWorkflow('shift-end')
  }

  return {
    workflowStore,
    startDate,
    endDate,
    kpiData,
    fetchKPIData,
    navigateToAbsenteeism,
    navigateToDowntimeAnalysis,
    navigateToAttendance,
    navigateToQualityTrends,
    navigateToReworkAnalysis,
    openScheduleDialog,
    handleAbsenteeismAction,
    exportQualityReport,
    openActionDialog,
    handleCompletenessNavigate,
    handleStartShift,
    handleEndShift,
  }
}
