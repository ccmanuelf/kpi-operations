import { describe, it, expect } from 'vitest'
import {
  DELAY_CLASSIFICATION_CODES,
  JUSTIFIED_DELAY_REASON_CODES,
  classificationLabelKey,
  delayReasonLabelKey,
  delayBadge,
} from '../delayTaxonomy'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'

const resolve = (obj: Record<string, unknown>, key: string) =>
  key.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], obj)

describe('delay taxonomy constants (mirror of backend/orm/delay_taxonomy.py)', () => {
  it('has 2 classifications and 6 justified reasons', () => {
    expect(DELAY_CLASSIFICATION_CODES).toHaveLength(2)
    expect(DELAY_CLASSIFICATION_CODES).toEqual(['justified', 'unjustified'])
    expect(JUSTIFIED_DELAY_REASON_CODES).toHaveLength(6)
    expect(JUSTIFIED_DELAY_REASON_CODES).toContain('upstream_hold')
  })

  it('every label key resolves in BOTH locales (incl. delay.classifications.unclassified used by the badge)', () => {
    const keys = [
      ...DELAY_CLASSIFICATION_CODES.map(classificationLabelKey),
      ...JUSTIFIED_DELAY_REASON_CODES.map(delayReasonLabelKey),
      classificationLabelKey('unclassified'),
    ]
    for (const k of keys) {
      expect(resolve(en, k), `en missing ${k}`).toBeTypeOf('string')
      expect(resolve(es, k), `es missing ${k}`).toBeTypeOf('string')
    }
  })

  it('camelCases multi-word reason codes for the label key', () => {
    expect(delayReasonLabelKey('customer_change_order')).toBe('delay.reasons.customerChangeOrder')
    expect(delayReasonLabelKey('material_supplier_delay')).toBe('delay.reasons.materialSupplierDelay')
    expect(delayReasonLabelKey('other')).toBe('delay.reasons.other')
  })

  it('delayBadge: null when the order is not late', () => {
    expect(delayBadge({ is_late: false, delay_classification: null })).toBeNull()
    expect(delayBadge({ is_late: false, delay_classification: 'justified' })).toBeNull()
    expect(delayBadge({ is_late: undefined, delay_classification: null })).toBeNull()
  })

  it('delayBadge: late + null classification -> unclassified/warning', () => {
    expect(delayBadge({ is_late: true, delay_classification: null })).toEqual({
      key: 'unclassified',
      color: 'warning',
    })
    expect(delayBadge({ is_late: true })).toEqual({ key: 'unclassified', color: 'warning' })
  })

  it('delayBadge: late + justified -> justified/info', () => {
    expect(delayBadge({ is_late: true, delay_classification: 'justified' })).toEqual({
      key: 'justified',
      color: 'info',
    })
  })

  it('delayBadge: late + unjustified -> unjustified/error', () => {
    expect(delayBadge({ is_late: true, delay_classification: 'unjustified' })).toEqual({
      key: 'unjustified',
      color: 'error',
    })
  })
})
