import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * Keyboard shortcuts store
 * Manages global state for keyboard shortcuts system
 */
export const useKeyboardShortcutsStore = defineStore('keyboardShortcuts', () => {
  // State
  const enabled = ref(true)
  const customShortcuts = ref({})
  const shortcutHistory = ref([])
  const preferences = ref({
    showTooltips: true,
    showNotifications: true,
    enableSounds: false,
    customizationEnabled: false
  })

  // Getters
  const isEnabled = computed(() => enabled.value)
  const getPreferences = computed(() => preferences.value)

  /**
   * Enable/disable all shortcuts
   */
  const setEnabled = (value) => {
    enabled.value = value
    saveToLocalStorage()
  }

  /**
   * Toggle shortcuts on/off
   */
  const toggleEnabled = () => {
    enabled.value = !enabled.value
    saveToLocalStorage()
  }

  /**
   * Update preferences
   */
  const updatePreferences = (newPrefs) => {
    preferences.value = { ...preferences.value, ...newPrefs }
    saveToLocalStorage()
  }

  /**
   * Set custom shortcut
   */
  const setCustomShortcut = (id, config) => {
    customShortcuts.value[id] = config
    saveToLocalStorage()
  }

  /**
   * Remove custom shortcut
   */
  const removeCustomShortcut = (id) => {
    delete customShortcuts.value[id]
    saveToLocalStorage()
  }

  /**
   * Get custom shortcut
   */
  const getCustomShortcut = (id) => {
    return customShortcuts.value[id]
  }

  /**
   * Add to history
   */
  const addToHistory = (shortcut) => {
    shortcutHistory.value.unshift({
      ...shortcut,
      timestamp: Date.now()
    })

    // Keep only last 100 items
    if (shortcutHistory.value.length > 100) {
      shortcutHistory.value = shortcutHistory.value.slice(0, 100)
    }
  }

  /**
   * Clear history
   */
  const clearHistory = () => {
    shortcutHistory.value = []
  }

  /**
   * Get recent shortcuts
   */
  const getRecentShortcuts = (limit = 10) => {
    return shortcutHistory.value.slice(0, limit)
  }

  /**
   * Get most used shortcuts
   */
  const getMostUsedShortcuts = (limit = 10) => {
    const counts = {}

    shortcutHistory.value.forEach(item => {
      counts[item.id] = (counts[item.id] || 0) + 1
    })

    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, limit)
      .map(([id, count]) => ({ id, count }))
  }

  /**
   * Save to localStorage
   */
  const saveToLocalStorage = () => {
    try {
      const data = {
        enabled: enabled.value,
        customShortcuts: customShortcuts.value,
        preferences: preferences.value
      }
      localStorage.setItem('kpi-keyboard-shortcuts', JSON.stringify(data))
    } catch (error) {
      console.error('Failed to save keyboard shortcuts to localStorage:', error)
    }
  }

  /**
   * Load from localStorage
   */
  const loadFromLocalStorage = () => {
    try {
      const stored = localStorage.getItem('kpi-keyboard-shortcuts')
      if (stored) {
        const data = JSON.parse(stored)
        enabled.value = data.enabled ?? true
        customShortcuts.value = data.customShortcuts || {}
        preferences.value = { ...preferences.value, ...data.preferences }
      }
    } catch (error) {
      console.error('Failed to load keyboard shortcuts from localStorage:', error)
    }
  }

  /**
   * Reset to defaults
   */
  const resetToDefaults = () => {
    enabled.value = true
    customShortcuts.value = {}
    preferences.value = {
      showTooltips: true,
      showNotifications: true,
      enableSounds: false,
      customizationEnabled: false
    }
    clearHistory()
    saveToLocalStorage()
  }

  /**
   * Export configuration
   */
  const exportConfiguration = () => {
    return {
      enabled: enabled.value,
      customShortcuts: customShortcuts.value,
      preferences: preferences.value,
      exportedAt: new Date().toISOString()
    }
  }

  /**
   * Import configuration
   */
  const importConfiguration = (config) => {
    if (config.enabled !== undefined) enabled.value = config.enabled
    if (config.customShortcuts) customShortcuts.value = config.customShortcuts
    if (config.preferences) preferences.value = { ...preferences.value, ...config.preferences }
    saveToLocalStorage()
  }

  // Initialize from localStorage
  loadFromLocalStorage()

  return {
    // State
    enabled,
    customShortcuts,
    shortcutHistory,
    preferences,

    // Getters
    isEnabled,
    getPreferences,

    // Actions
    setEnabled,
    toggleEnabled,
    updatePreferences,
    setCustomShortcut,
    removeCustomShortcut,
    getCustomShortcut,
    addToHistory,
    clearHistory,
    getRecentShortcuts,
    getMostUsedShortcuts,
    saveToLocalStorage,
    loadFromLocalStorage,
    resetToDefaults,
    exportConfiguration,
    importConfiguration
  }
})
