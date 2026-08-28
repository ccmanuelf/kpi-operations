/**
 * Unit tests for the structured 409/422 detail formatter.
 *
 * Resolves against the REAL en/es bundles (no identity-`t` mock): the point of
 * these assertions is that the shipped translations exist and read correctly,
 * which an identity mock would hide.
 */
import { describe, it, expect, afterEach } from 'vitest'
import i18n from '@/i18n'
import en from '@/i18n/locales/en.json'
import es from '@/i18n/locales/es.json'
import {
  ENTITY_LABEL_KEYS,
  blockedByRows,
  entityLabel,
  formatStructuredDetail,
  isStructuredDetail,
} from '../structuredErrors'

// Verbatim from the deployed backend (409 on DELETE /api/work-orders/{id}).
const BLOCKED_DETAIL = {
  message:
    "Cannot delete this WORK_ORDER record while other records still reference it. Delete or reassign them first: DOWNTIME_ENTRY (1), JOB (1), PRODUCTION_ENTRY (4), QUALITY_ENTRY (4).",
  blocked_by: [
    { table: 'DOWNTIME_ENTRY', count: 1 },
    { table: 'JOB', count: 1 },
    { table: 'PRODUCTION_ENTRY', count: 4 },
    { table: 'QUALITY_ENTRY', count: 4 },
  ],
}

// Verbatim from the deployed backend (422 on a write attaching to a hidden parent).
const HIDDEN_PARENT_DETAIL = {
  message:
    'Cannot reference a deleted record: WORK_ORDER WO-0002. The referenced record has been deleted and is no longer available.',
  hidden_parents: [{ table: 'WORK_ORDER', id: 'WO-0002' }],
}

// FastAPI's own validation errors are ALSO 422, with `detail` as a LIST.
const PYDANTIC_DETAIL = [
  { type: 'missing', loc: ['body', 'work_order_id'], msg: 'Field required', input: {} },
]

const resolve = (bundle: Record<string, unknown>, path: string): unknown =>
  path
    .split('.')
    .reduce<unknown>((acc, k) => (acc && typeof acc === 'object' ? (acc as Record<string, unknown>)[k] : undefined), bundle)

describe('isStructuredDetail', () => {
  it('accepts both backend payloads', () => {
    expect(isStructuredDetail(BLOCKED_DETAIL)).toBe(true)
    expect(isStructuredDetail(HIDDEN_PARENT_DETAIL)).toBe(true)
  })

  it('rejects a FastAPI validation array', () => {
    expect(isStructuredDetail(PYDANTIC_DETAIL)).toBe(false)
  })

  it('rejects a string detail, null, and a bare message object', () => {
    expect(isStructuredDetail('Work order not found')).toBe(false)
    expect(isStructuredDetail(null)).toBe(false)
    expect(isStructuredDetail({ message: 'something went wrong' })).toBe(false)
  })
})

describe('formatStructuredDetail — 409 blocked_by', () => {
  it('formats a single blocker', () => {
    expect(formatStructuredDetail({ blocked_by: [{ table: 'JOB', count: 1 }] })).toBe(
      'Cannot delete this record — other records still reference it: Job (1). Delete or reassign them first.',
    )
  })

  it('comma-joins every blocker in order', () => {
    expect(formatStructuredDetail(BLOCKED_DETAIL)).toBe(
      'Cannot delete this record — other records still reference it: ' +
        'Downtime entry (1), Job (1), Production entries (4), Quality entries (4). ' +
        'Delete or reassign them first.',
    )
  })

  it('picks the singular form at count 1 and the plural above it', () => {
    expect(entityLabel('PRODUCTION_ENTRY', 1)).toBe('Production entry')
    expect(entityLabel('PRODUCTION_ENTRY', 4)).toBe('Production entries')
  })

  it('falls back to the raw table name for an unmapped table', () => {
    expect(formatStructuredDetail({ blocked_by: [{ table: 'MYSTERY_TABLE', count: 2 }] })).toBe(
      'Cannot delete this record — other records still reference it: MYSTERY_TABLE (2). ' +
        'Delete or reassign them first.',
    )
  })

  it('falls back to the backend message when the list is empty', () => {
    expect(formatStructuredDetail({ message: 'Nothing blocks it.', blocked_by: [] })).toBe(
      'Nothing blocks it.',
    )
  })
})

describe('formatStructuredDetail — 422 hidden_parents', () => {
  it('renders "label id" per entry', () => {
    expect(formatStructuredDetail(HIDDEN_PARENT_DETAIL)).toBe(
      'Cannot reference a deleted record: Work order WO-0002. ' +
        'It has been deleted and is no longer available.',
    )
  })

  it('normalizes the lowercase shift_coverage table name', () => {
    expect(formatStructuredDetail({ hidden_parents: [{ table: 'shift_coverage', id: 3 }] })).toBe(
      'Cannot reference a deleted record: Shift coverage record 3. ' +
        'It has been deleted and is no longer available.',
    )
  })
})

describe('locale', () => {
  afterEach(() => {
    i18n.global.locale.value = 'en'
  })

  it('returns Spanish with no English leak when the locale is es', () => {
    i18n.global.locale.value = 'es'
    expect(formatStructuredDetail(HIDDEN_PARENT_DETAIL)).toBe(
      'No se puede referenciar un registro eliminado: Orden de Trabajo WO-0002. ' +
        'Fue eliminado y ya no está disponible.',
    )
    expect(formatStructuredDetail({ blocked_by: [{ table: 'HOLD_ENTRY', count: 3 }] })).toBe(
      'No se puede eliminar este registro — otros registros aún lo referencian: Retenciones (3). ' +
        'Elimínalos o reasígnalos primero.',
    )
  })
})

describe('ENTITY_LABEL_KEYS', () => {
  it('resolves in both bundles with both plural forms present', () => {
    for (const key of Object.values(ENTITY_LABEL_KEYS)) {
      for (const bundle of [en, es]) {
        const value = resolve(bundle as Record<string, unknown>, key)
        expect(typeof value, key).toBe('string')
        // A dropped plural form would silently make every count render the
        // singular; the pipe is what vue-i18n splits on.
        expect(String(value), key).toContain('|')
      }
    }
  })
})

describe('blockedByRows', () => {
  it('yields one localized row per blocker', () => {
    expect(blockedByRows(BLOCKED_DETAIL)).toEqual([
      { table: 'DOWNTIME_ENTRY', count: 1, label: 'Downtime entry' },
      { table: 'JOB', count: 1, label: 'Job' },
      { table: 'PRODUCTION_ENTRY', count: 4, label: 'Production entries' },
      { table: 'QUALITY_ENTRY', count: 4, label: 'Quality entries' },
    ])
  })

  it('is empty for a payload with no blockers', () => {
    expect(blockedByRows(undefined)).toEqual([])
    expect(blockedByRows(HIDDEN_PARENT_DETAIL)).toEqual([])
  })
})
