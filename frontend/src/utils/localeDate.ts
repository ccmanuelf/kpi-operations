/**
 * Locale-aware date/time formatting shared by AG Grid `valueFormatter`
 * callbacks and any other date-display call site in the app.
 *
 * Two independent bugs share this fix: `date-fns`'s `format()` defaults to
 * the `en-US` locale regardless of the app's active i18n locale (grid date
 * columns kept showing "Jul 17, 2026" under the Spanish UI), and native
 * `Date.prototype.toLocaleDateString()`/`toLocaleTimeString()`/
 * `toLocaleString()` either hardcoded `'en-US'` or omitted a locale
 * argument entirely (falling back to the *browser's* language instead of
 * the app's selected locale). Both wrappers below thread the active
 * `vue-i18n` locale through so every date/time render stays in sync with
 * it, whichever underlying API a given call site uses.
 */
import { format, type Locale as DateFnsLocale } from 'date-fns'
import { enUS, es } from 'date-fns/locale'
import type { Locale as AppLocale } from '@/i18n'

const DATE_FNS_LOCALES: Record<AppLocale, DateFnsLocale> = { en: enUS, es }

// Mexico is this app's Spanish-locale market (see numberFormats.es.currency
// = 'MXN' in src/i18n/index.ts) — es-MX, not es-ES, is the consistent Intl
// tag choice for the same locale.
const INTL_LOCALE_TAGS: Record<AppLocale, string> = { en: 'en-US', es: 'es-MX' }

/**
 * Resolve an app locale ('en' | 'es') to its date-fns `Locale` object.
 * Falls back to `en` for any unrecognized value. Exported so callers that
 * need a raw date-fns function (e.g. `formatDistanceToNow`) beyond the
 * `format()` wrapper below can stay locale-consistent too.
 */
export function getDateFnsLocale(locale: AppLocale | string | undefined): DateFnsLocale {
  return DATE_FNS_LOCALES[locale as AppLocale] ?? enUS
}

/**
 * Resolve an app locale ('en' | 'es') to an Intl/BCP-47 locale tag. Falls
 * back to `en-US` for any unrecognized value.
 */
export function getIntlLocaleTag(locale: AppLocale | string | undefined): string {
  return INTL_LOCALE_TAGS[locale as AppLocale] ?? INTL_LOCALE_TAGS.en
}

/**
 * Format a date using the given app locale ('en' | 'es'). Falls back to
 * `en` for any unrecognized locale value so a bad/missing locale never
 * throws — it degrades to the previous (English) behavior instead.
 */
export function formatLocaleDate(
  date: Date | number | string,
  pattern: string,
  locale: AppLocale | string | undefined,
): string {
  return format(new Date(date), pattern, { locale: getDateFnsLocale(locale) })
}

/**
 * Locale-aware drop-in replacements for the native `Date.prototype`
 * `toLocaleDateString`/`toLocaleTimeString`/`toLocaleString`. Preserve the
 * same `Intl.DateTimeFormatOptions` shape each call site already used
 * (weekday/month/day granularity, etc.) — only the locale tag is fixed, so
 * output shape at each call site is unchanged beyond month/day-name
 * language and ordering.
 */
export function formatLocaleDateIntl(
  date: Date | number | string,
  locale: AppLocale | string | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  return new Date(date).toLocaleDateString(getIntlLocaleTag(locale), options)
}

export function formatLocaleTimeIntl(
  date: Date | number | string,
  locale: AppLocale | string | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  return new Date(date).toLocaleTimeString(getIntlLocaleTag(locale), options)
}

export function formatLocaleDateTimeIntl(
  date: Date | number | string,
  locale: AppLocale | string | undefined,
  options?: Intl.DateTimeFormatOptions,
): string {
  return new Date(date).toLocaleString(getIntlLocaleTag(locale), options)
}
