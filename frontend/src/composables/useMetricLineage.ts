/**
 * useMetricLineage — Phase 4 dual-view inspector composable.
 *
 * Lazily loads the full lineage (formula, inputs, assumptions applied) for
 * one persisted metric_calculation_result row. Used by the inspector
 * side-panel/modal when the user clicks a metric value.
 *
 * Pattern follows the existing useKPIDashboardData / useKPIReports composables:
 * a single ref<T | null> + loading + error, returned alongside a `load(id)`
 * action.
 */

import { ref } from 'vue'

import { getMetricLineage, type MetricLineage } from '@/services/api/metricResults'

export function useMetricLineage() {
  const lineage = ref<MetricLineage | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (resultId: number) => {
    loading.value = true
    error.value = null
    try {
      const response = await getMetricLineage(resultId)
      lineage.value = response.data
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load metric lineage'
      error.value = message
      lineage.value = null
    } finally {
      loading.value = false
    }
  }

  const clear = () => {
    lineage.value = null
    error.value = null
  }

  return { lineage, loading, error, load, clear }
}
