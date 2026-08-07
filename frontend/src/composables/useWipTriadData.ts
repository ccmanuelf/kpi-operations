/**
 * Narrow, store-free WIP-aging fetch for WipTriadBlock's three headline
 * cards (spec §6 Q5).
 *
 * Deliberately does NOT go through useWIPAgingData().initialize() -- that
 * mutates the SHARED kpi store's dateRange to its own 30-day default and
 * fires extra fetches (getClients, hold history) this block never renders,
 * silently repointing every other KPI screen's date range the moment the
 * Summaries tab opens (review finding). getWIPAging() already composes
 * GET /kpi/wip-aging + GET /kpi/wip-aging/top into exactly the
 * {average_days, max_days, age_15_plus} shape these three cards need (see
 * frontend/src/services/api/kpi.ts) -- no store required. The default
 * window mirrors useWIPAgingData's own default (last 30 days), so this
 * fetch path change doesn't alter what the cards display.
 */
import { ref } from 'vue'
import { getWIPAging } from '@/services/api/kpi'
import { localISO } from '@/composables/usePivotView'

export interface WipTriadData {
  average_days: number | null
  max_days: number | null
  age_15_plus: number | null
  [key: string]: unknown
}

export function useWipTriadData() {
  const wipData = ref<WipTriadData | null>(null)
  const loading = ref(false)

  async function fetch(): Promise<void> {
    loading.value = true
    try {
      const end = new Date()
      const start = new Date(end.getTime() - 30 * 24 * 3600 * 1000)
      const { data } = await getWIPAging({ start_date: localISO(start), end_date: localISO(end) })
      wipData.value = data as WipTriadData
    } finally {
      loading.value = false
    }
  }

  return { wipData, loading, fetch }
}
