/**
 * Pure helpers backing AllocationEditorDialog.vue — row add/remove and
 * client-side validation mirroring backend/calculations/labor_hours.py::
 * validate_allocations (duplicate category, hours <= 0, total allocated
 * hours > actual_hours). Kept separate from constants/laborTaxonomy.ts
 * (a lean mirror of the backend enum module) per the script-setup testing
 * convention: AllocationEditorDialog.vue is a plain <script setup> SFC, so
 * its logic lives here where it's directly unit-testable.
 *
 * Note on the server rule: allocated total must not EXCEED actual_hours —
 * it need not equal it. Unallocated remainder defaults to
 * productive-unbilled server-side (see available_for_efficiency_hours),
 * so under-allocating is valid; only over-allocating is blocked.
 */

export interface AllocationRow {
  category: string | null
  hours: number | null
}

export const emptyAllocationRow = (): AllocationRow => ({ category: null, hours: null })

export const addAllocationRow = (rows: AllocationRow[]): AllocationRow[] => [
  ...rows,
  emptyAllocationRow(),
]

export const removeAllocationRow = (rows: AllocationRow[], index: number): AllocationRow[] =>
  rows.filter((_, i) => i !== index)

// Sum of hours across rows that have both a category and positive hours
// (mid-entry blank rows don't count toward the total).
export const allocatedTotal = (rows: AllocationRow[]): number =>
  rows.reduce(
    (sum, r) => sum + (r.category && typeof r.hours === 'number' && r.hours > 0 ? r.hours : 0),
    0,
  )

export const hasDuplicateCategories = (rows: AllocationRow[]): boolean => {
  const seen = new Set<string>()
  for (const row of rows) {
    if (!row.category) continue
    if (seen.has(row.category)) return true
    seen.add(row.category)
  }
  return false
}

// A row with a category chosen but no positive hours is invalid (mirrors
// the server's `hours <= 0` rejection); a fully-blank trailing row is not
// flagged — it's simply dropped by toAllocationItems on save.
export const hasInvalidHours = (rows: AllocationRow[]): boolean =>
  rows.some((r) => r.category && (typeof r.hours !== 'number' || r.hours <= 0))

export const exceedsActualHours = (
  rows: AllocationRow[],
  actualHours: number | null | undefined,
): boolean => allocatedTotal(rows) > (actualHours ?? 0)

export interface AllocationValidation {
  valid: boolean
  duplicateCategory: boolean
  invalidHours: boolean
  exceedsActual: boolean
}

export const validateAllocations = (
  rows: AllocationRow[],
  actualHours: number | null | undefined,
): AllocationValidation => {
  const duplicateCategory = hasDuplicateCategories(rows)
  const invalidHours = hasInvalidHours(rows)
  const exceedsActual = exceedsActualHours(rows, actualHours)
  return {
    valid: !duplicateCategory && !invalidHours && !exceedsActual,
    duplicateCategory,
    invalidHours,
    exceedsActual,
  }
}

// Backs the i18n `labor.allocatedSummary` ("{allocated} / {actual} h") template.
export const allocationSummary = (
  rows: AllocationRow[],
  actualHours: number | null | undefined,
): { allocated: number; actual: number } => ({
  allocated: allocatedTotal(rows),
  actual: actualHours ?? 0,
})

export interface AllocationItemPayload {
  category: string
  hours: number
}

// Storage is Numeric(5,2) and the backend schema now rejects >2dp payloads
// (decimal_places=2). The hours input here is a free-typed <input type="number">
// with no browser-enforced precision, so round to 2dp on the way out — matching
// what the server will accept — rather than letting a >2dp value 422 at submit.
const roundToTwoDp = (value: number): number => Math.round((value + Number.EPSILON) * 100) / 100

// Rows ready to submit: category selected + hours > 0 (drops blank/incomplete rows).
export const toAllocationItems = (rows: AllocationRow[]): AllocationItemPayload[] =>
  rows
    .filter((r) => Boolean(r.category) && typeof r.hours === 'number' && (r.hours as number) > 0)
    .map((r) => ({ category: r.category as string, hours: roundToTwoDp(r.hours as number) }))

// Seeds the editor's rows from a saved allocations list (or a single blank
// row when there's nothing saved yet, so the dialog always has an editable row).
export const allocationRowsFromItems = (
  items: AllocationItemPayload[] | undefined | null,
): AllocationRow[] =>
  items && items.length > 0
    ? items.map((i) => ({ category: i.category, hours: i.hours }))
    : [emptyAllocationRow()]
