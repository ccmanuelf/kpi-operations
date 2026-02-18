/**
 * Composable for Simulation view reactive state and data fetching.
 * Handles: loading state, guide data, capacity planning calculation,
 * production line configuration, and simulation execution.
 */
import { ref, onMounted } from 'vue'
import {
  calculateCapacityRequirements,
  getProductionLineGuide,
  getDefaultProductionLineConfig,
  runProductionLineSimulation
} from '@/services/api/simulation'
import { useNotificationStore } from '@/stores/notificationStore'

export function useSimulationData() {
  const notificationStore = useNotificationStore()

  // UI state
  const activeTab = ref('production-line')
  const loading = ref(false)
  const showGuide = ref(false)
  const guideTab = ref('quick-start')
  const guide = ref(null)

  // Capacity Planning
  const capacityForm = ref({
    target_units: 100,
    shift_hours: 8,
    cycle_time_hours: 0.25,
    target_efficiency: 85,
    absenteeism_rate: 5,
    include_buffer: true
  })
  const capacityResult = ref(null)

  // Production Line Simulation
  const lineConfig = ref({
    num_stations: 4,
    workers_per_station: 2,
    floating_pool_size: 0,
    base_cycle_time: 15
  })
  const simulationParams = ref({
    duration_hours: 8,
    random_seed: 42
  })
  const productionLineConfig = ref(null)
  const simulationResult = ref(null)

  // Fetch guide on mount
  onMounted(async () => {
    try {
      const response = await getProductionLineGuide()
      guide.value = response.data
    } catch (error) {
      console.error('Failed to load guide:', error)
      notificationStore.showError('Failed to load simulation guide. Please refresh the page.')
    }
  })

  async function calculateCapacity() {
    loading.value = true
    try {
      const response = await calculateCapacityRequirements(capacityForm.value)
      capacityResult.value = response.data
    } catch (error) {
      console.error('Failed to calculate capacity:', error)
      notificationStore.showError('Failed to calculate capacity requirements. Please try again.')
    } finally {
      loading.value = false
    }
  }

  async function loadDefaultConfig() {
    loading.value = true
    try {
      const response = await getDefaultProductionLineConfig(lineConfig.value)
      productionLineConfig.value = response.data
    } catch (error) {
      console.error('Failed to load config:', error)
      notificationStore.showError('Failed to load production line configuration. Please try again.')
    } finally {
      loading.value = false
    }
  }

  async function runSimulation() {
    if (!productionLineConfig.value) return

    loading.value = true
    try {
      const response = await runProductionLineSimulation(productionLineConfig.value, simulationParams.value)
      simulationResult.value = response.data
    } catch (error) {
      console.error('Failed to run simulation:', error)
      notificationStore.showError('Failed to run simulation. Please try again.')
    } finally {
      loading.value = false
    }
  }

  function loadExampleScenario(scenario) {
    if (scenario.config_change) {
      if (scenario.name.toLowerCase().includes('floating')) {
        lineConfig.value.floating_pool_size = 2
      } else if (scenario.name.toLowerCase().includes('worker')) {
        lineConfig.value.workers_per_station = 3
      } else if (scenario.name.toLowerCase().includes('cycle') || scenario.name.toLowerCase().includes('time')) {
        lineConfig.value.base_cycle_time = 12
      }
    }
    if (scenario.station_modifications) {
      lineConfig.value.num_stations = 5
    }

    showGuide.value = false
    activeTab.value = 'production-line'
    loadDefaultConfig()
  }

  function loadSampleData() {
    lineConfig.value = {
      num_stations: 4,
      workers_per_station: 2,
      floating_pool_size: 0,
      base_cycle_time: 15
    }
    simulationParams.value = {
      duration_hours: 8,
      random_seed: 42
    }

    showGuide.value = false
    activeTab.value = 'production-line'
    loadDefaultConfig()
  }

  return {
    // UI state
    activeTab,
    loading,
    showGuide,
    guideTab,
    guide,
    // Capacity planning
    capacityForm,
    capacityResult,
    calculateCapacity,
    // Production line
    lineConfig,
    simulationParams,
    productionLineConfig,
    simulationResult,
    loadDefaultConfig,
    runSimulation,
    // Guide helpers
    loadExampleScenario,
    loadSampleData
  }
}
