import { describe, it, expect } from 'vitest'
import {
  formatLocaleDate,
  formatLocaleDateIntl,
  formatLocaleTimeIntl,
  formatLocaleDateTimeIntl,
  getIntlLocaleTag,
} from '../localeDate'

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

// Class extension: native Date.prototype.toLocaleDateString/toLocaleTimeString/
// toLocaleString either hardcoded 'en-US' or omitted a locale (following the
// BROWSER's language instead of the app's selected i18n locale) across ~20
// call sites. These Intl-based wrappers fix the locale while preserving each
// site's existing Intl.DateTimeFormatOptions shape.
describe('getIntlLocaleTag', () => {
  it('maps en -> en-US and es -> es-MX (the app targets the Mexican es market)', () => {
    expect(getIntlLocaleTag('en')).toBe('en-US')
    expect(getIntlLocaleTag('es')).toBe('es-MX')
  })

  it('falls back to en-US for an unrecognized or undefined locale', () => {
    expect(getIntlLocaleTag('fr')).toBe('en-US')
    expect(getIntlLocaleTag(undefined)).toBe('en-US')
  })
})

describe('formatLocaleDateIntl', () => {
  const date = new Date('2026-07-17T14:30:00')

  it('formats with no options using the given locale', () => {
    expect(formatLocaleDateIntl(date, 'en')).toBe('7/17/2026')
    expect(formatLocaleDateIntl(date, 'es')).toBe('17/7/2026')
  })

  it('preserves caller-supplied options (weekday/month/day) while fixing the locale', () => {
    const options: Intl.DateTimeFormatOptions = { weekday: 'short', month: 'short', day: 'numeric' }
    expect(formatLocaleDateIntl(date, 'en', options)).toBe('Fri, Jul 17')
    expect(formatLocaleDateIntl(date, 'es', options)).toBe('vie 17 de jul')
  })
})

describe('formatLocaleTimeIntl', () => {
  const date = new Date('2026-07-17T14:30:00')

  it('formats a time with the given locale', () => {
    const options: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit' }
    expect(formatLocaleTimeIntl(date, 'en', options)).toBe('02:30 PM')
    expect(formatLocaleTimeIntl(date, 'es', options)).toBe('02:30 p.m.')
  })
})

describe('formatLocaleDateTimeIntl', () => {
  const date = new Date('2026-07-17T14:30:00')

  it('formats a combined date+time with the given locale', () => {
    expect(formatLocaleDateTimeIntl(date, 'en')).toBe('7/17/2026, 2:30:00 PM')
    expect(formatLocaleDateTimeIntl(date, 'es')).toBe('17/7/2026, 2:30:00 p.m.')
  })
})
