/**
 * Unit tests for Dashboard Store
 * Tests dashboard preferences, widget management, and role-based layouts
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDashboardStore } from '../dashboardStore'

// Mock the API module
vi.mock('@/services/api', () => ({
  default: {
    getDashboardPreferences: vi.fn(),
    saveDashboardPreferences: vi.fn(),
    resetDashboardPreferences: vi.fn()
  }
}))

// Mock auth store
vi.mock('../authStore', () => ({
  useAuthStore: vi.fn(() => ({
    isAuthenticated: true,
    currentUser: { role: 'admin' }
  }))
}))

import api from '@/services/api'

describe('Dashboard Store', () => {
  let localStorageMock

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    localStorageMock = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn()
    }
    Object.defineProperty(global, 'localStorage', {
      value: localStorageMock,
      writable: true
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Initial State', () => {
    it('initializes with default layout', () => {
      const store = useDashboardStore()

      expect(store.layout).toBe('grid')
      expect(store.theme).toBe('default')
      expect(store.isCustomizing).toBe(false)
      expect(store.isLoading).toBe(false)
    })

    it('initializes with empty widgets array', () => {
      const store = useDashboardStore()

      expect(store.widgets).toEqual([])
    })
  })

  describe('Getters', () => {
    it('visibleWidgets returns only visible widgets sorted by order', () => {
      const store = useDashboardStore()
      store.widgets = [
        { widget_key: 'a', is_visible: true, widget_order: 2 },
        { widget_key: 'b', is_visible: false, widget_order: 1 },
        { widget_key: 'c', is_visible: true, widget_order: 1 }
      ]

      expect(store.visibleWidgets).toHaveLength(2)
      expect(store.visibleWidgets[0].widget_key).toBe('c')
      expect(store.visibleWidgets[1].widget_key).toBe('a')
    })

    it('hiddenWidgets returns only hidden widgets', () => {
      const store = useDashboardStore()
      store.widgets = [
        { widget_key: 'a', is_visible: true },
        { widget_key: 'b', is_visible: false }
      ]

      expect(store.hiddenWidgets).toHaveLength(1)
      expect(store.hiddenWidgets[0].widget_key).toBe('b')
    })

    it('userRole returns lowercase role from auth store', () => {
      const store = useDashboardStore()

      expect(store.userRole).toBe('admin')
    })

    it('availableWidgets returns widgets based on role', () => {
      const store = useDashboardStore()

      // Admin should have access to all widgets
      expect(store.availableWidgets.length).toBeGreaterThan(0)
      expect(store.availableWidgets.some(w => w.widget_key === 'system_health')).toBe(true)
    })
  })

  describe('LocalStorage Operations', () => {
    it('initializes and uses localStorage during API sync', async () => {
      const mockData = {
        layout: 'list',
        widgets: [{ widget_key: 'test', is_visible: true }],
        theme: 'dark'
      }
      api.getDashboardPreferences.mockResolvedValue({ data: mockData })

      const store = useDashboardStore()
      await store.loadFromAPI()

      // localStorage should be updated after API load
      expect(localStorageMock.setItem).toHaveBeenCalled()
    })

    it('persists changes after API save', async () => {
      api.saveDashboardPreferences.mockResolvedValue({})

      const store = useDashboardStore()
      store.layout = 'compact'
      store.widgets = [{ widget_key: 'test' }]
      store.theme = 'dark'

      await store.saveToAPI()

      expect(localStorageMock.setItem).toHaveBeenCalled()
    })

    it('handles API load failure gracefully', async () => {
      api.getDashboardPreferences.mockRejectedValue(new Error('API Error'))
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const store = useDashboardStore()
      const result = await store.loadFromAPI()

      expect(result).toBe(false)
      consoleSpy.mockRestore()
    })
  })

  describe('API Operations', () => {
    it('loads preferences from API', async () => {
      const mockData = {
        layout: 'list',
        widgets: [{ widget_key: 'qr_scanner' }],
        theme: 'dark'
      }
      api.getDashboardPreferences.mockResolvedValue({ data: mockData })

      const store = useDashboardStore()
      const result = await store.loadFromAPI()

      expect(result).toBe(true)
      expect(store.layout).toBe('list')
      expect(store.theme).toBe('dark')
      expect(store.isSynced).toBe(true)
    })

    it('handles API load failure', async () => {
      api.getDashboardPreferences.mockRejectedValue(new Error('API Error'))
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const store = useDashboardStore()
      const result = await store.loadFromAPI()

      expect(result).toBe(false)
      consoleSpy.mockRestore()
    })

    it('saves preferences to API', async () => {
      api.saveDashboardPreferences.mockResolvedValue({})

      const store = useDashboardStore()
      store.layout = 'grid'
      store.widgets = []
      store.theme = 'default'

      const result = await store.saveToAPI()

      expect(result).toBe(true)
      expect(api.saveDashboardPreferences).toHaveBeenCalled()
      expect(store.isSynced).toBe(true)
    })
  })

  describe('Widget Management', () => {
    it('toggles widget visibility', () => {
      const store = useDashboardStore()
      store.widgets = [{ widget_key: 'test', is_visible: true }]

      store.toggleWidgetVisibility('test')

      expect(store.widgets[0].is_visible).toBe(false)
      expect(store.isSynced).toBe(false)
    })

    it('adds new widget', () => {
      const store = useDashboardStore()
      store.widgets = []

      store.addWidget('qr_scanner')

      expect(store.widgets).toHaveLength(1)
      expect(store.widgets[0].widget_key).toBe('qr_scanner')
      expect(store.widgets[0].is_visible).toBe(true)
    })

    it('makes existing widget visible when adding', () => {
      const store = useDashboardStore()
      store.widgets = [{ widget_key: 'test', is_visible: false }]

      store.addWidget('test')

      expect(store.widgets[0].is_visible).toBe(true)
    })

    it('removes widget by hiding it', () => {
      const store = useDashboardStore()
      store.widgets = [{ widget_key: 'test', is_visible: true }]

      store.removeWidget('test')

      expect(store.widgets[0].is_visible).toBe(false)
    })

    it('moves widget to new position', () => {
      const store = useDashboardStore()
      store.widgets = [
        { widget_key: 'a', is_visible: true, widget_order: 1 },
        { widget_key: 'b', is_visible: true, widget_order: 2 },
        { widget_key: 'c', is_visible: true, widget_order: 3 }
      ]

      store.moveWidget(0, 2)

      // After move, 'a' should be at position 3
      const widgetA = store.widgets.find(w => w.widget_key === 'a')
      expect(widgetA.widget_order).toBe(3)
      expect(store.isSynced).toBe(false)
    })
  })

  describe('Layout and Theme', () => {
    it('sets layout', () => {
      const store = useDashboardStore()

      store.setLayout('list')

      expect(store.layout).toBe('list')
      expect(store.isSynced).toBe(false)
    })

    it('sets theme', () => {
      const store = useDashboardStore()

      store.setTheme('dark')

      expect(store.theme).toBe('dark')
      expect(store.isSynced).toBe(false)
    })
  })

  describe('Customization Mode', () => {
    it('starts customizing', () => {
      const store = useDashboardStore()

      store.startCustomizing()

      expect(store.isCustomizing).toBe(true)
    })

    it('finishes customizing and saves to API', async () => {
      api.saveDashboardPreferences.mockResolvedValue({})

      const store = useDashboardStore()
      store.isCustomizing = true

      await store.finishCustomizing()

      expect(store.isCustomizing).toBe(false)
      expect(api.saveDashboardPreferences).toHaveBeenCalled()
    })

    it('cancels customizing and reverts changes', () => {
      const storedData = {
        layout: 'grid',
        widgets: [],
        theme: 'default'
      }
      localStorageMock.getItem.mockReturnValue(JSON.stringify(storedData))

      const store = useDashboardStore()
      store.isCustomizing = true
      store.layout = 'list'

      store.cancelCustomizing()

      expect(store.isCustomizing).toBe(false)
    })
  })

  describe('Role Defaults', () => {
    it('applies role defaults via resetToDefaults', async () => {
      api.resetDashboardPreferences.mockResolvedValue({})

      const store = useDashboardStore()
      await store.resetToDefaults()

      expect(store.widgets.length).toBeGreaterThan(0)
      // Admin role should have certain widgets
      expect(store.widgets.some(w => w.widget_key === 'system_health')).toBe(true)
    })

    it('resets to defaults and syncs with API', async () => {
      api.resetDashboardPreferences.mockResolvedValue({})

      const store = useDashboardStore()
      store.widgets = [{ widget_key: 'custom', is_visible: true }]

      await store.resetToDefaults()

      expect(api.resetDashboardPreferences).toHaveBeenCalled()
      expect(store.widgets.some(w => w.widget_key === 'system_health')).toBe(true)
    })
  })
})
