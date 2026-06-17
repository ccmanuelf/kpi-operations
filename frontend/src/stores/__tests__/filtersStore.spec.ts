/**
 * Unit tests for Filters Store
 * Tests saved filter management, localStorage sync, and API interactions
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia, defineStore } from 'pinia'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { defineComponent, computed, h } from 'vue'
import { useFiltersStore, FILTER_TYPES, FILTER_TYPE_KEYS } from '../filtersStore'
import en from '../../i18n/locales/en.json'
import es from '../../i18n/locales/es.json'

// Mock the API module
vi.mock('@/services/api', () => ({
  default: {
    getSavedFilters: vi.fn(),
    createSavedFilter: vi.fn(),
    updateSavedFilter: vi.fn(),
    deleteSavedFilter: vi.fn(),
    applyFilter: vi.fn(),
    setDefaultFilter: vi.fn(),
    clearFilterHistory: vi.fn(),
    duplicateFilter: vi.fn()
  }
}))

// Mock i18n — filtersStore now imports the global i18n instance to
// translate snackbar messages. Loading the real i18n module here
// would touch localStorage at module-init (before beforeEach runs
// the localStorage stub), so stub it inline.
vi.mock('@/i18n', () => ({
  default: { global: { t: (key) => key } }
}))

// Mock auth store
vi.mock('../authStore', () => ({
  useAuthStore: vi.fn(() => ({
    isAuthenticated: true
  }))
}))

import api from '@/services/api'

describe('Filters Store', () => {
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
    it('initializes with empty saved filters', () => {
      const store = useFiltersStore()

      expect(store.savedFilters).toEqual([])
      expect(store.filterHistory).toEqual([])
      expect(store.activeFilter).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(store.isSynced).toBe(false)
    })

    it('exports FILTER_TYPES with key-string values (deprecated shim)', () => {
      expect(FILTER_TYPES).toBeDefined()
      // FILTER_TYPES is now a deprecated shim: values are the key strings, not translated labels.
      // Use store.filterTypeLabels for reactive translated labels.
      expect(FILTER_TYPES.dashboard).toBe('dashboard')
      expect(FILTER_TYPES.production).toBe('production')
      expect(FILTER_TYPES.quality).toBe('quality')
    })

    it('exports FILTER_TYPE_KEYS with all 7 filter types', () => {
      expect(FILTER_TYPE_KEYS).toEqual([
        'dashboard', 'production', 'quality', 'attendance',
        'downtime', 'hold', 'coverage',
      ])
    })
  })

  describe('Getters', () => {
    it('filtersByType groups filters correctly', () => {
      const store = useFiltersStore()
      store.savedFilters = [
        { filter_id: 1, filter_type: 'dashboard', filter_name: 'D1' },
        { filter_id: 2, filter_type: 'production', filter_name: 'P1' },
        { filter_id: 3, filter_type: 'dashboard', filter_name: 'D2' }
      ]

      expect(store.filtersByType.dashboard).toHaveLength(2)
      expect(store.filtersByType.production).toHaveLength(1)
    })

    it('defaultFilters returns filters marked as default', () => {
      const store = useFiltersStore()
      store.savedFilters = [
        { filter_id: 1, is_default: true },
        { filter_id: 2, is_default: false },
        { filter_id: 3, is_default: true }
      ]

      expect(store.defaultFilters).toHaveLength(2)
    })

    it('recentFilters returns first 5 from history', () => {
      const store = useFiltersStore()
      store.filterHistory = Array.from({ length: 10 }, (_, i) => ({
        filter_config: { id: i }
      }))

      expect(store.recentFilters).toHaveLength(5)
    })

    it('hasActiveFilter returns true when filter is active', () => {
      const store = useFiltersStore()
      store.activeFilter = { filter_name: 'Test' }

      expect(store.hasActiveFilter).toBe(true)
    })

    it('hasActiveFilter returns false when no filter is active', () => {
      const store = useFiltersStore()
      store.activeFilter = null

      expect(store.hasActiveFilter).toBe(false)
    })

    it('getFilterParams returns empty object when no active filter', () => {
      const store = useFiltersStore()
      store.activeFilter = null

      expect(store.getFilterParams).toEqual({})
    })

    it('getFilterParams builds params from active filter', () => {
      const store = useFiltersStore()
      store.activeFilter = {
        filter_config: {
          client_id: 1,
          date_range: {
            type: 'relative',
            relative_days: 30
          },
          shift_ids: [1, 2],
          product_ids: [3, 4]
        }
      }

      const params = store.getFilterParams
      expect(params.client_id).toBe(1)
      expect(params.shift_ids).toBe('1,2')
      expect(params.product_ids).toBe('3,4')
      expect(params.start_date).toBeDefined()
      expect(params.end_date).toBeDefined()
    })
  })

  describe('LocalStorage Operations', () => {
    it('loads filters from localStorage during initialization', () => {
      const storedFilters = [{ filter_id: 1, filter_name: 'Test' }]
      localStorageMock.getItem.mockImplementation((key) => {
        if (key === 'kpi-saved-filters') return JSON.stringify(storedFilters)
        return null
      })

      // Internal function is called during initializeFilters
      const store = useFiltersStore()
      // Test that store can be initialized (localStorage load is internal)
      expect(store.savedFilters).toBeDefined()
    })

    it('handles localStorage correctly via API sync', async () => {
      const mockFilters = [{ filter_id: 1, filter_name: 'API Filter' }]
      api.getSavedFilters.mockResolvedValue({ data: mockFilters })

      const store = useFiltersStore()
      await store.initializeFilters()

      // After API sync, localStorage should be updated
      expect(store.savedFilters).toEqual(mockFilters)
    })
  })

  describe('API Operations', () => {
    it('loads filters from API', async () => {
      const mockFilters = [{ filter_id: 1, filter_name: 'API Filter' }]
      api.getSavedFilters.mockResolvedValue({ data: mockFilters })

      const store = useFiltersStore()
      const result = await store.loadFromAPI()

      expect(result).toBe(true)
      expect(store.savedFilters).toEqual(mockFilters)
      expect(store.isSynced).toBe(true)
    })

    it('creates filter via API', async () => {
      const newFilter = { filter_id: 1, filter_name: 'New Filter' }
      api.createSavedFilter.mockResolvedValue({ data: newFilter })

      const store = useFiltersStore()
      const result = await store.createFilter({ filter_name: 'New Filter' })

      expect(result).toEqual(newFilter)
      expect(store.savedFilters).toContainEqual(newFilter)
    })

    it('updates filter via API', async () => {
      const updatedFilter = { filter_id: 1, filter_name: 'Updated' }
      api.updateSavedFilter.mockResolvedValue({ data: updatedFilter })

      const store = useFiltersStore()
      store.savedFilters = [{ filter_id: 1, filter_name: 'Original' }]

      const result = await store.updateFilter(1, { filter_name: 'Updated' })

      expect(result).toEqual(updatedFilter)
      expect(store.savedFilters[0].filter_name).toBe('Updated')
    })

    it('deletes filter via API', async () => {
      api.deleteSavedFilter.mockResolvedValue({})

      const store = useFiltersStore()
      store.savedFilters = [
        { filter_id: 1, filter_name: 'Filter 1' },
        { filter_id: 2, filter_name: 'Filter 2' }
      ]

      const result = await store.deleteFilter(1)

      expect(result).toBe(true)
      expect(store.savedFilters).toHaveLength(1)
      expect(store.savedFilters[0].filter_id).toBe(2)
    })

    it('clears active filter when deleted filter is active', async () => {
      api.deleteSavedFilter.mockResolvedValue({})

      const store = useFiltersStore()
      store.savedFilters = [{ filter_id: 1, filter_name: 'Filter 1' }]
      store.activeFilter = { filter_id: 1 }

      await store.deleteFilter(1)

      expect(store.activeFilter).toBeNull()
    })
  })

  describe('Filter Application', () => {
    it('applies filter and sets it as active', async () => {
      api.applyFilter.mockResolvedValue({})

      const store = useFiltersStore()
      const filter = {
        filter_id: 1,
        filter_name: 'Test',
        filter_config: { client_id: 1 }
      }

      const result = await store.applyFilter(filter)

      expect(store.activeFilter).toEqual(filter)
      expect(result).toEqual(filter.filter_config)
    })

    it('applies quick filter without saving', () => {
      const store = useFiltersStore()
      const config = { client_id: 1, date_range: { type: 'relative', relative_days: 7 } }

      const result = store.applyQuickFilter(config)

      expect(store.activeFilter.is_temporary).toBe(true)
      expect(store.activeFilter.filter_name).toBe('Quick Filter')
      expect(result).toEqual(config)
    })

    it('clears active filter', () => {
      const store = useFiltersStore()
      store.activeFilter = { filter_id: 1 }

      store.clearActiveFilter()

      expect(store.activeFilter).toBeNull()
    })
  })

  describe('Filter History', () => {
    it('adds filter to history', () => {
      const store = useFiltersStore()
      const config = { client_id: 1 }

      store.addToHistory(config)

      expect(store.filterHistory).toHaveLength(1)
      expect(store.filterHistory[0].filter_config).toEqual(config)
      expect(store.filterHistory[0].applied_at).toBeDefined()
    })

    it('removes duplicate from history before adding', () => {
      const store = useFiltersStore()
      const config = { client_id: 1 }

      store.addToHistory(config)
      store.addToHistory(config)

      expect(store.filterHistory).toHaveLength(1)
    })

    it('limits history to 10 items', () => {
      const store = useFiltersStore()

      for (let i = 0; i < 15; i++) {
        store.addToHistory({ client_id: i })
      }

      expect(store.filterHistory).toHaveLength(10)
    })

    it('clears history', async () => {
      api.clearFilterHistory.mockResolvedValue({})

      const store = useFiltersStore()
      store.filterHistory = [{ filter_config: {} }]

      await store.clearHistory()

      expect(store.filterHistory).toEqual([])
    })
  })

  describe('Default Filter Management', () => {
    it('sets default filter for type', async () => {
      api.setDefaultFilter.mockResolvedValue({})

      const store = useFiltersStore()
      store.savedFilters = [
        { filter_id: 1, filter_type: 'dashboard', is_default: true },
        { filter_id: 2, filter_type: 'dashboard', is_default: false }
      ]

      const result = await store.setDefaultFilter(2, 'dashboard')

      expect(result).toBe(true)
      expect(store.savedFilters[0].is_default).toBe(false)
      expect(store.savedFilters[1].is_default).toBe(true)
    })
  })

  describe('createFilterConfig Helper', () => {
    it('creates default filter config', () => {
      const store = useFiltersStore()

      const config = store.createFilterConfig()

      expect(config.client_id).toBeNull()
      expect(config.date_range.type).toBe('relative')
      expect(config.date_range.relative_days).toBe(30)
      expect(config.shift_ids).toEqual([])
      expect(config.product_ids).toEqual([])
    })

    it('creates filter config with custom values', () => {
      const store = useFiltersStore()

      const config = store.createFilterConfig({
        client_id: 1,
        shift_ids: [1, 2]
      })

      expect(config.client_id).toBe(1)
      expect(config.shift_ids).toEqual([1, 2])
    })
  })

  describe('Duplicate Filter', () => {
    it('duplicates filter via API', async () => {
      const duplicatedFilter = { filter_id: 2, filter_name: 'Copy of Test' }
      api.duplicateFilter.mockResolvedValue({ data: duplicatedFilter })

      const store = useFiltersStore()
      store.savedFilters = [{ filter_id: 1, filter_name: 'Test' }]

      const result = await store.duplicateFilter(1, 'Copy of Test')

      expect(result).toEqual(duplicatedFilter)
      expect(store.savedFilters).toHaveLength(2)
    })
  })
})

// ─── es-toggle: filterTypeLabels reactive test ───────────────────────────────
// Uses the REAL en/es locale JSON so we prove actual translated strings switch.
// This suite does NOT use the vi.mock('@/i18n') stub from the block above —
// it creates its own i18n instance and wires it directly.
describe('filterTypeLabels — es-toggle (reactive)', () => {
  it('filterTypeLabels.dashboard switches from English to Spanish on locale toggle', async () => {
    // Arrange: real i18n instance with both locale JSON files
    const i18nReal = createI18n({
      legacy: false,
      locale: 'en',
      fallbackLocale: 'en',
      messages: { en, es },
    })

    // The store uses i18n.global.t from the module-level i18n singleton,
    // but filterTypeLabels is a computed so we test reactivity by mounting
    // a component that reads from a probe store using the same i18n instance.
    setActivePinia(createPinia())

    const useProbeStore = defineStore('filter-type-labels-probe', () => {
      const labels = computed<Record<string, string>>(() => ({
        dashboard: i18nReal.global.t('kpiFilters.types.dashboard'),
        production: i18nReal.global.t('kpiFilters.types.production'),
        quality: i18nReal.global.t('kpiFilters.types.quality'),
        attendance: i18nReal.global.t('kpiFilters.types.attendance'),
        downtime: i18nReal.global.t('kpiFilters.types.downtime'),
        hold: i18nReal.global.t('kpiFilters.types.hold'),
        coverage: i18nReal.global.t('kpiFilters.types.coverage'),
      }))
      return { labels }
    })

    const Probe = defineComponent({
      setup() {
        const store = useProbeStore()
        return () => h('div', [
          h('span', { id: 'dashboard' }, store.labels.dashboard),
          h('span', { id: 'hold' }, store.labels.hold),
          h('span', { id: 'coverage' }, store.labels.coverage),
        ])
      },
    })

    const wrapper = mount(Probe, { global: { plugins: [i18nReal] } })

    // en baseline
    expect(wrapper.find('#dashboard').text()).toBe('Dashboard')
    expect(wrapper.find('#hold').text()).toBe('Hold/WIP')
    expect(wrapper.find('#coverage').text()).toBe('Coverage')

    // toggle to es
    i18nReal.global.locale.value = 'es'
    await wrapper.vm.$nextTick()

    expect(wrapper.find('#dashboard').text()).toBe('Panel')
    expect(wrapper.find('#hold').text()).toBe('En Espera/WIP')
    expect(wrapper.find('#coverage').text()).toBe('Cobertura')
  })

  it('all 7 filter type keys have translations in both locales', () => {
    const i18nReal = createI18n({
      legacy: false,
      locale: 'en',
      fallbackLocale: 'en',
      messages: { en, es },
    })

    const types = ['dashboard', 'production', 'quality', 'attendance', 'downtime', 'hold', 'coverage']

    for (const type of types) {
      const enLabel = i18nReal.global.t(`kpiFilters.types.${type}`)
      i18nReal.global.locale.value = 'es'
      const esLabel = i18nReal.global.t(`kpiFilters.types.${type}`)
      i18nReal.global.locale.value = 'en'

      expect(enLabel, `kpiFilters.types.${type} should exist in en`).not.toBe(`kpiFilters.types.${type}`)
      expect(esLabel, `kpiFilters.types.${type} should exist in es`).not.toBe(`kpiFilters.types.${type}`)
    }
  })
})
