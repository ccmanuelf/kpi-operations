/**
 * Composable for retaining and comparing simulation V2 results.
 *
 * Keeps at most two results in memory (current + previous) and provides
 * helpers for computing deltas between consecutive runs.
 */
import { ref, computed } from 'vue'

/**
 * Module-level state so history survives component re-mounts
 * but is lost on full page reload (by design — ephemeral tool).
 */
const currentResult = ref(null)
const previousResult = ref(null)

export function useSimulationComparison() {
  /** Whether a previous run exists for comparison. */
  const hasHistory = computed(() => previousResult.value !== null)

  /**
   * Push a new simulation result into the history ring.
   * The current result becomes the previous; the new one becomes current.
   *
   * @param {Object} result - The SimulationResults payload from the API.
   */
  function saveResult(result) {
    if (!result) return
    previousResult.value = currentResult.value
    currentResult.value = structuredClone(result)
  }

  /**
   * Clear both result slots.
   */
  function clearHistory() {
    currentResult.value = null
    previousResult.value = null
  }

  /**
   * Compute the absolute and percentage delta for a numeric metric
   * extracted from `daily_summary` or `free_capacity`.
   *
   * @param {string} block  - Top-level result key (e.g. 'daily_summary', 'free_capacity').
   * @param {string} metric - Metric key inside the block (e.g. 'daily_throughput_pcs').
   * @returns {{ current: number, previous: number, delta: number, deltaPct: number, direction: 'improved'|'regressed'|'unchanged' } | null}
   */
  function getDelta(block, metric) {
    if (!currentResult.value || !previousResult.value) return null

    const cur = currentResult.value[block]?.[metric]
    const prev = previousResult.value[block]?.[metric]

    if (cur == null || prev == null) return null

    const delta = cur - prev
    const deltaPct = prev !== 0 ? ((delta / Math.abs(prev)) * 100) : 0

    let direction = 'unchanged'
    if (Math.abs(delta) > 0.001) {
      // For most production metrics, higher is better.
      // Exceptions are handled by the caller via the raw delta.
      direction = delta > 0 ? 'improved' : 'regressed'
    }

    return { current: cur, previous: prev, delta, deltaPct, direction }
  }

  /**
   * Count bottleneck stations in a result set.
   * @param {Object} result - A SimulationResults object.
   * @returns {number}
   */
  function countBottlenecks(result) {
    if (!result?.station_performance) return 0
    return result.station_performance.filter(s => s.is_bottleneck).length
  }

  return {
    currentResult,
    previousResult,
    hasHistory,
    saveResult,
    clearHistory,
    getDelta,
    countBottlenecks,
  }
}
