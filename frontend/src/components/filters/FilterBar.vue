<template>
  <v-toolbar density="compact" class="filter-bar" elevation="0" color="surface">
    <!-- Active Filter Display -->
    <v-chip-group class="ml-2">
      <!-- Named filter chip -->
      <v-chip
        v-if="activeFilter && !activeFilter.is_temporary"
        closable
        color="primary"
        variant="tonal"
        size="small"
        @click:close="clearFilter"
      >
        <v-icon start size="small">mdi-filter</v-icon>
        {{ activeFilter.filter_name }}
      </v-chip>

      <!-- Quick filter indicators -->
      <v-chip
        v-if="currentClientName"
        closable
        color="info"
        variant="tonal"
        size="small"
        @click:close="clearClientFilter"
      >
        <v-icon start size="small">mdi-domain</v-icon>
        {{ currentClientName }}
      </v-chip>

      <v-chip
        v-if="hasDateFilter"
        closable
        color="success"
        variant="tonal"
        size="small"
        @click:close="clearDateFilter"
      >
        <v-icon start size="small">mdi-calendar</v-icon>
        {{ dateRangeLabel }}
      </v-chip>

      <v-chip
        v-if="selectedShifts.length > 0"
        closable
        color="warning"
        variant="tonal"
        size="small"
        @click:close="clearShiftFilter"
      >
        <v-icon start size="small">mdi-clock-outline</v-icon>
        {{ selectedShifts.length }} Shift{{ selectedShifts.length > 1 ? 's' : '' }}
      </v-chip>
    </v-chip-group>

    <v-spacer></v-spacer>

    <!-- Date Range Selector -->
    <v-menu :close-on-content-click="false" location="bottom end">
      <template #activator="{ props }">
        <v-btn
          v-bind="props"
          variant="outlined"
          size="small"
          class="mr-2"
          :color="hasDateFilter ? 'primary' : undefined"
        >
          <v-icon start size="small">mdi-calendar</v-icon>
          {{ dateRangeLabel }}
          <v-icon end size="small">mdi-chevron-down</v-icon>
        </v-btn>
      </template>
      <v-card min-width="280">
        <v-card-text class="pa-3">
          <v-list density="compact" nav class="pa-0">
            <v-list-item
              v-for="option in dateRangeOptions"
              :key="option.value"
              :active="dateRangeType === option.value"
              @click="applyDateRange(option.value)"
            >
              <template #prepend>
                <v-icon size="small">{{ option.icon }}</v-icon>
              </template>
              <v-list-item-title>{{ option.label }}</v-list-item-title>
            </v-list-item>
          </v-list>

          <v-divider class="my-2"></v-divider>

          <div class="text-caption text-medium-emphasis mb-2">Custom Range</div>
          <v-row dense>
            <v-col cols="6">
              <v-text-field
                v-model="customStartDate"
                type="date"
                :label="t('common.start')"
                density="compact"
                variant="outlined"
                hide-details
              ></v-text-field>
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="customEndDate"
                type="date"
                :label="t('common.end')"
                density="compact"
                variant="outlined"
                hide-details
              ></v-text-field>
            </v-col>
          </v-row>
          <v-btn
            block
            size="small"
            color="primary"
            variant="tonal"
            class="mt-2"
            :disabled="!customStartDate || !customEndDate"
            @click="applyCustomDateRange"
          >
            Apply Custom Range
          </v-btn>
        </v-card-text>
      </v-card>
    </v-menu>

    <!-- Client Selector -->
    <v-select
      v-model="selectedClientId"
      :items="clients"
      item-title="client_name"
      item-value="client_id"
      :label="t('common.client')"
      density="compact"
      variant="outlined"
      hide-details
      clearable
      class="client-select mr-2"
      style="max-width: 180px"
      @update:model-value="onClientChange"
    >
      <template #prepend-inner>
        <v-icon size="small">mdi-domain</v-icon>
      </template>
    </v-select>

    <!-- Saved Filters Dropdown -->
    <v-menu :close-on-content-click="false" location="bottom end">
      <template #activator="{ props }">
        <v-btn
          v-bind="props"
          icon
          size="small"
          variant="text"
          :color="activeFilter ? 'primary' : undefined"
        >
          <v-badge
            :content="savedFiltersCount"
            :model-value="savedFiltersCount > 0"
            color="primary"
            offset-x="-4"
            offset-y="-4"
          >
            <v-icon>mdi-filter-variant</v-icon>
          </v-badge>
        </v-btn>
      </template>
      <v-card min-width="320" max-width="400">
        <v-card-title class="d-flex align-center py-2 px-3 bg-grey-lighten-4">
          <v-icon start size="small">mdi-filter-variant</v-icon>
          <span class="text-subtitle-2">Saved Filters</span>
          <v-spacer></v-spacer>
          <v-btn
            icon
            size="x-small"
            variant="text"
            @click="openFilterManager"
          >
            <v-icon size="small">mdi-cog</v-icon>
          </v-btn>
        </v-card-title>

        <v-divider></v-divider>

        <v-card-text class="pa-0" style="max-height: 300px; overflow-y: auto">
          <!-- Recent Filters -->
          <div v-if="recentFilters.length > 0" class="px-3 pt-2">
            <div class="text-caption text-medium-emphasis mb-1">Recent</div>
            <v-list density="compact" nav class="pa-0">
              <v-list-item
                v-for="(item, index) in recentFilters"
                :key="'recent-' + index"
                class="rounded mb-1"
                @click="applyRecentFilter(item)"
              >
                <template #prepend>
                  <v-icon size="small" color="grey">mdi-history</v-icon>
                </template>
                <v-list-item-title class="text-body-2">
                  {{ formatFilterPreview(item.filter_config) }}
                </v-list-item-title>
                <v-list-item-subtitle class="text-caption">
                  {{ formatTimeAgo(item.applied_at) }}
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </div>

          <v-divider v-if="recentFilters.length > 0 && savedFiltersCount > 0" class="my-2"></v-divider>

          <!-- Saved Filters by Type -->
          <div v-for="(filters, type) in filtersByTypeFiltered" :key="type" class="px-3 py-2">
            <div class="text-caption text-medium-emphasis mb-1">{{ FILTER_TYPES[type] }}</div>
            <v-list density="compact" nav class="pa-0">
              <v-list-item
                v-for="filter in filters"
                :key="filter.filter_id"
                :active="activeFilter?.filter_id === filter.filter_id"
                class="rounded mb-1"
                @click="applySavedFilter(filter)"
              >
                <template #prepend>
                  <v-icon size="small" :color="filter.is_default ? 'primary' : 'grey'">
                    {{ filter.is_default ? 'mdi-star' : 'mdi-filter-outline' }}
                  </v-icon>
                </template>
                <v-list-item-title class="text-body-2">
                  {{ filter.filter_name }}
                </v-list-item-title>
                <template #append>
                  <v-chip v-if="filter.usage_count" size="x-small" color="grey" variant="text">
                    {{ filter.usage_count }}x
                  </v-chip>
                </template>
              </v-list-item>
            </v-list>
          </div>

          <!-- Empty State -->
          <div v-if="savedFiltersCount === 0 && recentFilters.length === 0" class="pa-4 text-center">
            <v-icon size="48" color="grey-lighten-1">mdi-filter-off-outline</v-icon>
            <p class="text-body-2 text-medium-emphasis mt-2">No saved filters yet</p>
          </div>
        </v-card-text>

        <v-divider></v-divider>

        <v-card-actions class="pa-2">
          <v-btn
            v-if="hasActiveFilter"
            size="small"
            variant="text"
            color="error"
            @click="clearFilter"
          >
            <v-icon start size="small">mdi-close</v-icon>
            Clear
          </v-btn>
          <v-spacer></v-spacer>
          <v-btn
            size="small"
            variant="text"
            @click="openFilterManager"
          >
            Manage
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-menu>

    <!-- Save Current Filter Button -->
    <v-btn
      icon
      size="small"
      variant="text"
      :disabled="!canSaveFilter"
      @click="openSaveDialog"
    >
      <v-icon>mdi-content-save-plus</v-icon>
      <v-tooltip activator="parent" location="bottom">
        Save current filter
      </v-tooltip>
    </v-btn>

    <!-- Clear All Filters -->
    <v-btn
      v-if="hasAnyFilter"
      icon
      size="small"
      variant="text"
      color="error"
      @click="clearAllFilters"
    >
      <v-icon>mdi-filter-remove</v-icon>
      <v-tooltip activator="parent" location="bottom">
        Clear all filters
      </v-tooltip>
    </v-btn>

    <!-- Save Filter Dialog -->
    <SaveFilterDialog
      v-model="showSaveDialog"
      :filter-config="currentFilterConfig"
      :suggested-type="suggestedFilterType"
      @saved="onFilterSaved"
    />

    <!-- Filter Manager Dialog -->
    <FilterManager
      v-model="showFilterManager"
      @filter-applied="onFilterAppliedFromManager"
    />
  </v-toolbar>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFiltersStore, FILTER_TYPES } from '@/stores/filtersStore'
import { useProductionDataStore } from '@/stores/productionDataStore'
import { format, subDays, formatDistanceToNow } from 'date-fns'
import api from '@/services/api'
import { debounce } from '@/utils/performance'
import SaveFilterDialog from './SaveFilterDialog.vue'
import FilterManager from './FilterManager.vue'

const { t } = useI18n()

const props = defineProps({
  filterType: {
    type: String,
    default: 'dashboard',
    validator: (value) => Object.keys(FILTER_TYPES).includes(value)
  }
})

const emit = defineEmits(['filter-change'])

const filtersStore = useFiltersStore()
const kpiStore = useProductionDataStore()

// Local state
const clients = ref([])
const selectedClientId = ref(null)
const selectedShifts = ref([])
const dateRangeType = ref('30d')
const customStartDate = ref('')
const customEndDate = ref('')
const showSaveDialog = ref(false)
const showFilterManager = ref(false)

// Date range options
const dateRangeOptions = [
  { value: 'today', label: 'Today', icon: 'mdi-calendar-today', days: 0 },
  { value: '7d', label: 'Last 7 Days', icon: 'mdi-calendar-week', days: 7 },
  { value: '30d', label: 'Last 30 Days', icon: 'mdi-calendar-month', days: 30 },
  { value: '90d', label: 'Last 90 Days', icon: 'mdi-calendar-range', days: 90 },
  { value: 'ytd', label: 'Year to Date', icon: 'mdi-calendar-star', days: null },
  { value: 'custom', label: 'Custom Range', icon: 'mdi-calendar-edit', days: null }
]

// Computed properties
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
  const option = dateRangeOptions.find(o => o.value === dateRangeType.value)
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

// Methods
const getDateRangeConfig = () => {
  if (dateRangeType.value === 'custom' && customStartDate.value && customEndDate.value) {
    return {
      type: 'absolute',
      start_date: customStartDate.value,
      end_date: customEndDate.value
    }
  }

  const option = dateRangeOptions.find(o => o.value === dateRangeType.value)
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
      const match = dateRangeOptions.find(o => o.days === config.date_range.relative_days)
      dateRangeType.value = match?.value || '30d'
    }
  }
}

const openSaveDialog = () => {
  showSaveDialog.value = true
}

const openFilterManager = () => {
  showFilterManager.value = true
}

const onFilterSaved = (savedFilter) => {
  // Optionally apply the newly saved filter
  applySavedFilter(savedFilter)
}

const onFilterAppliedFromManager = (filter) => {
  applySavedFilter(filter)
}

/**
 * Debounced filter emission to prevent excessive API calls
 * when users quickly change multiple filter options.
 * Uses 300ms delay which feels responsive but prevents flooding.
 */
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

// Cleanup debounced function on unmount
onUnmounted(() => {
  debouncedEmitFilterChange.cancel()
})

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

// Load reference data
const loadClients = async () => {
  try {
    const response = await api.getClients()
    clients.value = response.data || []
  } catch (e) {
    console.error('Failed to load clients:', e)
  }
}

// Initialize
onMounted(async () => {
  await Promise.all([
    filtersStore.initializeFilters(),
    loadClients()
  ])

  // Apply default filter for this type if exists
  const defaultFilter = filtersStore.getDefaultForType(props.filterType)
  if (defaultFilter) {
    await applySavedFilter(defaultFilter)
  }
})

// Watch for active filter changes from store
watch(activeFilter, (newFilter) => {
  if (newFilter?.filter_config) {
    applyFilterConfigToLocal(newFilter.filter_config)
  }
})
</script>

<style scoped>
.filter-bar {
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.client-select :deep(.v-field__input) {
  font-size: 0.875rem;
}

.client-select :deep(.v-field) {
  border-radius: 4px;
}
</style>
