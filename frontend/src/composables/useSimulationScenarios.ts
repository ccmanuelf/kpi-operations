/**
 * Composable for Simulation scenario comparison logic.
 * Manages a list of named scenarios (add/remove) and runs the
 * comparison against a baseline configuration.
 */
import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { compareProductionScenarios } from '@/services/api/simulation'
import { useNotificationStore } from '@/stores/notificationStore'

export interface ScenarioInput {
  name: string
  workers_per_station: number
  floating_pool_size: number
  [key: string]: unknown
}

export function useSimulationScenarios(
  productionLineConfig: Ref<Record<string, unknown> | null>,
  simulationParams: Ref<Record<string, unknown> | null>,
  loading: Ref<boolean>,
) {
  const notificationStore = useNotificationStore()
  const { t } = useI18n()

  const scenarios = ref<ScenarioInput[]>([])
  const newScenario = ref<ScenarioInput>({
    name: '',
    workers_per_station: 2,
    floating_pool_size: 0,
  })
  const comparisonResult = ref<unknown | null>(null)

  function addScenario(): void {
    if (newScenario.value.name) {
      scenarios.value.push({ ...newScenario.value })
      newScenario.value = { name: '', workers_per_station: 2, floating_pool_size: 0 }
    }
  }

  function removeScenario(idx: number): void {
    scenarios.value.splice(idx, 1)
  }

  async function compareScenarios(): Promise<void> {
    if (!productionLineConfig.value || scenarios.value.length < 1) return

    loading.value = true
    try {
      const response = await compareProductionScenarios(
        productionLineConfig.value,
        scenarios.value,
        simulationParams.value || undefined,
      )
      comparisonResult.value = response.data
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to compare scenarios:', error)
      notificationStore.showError(t('notifications.simulation.scenarioCompareFailed'))
    } finally {
      loading.value = false
    }
  }

  return {
    scenarios,
    newScenario,
    comparisonResult,
    addScenario,
    removeScenario,
    compareScenarios,
  }
}
