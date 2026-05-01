/**
 * useDualViewInspector — dashboard click → inspector drawer bridge.
 *
 * Flow:
 *   1. Caller invokes `openForKpi(kpiKey)` from a click handler.
 *   2. We map the KPI key to one of the 3 dual-view services
 *      (`oee`, `onTimeDelivery` → otd, `quality` → fpy) and POST a
 *      `(client_id, period_start, period_end)` tuple to
 *      `/api/metrics/calculate/from-period/{metric}`.
 *   3. The backend aggregates raw inputs from real production data
 *      (ProductionEntry / DowntimeEntry / QualityEntry / WorkOrder),
 *      runs both modes, persists a `METRIC_CALCULATION_RESULT` row,
 *      and returns its `result_id`.
 *   4. We hand `resultId` to the inspector drawer, which fetches the
 *      full lineage via `getMetricLineage`.
 */

import { ref } from 'vue'

import {
  calculateFPYFromPeriod,
  calculateOEEFromPeriod,
  calculateOTDFromPeriod,
} from '@/services/api/dualViewCalc'

export type DualViewCapableKey = 'oee' | 'onTimeDelivery' | 'quality'

export const DUAL_VIEW_CAPABLE_KEYS: ReadonlySet<DualViewCapableKey> = new Set([
  'oee',
  'onTimeDelivery',
  'quality',
])

interface PeriodLike {
  start?: string | Date | null
  end?: string | Date | null
}

const toIso = (value: string | Date | null | undefined): string => {
  if (value instanceof Date) return value.toISOString()
  if (typeof value === 'string' && value) return new Date(value).toISOString()
  return new Date().toISOString()
}

const monthRange = (): { period_start: string; period_end: string } => {
  const now = new Date()
  return {
    period_start: new Date(now.getFullYear(), now.getMonth(), 1).toISOString(),
    period_end: new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59).toISOString(),
  }
}

export function useDualViewInspector(
  getClientId: () => string | null,
  getPeriod?: () => PeriodLike | null
) {
  const open = ref(false)
  const resultId = ref<number | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const close = () => {
    open.value = false
  }

  const resolvePeriod = (): { period_start: string; period_end: string } => {
    const supplied = getPeriod?.()
    if (supplied?.start && supplied?.end) {
      return { period_start: toIso(supplied.start), period_end: toIso(supplied.end) }
    }
    return monthRange()
  }

  const openForKpi = async (kpiKey: string) => {
    if (!DUAL_VIEW_CAPABLE_KEYS.has(kpiKey as DualViewCapableKey)) {
      error.value = `Inspector not available for metric: ${kpiKey}`
      return
    }
    const clientId = getClientId()
    if (!clientId) {
      error.value = 'No client selected'
      return
    }

    loading.value = true
    error.value = null
    try {
      const period = resolvePeriod()
      const body = { client_id: clientId, ...period }
      let response
      switch (kpiKey as DualViewCapableKey) {
        case 'oee':
          response = await calculateOEEFromPeriod(body)
          break
        case 'onTimeDelivery':
          response = await calculateOTDFromPeriod(body)
          break
        case 'quality':
          response = await calculateFPYFromPeriod(body)
          break
      }
      resultId.value = response.data.result_id
      open.value = true
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to open inspector'
    } finally {
      loading.value = false
    }
  }

  return { open, resultId, loading, error, openForKpi, close }
}
