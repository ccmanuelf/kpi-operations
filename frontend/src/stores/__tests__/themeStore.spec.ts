import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useThemeStore } from '../themeStore'

const localStorageMock = {
  store: {},
  getItem: vi.fn((key) => localStorageMock.store[key] || null),
  setItem: vi.fn((key, value) => { localStorageMock.store[key] = value }),
  removeItem: vi.fn((key) => { delete localStorageMock.store[key] }),
  clear: vi.fn(() => { localStorageMock.store = {} })
}

describe('Theme Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorageMock.clear()
    vi.stubGlobal('localStorage', localStorageMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('Initial State', () => {
    it('defaults to light mode', () => {
      const store = useThemeStore()
      expect(store.isDark).toBe(false)
    })

    it('loads dark mode from localStorage', () => {
      localStorageMock.store['kpi-theme'] = JSON.stringify({ isDark: true })
      const store = useThemeStore()
      expect(store.isDark).toBe(true)
    })

    it('loads light mode from localStorage', () => {
      localStorageMock.store['kpi-theme'] = JSON.stringify({ isDark: false })
      const store = useThemeStore()
      expect(store.isDark).toBe(false)
    })
  })

  describe('toggleTheme', () => {
    it('toggles from light to dark', () => {
      const store = useThemeStore()
      expect(store.isDark).toBe(false)
      store.toggleTheme()
      expect(store.isDark).toBe(true)
    })

    it('toggles from dark to light', () => {
      localStorageMock.store['kpi-theme'] = JSON.stringify({ isDark: true })
      const store = useThemeStore()
      expect(store.isDark).toBe(true)
      store.toggleTheme()
      expect(store.isDark).toBe(false)
    })

    it('persists after toggle', () => {
      const store = useThemeStore()
      store.toggleTheme()
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'kpi-theme',
        JSON.stringify({ isDark: true })
      )
    })
  })

  describe('Persistence', () => {
    it('saves to localStorage on toggle', () => {
      const store = useThemeStore()
      store.toggleTheme()
      const saved = JSON.parse(localStorageMock.store['kpi-theme'])
      expect(saved.isDark).toBe(true)
    })

    it('survives double toggle roundtrip', () => {
      const store = useThemeStore()
      store.toggleTheme()
      store.toggleTheme()
      const saved = JSON.parse(localStorageMock.store['kpi-theme'])
      expect(saved.isDark).toBe(false)
    })
  })

  describe('Corrupt JSON handling', () => {
    it('defaults to light on corrupt localStorage', () => {
      localStorageMock.store['kpi-theme'] = 'not-valid-json'
      const store = useThemeStore()
      expect(store.isDark).toBe(false)
    })

    it('defaults to light on null isDark', () => {
      localStorageMock.store['kpi-theme'] = JSON.stringify({ isDark: null })
      const store = useThemeStore()
      expect(store.isDark).toBe(false)
    })

    it('defaults to light on missing isDark key', () => {
      localStorageMock.store['kpi-theme'] = JSON.stringify({ otherKey: 'value' })
      const store = useThemeStore()
      expect(store.isDark).toBe(false)
    })
  })
})
