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
  formatValidationDetail,
  isStructuredDetail,
  isValidationDetail,
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

describe('isStructuredDetail rejects shapes that would blank the message', () => {
  it('rejects a present-but-empty member rather than formatting it to nothing', () => {
    // `in` would accept these; formatStructuredDetail then returns '' and the
    // interceptor overwrites a usable detail with an empty string.
    expect(isStructuredDetail({ blocked_by: undefined })).toBe(false)
    expect(isStructuredDetail({ hidden_parents: null })).toBe(false)
    expect(isStructuredDetail({ blocked_by: 'nope' })).toBe(false)
  })

  it('still accepts an empty array, which the message fallback handles', () => {
    expect(isStructuredDetail({ message: 'm', blocked_by: [] })).toBe(true)
    expect(formatStructuredDetail({ message: 'm', blocked_by: [] })).toBe('m')
  })
})

describe('formatValidationDetail — FastAPI\'s own 422', () => {
  // Verbatim from the running app: ten write endpoints probed with bad bodies.
  // `missing` was 39 of the 45 occurrences.
  const MISSING = { type: 'missing', loc: ['body', 'client_id'], msg: 'Field required' }
  const INT_PARSING = {
    type: 'int_parsing',
    loc: ['body', 'planned_quantity'],
    msg: 'Input should be a valid integer, unable to parse string as an integer',
  }
  const PATTERN = {
    type: 'string_pattern_mismatch',
    loc: ['body', 'status'],
    msg: "String should match pattern '^(RECEIVED|RELEASED|DEMOTED|ACTIVE|IN_PROGRESS|ON_HOLD|COMPLETED|SHIPPED|CLOSED|REJECTED|CANCELLED)$'",
    ctx: { pattern: '^(RECEIVED|RELEASED|DEMOTED|ACTIVE|IN_PROGRESS|ON_HOLD|COMPLETED|SHIPPED|CLOSED|REJECTED|CANCELLED)$' },
  }
  const GREATER_THAN = {
    type: 'greater_than',
    loc: ['body', 'planned_quantity'],
    msg: 'Input should be greater than 0',
    ctx: { gt: 0 },
  }
  const TOO_LONG = {
    type: 'string_too_long',
    loc: ['body', 'client_id'],
    msg: 'String should have at most 50 characters',
    ctx: { max_length: 50 },
  }

  it('names the field in human terms and localizes the message', () => {
    expect(formatValidationDetail([MISSING])).toBe('Client: This field is required')
  })

  it('drops the _id suffix rather than saying "Work order id"', () => {
    expect(
      formatValidationDetail([{ ...MISSING, loc: ['body', 'work_order_id'] }]),
    ).toBe('Work order: This field is required')
  })

  it('interpolates the real bound from ctx', () => {
    expect(formatValidationDetail([GREATER_THAN])).toBe('Planned quantity: Must be greater than 0')
    expect(formatValidationDetail([TOO_LONG])).toBe('Client: Maximum 50 characters allowed')
  })

  it('never shows the user a raw regex', () => {
    const out = formatValidationDetail([PATTERN])
    expect(out).toBe('Status: Invalid format')
    expect(out).not.toContain('RECEIVED')
    expect(out).not.toContain('^(')
  })

  it('joins several errors into one sentence', () => {
    expect(formatValidationDetail([MISSING, INT_PARSING])).toBe(
      'Client: This field is required; Planned quantity: Must be a whole number',
    )
  })

  it('falls back to a localized generic for an unmapped type', () => {
    const out = formatValidationDetail([
      { type: 'some_future_pydantic_type', loc: ['body', 'widget'], msg: 'English from Pydantic' },
    ])
    expect(out).toBe('Widget: Invalid value')
    // The English msg must not leak through.
    expect(out).not.toContain('English from Pydantic')
  })

  it('falls back rather than interpolating undefined when ctx is missing', () => {
    // A bounded type whose ctx did not arrive would otherwise render
    // "Must be greater than undefined".
    const out = formatValidationDetail([{ ...GREATER_THAN, ctx: undefined }])
    expect(out).toBe('Planned quantity: Invalid value')
    expect(out).not.toContain('undefined')
  })

  it('labels a nested list item by position', () => {
    expect(
      formatValidationDetail([{ ...MISSING, loc: ['body', 'items', 0, 'quantity'] }]),
    ).toBe('Quantity: This field is required')
  })

  it('renders in Spanish under the es locale', () => {
    i18n.global.locale.value = 'es'
    try {
      expect(formatValidationDetail([MISSING])).toBe('Client: Este campo es requerido')
      expect(formatValidationDetail([PATTERN])).toBe('Status: Formato inválido')
    } finally {
      i18n.global.locale.value = 'en'
    }
  })

  it('recognises the validation shape and rejects our structured one', () => {
    expect(isValidationDetail([MISSING])).toBe(true)
    expect(isValidationDetail([])).toBe(false)
    expect(isValidationDetail({ blocked_by: [] })).toBe(false)
    expect(isValidationDetail('a string')).toBe(false)
    expect(isValidationDetail([{ nope: 1 }])).toBe(false)
  })
})

describe('ENTITY_LABEL_KEYS', () => {
  // Exactly the tables the backend can put in front of a user, computed from
  // its own registry rather than guessed:
  //   blocked_by      -> INDEPENDENT children of a deleted row: DOWNTIME_ENTRY,
  //                      HOLD_ENTRY, JOB, PRODUCTION_ENTRY, QUALITY_ENTRY
  //   hidden_parents  -> any of the 12 AUTO_FILTERED_TABLES
  // The union is the 12 below; the blockers are all themselves auto-filtered.
  // The four cascade children (ALERT_HISTORY, ATTENDANCE_HOUR_ALLOCATION,
  // HOLD_STATUS_TRANSITION, WORKFLOW_TRANSITION_LOG) are deliberately absent:
  // they are OWNED/DERIVED, so they are hidden WITH their parent instead of
  // blocking it, and they are not parents anything can attach to. Labelling
  // them would imply a message no user can receive.
  // vitest cannot read the backend registry, so this list is the seam: a table
  // added to AUTO_FILTERED_TABLES must be added here and given a label.
  const BACKEND_TABLES = [
    'ALERT', 'ATTENDANCE_ENTRY', 'DEFECT_DETAIL', 'DOWNTIME_ENTRY',
    'FLOATING_POOL', 'HOLD_ENTRY', 'JOB', 'PART_OPPORTUNITIES',
    'PRODUCTION_ENTRY', 'QUALITY_ENTRY', 'SHIFT_COVERAGE', 'WORK_ORDER',
  ]

  it('covers every table the backend can name in a blocked_by or hidden_parents', () => {
    const missing = BACKEND_TABLES.filter((t) => !(t in ENTITY_LABEL_KEYS))
    expect(missing).toEqual([])
  })

  it('resolves in both bundles with BOTH plural halves non-empty', () => {
    // toContain('|') was not enough: "Alert |" contains a pipe and passes, while
    // entityLabel('ALERT', 3) then renders the empty string, producing
    // "... still reference it:  (3)." Both halves have to actually be there.
    for (const key of Object.values(ENTITY_LABEL_KEYS)) {
      for (const [name, bundle] of [['en', en], ['es', es]] as const) {
        const value = resolve(bundle as Record<string, unknown>, key)
        expect(typeof value, `${name}:${key}`).toBe('string')
        const halves = String(value).split('|').map((h) => h.trim())
        expect(halves, `${name}:${key}`).toHaveLength(2)
        expect(halves.every((h) => h.length > 0), `${name}:${key} has an empty form`).toBe(true)
      }
    }
  })

  it('is actually translated — no Spanish label is a copy of its English one', () => {
    // The parity gate only proves a key EXISTS in both bundles. An untranslated
    // label passes it and ships English to an es user.
    const untranslated = Object.values(ENTITY_LABEL_KEYS).filter(
      (key) =>
        resolve(es as Record<string, unknown>, key) === resolve(en as Record<string, unknown>, key),
    )
    expect(untranslated).toEqual([])
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
