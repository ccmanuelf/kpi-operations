import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface ShortcutConfig {
  id?: string
  keys?: string[]
  description?: string
  enabled?: boolean
  [key: string]: unknown
}

export interface ShortcutHistoryEntry extends ShortcutConfig {
  id: string
  timestamp: number
}

export interface ShortcutPreferences {
  showTooltips: boolean
  showNotifications: boolean
  enableSounds: boolean
  customizationEnabled: boolean
}

export interface ExportedShortcutConfig {
  enabled: boolean
  customShortcuts: Record<string, ShortcutConfig>
  preferences: ShortcutPreferences
  exportedAt?: string
}

const STORAGE_KEY = 'kpi-keyboard-shortcuts'

const defaultPreferences = (): ShortcutPreferences => ({
  showTooltips: true,
  showNotifications: true,
  enableSounds: false,
  customizationEnabled: false,
})

export const useKeyboardShortcutsStore = defineStore('keyboardShortcuts', () => {
  const enabled = ref(true)
  const customShortcuts = ref<Record<string, ShortcutConfig>>({})
  const shortcutHistory = ref<ShortcutHistoryEntry[]>([])
  const preferences = ref<ShortcutPreferences>(defaultPreferences())

  const isEnabled = computed(() => enabled.value)
  const getPreferences = computed(() => preferences.value)

  const saveToLocalStorage = () => {
    try {
      const data = {
        enabled: enabled.value,
        customShortcuts: customShortcuts.value,
        preferences: preferences.value,
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to save keyboard shortcuts to localStorage:', error)
    }
  }

  const setEnabled = (value: boolean) => {
    enabled.value = value
    saveToLocalStorage()
  }

  const toggleEnabled = () => {
    enabled.value = !enabled.value
    saveToLocalStorage()
  }

  const updatePreferences = (newPrefs: Partial<ShortcutPreferences>) => {
    preferences.value = { ...preferences.value, ...newPrefs }
    saveToLocalStorage()
  }

  const setCustomShortcut = (id: string, config: ShortcutConfig) => {
    customShortcuts.value[id] = config
    saveToLocalStorage()
  }

  const removeCustomShortcut = (id: string) => {
    delete customShortcuts.value[id]
    saveToLocalStorage()
  }

  const getCustomShortcut = (id: string): ShortcutConfig | undefined => {
    return customShortcuts.value[id]
  }

  const addToHistory = (shortcut: ShortcutConfig & { id: string }) => {
    shortcutHistory.value.unshift({
      ...shortcut,
      timestamp: Date.now(),
    })

    if (shortcutHistory.value.length > 100) {
      shortcutHistory.value = shortcutHistory.value.slice(0, 100)
    }
  }

  const clearHistory = () => {
    shortcutHistory.value = []
  }

  const getRecentShortcuts = (limit = 10): ShortcutHistoryEntry[] => {
    return shortcutHistory.value.slice(0, limit)
  }

  const getMostUsedShortcuts = (limit = 10): { id: string; count: number }[] => {
    const counts: Record<string, number> = {}

    shortcutHistory.value.forEach((item) => {
      counts[item.id] = (counts[item.id] || 0) + 1
    })

    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, limit)
      .map(([id, count]) => ({ id, count }))
  }

  const loadFromLocalStorage = () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const data = JSON.parse(stored) as Partial<ExportedShortcutConfig>
        enabled.value = data.enabled ?? true
        customShortcuts.value = data.customShortcuts || {}
        if (data.preferences) {
          preferences.value = { ...preferences.value, ...data.preferences }
        }
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Failed to load keyboard shortcuts from localStorage:', error)
    }
  }

  const resetToDefaults = () => {
    enabled.value = true
    customShortcuts.value = {}
    preferences.value = defaultPreferences()
    clearHistory()
    saveToLocalStorage()
  }

  const exportConfiguration = (): ExportedShortcutConfig => {
    return {
      enabled: enabled.value,
      customShortcuts: customShortcuts.value,
      preferences: preferences.value,
      exportedAt: new Date().toISOString(),
    }
  }

  const importConfiguration = (config: Partial<ExportedShortcutConfig>) => {
    if (config.enabled !== undefined) enabled.value = config.enabled
    if (config.customShortcuts) customShortcuts.value = config.customShortcuts
    if (config.preferences) {
      preferences.value = { ...preferences.value, ...config.preferences }
    }
    saveToLocalStorage()
  }

  loadFromLocalStorage()

  return {
    enabled,
    customShortcuts,
    shortcutHistory,
    preferences,
    isEnabled,
    getPreferences,
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
    importConfiguration,
  }
})
