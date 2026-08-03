// Mirror of backend/orm/downtime_taxonomy.py — keep the two in lockstep.
// The reference endpoint (GET /api/downtime-reasons) serves the same
// data at runtime for store-driven consumers; this module exists for
// grid/editor code paths that must not depend on a fetch having completed.

export const DOWNTIME_REASON_CODES: string[] = [
  'EQUIPMENT_FAILURE',
  'MATERIAL_SHORTAGE',
  'SETUP_CHANGEOVER',
  'QUALITY_HOLD',
  'MAINTENANCE',
  'POWER_OUTAGE',
  'OPERATOR_UNAVAILABLE',
  'OTHER',
]

export const DOWNTIME_CATEGORY_CODES: string[] = [
  'machine',
  'materials',
  'scheduling',
  'attendance',
  'other',
]

export const DEFAULT_CATEGORY_BY_REASON: Record<string, string> = {
  EQUIPMENT_FAILURE: 'machine',
  MAINTENANCE: 'machine',
  MATERIAL_SHORTAGE: 'materials',
  SETUP_CHANGEOVER: 'scheduling',
  OPERATOR_UNAVAILABLE: 'attendance',
  QUALITY_HOLD: 'other',
  POWER_OUTAGE: 'other',
  OTHER: 'other',
}

const camel = (v: string): string => {
  const parts = v.toLowerCase().split('_')
  return parts[0] + parts.slice(1).map((p) => p[0].toUpperCase() + p.slice(1)).join('')
}

export const reasonLabelKey = (id: string): string => `taxonomy.reasons.${camel(id)}`
export const categoryLabelKey = (id: string): string => `taxonomy.categories.${id}`
