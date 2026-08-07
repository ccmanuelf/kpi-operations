/** All Summaries view logic lives here (not in <script setup>) so it is
 * unit-testable — the VTU-can't-reach-script-setup lesson. */
import { ref, type Ref } from 'vue'
import api from '@/services/api/client'
import { useCSVExport } from '@/composables/useCSVExport'
import { localISO } from '@/utils/localeDate'
import {
  DATASET_GROUPINGS, type PivotColumn, type PivotViewPreset,
} from '@/composables/pivotPresets'

export type PivotRow = Record<string, unknown> & { bucket_start: string; group_key: string | null }

/** Last-write-wins on colliding (bucket_start, group_key) keys: `secondary`
 * overwrites any measure `primary` already carries for that key. Safe ONLY
 * because colliding keys must be value-equal by construction -- Q1 merges
 * production then labor (preset.datasets = ['production', 'labor']), and
 * both datasets derive earned_hours/excluded_entries from the SAME mirrored
 * formula (backend/pivot/hooks.py::fetch_labor mirrors
 * backend/calculations/labor_hours.py::earned_hours verbatim -- see
 * test_hooks_golden.py), so labor's value landing last (it's fetched after
 * production in Q1) is equivalent to production's, not a silent overwrite
 * with different data. If a future preset ever merges two datasets whose
 * colliding keys carry DIFFERENT semantics under the same measure name,
 * this function will silently pick the last one -- audit before adding such
 * a preset. */
export function mergePivotRows(primary: PivotRow[], secondary: PivotRow[]): PivotRow[] {
  const byKey = new Map<string, PivotRow>()
  for (const r of primary) byKey.set(`${r.bucket_start}|${r.group_key}`, { ...r })
  for (const r of secondary) {
    const k = `${r.bucket_start}|${r.group_key}`
    const existing = byKey.get(k)
    if (existing) Object.assign(existing, r)
    else byKey.set(k, { ...r })
  }
  return [...byKey.values()].sort((a, b) =>
    a.bucket_start === b.bucket_start
      ? String(a.group_key).localeCompare(String(b.group_key))
      : a.bucket_start.localeCompare(b.bucket_start))
}

export function displayValue(row: Record<string, unknown>, col: PivotColumn): string {
  const v = row[col.key]
  if (v === null || v === undefined) return '—'  // null AND absent (spec §5 asymmetry)
  const n = Number(v)
  if (col.kind === 'percent') return `${n.toFixed(2)}%`
  if (col.kind === 'count') return String(Math.round(n))
  return n.toFixed(2)
}

export function usePivotView(preset: PivotViewPreset) {
  const bucket = ref<string>('month')
  const groupBy = ref<string | null>(null)
  const end = new Date()
  const start = new Date(end.getTime() - 90 * 24 * 3600 * 1000)
  const startDate = ref(localISO(start))
  const endDate = ref(localISO(end))
  const clientId: Ref<string | null> = ref(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const rows = ref<PivotRow[]>([])
  const totals = ref<Record<string, unknown>>({})
  const { downloading, downloadCSVByPath } = useCSVExport()
  // Monotonic request-token guard: refresh() is re-triggered on every
  // selector change (bucket/groupBy/date), so a slow earlier request can
  // resolve AFTER a faster later one and overwrite the newer selection's
  // rows with stale data. Each call captures its own token; only the call
  // that still owns the latest token is allowed to commit state.
  let requestSeq = 0

  // Whether `dataset` supports the currently-selected grouping at all
  // (i.e. it's in that dataset's DATASET_GROUPINGS allow-list). Shared by
  // refresh() (which SKIPS a non-supporting dataset entirely -- see below)
  // and paramsFor() (which download() still calls for every dataset
  // regardless, since each dataset's CSV is its own file).
  function datasetSupportsActiveGrouping(dataset: string): boolean {
    return !groupBy.value || (DATASET_GROUPINGS[dataset] ?? []).includes(groupBy.value)
  }

  function paramsFor(dataset: string): Record<string, unknown> {
    const p: Record<string, unknown> = {
      bucket: bucket.value, start_date: startDate.value, end_date: endDate.value,
    }
    // Only relevant to callers that still fetch a non-supporting dataset
    // (download() -- see below). refresh() never reaches here for a
    // non-supporting dataset; it skips the dataset before calling
    // paramsFor at all. When it IS reached for a non-supporting dataset
    // (download's per-dataset CSV export), no group_by param is sent, so
    // that dataset's CSV is time-only rather than 422ing on an
    // unsupported group_by value.
    if (groupBy.value && datasetSupportsActiveGrouping(dataset)) {
      p.group_by = groupBy.value
    }
    if (clientId.value) p.client_id = clientId.value
    return p
  }

  async function refresh(): Promise<void> {
    const token = ++requestSeq
    loading.value = true
    error.value = null
    try {
      let merged: PivotRow[] = []
      let mergedTotals: Record<string, unknown> = {}
      for (const ds of preset.datasets) {
        // A grouping this dataset doesn't support at all means every one of
        // its columns is hidden by hideForGroupings anyway (pivotPresets.ts
        // -- e.g. Q3's quality columns under delay_reason), so a time-only
        // fallback row would render as a pure-noise all-blank row per
        // bucket. SKIP the dataset entirely instead -- saves the request
        // too -- rather than fetching it only to hide everything it
        // returned.
        if (!datasetSupportsActiveGrouping(ds)) continue
        const { data } = await api.get(`/pivot/${ds}`, { params: paramsFor(ds) })
        merged = merged.length ? mergePivotRows(merged, data.rows) : data.rows
        mergedTotals = { ...mergedTotals, ...data.totals }
      }
      // A newer refresh() may have started (and possibly already finished)
      // while this one was in flight -- discard this stale response instead
      // of overwriting the state a later selection already produced.
      if (token !== requestSeq) return
      rows.value = merged
      totals.value = mergedTotals
    } catch (e) {
      if (token !== requestSeq) return
      const ax = e as { response?: { data?: { detail?: unknown } }; message?: string }
      error.value = String(ax?.response?.data?.detail ?? ax?.message ?? 'load failed')
    } finally {
      if (token === requestSeq) loading.value = false
    }
  }

  async function download(): Promise<void> {
    // One CSV per dataset of the view — each grid slice is downloadable as
    // its own underlying data (data-first position; composite views issue
    // one file per dataset).
    for (const ds of preset.datasets) {
      await downloadCSVByPath(`/pivot/${ds}/csv`, paramsFor(ds),
        `pivot_${ds}_${bucket.value}_${startDate.value}_${endDate.value}.csv`)
    }
  }

  return {
    bucket, groupBy, startDate, endDate, clientId, loading, error, rows, totals, downloading, refresh, download,
  }
}
