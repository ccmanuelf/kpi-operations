/**
 * Saved filters store — personal filter presets with localStorage +
 * API sync. Composition-API style.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import i18n from '@/i18n'
import { useAuthStore } from './authStore'
import { useNotificationStore } from './notificationStore'

export type FilterType =
  | 'dashboard'
  | 'production'
  | 'quality'
  | 'attendance'
  | 'downtime'
  | 'hold'
  | 'coverage'

export interface DateRange {
  type: 'relative' | 'absolute'
  relative_days?: number
  start_date?: string
  end_date?: string
}

export interface FilterConfig {
  client_id?: string | number | null
  date_range?: DateRange
  shift_ids?: (string | number)[]
  product_ids?: (string | number)[]
  work_order_status?: string[]
  kpi_thresholds?: Record<string, unknown>
  [key: string]: unknown
}

export interface SavedFilter {
  filter_id?: string | number
  filter_name: string
  filter_type?: FilterType
  filter_config: FilterConfig
  is_default?: boolean
  is_temporary?: boolean
  usage_count?: number
  last_used_at?: string
  [key: string]: unknown
}

export interface FilterHistoryEntry {
  filter_config: FilterConfig
  applied_at: string
}

export interface FilterParams {
  client_id?: string | number
  start_date?: string
  end_date?: string
  shift_ids?: string
  product_ids?: string
  [key: string]: unknown
}

const t = (key: string): string => i18n.global.t(key)

const STORAGE_KEY = 'kpi-saved-filters'
const HISTORY_KEY = 'kpi-filter-history'
const MAX_HISTORY = 10

export const FILTER_TYPES: Record<FilterType, string> = {
  dashboard: 'Dashboard',
  production: 'Production',
  quality: 'Quality',
  attendance: 'Attendance',
  downtime: 'Downtime',
  hold: 'Hold/WIP',
  coverage: 'Coverage',
}

export const useFiltersStore = defineStore('filters', () => {
  const authStore = useAuthStore()

  const savedFilters = ref<SavedFilter[]>([])
  const filterHistory = ref<FilterHistoryEntry[]>([])
  const activeFilter = ref<SavedFilter | null>(null)
  const isLoading = ref(false)
  const isSynced = ref(false)

  const filtersByType = computed<Record<FilterType, SavedFilter[]>>(() => {
    const grouped = {} as Record<FilterType, SavedFilter[]>
    ;(Object.keys(FILTER_TYPES) as FilterType[]).forEach((type) => {
      grouped[type] = savedFilters.value.filter((f) => f.filter_type === type)
    })
    return grouped
  })

  const defaultFilters = computed(() => savedFilters.value.filter((f) => f.is_default))

  const getDefaultForType = computed(
    () =>
      (type: FilterType): SavedFilter | undefined =>
        savedFilters.value.find((f) => f.filter_type === type && f.is_default),
  )

  const recentFilters = computed(() => [...filterHistory.value].slice(0, 5))

  const hasActiveFilter = computed(() => activeFilter.value !== null)

  const saveToLocalStorage = (): void => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(savedFilters.value))
      localStorage.setItem(HISTORY_KEY, JSON.stringify(filterHistory.value))
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to save filters to localStorage:', e)
    }
  }

  const loadFromLocalStorage = (): boolean => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        savedFilters.value = JSON.parse(stored) as SavedFilter[]
      }

      const history = localStorage.getItem(HISTORY_KEY)
      if (history) {
        filterHistory.value = JSON.parse(history) as FilterHistoryEntry[]
      }
      return true
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to load filters from localStorage:', e)
    }
    return false
  }

  const loadFromAPI = async (): Promise<boolean> => {
    if (!authStore.isAuthenticated) return false

    try {
      isLoading.value = true
      const response = await api.getSavedFilters()
      if (response.data) {
        savedFilters.value = response.data as SavedFilter[]
        isSynced.value = true
        saveToLocalStorage()
        return true
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to load filters from API:', e)
      useNotificationStore().showError(t('notifications.filters.loadFailed'))
    } finally {
      isLoading.value = false
    }
    return false
  }

  const initializeFilters = async (): Promise<void> => {
    loadFromLocalStorage()
    if (authStore.isAuthenticated) {
      await loadFromAPI()
    }
  }

  const createFilter = async (filterData: Partial<SavedFilter>): Promise<SavedFilter | null> => {
    try {
      isLoading.value = true
      const response = await api.createSavedFilter(filterData)
      if (response.data) {
        savedFilters.value.push(response.data as SavedFilter)
        saveToLocalStorage()
        isSynced.value = true
        return response.data as SavedFilter
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to create filter:', e)
      useNotificationStore().showError(t('notifications.filters.createFailed'))
      return null
    } finally {
      isLoading.value = false
    }
    return null
  }

  const updateFilter = async (
    filterId: string | number,
    filterData: Partial<SavedFilter>,
  ): Promise<SavedFilter | null> => {
    try {
      isLoading.value = true
      const response = await api.updateSavedFilter(filterId, filterData)
      if (response.data) {
        const index = savedFilters.value.findIndex((f) => f.filter_id === filterId)
        if (index !== -1) {
          savedFilters.value[index] = response.data as SavedFilter
        }
        saveToLocalStorage()
        return response.data as SavedFilter
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to update filter:', e)
      useNotificationStore().showError(t('notifications.filters.updateFailed'))
      return null
    } finally {
      isLoading.value = false
    }
    return null
  }

  const deleteFilter = async (filterId: string | number): Promise<boolean> => {
    try {
      isLoading.value = true
      await api.deleteSavedFilter(filterId)
      savedFilters.value = savedFilters.value.filter((f) => f.filter_id !== filterId)
      saveToLocalStorage()

      if (activeFilter.value?.filter_id === filterId) {
        activeFilter.value = null
      }
      return true
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to delete filter:', e)
      useNotificationStore().showError(t('notifications.filters.deleteFailed'))
      return false
    } finally {
      isLoading.value = false
    }
  }

  const addToHistory = (filterConfig: FilterConfig): void => {
    const configString = JSON.stringify(filterConfig)
    filterHistory.value = filterHistory.value.filter(
      (h) => JSON.stringify(h.filter_config) !== configString,
    )

    filterHistory.value.unshift({
      filter_config: filterConfig,
      applied_at: new Date().toISOString(),
    })

    if (filterHistory.value.length > MAX_HISTORY) {
      filterHistory.value = filterHistory.value.slice(0, MAX_HISTORY)
    }

    saveToLocalStorage()
  }

  const applyFilter = async (filter: SavedFilter): Promise<FilterConfig> => {
    activeFilter.value = filter
    addToHistory(filter.filter_config)

    if (filter.filter_id) {
      try {
        await api.applyFilter(filter.filter_id)
        const localFilter = savedFilters.value.find((f) => f.filter_id === filter.filter_id)
        if (localFilter) {
          localFilter.usage_count = (localFilter.usage_count || 0) + 1
          localFilter.last_used_at = new Date().toISOString()
        }
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Failed to track filter usage:', e)
      }
    }

    return filter.filter_config
  }

  const applyQuickFilter = (filterConfig: FilterConfig): FilterConfig => {
    activeFilter.value = {
      filter_name: 'Quick Filter',
      filter_config: filterConfig,
      is_temporary: true,
    }
    addToHistory(filterConfig)
    return filterConfig
  }

  const clearActiveFilter = (): void => {
    activeFilter.value = null
  }

  const setDefaultFilter = async (
    filterId: string | number,
    filterType: FilterType,
  ): Promise<boolean> => {
    try {
      isLoading.value = true
      await api.setDefaultFilter(filterId)

      savedFilters.value.forEach((f) => {
        if (f.filter_type === filterType) {
          f.is_default = f.filter_id === filterId
        }
      })
      saveToLocalStorage()
      return true
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to set default filter:', e)
      useNotificationStore().showError(t('notifications.filters.setDefaultFailed'))
      return false
    } finally {
      isLoading.value = false
    }
  }

  const clearHistory = async (): Promise<void> => {
    filterHistory.value = []
    saveToLocalStorage()

    try {
      await api.clearFilterHistory()
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to clear filter history on API:', e)
    }
  }

  const duplicateFilter = async (
    filterId: string | number,
    newName: string,
  ): Promise<SavedFilter | null> => {
    try {
      isLoading.value = true
      const response = await api.duplicateFilter(filterId, newName)
      if (response.data) {
        savedFilters.value.push(response.data as SavedFilter)
        saveToLocalStorage()
        return response.data as SavedFilter
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to duplicate filter:', e)
      useNotificationStore().showError(t('notifications.filters.duplicateFailed'))
      return null
    } finally {
      isLoading.value = false
    }
    return null
  }

  interface CreateFilterConfigParams {
    client_id?: string | number | null
    date_range?: DateRange | null
    shift_ids?: (string | number)[]
    product_ids?: (string | number)[]
    work_order_status?: string[]
    kpi_thresholds?: Record<string, unknown>
  }

  const createFilterConfig = ({
    client_id = null,
    date_range = null,
    shift_ids = [],
    product_ids = [],
    work_order_status = [],
    kpi_thresholds = {},
  }: CreateFilterConfigParams = {}): FilterConfig => {
    return {
      client_id,
      date_range: date_range || {
        type: 'relative',
        relative_days: 30,
      },
      shift_ids,
      product_ids,
      work_order_status,
      kpi_thresholds,
    }
  }

  const getFilterParams = computed<FilterParams>(() => {
    if (!activeFilter.value?.filter_config) return {}

    const config = activeFilter.value.filter_config
    const params: FilterParams = {}

    if (config.client_id) {
      params.client_id = config.client_id as string | number
    }

    if (config.date_range) {
      if (config.date_range.type === 'relative' && config.date_range.relative_days) {
        const end = new Date()
        const start = new Date()
        start.setDate(start.getDate() - config.date_range.relative_days)
        params.start_date = start.toISOString().split('T')[0]
        params.end_date = end.toISOString().split('T')[0]
      } else if (config.date_range.type === 'absolute') {
        params.start_date = config.date_range.start_date
        params.end_date = config.date_range.end_date
      }
    }

    if (config.shift_ids?.length) {
      params.shift_ids = config.shift_ids.join(',')
    }

    if (config.product_ids?.length) {
      params.product_ids = config.product_ids.join(',')
    }

    return params
  })

  return {
    savedFilters,
    filterHistory,
    activeFilter,
    isLoading,
    isSynced,
    filtersByType,
    defaultFilters,
    getDefaultForType,
    recentFilters,
    hasActiveFilter,
    getFilterParams,
    initializeFilters,
    loadFromAPI,
    createFilter,
    updateFilter,
    deleteFilter,
    applyFilter,
    applyQuickFilter,
    clearActiveFilter,
    setDefaultFilter,
    addToHistory,
    clearHistory,
    duplicateFilter,
    createFilterConfig,
    FILTER_TYPES,
  }
})
