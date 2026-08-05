// Mirror of backend/orm/labor_taxonomy.py — keep the two in lockstep.
//
// Third sibling of downtimeTaxonomy.ts / delayTaxonomy.ts — same conventions.
// LABOR_CLASS_CODES: employee-level default + per-entry override (NULL =
// unclassified, never an enum member — same "absence of a value" pattern as
// delayTaxonomy's unclassified). HOUR_CATEGORY_CODES: 8-category intra-day
// allocation ledger, in backend declaration order. BILLABLE/PRODUCTIVE are
// static classification sets mirroring the backend frozensets.

export const LABOR_CLASS_CODES: string[] = ['direct', 'indirect']

export const HOUR_CATEGORY_CODES: string[] = [
  'billed_production',
  'unbilled_production',
  'training',
  'meeting',
  'idle_wait',
  'other_nonproductive',
  'paid_leave',
  'medical',
]

export const BILLABLE_CATEGORIES: Set<string> = new Set(['billed_production'])

export const PRODUCTIVE_CATEGORIES: Set<string> = new Set([
  'billed_production',
  'unbilled_production',
])

const camel = (v: string): string => {
  const parts = v.toLowerCase().split('_')
  return parts[0] + parts.slice(1).map((p) => p[0].toUpperCase() + p.slice(1)).join('')
}

export const laborClassLabelKey = (id: string): string => `labor.classes.${id}`
export const hourCategoryLabelKey = (id: string): string => `labor.categories.${camel(id)}`
