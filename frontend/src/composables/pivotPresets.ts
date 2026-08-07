/** Declarative presets for the five Summaries views (spec §6). The backend
 * registry (backend/pivot/registry.py) is the authority for datasets,
 * group_by allow-lists, and measure keys — these presets must reference
 * only keys that exist there. */
import { JUSTIFIED_DELAY_REASON_CODES, delayReasonLabelKey } from '@/constants/delayTaxonomy'

export interface PivotColumn {
  key: string
  headerKey: string
  kind: 'number' | 'percent' | 'count'
  // Groupings under which this column is structurally meaningless and must
  // be hidden (e.g. a per-reason OTD% — spec §6, see the q3 comment below).
  hideForGroupings?: string[]
}
export interface PivotGrouping { value: string | null; labelKey: string }
export interface PivotViewPreset {
  id: 'q1' | 'q2' | 'q3' | 'q4' | 'q5'
  titleKey: string
  datasets: string[]
  groupings: PivotGrouping[]
  columns: PivotColumn[]
  showWipTriad?: boolean
}

export const VALID_BUCKETS = ['week', 'month', 'quarter', 'year'] as const

// Literal (non-template-literal) i18n keys for bucket labels — a template-literal
// key like `pivot.buckets.${b}` evades the referenced-keys i18n gate, which can
// only statically verify literal key strings.
export const BUCKET_LABEL_KEYS: Record<(typeof VALID_BUCKETS)[number], string> = {
  week: 'pivot.buckets.week',
  month: 'pivot.buckets.month',
  quarter: 'pivot.buckets.quarter',
  year: 'pivot.buckets.year',
}

const timeOnly: PivotGrouping = { value: null, labelKey: 'pivot.grouping.timeOnly' }
const byClient: PivotGrouping = { value: 'client', labelKey: 'pivot.grouping.client' }

export const PIVOT_VIEWS: PivotViewPreset[] = [
  {
    // Q1: the cross-metric hours-basis view — production + labor merged per bucket.
    // Groupings limited to the intersection both datasets support (time-only, client).
    id: 'q1',
    titleKey: 'pivot.views.q1',
    datasets: ['production', 'labor'],
    groupings: [timeOnly, byClient],
    columns: [
      { key: 'units', headerKey: 'pivot.cols.units', kind: 'count' },
      { key: 'earned_hours', headerKey: 'pivot.cols.earnedHours', kind: 'number' },
      { key: 'run_hours', headerKey: 'pivot.cols.runHours', kind: 'number' },
      { key: 'actual', headerKey: 'pivot.cols.attendanceHours', kind: 'number' },
      { key: 'operators', headerKey: 'pivot.cols.operators', kind: 'count' },
      { key: 'normal', headerKey: 'pivot.cols.otNormal', kind: 'number' },
      { key: 'double', headerKey: 'pivot.cols.otDouble', kind: 'number' },
      { key: 'triple', headerKey: 'pivot.cols.otTriple', kind: 'number' },
      { key: 'billed', headerKey: 'pivot.cols.billed', kind: 'number' },
      { key: 'available_for_efficiency', headerKey: 'pivot.cols.available', kind: 'number' },
      { key: 'efficiency_available_basis', headerKey: 'pivot.cols.efficiency', kind: 'percent' },
    ],
  },
  {
    id: 'q2',
    titleKey: 'pivot.views.q2',
    datasets: ['downtime'],
    groupings: [
      timeOnly, byClient,
      { value: 'category', labelKey: 'pivot.grouping.category' },
      { value: 'reason', labelKey: 'pivot.grouping.reason' },
      { value: 'line', labelKey: 'pivot.grouping.line' },
    ],
    columns: [
      { key: 'downtime_hours', headerKey: 'pivot.cols.downtimeHours', kind: 'number' },
      { key: 'events', headerKey: 'pivot.cols.events', kind: 'count' },
      { key: 'share_of_window_pct', headerKey: 'pivot.cols.share', kind: 'percent' },
    ],
  },
  {
    // Q3: quality + delivery merged. delay_reason grouping shows LATE COUNTS
    // by reason — never a per-reason OTD% (spec §6; on-time orders all land
    // in the "none" bucket, making per-reason OTD% structurally meaningless).
    id: 'q3',
    titleKey: 'pivot.views.q3',
    datasets: ['quality', 'delivery'],
    groupings: [
      timeOnly, byClient,
      { value: 'style', labelKey: 'pivot.grouping.style' },
      { value: 'delay_reason', labelKey: 'pivot.grouping.delayReason' },
    ],
    columns: [
      // inspected/defects/fpy_pct are QUALITY measures -- delay_reason is a
      // DELIVERY-side grouping, so every reason row renders these as bare
      // "—" noise (quality entries carry no delay reason). Hidden under
      // delay_reason for the same structural reason otd_gross_pct/
      // otd_net_pct are below; delivered/on_time/justified_late stay since
      // those ARE meaningful per delay reason.
      { key: 'inspected', headerKey: 'pivot.cols.inspected', kind: 'count', hideForGroupings: ['delay_reason'] },
      { key: 'defects', headerKey: 'pivot.cols.defects', kind: 'count', hideForGroupings: ['delay_reason'] },
      { key: 'fpy_pct', headerKey: 'pivot.cols.fpy', kind: 'percent', hideForGroupings: ['delay_reason'] },
      { key: 'delivered', headerKey: 'pivot.cols.delivered', kind: 'count' },
      { key: 'on_time', headerKey: 'pivot.cols.onTime', kind: 'count' },
      { key: 'justified_late', headerKey: 'pivot.cols.justifiedLate', kind: 'count' },
      { key: 'otd_gross_pct', headerKey: 'pivot.cols.otdGross', kind: 'percent', hideForGroupings: ['delay_reason'] },
      { key: 'otd_net_pct', headerKey: 'pivot.cols.otdNet', kind: 'percent', hideForGroupings: ['delay_reason'] },
    ],
  },
  {
    // Q4 ships rendering what the engine serves today (downtime lens);
    // PR-C's transitions dataset + correlation block light it up fully.
    id: 'q4',
    titleKey: 'pivot.views.q4',
    datasets: ['downtime'],
    groupings: [timeOnly, byClient, { value: 'line', labelKey: 'pivot.grouping.line' }],
    columns: [
      { key: 'downtime_hours', headerKey: 'pivot.cols.downtimeHours', kind: 'number' },
      { key: 'events', headerKey: 'pivot.cols.events', kind: 'count' },
    ],
  },
  {
    id: 'q5',
    titleKey: 'pivot.views.q5',
    datasets: ['holds'],
    showWipTriad: true,
    groupings: [
      timeOnly, byClient,
      { value: 'reason_category', labelKey: 'pivot.grouping.holdCategory' },
      { value: 'reason', labelKey: 'pivot.grouping.holdReason' },
    ],
    columns: [
      { key: 'holds', headerKey: 'pivot.cols.holds', kind: 'count' },
      { key: 'hold_days', headerKey: 'pivot.cols.holdDays', kind: 'number' },
      { key: 'avg_days_per_hold', headerKey: 'pivot.cols.avgDaysPerHold', kind: 'number' },
    ],
  },
]

export const DATASET_GROUPINGS: Record<string, string[]> = {
  production: ['client', 'line', 'product'],
  labor: ['client', 'labor_class'],
  downtime: ['client', 'category', 'reason', 'line'],
  quality: ['client', 'style'],
  delivery: ['client', 'style', 'delay_reason'],
  holds: ['client', 'reason_category', 'reason'],
}

/** Pure: the preset's columns minus any whose `hideForGroupings` includes
 * the current grouping. Exported so the panel's columnDefs can stay a thin
 * consumer and this filtering rule is independently unit-testable. */
export function visibleColumns(preset: PivotViewPreset, groupBy: string | null): PivotColumn[] {
  return preset.columns.filter((c) => !groupBy || !c.hideForGroupings?.includes(groupBy))
}

// Backend group-by sentinels (backend/pivot/hooks.py + registry.py + engine.py
// coalesce nulls into these literal strings) mapped to i18n keys so the grid
// never renders a raw English sentinel to a Spanish-locale user.
const GROUP_SENTINEL_KEYS: Record<string, string> = {
  none: 'pivot.sentinels.none',
  uncategorized: 'pivot.sentinels.uncategorized',
  unknown: 'pivot.sentinels.unknown',
  unclassified: 'pivot.sentinels.unclassified',
}

/** Pure: renders a group_key cell value — null stays an em dash, a known
 * sentinel is localized, a delay-reason group value maps to its existing
 * `delay.reasons.*` i18n label (the WO delay-classification drawer already
 * defines these — see constants/delayTaxonomy.ts; reused here rather than
 * duplicated), and any other value renders as-is. `groupBy` is optional so
 * existing (non-grouping-aware) callers keep working unchanged. */
export function groupLabel(
  value: unknown,
  t: (_key: string) => string,
  groupBy?: string | null,
): string {
  if (value === null || value === undefined) return '—'
  const s = String(value)
  if (groupBy === 'delay_reason' && JUSTIFIED_DELAY_REASON_CODES.includes(s)) {
    return t(delayReasonLabelKey(s))
  }
  const key = GROUP_SENTINEL_KEYS[s]
  return key ? t(key) : s
}
