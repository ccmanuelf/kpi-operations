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
 * WIP currently on hold, not a windowed time series, so omitting the
 * params expresses the intent directly -- the backend defaults `as_of` to
 * today.
 *
 * HISTORY: this originally omitted the params as a WORKAROUND. The backend
 * (GET /kpi/wip-aging) used to filter by hold_date falling INSIDE
 * start_date/end_date, so a trailing-30-day window silently excluded every
 * hold older than 30 days -- windowing an AGING metric excluded precisely
 * the worst holds. A production DB with 4 chronic holds 60-70 days old
 * showed Avg "--" and Aged-15+ "0" under the inherited 30-day window.
 * That backend semantic is now FIXED (owner ruling 2026-08-07): a windowed
 * call is an as-of snapshot at `end_date`, so passing a window here would
 * no longer drop chronic holds. Omitting the params remains correct for
 * these three cards, which are explicitly as-of-now.
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
