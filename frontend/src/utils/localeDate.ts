/**
 * Locale-aware date formatting shared by AG Grid `valueFormatter` callbacks.
 *
 * `date-fns`'s `format()` defaults to the `en-US` locale regardless of the
 * app's active i18n locale, so grid date columns kept showing "Jul 17,
 * 2026" even under the Spanish UI (sweep observation: ES dates). Threading
 * the active locale through here keeps month names/order in sync with
 * `vue-i18n`'s current locale.
 */
import { format, type Locale as DateFnsLocale } from 'date-fns'
import { enUS, es } from 'date-fns/locale'
import type { Locale as AppLocale } from '@/i18n'

const DATE_FNS_LOCALES: Record<AppLocale, DateFnsLocale> = { en: enUS, es }

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
