/**
 * Composable for FilterBar local state and filter-application
 * logic. Date-range management, client/shift selectors, saved-
 * filter application, debounced filter emission.
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import {
  useFiltersStore,
  type DateRange,
  type FilterConfig,
  type FilterType,
  type SavedFilter,
  type FilterHistoryEntry,
} from '@/stores/filtersStore'
import { format, formatDistanceToNow } from 'date-fns'
import api from '@/services/api'
import { debounce } from '@/utils/performance'

interface DateRangeOption {
  value: string
  label: string
  icon: string
  days: number | null
}

interface ClientRow {
  client_id: string | number
  client_name?: string
  [key: string]: unknown
}

interface FilterBarProps {
  filterType: FilterType | string
  [key: string]: unknown
}

type EmitFn = (event: string, payload?: unknown) => void

interface DebouncedFn {
  (): void
  cancel?: () => void
}

const DATE_RANGE_OPTIONS: DateRangeOption[] = [
  { value: 'today', label: 'Today', icon: 'mdi-calendar-today', days: 0 },
  { value: '7d', label: 'Last 7 Days', icon: 'mdi-calendar-week', days: 7 },
  { value: '30d', label: 'Last 30 Days', icon: 'mdi-calendar-month', days: 30 },
  { value: '90d', label: 'Last 90 Days', icon: 'mdi-calendar-range', days: 90 },
  { value: 'ytd', label: 'Year to Date', icon: 'mdi-calendar-star', days: null },
  { value: 'custom', label: 'Custom Range', icon: 'mdi-calendar-edit', days: null },
]

export default function useFilterBarData(props: FilterBarProps, emit: EmitFn) {
  const filtersStore = useFiltersStore()

  const clients = ref<ClientRow[]>([])
  const selectedClientId = ref<string | number | null>(null)
  const selectedShifts = ref<(string | number)[]>([])
  const dateRangeType = ref<string>('30d')
  const customStartDate = ref('')
  const customEndDate = ref('')
  const showSaveDialog = ref(false)
  const showFilterManager = ref(false)

  const activeFilter = computed(() => filtersStore.activeFilter)
  const hasActiveFilter = computed(() => filtersStore.hasActiveFilter)
  const recentFilters = computed(() => filtersStore.recentFilters)
  const filtersByType = computed(() => filtersStore.filtersByType)
  const savedFiltersCount = computed(() => filtersStore.savedFilters.length)

  const filtersByTypeFiltered = computed(() => {
    const filtered: Record<string, SavedFilter[]> = {}
    Object.entries(filtersByType.value).forEach(([type, filters]) => {
      if (filters.length > 0) {
        filtered[type] = filters
      }
    })
    return filtered
  })

  const currentClientName = computed<string | null>(() => {
    if (!selectedClientId.value) return null
    const client = clients.value.find((c) => c.client_id === selectedClientId.value)
    return client?.client_name || null
  })

  const hasDateFilter = computed(
    () =>
      dateRangeType.value !== '30d' || !!customStartDate.value || !!customEndDate.value,
  )

  const hasAnyFilter = computed(
    () =>
      hasActiveFilter.value ||
      !!selectedClientId.value ||
      hasDateFilter.value ||
      selectedShifts.value.length > 0,
  )

  const canSaveFilter = computed(
    () =>
      !!selectedClientId.value || hasDateFilter.value || selectedShifts.value.length > 0,
  )

  const suggestedFilterType = computed(() => props.filterType)

  const dateRangeLabel = computed(() => {
    if (dateRangeType.value === 'custom' && customStartDate.value && customEndDate.value) {
      return `${format(new Date(customStartDate.value), 'MMM d')} - ${format(
        new Date(customEndDate.value),
        'MMM d',
      )}`
    }
    const option = DATE_RANGE_OPTIONS.find((o) => o.value === dateRangeType.value)
    return option?.label || 'Select Date Range'
  })

  const getDateRangeConfig = (): DateRange => {
    if (dateRangeType.value === 'custom' && customStartDate.value && customEndDate.value) {
      return {
        type: 'absolute',
        start_date: customStartDate.value,
        end_date: customEndDate.value,
      }
    }

    const option = DATE_RANGE_OPTIONS.find((o) => o.value === dateRangeType.value)
    if (option?.days !== null && option?.days !== undefined) {
      return {
        type: 'relative',
        relative_days: option.days || 1,
      }
    }

    if (dateRangeType.value === 'ytd') {
      const now = new Date()
      return {
        type: 'absolute',
        start_date: `${now.getFullYear()}-01-01`,
        end_date: format(now, 'yyyy-MM-dd'),
      }
    }

    return {
      type: 'relative',
      relative_days: 30,
    }
  }

  const currentFilterConfig = computed<FilterConfig>(() =>
    filtersStore.createFilterConfig({
      client_id: selectedClientId.value,
      date_range: getDateRangeConfig(),
      shift_ids: selectedShifts.value,
      product_ids: [],
      work_order_status: [],
      kpi_thresholds: {},
    }),
  )

  const applyFilterConfigToLocal = (config: FilterConfig): void => {
    if (config.client_id) {
      selectedClientId.value = config.client_id as string | number
    }
    if (config.shift_ids?.length) {
      selectedShifts.value = config.shift_ids
    }
    if (config.date_range) {
      if (
        config.date_range.type === 'absolute' &&
        config.date_range.start_date &&
        config.date_range.end_date
      ) {
        dateRangeType.value = 'custom'
        customStartDate.value = config.date_range.start_date
        customEndDate.value = config.date_range.end_date
      } else if (config.date_range.relative_days) {
        const match = DATE_RANGE_OPTIONS.find(
          (o) => o.days === config.date_range?.relative_days,
        )
        dateRangeType.value = match?.value || '30d'
      }
    }
  }

  const debouncedEmitFilterChange = debounce(() => {
    const filterParams = {
      ...currentFilterConfig.value,
      ...filtersStore.getFilterParams,
    }
    emit('filter-change', filterParams)
  }, 300) as DebouncedFn

  const emitFilterChange = (): void => {
    debouncedEmitFilterChange()
  }

  const applyDateRange = (value: string): void => {
    dateRangeType.value = value
    if (value !== 'custom') {
      customStartDate.value = ''
      customEndDate.value = ''
      emitFilterChange()
    }
  }

  const applyCustomDateRange = (): void => {
    if (customStartDate.value && customEndDate.value) {
      dateRangeType.value = 'custom'
      emitFilterChange()
    }
  }

  const onClientChange = (): void => {
    emitFilterChange()
  }

  const clearClientFilter = (): void => {
    selectedClientId.value = null
    emitFilterChange()
  }

  const clearDateFilter = (): void => {
    dateRangeType.value = '30d'
    customStartDate.value = ''
    customEndDate.value = ''
    emitFilterChange()
  }

  const clearShiftFilter = (): void => {
    selectedShifts.value = []
    emitFilterChange()
  }

  const clearFilter = (): void => {
    filtersStore.clearActiveFilter()
    emitFilterChange()
  }

  const clearAllFilters = (): void => {
    filtersStore.clearActiveFilter()
    selectedClientId.value = null
    selectedShifts.value = []
    dateRangeType.value = '30d'
    customStartDate.value = ''
    customEndDate.value = ''
    emitFilterChange()
  }

  const applySavedFilter = async (filter: SavedFilter): Promise<void> => {
    await filtersStore.applyFilter(filter)
    applyFilterConfigToLocal(filter.filter_config)
    emitFilterChange()
  }

  const applyRecentFilter = (historyItem: FilterHistoryEntry): void => {
    filtersStore.applyQuickFilter(historyItem.filter_config)
    applyFilterConfigToLocal(historyItem.filter_config)
    emitFilterChange()
  }

  const openSaveDialog = (): void => {
    showSaveDialog.value = true
  }

  const openFilterManager = (): void => {
    showFilterManager.value = true
  }

  const onFilterSaved = (savedFilter: SavedFilter): void => {
    applySavedFilter(savedFilter)
  }

  const onFilterAppliedFromManager = (filter: SavedFilter): void => {
    applySavedFilter(filter)
  }

  const formatFilterPreview = (config: FilterConfig): string => {
    const parts: string[] = []
    if (config.client_id) {
      const client = clients.value.find((c) => c.client_id === config.client_id)
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

  const formatTimeAgo = (dateString: string | null | undefined): string => {
    if (!dateString) return ''
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true })
    } catch {
      return ''
    }
  }

  const loadClients = async (): Promise<void> => {
    try {
      const response = await api.getClients()
      clients.value = response.data || []
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to load clients:', e)
    }
  }

  onMounted(async () => {
    await Promise.all([filtersStore.initializeFilters(), loadClients()])

    const defaultFilter = filtersStore.getDefaultForType(props.filterType as FilterType)
    if (defaultFilter) {
      await applySavedFilter(defaultFilter)
    }
  })

  onUnmounted(() => {
    debouncedEmitFilterChange.cancel?.()
  })

  watch(activeFilter, (newFilter) => {
    if (newFilter?.filter_config) {
      applyFilterConfigToLocal(newFilter.filter_config)
    }
  })

  return {
    dateRangeOptions: DATE_RANGE_OPTIONS,
    clients,
    selectedClientId,
    selectedShifts,
    dateRangeType,
    customStartDate,
    customEndDate,
    showSaveDialog,
    showFilterManager,
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
    formatFilterPreview,
    formatTimeAgo,
  }
}
