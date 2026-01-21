/**
 * Saved Filters Store
 * Manages personal saved filters with localStorage + API sync
 * Pattern follows keyboardShortcutsStore.js
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import { useAuthStore } from './authStore'

const STORAGE_KEY = 'kpi-saved-filters'
const HISTORY_KEY = 'kpi-filter-history'
const MAX_HISTORY = 10

// Filter types supported by the system
export const FILTER_TYPES = {
  dashboard: 'Dashboard',
  production: 'Production',
  quality: 'Quality',
  attendance: 'Attendance',
  downtime: 'Downtime',
  hold: 'Hold/WIP',
  coverage: 'Coverage'
}

export const useFiltersStore = defineStore('filters', () => {
  const authStore = useAuthStore()

  // State
  const savedFilters = ref([])
  const filterHistory = ref([])
  const activeFilter = ref(null)
  const isLoading = ref(false)
  const isSynced = ref(false)

  // Getters
  const filtersByType = computed(() => {
    const grouped = {}
    Object.keys(FILTER_TYPES).forEach(type => {
      grouped[type] = savedFilters.value.filter(f => f.filter_type === type)
    })
    return grouped
  })

  const defaultFilters = computed(() =>
    savedFilters.value.filter(f => f.is_default)
  )

  const getDefaultForType = computed(() => (type) =>
    savedFilters.value.find(f => f.filter_type === type && f.is_default)
  )

  const recentFilters = computed(() =>
    [...filterHistory.value].slice(0, 5)
  )

  const hasActiveFilter = computed(() => activeFilter.value !== null)

  // Actions
  const loadFromLocalStorage = () => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        savedFilters.value = JSON.parse(stored)
      }

      const history = localStorage.getItem(HISTORY_KEY)
      if (history) {
        filterHistory.value = JSON.parse(history)
      }
      return true
    } catch (e) {
      console.error('Failed to load filters from localStorage:', e)
    }
    return false
  }

  const saveToLocalStorage = () => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(savedFilters.value))
      localStorage.setItem(HISTORY_KEY, JSON.stringify(filterHistory.value))
    } catch (e) {
      console.error('Failed to save filters to localStorage:', e)
    }
  }

  const loadFromAPI = async () => {
    if (!authStore.isAuthenticated) return false

    try {
      isLoading.value = true
      const response = await api.getSavedFilters()
      if (response.data) {
        savedFilters.value = response.data
        isSynced.value = true
        saveToLocalStorage()
        return true
      }
    } catch (e) {
      console.error('Failed to load filters from API:', e)
    } finally {
      isLoading.value = false
    }
    return false
  }

  const initializeFilters = async () => {
    loadFromLocalStorage()
    if (authStore.isAuthenticated) {
      await loadFromAPI()
    }
  }

  const createFilter = async (filterData) => {
    try {
      isLoading.value = true
      const response = await api.createSavedFilter(filterData)
      if (response.data) {
        savedFilters.value.push(response.data)
        saveToLocalStorage()
        isSynced.value = true
        return response.data
      }
    } catch (e) {
      console.error('Failed to create filter:', e)
      return null
    } finally {
      isLoading.value = false
    }
    return null
  }

  const updateFilter = async (filterId, filterData) => {
    try {
      isLoading.value = true
      const response = await api.updateSavedFilter(filterId, filterData)
      if (response.data) {
        const index = savedFilters.value.findIndex(f => f.filter_id === filterId)
        if (index !== -1) {
          savedFilters.value[index] = response.data
        }
        saveToLocalStorage()
        return response.data
      }
    } catch (e) {
      console.error('Failed to update filter:', e)
      return null
    } finally {
      isLoading.value = false
    }
    return null
  }

  const deleteFilter = async (filterId) => {
    try {
      isLoading.value = true
      await api.deleteSavedFilter(filterId)
      savedFilters.value = savedFilters.value.filter(f => f.filter_id !== filterId)
      saveToLocalStorage()

      if (activeFilter.value?.filter_id === filterId) {
        activeFilter.value = null
      }
      return true
    } catch (e) {
      console.error('Failed to delete filter:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  const applyFilter = async (filter) => {
    // Set as active filter
    activeFilter.value = filter

    // Add to history
    addToHistory(filter.filter_config)

    // Track usage on API
    if (filter.filter_id) {
      try {
        await api.applyFilter(filter.filter_id)
        // Update local usage count
        const localFilter = savedFilters.value.find(f => f.filter_id === filter.filter_id)
        if (localFilter) {
          localFilter.usage_count = (localFilter.usage_count || 0) + 1
          localFilter.last_used_at = new Date().toISOString()
        }
      } catch (e) {
        console.error('Failed to track filter usage:', e)
      }
    }

    return filter.filter_config
  }

  const applyQuickFilter = (filterConfig) => {
    // Apply a filter configuration without saving
    activeFilter.value = {
      filter_name: 'Quick Filter',
      filter_config: filterConfig,
      is_temporary: true
    }
    addToHistory(filterConfig)
    return filterConfig
  }

  const clearActiveFilter = () => {
    activeFilter.value = null
  }

  const setDefaultFilter = async (filterId, filterType) => {
    try {
      isLoading.value = true
      await api.setDefaultFilter(filterId)

      // Clear other defaults for this type
      savedFilters.value.forEach(f => {
        if (f.filter_type === filterType) {
          f.is_default = f.filter_id === filterId
        }
      })
      saveToLocalStorage()
      return true
    } catch (e) {
      console.error('Failed to set default filter:', e)
      return false
    } finally {
      isLoading.value = false
    }
  }

  const addToHistory = (filterConfig) => {
    // Remove duplicate if exists
    const configString = JSON.stringify(filterConfig)
    filterHistory.value = filterHistory.value.filter(
      h => JSON.stringify(h.filter_config) !== configString
    )

    // Add to front
    filterHistory.value.unshift({
      filter_config: filterConfig,
      applied_at: new Date().toISOString()
    })

    // Trim to max
    if (filterHistory.value.length > MAX_HISTORY) {
      filterHistory.value = filterHistory.value.slice(0, MAX_HISTORY)
    }

    saveToLocalStorage()
  }

  const clearHistory = async () => {
    filterHistory.value = []
    saveToLocalStorage()

    try {
      await api.clearFilterHistory()
    } catch (e) {
      console.error('Failed to clear filter history on API:', e)
    }
  }

  const duplicateFilter = async (filterId, newName) => {
    try {
      isLoading.value = true
      const response = await api.duplicateFilter(filterId, newName)
      if (response.data) {
        savedFilters.value.push(response.data)
        saveToLocalStorage()
        return response.data
      }
    } catch (e) {
      console.error('Failed to duplicate filter:', e)
      return null
    } finally {
      isLoading.value = false
    }
    return null
  }

  // Helper to create filter config object
  const createFilterConfig = ({
    client_id = null,
    date_range = null,
    shift_ids = [],
    product_ids = [],
    work_order_status = [],
    kpi_thresholds = {}
  } = {}) => {
    return {
      client_id,
      date_range: date_range || {
        type: 'relative',
        relative_days: 30
      },
      shift_ids,
      product_ids,
      work_order_status,
      kpi_thresholds
    }
  }

  // Parse active filter for API calls
  const getFilterParams = computed(() => {
    if (!activeFilter.value?.filter_config) return {}

    const config = activeFilter.value.filter_config
    const params = {}

    if (config.client_id) {
      params.client_id = config.client_id
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
    // State
    savedFilters,
    filterHistory,
    activeFilter,
    isLoading,
    isSynced,

    // Getters
    filtersByType,
    defaultFilters,
    getDefaultForType,
    recentFilters,
    hasActiveFilter,
    getFilterParams,

    // Actions
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

    // Constants
    FILTER_TYPES
  }
})
