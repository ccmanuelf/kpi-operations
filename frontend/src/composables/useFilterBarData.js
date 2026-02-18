/**
 * Composable for FilterBar local state and filter-application logic.
 * Handles: date-range management, client/shift selectors, saved-filter
 * application, formatting helpers, and debounced filter emission.
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useFiltersStore } from '@/stores/filtersStore'
import { format, formatDistanceToNow } from 'date-fns'
import api from '@/services/api'
import { debounce } from '@/utils/performance'

// Static date range options (shared across all instances)
const DATE_RANGE_OPTIONS = [
  { value: 'today', label: 'Today', icon: 'mdi-calendar-today', days: 0 },
  { value: '7d', label: 'Last 7 Days', icon: 'mdi-calendar-week', days: 7 },
  { value: '30d', label: 'Last 30 Days', icon: 'mdi-calendar-month', days: 30 },
  { value: '90d', label: 'Last 90 Days', icon: 'mdi-calendar-range', days: 90 },
  { value: 'ytd', label: 'Year to Date', icon: 'mdi-calendar-star', days: null },
  { value: 'custom', label: 'Custom Range', icon: 'mdi-calendar-edit', days: null }
]

export default function useFilterBarData(props, emit) {
  const filtersStore = useFiltersStore()

  // ---------- Local state ----------
  const clients = ref([])
  const selectedClientId = ref(null)
  const selectedShifts = ref([])
  const dateRangeType = ref('30d')
  const customStartDate = ref('')
  const customEndDate = ref('')
  const showSaveDialog = ref(false)
  const showFilterManager = ref(false)

  // ---------- Store-derived computed ----------
  const activeFilter = computed(() => filtersStore.activeFilter)
  const hasActiveFilter = computed(() => filtersStore.hasActiveFilter)
  const recentFilters = computed(() => filtersStore.recentFilters)
  const filtersByType = computed(() => filtersStore.filtersByType)
  const savedFiltersCount = computed(() => filtersStore.savedFilters.length)

  const filtersByTypeFiltered = computed(() => {
    const filtered = {}
    Object.entries(filtersByType.value).forEach(([type, filters]) => {
      if (filters.length > 0) {
        filtered[type] = filters
      }
    })
    return filtered
  })

  // ---------- Derived local computed ----------
  const currentClientName = computed(() => {
    if (!selectedClientId.value) return null
    const client = clients.value.find(c => c.client_id === selectedClientId.value)
    return client?.client_name || null
  })

  const hasDateFilter = computed(() => {
    return dateRangeType.value !== '30d' || customStartDate.value || customEndDate.value
  })

  const hasAnyFilter = computed(() => {
    return hasActiveFilter.value || selectedClientId.value || hasDateFilter.value || selectedShifts.value.length > 0
  })

  const canSaveFilter = computed(() => {
    return selectedClientId.value || hasDateFilter.value || selectedShifts.value.length > 0
  })

  const suggestedFilterType = computed(() => props.filterType)

  const dateRangeLabel = computed(() => {
    if (dateRangeType.value === 'custom' && customStartDate.value && customEndDate.value) {
      return `${format(new Date(customStartDate.value), 'MMM d')} - ${format(new Date(customEndDate.value), 'MMM d')}`
    }
    const option = DATE_RANGE_OPTIONS.find(o => o.value === dateRangeType.value)
    return option?.label || 'Select Date Range'
  })

  const currentFilterConfig = computed(() => {
    return filtersStore.createFilterConfig({
      client_id: selectedClientId.value,
      date_range: getDateRangeConfig(),
      shift_ids: selectedShifts.value,
      product_ids: [],
      work_order_status: [],
      kpi_thresholds: {}
    })
  })

  // ---------- Internal helpers ----------
  const getDateRangeConfig = () => {
    if (dateRangeType.value === 'custom' && customStartDate.value && customEndDate.value) {
      return {
        type: 'absolute',
        start_date: customStartDate.value,
        end_date: customEndDate.value
      }
    }

    const option = DATE_RANGE_OPTIONS.find(o => o.value === dateRangeType.value)
    if (option?.days !== null && option?.days !== undefined) {
      return {
        type: 'relative',
        relative_days: option.days || 1
      }
    }

    if (dateRangeType.value === 'ytd') {
      const now = new Date()
      return {
        type: 'absolute',
        start_date: `${now.getFullYear()}-01-01`,
        end_date: format(now, 'yyyy-MM-dd')
      }
    }

    return {
      type: 'relative',
      relative_days: 30
    }
  }

  const applyFilterConfigToLocal = (config) => {
    if (config.client_id) {
      selectedClientId.value = config.client_id
    }
    if (config.shift_ids?.length) {
      selectedShifts.value = config.shift_ids
    }
    if (config.date_range) {
      if (config.date_range.type === 'absolute') {
        dateRangeType.value = 'custom'
        customStartDate.value = config.date_range.start_date
        customEndDate.value = config.date_range.end_date
      } else if (config.date_range.relative_days) {
        const match = DATE_RANGE_OPTIONS.find(o => o.days === config.date_range.relative_days)
        dateRangeType.value = match?.value || '30d'
      }
    }
  }

  // ---------- Debounced emission ----------
  const debouncedEmitFilterChange = debounce(() => {
    const filterParams = {
      ...currentFilterConfig.value,
      ...filtersStore.getFilterParams
    }
    emit('filter-change', filterParams)
  }, 300)

  const emitFilterChange = () => {
    debouncedEmitFilterChange()
  }

  // ---------- Public actions ----------
  const applyDateRange = (value) => {
    dateRangeType.value = value
    if (value !== 'custom') {
      customStartDate.value = ''
      customEndDate.value = ''
      emitFilterChange()
    }
  }

  const applyCustomDateRange = () => {
    if (customStartDate.value && customEndDate.value) {
      dateRangeType.value = 'custom'
      emitFilterChange()
    }
  }

  const onClientChange = () => {
    emitFilterChange()
  }

  const clearClientFilter = () => {
    selectedClientId.value = null
    emitFilterChange()
  }

  const clearDateFilter = () => {
    dateRangeType.value = '30d'
    customStartDate.value = ''
    customEndDate.value = ''
    emitFilterChange()
  }

  const clearShiftFilter = () => {
    selectedShifts.value = []
    emitFilterChange()
  }

  const clearFilter = () => {
    filtersStore.clearActiveFilter()
    emitFilterChange()
  }

  const clearAllFilters = () => {
    filtersStore.clearActiveFilter()
    selectedClientId.value = null
    selectedShifts.value = []
    dateRangeType.value = '30d'
    customStartDate.value = ''
    customEndDate.value = ''
    emitFilterChange()
  }

  const applySavedFilter = async (filter) => {
    await filtersStore.applyFilter(filter)
    applyFilterConfigToLocal(filter.filter_config)
    emitFilterChange()
  }

  const applyRecentFilter = (historyItem) => {
    filtersStore.applyQuickFilter(historyItem.filter_config)
    applyFilterConfigToLocal(historyItem.filter_config)
    emitFilterChange()
  }

  const openSaveDialog = () => {
    showSaveDialog.value = true
  }

  const openFilterManager = () => {
    showFilterManager.value = true
  }

  const onFilterSaved = (savedFilter) => {
    applySavedFilter(savedFilter)
  }

  const onFilterAppliedFromManager = (filter) => {
    applySavedFilter(filter)
  }

  // ---------- Formatting ----------
  const formatFilterPreview = (config) => {
    const parts = []
    if (config.client_id) {
      const client = clients.value.find(c => c.client_id === config.client_id)
      parts.push(client?.client_name || 'Client')
    }
    if (config.date_range?.relative_days) {
      parts.push(`${config.date_range.relative_days}d`)
    } else if (config.date_range?.type === 'absolute') {
      parts.push('Custom dates')
    }
    if (config.shift_ids?.length) {
      parts.push(`${config.shift_ids.length} shifts`)
    }
    return parts.length > 0 ? parts.join(' + ') : 'All data'
  }

  const formatTimeAgo = (dateString) => {
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true })
    } catch {
      return ''
    }
  }

  // ---------- Data loading ----------
  const loadClients = async () => {
    try {
      const response = await api.getClients()
      clients.value = response.data || []
    } catch (e) {
      console.error('Failed to load clients:', e)
    }
  }

  // ---------- Lifecycle ----------
  onMounted(async () => {
    await Promise.all([
      filtersStore.initializeFilters(),
      loadClients()
    ])

    const defaultFilter = filtersStore.getDefaultForType(props.filterType)
    if (defaultFilter) {
      await applySavedFilter(defaultFilter)
    }
  })

  onUnmounted(() => {
    debouncedEmitFilterChange.cancel()
  })

  // Watch for active filter changes from store
  watch(activeFilter, (newFilter) => {
    if (newFilter?.filter_config) {
      applyFilterConfigToLocal(newFilter.filter_config)
    }
  })

  return {
    // Static
    dateRangeOptions: DATE_RANGE_OPTIONS,
    // State
    clients,
    selectedClientId,
    selectedShifts,
    dateRangeType,
    customStartDate,
    customEndDate,
    showSaveDialog,
    showFilterManager,
    // Computed
    activeFilter,
    hasActiveFilter,
    recentFilters,
    filtersByTypeFiltered,
    savedFiltersCount,
    currentClientName,
    hasDateFilter,
    hasAnyFilter,
    canSaveFilter,
    suggestedFilterType,
    dateRangeLabel,
    currentFilterConfig,
    // Actions
    applyDateRange,
    applyCustomDateRange,
    onClientChange,
    clearClientFilter,
    clearDateFilter,
    clearShiftFilter,
    clearFilter,
    clearAllFilters,
    applySavedFilter,
    applyRecentFilter,
    openSaveDialog,
    openFilterManager,
    onFilterSaved,
    onFilterAppliedFromManager,
    // Formatters
    formatFilterPreview,
    formatTimeAgo
  }
}
