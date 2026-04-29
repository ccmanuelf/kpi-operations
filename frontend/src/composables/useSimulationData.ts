/**
 * Composable for the Simulation view's reactive state and data
 * fetching. Loading state, guide data, capacity calculation,
 * production line config, simulation execution, sample data.
 */
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  calculateCapacityRequirements,
  getProductionLineGuide,
  getDefaultProductionLineConfig,
  runProductionLineSimulation,
} from '@/services/api/simulation'
import { useNotificationStore } from '@/stores/notificationStore'

export interface CapacityFormState {
  target_units: number
  shift_hours: number
  cycle_time_hours: number
  target_efficiency: number
  absenteeism_rate: number
  include_buffer: boolean
  target_date?: string
}

export interface LineConfigState {
  num_stations: number
  workers_per_station: number
  floating_pool_size: number
  base_cycle_time: number
}

export interface SimulationParamsState {
  duration_hours: number
  random_seed: number
  arrival_rate_per_hour?: number
  max_units?: number
}

export interface ExampleScenario {
  name: string
  config_change?: boolean
  station_modifications?: boolean
  [key: string]: unknown
}

export function useSimulationData() {
  const notificationStore = useNotificationStore()
  const { t } = useI18n()

  const activeTab = ref('production-line')
  const loading = ref(false)
  const showGuide = ref(false)
  const guideTab = ref('quick-start')
  const guide = ref<unknown | null>(null)

  const capacityForm = ref<CapacityFormState>({
    target_units: 100,
    shift_hours: 8,
    cycle_time_hours: 0.25,
    target_efficiency: 85,
    absenteeism_rate: 5,
    include_buffer: true,
  })
  const capacityResult = ref<unknown | null>(null)

  const lineConfig = ref<LineConfigState>({
    num_stations: 4,
    workers_per_station: 2,
    floating_pool_size: 0,
    base_cycle_time: 15,
  })
  const simulationParams = ref<SimulationParamsState>({
    duration_hours: 8,
    random_seed: 42,
  })
  const productionLineConfig = ref<Record<string, unknown> | null>(null)
  const simulationResult = ref<unknown | null>(null)

  onMounted(async () => {
    try {
      const response = await getProductionLineGuide()
      guide.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load guide:', error)
      notificationStore.showError(t('notifications.simulation.guideLoadFailed'))
    }
  })

  async function calculateCapacity(): Promise<void> {
    loading.value = true
    try {
      // The capacity API requires `target_date` (ISO YYYY-MM-DD)
      // even though the form doesn't expose it; default to today
      // for behavioral parity with the JS version which passed the
      // form object directly and let the backend reject undefined.
      const payload = {
        ...capacityForm.value,
        target_date:
          capacityForm.value.target_date || new Date().toISOString().split('T')[0],
      }
      const response = await calculateCapacityRequirements(payload)
      capacityResult.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to calculate capacity:', error)
      notificationStore.showError(t('notifications.simulation.capacityCalcFailed'))
    } finally {
      loading.value = false
    }
  }

  async function loadDefaultConfig(): Promise<void> {
    loading.value = true
    try {
      const response = await getDefaultProductionLineConfig(lineConfig.value)
      productionLineConfig.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load config:', error)
      notificationStore.showError(t('notifications.simulation.lineConfigLoadFailed'))
    } finally {
      loading.value = false
    }
  }

  async function runSimulation(): Promise<void> {
    if (!productionLineConfig.value) return

    loading.value = true
    try {
      const response = await runProductionLineSimulation(
        productionLineConfig.value,
        simulationParams.value,
      )
      simulationResult.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to run simulation:', error)
      notificationStore.showError(t('notifications.simulation.runFailed'))
    } finally {
      loading.value = false
    }
  }

  function loadExampleScenario(scenario: ExampleScenario): void {
    if (scenario.config_change) {
      const lower = scenario.name.toLowerCase()
      if (lower.includes('floating')) {
        lineConfig.value.floating_pool_size = 2
      } else if (lower.includes('worker')) {
        lineConfig.value.workers_per_station = 3
      } else if (lower.includes('cycle') || lower.includes('time')) {
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

  function loadSampleData(): void {
    lineConfig.value = {
      num_stations: 4,
      workers_per_station: 2,
      floating_pool_size: 0,
      base_cycle_time: 15,
    }
    simulationParams.value = {
      duration_hours: 8,
      random_seed: 42,
    }

    showGuide.value = false
    activeTab.value = 'production-line'
    loadDefaultConfig()
  }

  return {
    activeTab,
    loading,
    showGuide,
    guideTab,
    guide,
    capacityForm,
    capacityResult,
    calculateCapacity,
    lineConfig,
    simulationParams,
    productionLineConfig,
    simulationResult,
    loadDefaultConfig,
    runSimulation,
    loadExampleScenario,
    loadSampleData,
  }
}
