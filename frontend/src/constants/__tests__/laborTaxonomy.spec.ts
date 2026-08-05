import { describe, it, expect } from 'vitest'
import {
  LABOR_CLASS_CODES,
  HOUR_CATEGORY_CODES,
  BILLABLE_CATEGORIES,
  PRODUCTIVE_CATEGORIES,
  laborClassLabelKey,
  hourCategoryLabelKey,
} from '../laborTaxonomy'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'

const resolve = (obj: Record<string, unknown>, key: string) =>
  key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], obj)

describe('labor taxonomy constants (mirror of backend/orm/labor_taxonomy.py)', () => {
  it('has 2 labor classes and 8 hour categories, in backend declaration order', () => {
    expect(LABOR_CLASS_CODES).toEqual(['direct', 'indirect'])
    expect(HOUR_CATEGORY_CODES).toEqual([
      'billed_production',
      'unbilled_production',
      'training',
      'meeting',
      'idle_wait',
      'other_nonproductive',
      'paid_leave',
      'medical',
    ])
  })

  it('billable/productive sets mirror the backend frozensets', () => {
    expect([...BILLABLE_CATEGORIES]).toEqual(['billed_production'])
    expect([...PRODUCTIVE_CATEGORIES]).toEqual(['billed_production', 'unbilled_production'])
    for (const c of BILLABLE_CATEGORIES) {
      expect(PRODUCTIVE_CATEGORIES.has(c)).toBe(true)
    }
  })

  it('every label key resolves in BOTH locales (incl. unclassified render key)', () => {
    const keys = [
      ...LABOR_CLASS_CODES.map(laborClassLabelKey),
      ...HOUR_CATEGORY_CODES.map(hourCategoryLabelKey),
      'labor.unclassified',
    ]
    for (const k of keys) {
      expect(resolve(en, k), `en missing ${k}`).toBeTypeOf('string')
      expect(resolve(es, k), `es missing ${k}`).toBeTypeOf('string')
    }
  })

  it('camelCases multi-word category codes for the label key', () => {
    expect(hourCategoryLabelKey('billed_production')).toBe('labor.categories.billedProduction')
    expect(hourCategoryLabelKey('idle_wait')).toBe('labor.categories.idleWait')
    expect(hourCategoryLabelKey('other_nonproductive')).toBe('labor.categories.otherNonproductive')
    expect(hourCategoryLabelKey('medical')).toBe('labor.categories.medical')
    expect(laborClassLabelKey('direct')).toBe('labor.classes.direct')
  })
})
