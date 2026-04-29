/**
 * Unit tests for Keyboard Shortcuts Store
 * Phase 8: Increase test coverage
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useKeyboardShortcutsStore } from '../keyboardShortcutsStore'

// Mock localStorage
const localStorageMock = {
  store: {},
  getItem: vi.fn((key) => localStorageMock.store[key] || null),
  setItem: vi.fn((key, value) => { localStorageMock.store[key] = value }),
  removeItem: vi.fn((key) => { delete localStorageMock.store[key] }),
  clear: vi.fn(() => { localStorageMock.store = {} })
}

describe('Keyboard Shortcuts Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorageMock.clear()
    vi.stubGlobal('localStorage', localStorageMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('Initial State', () => {
    it('has shortcuts enabled by default', () => {
      const store = useKeyboardShortcutsStore()

      expect(store.enabled).toBe(true)
      expect(store.isEnabled).toBe(true)
    })

    it('has default preferences', () => {
      const store = useKeyboardShortcutsStore()

      expect(store.preferences.showTooltips).toBe(true)
      expect(store.preferences.showNotifications).toBe(true)
      expect(store.preferences.enableSounds).toBe(false)
      expect(store.preferences.customizationEnabled).toBe(false)
    })

    it('starts with empty custom shortcuts', () => {
      const store = useKeyboardShortcutsStore()

      expect(store.customShortcuts).toEqual({})
    })

    it('starts with empty history', () => {
      const store = useKeyboardShortcutsStore()

      expect(store.shortcutHistory).toEqual([])
    })
  })

  describe('Enable/Disable', () => {
    it('sets enabled state', () => {
      const store = useKeyboardShortcutsStore()

      store.setEnabled(false)

      expect(store.enabled).toBe(false)
      expect(store.isEnabled).toBe(false)
    })

    it('toggles enabled state', () => {
      const store = useKeyboardShortcutsStore()

      expect(store.enabled).toBe(true)
      store.toggleEnabled()
      expect(store.enabled).toBe(false)
      store.toggleEnabled()
      expect(store.enabled).toBe(true)
    })

    it('saves to localStorage when toggling', () => {
      const store = useKeyboardShortcutsStore()

      store.toggleEnabled()

      expect(localStorageMock.setItem).toHaveBeenCalled()
    })
  })

  describe('Preferences', () => {
    it('updates preferences', () => {
      const store = useKeyboardShortcutsStore()

      store.updatePreferences({ showTooltips: false })

      expect(store.preferences.showTooltips).toBe(false)
      expect(store.preferences.showNotifications).toBe(true) // Unchanged
    })

    it('merges new preferences with existing', () => {
      const store = useKeyboardShortcutsStore()

      store.updatePreferences({ enableSounds: true, customizationEnabled: true })

      expect(store.preferences.enableSounds).toBe(true)
      expect(store.preferences.customizationEnabled).toBe(true)
      expect(store.preferences.showTooltips).toBe(true) // Original value
    })

    it('returns preferences via getter', () => {
      const store = useKeyboardShortcutsStore()

      const prefs = store.getPreferences

      expect(prefs).toEqual(store.preferences)
    })
  })

  describe('Custom Shortcuts', () => {
    it('sets custom shortcut', () => {
      const store = useKeyboardShortcutsStore()

      store.setCustomShortcut('my-shortcut', { keys: ['ctrl', 'k'], action: 'search' })

      expect(store.customShortcuts['my-shortcut']).toEqual({
        keys: ['ctrl', 'k'],
        action: 'search'
      })
    })

    it('removes custom shortcut', () => {
      const store = useKeyboardShortcutsStore()
      store.setCustomShortcut('temp-shortcut', { keys: ['ctrl', 't'] })

      store.removeCustomShortcut('temp-shortcut')

      expect(store.customShortcuts['temp-shortcut']).toBeUndefined()
    })

    it('gets custom shortcut', () => {
      const store = useKeyboardShortcutsStore()
      store.setCustomShortcut('test', { keys: ['ctrl', 'x'] })

      const result = store.getCustomShortcut('test')

      expect(result).toEqual({ keys: ['ctrl', 'x'] })
    })

    it('returns undefined for non-existent shortcut', () => {
      const store = useKeyboardShortcutsStore()

      const result = store.getCustomShortcut('non-existent')

      expect(result).toBeUndefined()
    })
  })

  describe('History', () => {
    it('adds to history', () => {
      const store = useKeyboardShortcutsStore()

      store.addToHistory({ id: 'shortcut-1', action: 'navigate' })

      expect(store.shortcutHistory).toHaveLength(1)
      expect(store.shortcutHistory[0].id).toBe('shortcut-1')
      expect(store.shortcutHistory[0].timestamp).toBeDefined()
    })

    it('adds new items to beginning of history', () => {
      const store = useKeyboardShortcutsStore()

      store.addToHistory({ id: 'first' })
      store.addToHistory({ id: 'second' })

      expect(store.shortcutHistory[0].id).toBe('second')
      expect(store.shortcutHistory[1].id).toBe('first')
    })

    it('limits history to 100 items', () => {
      const store = useKeyboardShortcutsStore()

      for (let i = 0; i < 110; i++) {
        store.addToHistory({ id: `shortcut-${i}` })
      }

      expect(store.shortcutHistory).toHaveLength(100)
      expect(store.shortcutHistory[0].id).toBe('shortcut-109')
    })

    it('clears history', () => {
      const store = useKeyboardShortcutsStore()
      store.addToHistory({ id: 'test-1' })
      store.addToHistory({ id: 'test-2' })

      store.clearHistory()

      expect(store.shortcutHistory).toHaveLength(0)
    })

    it('gets recent shortcuts', () => {
      const store = useKeyboardShortcutsStore()
      for (let i = 0; i < 20; i++) {
        store.addToHistory({ id: `shortcut-${i}` })
      }

      const recent = store.getRecentShortcuts(5)

      expect(recent).toHaveLength(5)
      expect(recent[0].id).toBe('shortcut-19')
    })

    it('gets most used shortcuts', () => {
      const store = useKeyboardShortcutsStore()
      store.addToHistory({ id: 'common' })
      store.addToHistory({ id: 'common' })
      store.addToHistory({ id: 'common' })
      store.addToHistory({ id: 'rare' })

      const mostUsed = store.getMostUsedShortcuts(2)

      expect(mostUsed[0].id).toBe('common')
      expect(mostUsed[0].count).toBe(3)
    })
  })

  describe('localStorage Persistence', () => {
    it('saves to localStorage', () => {
      const store = useKeyboardShortcutsStore()

      store.setEnabled(false)

      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'kpi-keyboard-shortcuts',
        expect.any(String)
      )
    })

    it('loads from localStorage on init', () => {
      localStorageMock.store['kpi-keyboard-shortcuts'] = JSON.stringify({
        enabled: false,
        customShortcuts: { test: { keys: ['ctrl', 'p'] } },
        preferences: { showTooltips: false }
      })

      const store = useKeyboardShortcutsStore()

      expect(store.enabled).toBe(false)
      expect(store.customShortcuts.test).toEqual({ keys: ['ctrl', 'p'] })
      expect(store.preferences.showTooltips).toBe(false)
    })

    it('handles localStorage errors gracefully', () => {
      localStorageMock.getItem.mockImplementationOnce(() => {
        throw new Error('localStorage error')
      })

      // Should not throw
      expect(() => useKeyboardShortcutsStore()).not.toThrow()
    })

    it('handles invalid JSON in localStorage', () => {
      localStorageMock.store['kpi-keyboard-shortcuts'] = 'invalid json'

      // Should not throw
      expect(() => useKeyboardShortcutsStore()).not.toThrow()
    })
  })

  describe('Reset and Export/Import', () => {
    it('resets to defaults', () => {
      const store = useKeyboardShortcutsStore()
      store.setEnabled(false)
      store.setCustomShortcut('test', { keys: ['ctrl', 't'] })
      store.updatePreferences({ showTooltips: false })
      store.addToHistory({ id: 'test' })

      store.resetToDefaults()

      expect(store.enabled).toBe(true)
      expect(store.customShortcuts).toEqual({})
      expect(store.preferences.showTooltips).toBe(true)
      expect(store.shortcutHistory).toHaveLength(0)
    })

    it('exports configuration', () => {
      const store = useKeyboardShortcutsStore()
      store.setEnabled(false)
      store.setCustomShortcut('export-test', { keys: ['ctrl', 'e'] })

      const exported = store.exportConfiguration()

      expect(exported.enabled).toBe(false)
      expect(exported.customShortcuts['export-test']).toBeDefined()
      expect(exported.preferences).toBeDefined()
      expect(exported.exportedAt).toBeDefined()
    })

    it('imports configuration', () => {
      const store = useKeyboardShortcutsStore()
      const config = {
        enabled: false,
        customShortcuts: { imported: { keys: ['ctrl', 'i'] } },
        preferences: { enableSounds: true }
      }

      store.importConfiguration(config)

      expect(store.enabled).toBe(false)
      expect(store.customShortcuts.imported).toEqual({ keys: ['ctrl', 'i'] })
      expect(store.preferences.enableSounds).toBe(true)
    })

    it('handles partial import configuration', () => {
      const store = useKeyboardShortcutsStore()

      store.importConfiguration({ enabled: false })

      expect(store.enabled).toBe(false)
      expect(store.customShortcuts).toEqual({}) // Unchanged
    })
  })
})
