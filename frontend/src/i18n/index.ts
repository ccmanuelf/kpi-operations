import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import es from './locales/es.json'

export type Locale = 'en' | 'es'

const STORAGE_KEY = 'kpi-platform-language'

const isLocale = (v: string | null): v is Locale => v === 'en' || v === 'es'

const getStoredLanguage = (): Locale => {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem(STORAGE_KEY)
    return isLocale(stored) ? stored : 'en'
  }
  return 'en'
}

const i18n = createI18n({
  legacy: false,
  locale: getStoredLanguage(),
  fallbackLocale: 'en',
  messages: {
    en,
    es,
  },
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
  numberFormats: {
    en: {
      decimal: { style: 'decimal', minimumFractionDigits: 1, maximumFractionDigits: 2 },
      percent: { style: 'percent', minimumFractionDigits: 1 },
      currency: { style: 'currency', currency: 'USD' },
    },
    es: {
      decimal: { style: 'decimal', minimumFractionDigits: 1, maximumFractionDigits: 2 },
      percent: { style: 'percent', minimumFractionDigits: 1 },
      currency: { style: 'currency', currency: 'MXN' },
    },
  },
  datetimeFormats: {
    en: {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' },
      time: { hour: '2-digit', minute: '2-digit' },
    },
    es: {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' },
      time: { hour: '2-digit', minute: '2-digit' },
    },
  },
})

export const setLanguage = (locale: Locale): void => {
  i18n.global.locale.value = locale
  if (typeof window !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, locale)
    document.documentElement.setAttribute('lang', locale)
  }
}

export const getLanguage = (): Locale => i18n.global.locale.value as Locale

export default i18n
