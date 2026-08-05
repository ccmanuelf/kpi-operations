// Mirror of backend/orm/delay_taxonomy.py — keep the two in lockstep.
//
// 3-state model: WorkOrder.delay_classification is NULL (unclassified,
// default), 'justified', or 'unjustified'. Unclassified is the ABSENCE of
// a value — never an enum member, never offered as a selectable code here
// (the UI still needs a label for it: classificationLabelKey('unclassified')
// resolves fine even though 'unclassified' isn't in
// DELAY_CLASSIFICATION_CODES, same as downtimeTaxonomy's uncategorized
// render key). justified_delay_reason is populated only when
// classification === 'justified'.

export const DELAY_CLASSIFICATION_CODES: string[] = ['justified', 'unjustified']

export const JUSTIFIED_DELAY_REASON_CODES: string[] = [
  'customer_request',
  'customer_change_order',
  'material_supplier_delay',
  'force_majeure',
  'upstream_hold',
  'other',
]

const camel = (v: string): string => {
  const parts = v.toLowerCase().split('_')
  return parts[0] + parts.slice(1).map((p) => p[0].toUpperCase() + p.slice(1)).join('')
}

export const classificationLabelKey = (id: string): string => `delay.classifications.${id}`
export const delayReasonLabelKey = (id: string): string => `delay.reasons.${camel(id)}`

export interface DelayBadgeRow {
  is_late?: boolean
  delay_classification?: string | null
}

export interface DelayBadge {
  key: 'unclassified' | 'justified' | 'unjustified'
  color: 'warning' | 'info' | 'error'
}

// null when the order isn't late (nothing to classify); otherwise
// unclassified/justified/unjustified per the 3-state model above.
export const delayBadge = (row: DelayBadgeRow): DelayBadge | null => {
  if (!row.is_late) return null
  if (row.delay_classification === 'justified') return { key: 'justified', color: 'info' }
  if (row.delay_classification === 'unjustified') return { key: 'unjustified', color: 'error' }
  return { key: 'unclassified', color: 'warning' }
}
