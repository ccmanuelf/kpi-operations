/** All Summaries view logic lives here (not in <script setup>) so it is
 * unit-testable — the VTU-can't-reach-script-setup lesson. */
import { ref, type Ref } from 'vue'
import api from '@/services/api/client'
import { useCSVExport } from '@/composables/useCSVExport'
import {
  DATASET_GROUPINGS, type PivotColumn, type PivotViewPreset,
} from '@/composables/pivotPresets'

export type PivotRow = Record<string, unknown> & { bucket_start: string; group_key: string | null }

function iso(d: Date): string { return d.toISOString().slice(0, 10) }

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
  const startDate = ref(iso(start))
  const endDate = ref(iso(end))
  const clientId: Ref<string | null> = ref(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const rows = ref<PivotRow[]>([])
  const totals = ref<Record<string, unknown>>({})
  const { downloading, downloadCSVByPath } = useCSVExport()

  function paramsFor(dataset: string): Record<string, unknown> {
    const p: Record<string, unknown> = {
      bucket: bucket.value, start_date: startDate.value, end_date: endDate.value,
    }
    // A grouping the dataset doesn't support falls back to time-only for
    // that dataset; its rows then merge on bucket_start alone.
    if (groupBy.value && (DATASET_GROUPINGS[dataset] ?? []).includes(groupBy.value)) {
      p.group_by = groupBy.value
    }
    if (clientId.value) p.client_id = clientId.value
    return p
  }

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      let merged: PivotRow[] = []
      let mergedTotals: Record<string, unknown> = {}
      for (const ds of preset.datasets) {
        const { data } = await api.get(`/pivot/${ds}`, { params: paramsFor(ds) })
        merged = merged.length ? mergePivotRows(merged, data.rows) : data.rows
        mergedTotals = { ...mergedTotals, ...data.totals }
      }
      rows.value = merged
      totals.value = mergedTotals
    } catch (e) {
      const ax = e as { response?: { data?: { detail?: unknown } }; message?: string }
      error.value = String(ax?.response?.data?.detail ?? ax?.message ?? 'load failed')
    } finally {
      loading.value = false
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
