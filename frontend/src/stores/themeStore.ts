import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'kpi-theme'

interface StoredTheme {
  isDark?: boolean
}

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(false)

  const saveToLocalStorage = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ isDark: isDark.value }))
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to save theme to localStorage:', error)
    }
  }

  const toggleTheme = () => {
    isDark.value = !isDark.value
    saveToLocalStorage()
  }

  const loadFromLocalStorage = () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const data = JSON.parse(stored) as StoredTheme
        isDark.value = data.isDark === true
      }
    } catch {
      isDark.value = false
    }
  }

  loadFromLocalStorage()

  if (typeof window !== 'undefined') {
    window.addEventListener('storage', (e) => {
      if (e.key === STORAGE_KEY && e.newValue) {
        try {
          const parsed = JSON.parse(e.newValue) as StoredTheme
          isDark.value = parsed.isDark === true
        } catch {
          // ignore corrupt cross-tab data
        }
      }
    })
  }

  return {
    isDark,
    toggleTheme,
    loadFromLocalStorage,
  }
})
