/**
 * Vue i18n Configuration
 * Internationalization (i18n) setup for English/Spanish language support
 */
import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import es from './locales/es.json'

// Get saved language from localStorage or default to English
const getStoredLanguage = () => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('kpi-platform-language') || 'en'
  }
  return 'en'
}

const i18n = createI18n({
  legacy: false, // Use Composition API mode
  locale: getStoredLanguage(),
  fallbackLocale: 'en',
  messages: {
    en,
    es
  },
  // Enable missing key warnings in development
  missingWarn: process.env.NODE_ENV === 'development',
  fallbackWarn: process.env.NODE_ENV === 'development',
  // Number and date formatting
  numberFormats: {
    en: {
      decimal: { style: 'decimal', minimumFractionDigits: 1, maximumFractionDigits: 2 },
      percent: { style: 'percent', minimumFractionDigits: 1 },
      currency: { style: 'currency', currency: 'USD' }
    },
    es: {
      decimal: { style: 'decimal', minimumFractionDigits: 1, maximumFractionDigits: 2 },
      percent: { style: 'percent', minimumFractionDigits: 1 },
      currency: { style: 'currency', currency: 'MXN' }
    }
  },
  datetimeFormats: {
    en: {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' },
      time: { hour: '2-digit', minute: '2-digit' }
    },
    es: {
      short: { year: 'numeric', month: '2-digit', day: '2-digit' },
      long: { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' },
      time: { hour: '2-digit', minute: '2-digit' }
    }
  }
})

/**
 * Change language and persist to localStorage
 * @param {string} locale - 'en' or 'es'
 */
export const setLanguage = (locale) => {
  i18n.global.locale.value = locale
  if (typeof window !== 'undefined') {
    localStorage.setItem('kpi-platform-language', locale)
    document.documentElement.setAttribute('lang', locale)
  }
}

/**
 * Get current language
 * @returns {string} Current locale
 */
export const getLanguage = () => i18n.global.locale.value

export default i18n
