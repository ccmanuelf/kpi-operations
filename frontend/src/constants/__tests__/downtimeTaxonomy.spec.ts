import { describe, it, expect } from 'vitest'
import {
  DOWNTIME_REASON_CODES,
  DOWNTIME_CATEGORY_CODES,
  DEFAULT_CATEGORY_BY_REASON,
  reasonLabelKey,
  categoryLabelKey,
} from '../downtimeTaxonomy'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'

const resolve = (obj: Record<string, unknown>, key: string) =>
  key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], obj)

describe('downtime taxonomy constants (mirror of backend/orm/downtime_taxonomy.py)', () => {
  it('has 8 reasons and 5 selectable categories (no uncategorized)', () => {
    expect(DOWNTIME_REASON_CODES).toHaveLength(8)
    expect(DOWNTIME_REASON_CODES).toContain('OPERATOR_UNAVAILABLE')
    expect(DOWNTIME_CATEGORY_CODES).toEqual([
      'machine', 'materials', 'scheduling', 'attendance', 'other',
    ])
  })

  it('maps every reason to a selectable category', () => {
    for (const r of DOWNTIME_REASON_CODES) {
      expect(DOWNTIME_CATEGORY_CODES).toContain(DEFAULT_CATEGORY_BY_REASON[r])
    }
    expect(DEFAULT_CATEGORY_BY_REASON['OPERATOR_UNAVAILABLE']).toBe('attendance')
    expect(DEFAULT_CATEGORY_BY_REASON['SETUP_CHANGEOVER']).toBe('scheduling')
  })

  it('every label key resolves in BOTH locales (incl. uncategorized render key)', () => {
    const keys = [
      ...DOWNTIME_REASON_CODES.map(reasonLabelKey),
      ...DOWNTIME_CATEGORY_CODES.map(categoryLabelKey),
      categoryLabelKey('uncategorized'),
    ]
    for (const k of keys) {
      expect(resolve(en, k), `en missing ${k}`).toBeTypeOf('string')
      expect(resolve(es, k), `es missing ${k}`).toBeTypeOf('string')
    }
  })
})
