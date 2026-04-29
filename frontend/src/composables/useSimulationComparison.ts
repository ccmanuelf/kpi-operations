/**
 * Composable for retaining and comparing SimPy v2 results.
 * Module-level state so history survives component re-mounts but
 * is lost on full page reload — the simulation is an ephemeral
 * tool by design.
 */
import { ref, computed } from 'vue'

export interface StationPerformanceRow {
  is_bottleneck?: boolean
  [key: string]: unknown
}

export interface SimulationResultPayload {
  daily_summary?: Record<string, number | undefined>
  free_capacity?: Record<string, number | undefined>
  station_performance?: StationPerformanceRow[]
  [key: string]: unknown
}

export type Direction = 'improved' | 'regressed' | 'unchanged'

export interface DeltaResult {
  current: number
  previous: number
  delta: number
  deltaPct: number
  direction: Direction
}

const currentResult = ref<SimulationResultPayload | null>(null)
const previousResult = ref<SimulationResultPayload | null>(null)

export function useSimulationComparison() {
  const hasHistory = computed(() => previousResult.value !== null)

  function saveResult(result: SimulationResultPayload | null): void {
    if (!result) return
    previousResult.value = currentResult.value
    currentResult.value = structuredClone(result)
  }

  function clearHistory(): void {
    currentResult.value = null
    previousResult.value = null
  }

  function getDelta(
    block: keyof SimulationResultPayload,
    metric: string,
  ): DeltaResult | null {
    if (!currentResult.value || !previousResult.value) return null

    const curBlock = currentResult.value[block] as Record<string, number | undefined> | undefined
    const prevBlock = previousResult.value[block] as Record<string, number | undefined> | undefined

    const cur = curBlock?.[metric]
    const prev = prevBlock?.[metric]

    if (cur == null || prev == null) return null

    const delta = cur - prev
    const deltaPct = prev !== 0 ? (delta / Math.abs(prev)) * 100 : 0

    let direction: Direction = 'unchanged'
    if (Math.abs(delta) > 0.001) {
      direction = delta > 0 ? 'improved' : 'regressed'
    }

    return { current: cur, previous: prev, delta, deltaPct, direction }
  }

  function countBottlenecks(result: SimulationResultPayload | null): number {
    if (!result?.station_performance) return 0
    return result.station_performance.filter((s) => s.is_bottleneck).length
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
