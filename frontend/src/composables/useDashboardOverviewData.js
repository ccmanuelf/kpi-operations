/**
 * Composable for DashboardOverview data fetching, computed dates, and event handlers.
 * Extracted from DashboardOverview.vue to keep component under 500 lines.
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useWorkflowStore } from '@/stores/workflowStore'

export function useDashboardOverviewData(props) {
  const router = useRouter()
  const workflowStore = useWorkflowStore()

  // Computed date range
  const startDate = computed(() => {
    const today = new Date()
    const days = props.dateRange === '7d' ? 7 : props.dateRange === '90d' ? 90 : 30
    const start = new Date(today.getTime() - days * 24 * 60 * 60 * 1000)
    return start.toISOString().split('T')[0]
  })

  const endDate = computed(() => {
    return new Date().toISOString().split('T')[0]
  })

  // KPI data state
  const kpiData = ref({
    efficiency: 0,
    performance: 0,
    wipAging: 0,
    otd: 0,
    availability: 0,
    absenteeism: 0,
    ppm: 0,
    dpmo: 0,
    fpy: 0,
    rty: 0
  })

  const fetchKPIData = async () => {
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
        rtyRes
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
        axios.get('/api/quality/kpi/fpy-rty')
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
        rty: parseFloat(rtyRes.data.rty.toFixed(1))
      }
    } catch (error) {
      console.error('Error fetching KPI data:', error)
    }
  }

  onMounted(() => {
    fetchKPIData()
  })

  // Navigation methods
  const navigateToAbsenteeism = () => {
    router.push('/kpi/absenteeism')
  }

  const navigateToDowntimeAnalysis = () => {
    router.push('/kpi/availability')
  }

  const navigateToAttendance = () => {
    router.push('/kpi/absenteeism')
  }

  const navigateToQualityTrends = () => {
    router.push('/kpi/quality')
  }

  const navigateToReworkAnalysis = () => {
    router.push('/kpi/quality')
  }

  // Action handlers
  const openScheduleDialog = () => {
    console.log('Opening schedule review dialog')
  }

  const handleAbsenteeismAction = (actionId) => {
    console.log('Handling absenteeism action:', actionId)
  }

  const exportQualityReport = () => {
    console.log('Exporting quality by operator report')
  }

  const openActionDialog = () => {
    console.log('Opening corrective action dialog')
  }

  const handleCompletenessNavigate = (categoryId, route) => {
    console.log(`Navigating to ${categoryId} at ${route}`)
  }

  // Shift workflow handlers
  const handleStartShift = () => {
    workflowStore.startWorkflow('shift-start')
  }

  const handleEndShift = () => {
    workflowStore.startWorkflow('shift-end')
  }

  return {
    // Stores
    workflowStore,
    // Computed
    startDate,
    endDate,
    // State
    kpiData,
    // Methods
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
    handleEndShift
  }
}
