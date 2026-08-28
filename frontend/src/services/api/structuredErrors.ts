/**
 * Structured delete/reference errors — the backend's machine-readable
 * `detail` objects turned into one localized sentence.
 *
 * Two endpoints refuse a delete with 409 `{message, blocked_by}` and the
 * hidden-parent write guard refuses a write with 422 `{message,
 * hidden_parents}`. ~40 call sites read `error.response.data.detail` typed as
 * a string, so an object `detail` is truthy, skips their `|| fallback`, and
 * renders `[object Object]`. Rewriting the object into a finished sentence in
 * the single axios response interceptor fixes all of them at once.
 */
import i18n from '@/i18n'

export interface BlockedByEntry {
  table: string
  count: number
}

export interface HiddenParentEntry {
  table: string
  id: string | number
}

export interface StructuredDetail {
  message?: string
  blocked_by?: BlockedByEntry[]
  hidden_parents?: HiddenParentEntry[]
}

export interface BlockedByRow extends BlockedByEntry {
  label: string
}

// Literal (non-template-literal) i18n keys, following the BUCKET_LABEL_KEYS
// idiom in composables/pivotPresets.ts: a template-literal key like
// `errors.entities.${table}` evades the referenced-keys i18n gate, which can
// only statically verify literal key strings.
//
// The gate genuinely sees these only because review found it did not: its regex
// excluded a preceding dot, so `i18n.global.t(...)` — the idiom every
// non-component call site here uses, pivotPresets.ts included — matched nothing.
// Widening it (referenced-keys.spec.ts) brought 51 keys under verification.
//
// Covers every table the backend can name: `blocked_by` is limited to the
// INDEPENDENT children of WORK_ORDER and JOB, but `hidden_parents` can name
// any auto-filtered parent.
export const ENTITY_LABEL_KEYS: Record<string, string> = {
  ALERT: 'errors.entities.alert',
  ATTENDANCE_ENTRY: 'errors.entities.attendanceEntry',
  DEFECT_DETAIL: 'errors.entities.defectDetail',
  DOWNTIME_ENTRY: 'errors.entities.downtimeEntry',
  FLOATING_POOL: 'errors.entities.floatingPool',
  HOLD_ENTRY: 'errors.entities.holdEntry',
  JOB: 'errors.entities.job',
  PART_OPPORTUNITIES: 'errors.entities.partOpportunities',
  PRODUCTION_ENTRY: 'errors.entities.productionEntry',
  QUALITY_ENTRY: 'errors.entities.qualityEntry',
  SHIFT_COVERAGE: 'errors.entities.shiftCoverage',
  WORK_ORDER: 'errors.entities.workOrder',
}

/**
 * True only for our two payloads. FastAPI's own validation errors are ALSO
 * HTTP 422 but carry `detail` as a LIST of `{type, loc, msg, input}` — a guard
 * testing only `typeof detail === 'object'` would replace every validation
 * message in the application with our text, so arrays are rejected and one of
 * the two structured members is required.
 */
export const isStructuredDetail = (detail: unknown): detail is StructuredDetail =>
  typeof detail === 'object' &&
  detail !== null &&
  !Array.isArray(detail) &&
  ('blocked_by' in detail || 'hidden_parents' in detail)

/** Friendly label, falling back to the raw table name so an entity the
 *  backend gains before this map does still reads as something. `count`
 *  selects the plural form. Table names arrive uppercase except the
 *  `shift_coverage` outlier. */
export const entityLabel = (table: string, count: number): string => {
  const key = ENTITY_LABEL_KEYS[table.toUpperCase()]
  return key ? i18n.global.t(key, count) : table
}

/** One localized sentence. Empty arrays fall back to the backend's own
 *  English `message` rather than announcing an empty list. */
export const formatStructuredDetail = (detail: StructuredDetail): string => {
  if (detail.blocked_by?.length) {
    const blockers = detail.blocked_by
      .map((entry) => `${entityLabel(entry.table, entry.count)} (${entry.count})`)
      .join(', ')
    return i18n.global.t('errors.deleteBlocked', { blockers })
  }
  if (detail.hidden_parents?.length) {
    const parents = detail.hidden_parents
      .map((entry) => `${entityLabel(entry.table, 1)} ${entry.id}`)
      .join(', ')
    return i18n.global.t('errors.hiddenParent', { parents })
  }
  return detail.message ?? ''
}

/** Per-blocker rows for surfaces that can host markup (the work-order delete
 *  dialog), where the flattened sentence loses the one-line-per-entity shape. */
export const blockedByRows = (detail: StructuredDetail | undefined): BlockedByRow[] =>
  (detail?.blocked_by ?? []).map((entry) => ({
    ...entry,
    label: entityLabel(entry.table, entry.count),
  }))

interface StructuredErrorCarrier {
  response?: { data?: { detail?: unknown } }
  structuredDetail?: StructuredDetail
}

/**
 * Rewrite `error.response.data.detail` in place, keeping the original object
 * on the error itself: the sentence is what the string-typed extractors
 * render, but a dialog that wants one row per blocker cannot un-flatten it.
 */
export const normalizeStructuredDetail = (error: unknown): void => {
  const carrier = error as StructuredErrorCarrier | null
  const data = carrier?.response?.data
  if (!carrier || !data || !isStructuredDetail(data.detail)) return
  carrier.structuredDetail = data.detail
  data.detail = formatStructuredDetail(data.detail)
}

export const getStructuredDetail = (error: unknown): StructuredDetail | undefined =>
  (error as StructuredErrorCarrier | null)?.structuredDetail
