import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'kpi-theme'

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(false)

  const toggleTheme = () => {
    isDark.value = !isDark.value
    saveToLocalStorage()
  }

  const saveToLocalStorage = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ isDark: isDark.value }))
    } catch (error) {
      console.error('Failed to save theme to localStorage:', error)
    }
  }

  const loadFromLocalStorage = () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const data = JSON.parse(stored)
        isDark.value = data.isDark === true
      }
    } catch {
      // Corrupt JSON — reset to default light
      isDark.value = false
    }
  }

  // Initialize
  loadFromLocalStorage()

  // Sync across browser tabs
  if (typeof window !== 'undefined') {
    window.addEventListener('storage', (e) => {
      if (e.key === STORAGE_KEY && e.newValue) {
        try {
          isDark.value = JSON.parse(e.newValue).isDark === true
        } catch {
          // ignore corrupt cross-tab data
        }
      }
    })
  }

  return {
    isDark,
    toggleTheme,
    loadFromLocalStorage
  }
})
