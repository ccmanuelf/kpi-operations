import { describe, it, expect } from 'vitest'
import {
  DELAY_SUPERVISORY_ROLES,
  canEditDelayClassification,
  isDelaySectionVisible,
  buildDelayClassificationPayload,
} from '../useDelayClassification'

describe('canEditDelayClassification', () => {
  it('allows the supervisory set (admin/poweruser/leader/supervisor)', () => {
    expect(DELAY_SUPERVISORY_ROLES).toEqual(['admin', 'poweruser', 'leader', 'supervisor'])
    for (const role of DELAY_SUPERVISORY_ROLES) {
      expect(canEditDelayClassification(role)).toBe(true)
    }
  })

  it('denies operator/viewer and missing role', () => {
    expect(canEditDelayClassification('operator')).toBe(false)
    expect(canEditDelayClassification('viewer')).toBe(false)
    expect(canEditDelayClassification(null)).toBe(false)
    expect(canEditDelayClassification(undefined)).toBe(false)
  })
})

describe('isDelaySectionVisible', () => {
  it('true only when the row is late', () => {
    expect(isDelaySectionVisible({ is_late: true })).toBe(true)
    expect(isDelaySectionVisible({ is_late: false })).toBe(false)
    expect(isDelaySectionVisible(null)).toBe(false)
    expect(isDelaySectionVisible(undefined)).toBe(false)
    expect(isDelaySectionVisible({})).toBe(false)
  })
})

describe('buildDelayClassificationPayload', () => {
  it('unclassified (null) clears reason and note — explicit null clears server-side', () => {
    expect(
      buildDelayClassificationPayload({ classification: null, reason: 'other', note: 'stale note' }),
    ).toEqual({
      delay_classification: null,
      justified_delay_reason: null,
      delay_classification_note: null,
    })
  })

  it('justified carries the reason and note through', () => {
    expect(
      buildDelayClassificationPayload({
        classification: 'justified',
        reason: 'force_majeure',
        note: 'hurricane',
      }),
    ).toEqual({
      delay_classification: 'justified',
      justified_delay_reason: 'force_majeure',
      delay_classification_note: 'hurricane',
    })
  })

  it('unjustified drops the reason but keeps the note', () => {
    expect(
      buildDelayClassificationPayload({
        classification: 'unjustified',
        reason: 'customer_request',
        note: 'internal scheduling miss',
      }),
    ).toEqual({
      delay_classification: 'unjustified',
      justified_delay_reason: null,
      delay_classification_note: 'internal scheduling miss',
    })
  })

  it('empty-string note normalizes to null (not an empty string)', () => {
    expect(
      buildDelayClassificationPayload({ classification: 'unjustified', reason: null, note: '' }),
    ).toEqual({
      delay_classification: 'unjustified',
      justified_delay_reason: null,
      delay_classification_note: null,
    })
  })
})
