/**
 * The live payload, verbatim.
 *
 * Captured 2026-08-28 from the deployed VM through Caddy:
 *   POST https://192.168.2.234/api/work-orders
 *   {"work_order_id": 1, "planned_quantity": "abc", "status": "NOPE"}
 *
 * Five errors of four types in one response — including the pattern mismatch
 * whose Pydantic message is a raw regex. This is what the formatter is for, so
 * it is asserted against the real thing rather than a hand-written fixture.
 */
import { describe, it, expect } from 'vitest'
import i18n from '@/i18n'
import { formatValidationDetail, type ValidationEntry } from '../structuredErrors'

const LIVE: ValidationEntry[] = [
  { type: 'string_type', loc: ['body', 'work_order_id'], msg: 'Input should be a valid string' },
  { type: 'missing', loc: ['body', 'client_id'], msg: 'Field required' },
  { type: 'missing', loc: ['body', 'style_model'], msg: 'Field required' },
  {
    type: 'int_parsing',
    loc: ['body', 'planned_quantity'],
    msg: 'Input should be a valid integer, unable to parse string as an integer',
  },
  {
    type: 'string_pattern_mismatch',
    loc: ['body', 'status'],
    msg: "String should match pattern '^(RECEIVED|RELEASED|DEMOTED|ACTIVE|IN_PROGRESS|ON_HOLD|COMPLETED|SHIPPED|CLOSED|REJECTED|CANCELLED)$'",
    ctx: { pattern: '^(RECEIVED|RELEASED|DEMOTED|ACTIVE|IN_PROGRESS|ON_HOLD|COMPLETED|SHIPPED|CLOSED|REJECTED|CANCELLED)$' },
  },
]

describe('the live production validation payload', () => {
  it('renders every error as readable English', () => {
    expect(formatValidationDetail(LIVE)).toBe(
      'Work order: Must be text; ' +
        'Client: This field is required; ' +
        'Style model: This field is required; ' +
        'Planned quantity: Must be a whole number; ' +
        'Status: Invalid format',
    )
  })

  it('leaks neither the regex nor any Pydantic internals', () => {
    const out = formatValidationDetail(LIVE)
    for (const leak of ['RECEIVED', 'IN_PROGRESS', '^(', 'Input should be', 'pattern', 'unable to parse']) {
      expect(out, `leaked: ${leak}`).not.toContain(leak)
    }
  })

  it('renders the same payload in Spanish', () => {
    i18n.global.locale.value = 'es'
    try {
      const out = formatValidationDetail(LIVE)
      expect(out).toContain('Este campo es requerido')
      expect(out).toContain('Formato inválido')
      expect(out).not.toContain('This field is required')
    } finally {
      i18n.global.locale.value = 'en'
    }
  })
})
