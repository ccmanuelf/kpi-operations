/**
 * Composable for Simulation scenario comparison logic.
 * Handles: scenario list management (add/remove), and
 * running scenario comparison against a baseline configuration.
 */
import { ref } from 'vue'
import { compareProductionScenarios } from '@/services/api/simulation'
import { useNotificationStore } from '@/stores/notificationStore'

export function useSimulationScenarios(productionLineConfig, simulationParams, loading) {
  const notificationStore = useNotificationStore()

  const scenarios = ref([])
  const newScenario = ref({
    name: '',
    workers_per_station: 2,
    floating_pool_size: 0
  })
  const comparisonResult = ref(null)

  function addScenario() {
    if (newScenario.value.name) {
      scenarios.value.push({ ...newScenario.value })
      newScenario.value = { name: '', workers_per_station: 2, floating_pool_size: 0 }
    }
  }

  function removeScenario(idx) {
    scenarios.value.splice(idx, 1)
  }

  async function compareScenarios() {
    if (!productionLineConfig.value || scenarios.value.length < 1) return

    loading.value = true
    try {
      const response = await compareProductionScenarios(
        productionLineConfig.value,
        scenarios.value,
        simulationParams.value
      )
      comparisonResult.value = response.data
    } catch (error) {
      console.error('Failed to compare scenarios:', error)
      notificationStore.showError('Failed to compare scenarios. Please try again.')
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
    compareScenarios
  }
}
