import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useDualViewStore } from '../dualViewStore'

const localStorageMock = {
  store: {} as Record<string, string>,
  getItem: vi.fn((key: string) => localStorageMock.store[key] || null),
  setItem: vi.fn((key: string, value: string) => {
    localStorageMock.store[key] = value
  }),
  removeItem: vi.fn((key: string) => {
    delete localStorageMock.store[key]
  }),
  clear: vi.fn(() => {
    localStorageMock.store = {}
  }),
}

describe('Dual-View Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorageMock.clear()
    vi.stubGlobal('localStorage', localStorageMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  describe('Role-based defaults', () => {
    it('operator → site_adjusted', () => {
      const store = useDualViewStore()
      store.initFromUserRole('operator')
      expect(store.currentMode).toBe('site_adjusted')
      expect(store.userOverridden).toBe(false)
    })

    it('leader → site_adjusted', () => {
      const store = useDualViewStore()
      store.initFromUserRole('leader')
      expect(store.currentMode).toBe('site_adjusted')
    })

    it('poweruser → standard', () => {
      const store = useDualViewStore()
      store.initFromUserRole('poweruser')
      expect(store.currentMode).toBe('standard')
    })

    it('admin → standard', () => {
      const store = useDualViewStore()
      store.initFromUserRole('admin')
      expect(store.currentMode).toBe('standard')
    })

    it('unknown role → standard fallback', () => {
      const store = useDualViewStore()
      store.initFromUserRole('mystery_role')
      expect(store.currentMode).toBe('standard')
    })

    it('null role → standard fallback', () => {
      const store = useDualViewStore()
      store.initFromUserRole(null)
      expect(store.currentMode).toBe('standard')
    })
  })

  describe('User override', () => {
    it('toggleMode flips mode and marks user-overridden', () => {
      const store = useDualViewStore()
      store.initFromUserRole('admin')
      expect(store.currentMode).toBe('standard')

      store.toggleMode()
      expect(store.currentMode).toBe('site_adjusted')
      expect(store.userOverridden).toBe(true)
    })

    it('saved preference overrides role default on next init', () => {
      // First session: operator → site_adjusted (default)
      const first = useDualViewStore()
      first.initFromUserRole('operator')
      // User toggles to standard
      first.toggleMode()
      expect(first.currentMode).toBe('standard')

      // Second session: same operator role, but their previous toggle wins
      setActivePinia(createPinia())
      const second = useDualViewStore()
      second.initFromUserRole('operator')
      expect(second.currentMode).toBe('standard')
      expect(second.userOverridden).toBe(true)
    })

    it('reset clears persisted override', () => {
      const store = useDualViewStore()
      store.setMode('site_adjusted')
      expect(store.userOverridden).toBe(true)

      store.reset()
      expect(store.currentMode).toBe('standard')
      expect(store.userOverridden).toBe(false)
      expect(localStorageMock.store['kpi-dual-view-mode']).toBeUndefined()
    })
  })

  describe('Computed flags', () => {
    it('isStandard / isSiteAdjusted reflect currentMode', () => {
      const store = useDualViewStore()
      store.setMode('standard')
      expect(store.isStandard).toBe(true)
      expect(store.isSiteAdjusted).toBe(false)

      store.setMode('site_adjusted')
      expect(store.isStandard).toBe(false)
      expect(store.isSiteAdjusted).toBe(true)
    })
  })
})
