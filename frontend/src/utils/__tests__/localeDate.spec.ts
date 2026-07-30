import { describe, it, expect } from 'vitest'
import { formatLocaleDate } from '../localeDate'

// Observation: AG Grid date columns showed "Jul 17, 2026" under the es
// locale — date-fns' format() defaults to en-US regardless of the active
// i18n locale. formatLocaleDate must thread the app locale through.
describe('formatLocaleDate', () => {
  const date = '2026-07-17T00:00:00'

  it('formats in English month names for locale=en', () => {
    expect(formatLocaleDate(date, 'MMM dd, yyyy', 'en')).toBe('Jul 17, 2026')
  })

  it('formats in Spanish month names for locale=es', () => {
    expect(formatLocaleDate(date, 'MMM dd, yyyy', 'es')).toBe('jul 17, 2026')
  })

  it('falls back to English for an unrecognized locale', () => {
    expect(formatLocaleDate(date, 'MMM dd, yyyy', 'fr')).toBe('Jul 17, 2026')
  })

  it('falls back to English for an undefined locale', () => {
    expect(formatLocaleDate(date, 'MMM dd, yyyy', undefined)).toBe('Jul 17, 2026')
  })

  it('accepts a Date instance directly', () => {
    expect(formatLocaleDate(new Date(date), 'MMM dd, yyyy', 'en')).toBe('Jul 17, 2026')
  })
})
