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
 * frontend/src/services/api/kpi.ts) -- no store required.
 *
 * Calls getWIPAging() with NO date params. These cards ("Avg Days on
 * Hold", "Oldest Item", "Count Aged 15+") are an as-of-now snapshot of
 * WIP currently on hold, not a windowed time series. Live-VM finding: the
 * backend (GET /kpi/wip-aging) filters by hold_date falling INSIDE
 * start_date/end_date -- so a trailing-30-day window silently excludes
 * every hold older than 30 days, i.e. windowing an AGING metric excludes
 * precisely the worst holds. A production DB with 4 chronic holds
 * 60-70 days old showed Avg "--" and Aged-15+ "0" under the inherited
 * 30-day window, while the unwindowed endpoint correctly returned
 * {"total_held_quantity":4,"average_aging_days":64.5,"aging_over_30_days":4}.
 * Do not reintroduce a date window here without also fixing that
 * semantic on the backend/store side (tracked separately).
 */
import { ref } from 'vue'
import { getWIPAging } from '@/services/api/kpi'

export interface WipTriadData {
  average_days: number | null
  max_days: number | null
  age_15_plus: number | null
  [key: string]: unknown
}

export function useWipTriadData() {
  const wipData = ref<WipTriadData | null>(null)
  const loading = ref(false)

  // Named `load`, not `fetch` -- `fetch` shadows the global fetch API and
  // reads as a suspicious rebind at both the definition and every call
  // site that destructures it.
  async function load(): Promise<void> {
    loading.value = true
    try {
      const { data } = await getWIPAging()
      wipData.value = data as WipTriadData
    } finally {
      loading.value = false
    }
  }

  return { wipData, loading, load }
}
