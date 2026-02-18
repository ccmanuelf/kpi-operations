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
        {{ t('filterBar.shiftsCount', { count: selectedShifts.length }) }}
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

          <div class="text-caption text-medium-emphasis mb-2">{{ t('filterBar.customRange') }}</div>
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
            {{ t('filterBar.applyCustomRange') }}
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
          <span class="text-subtitle-2">{{ t('filterBar.savedFilters') }}</span>
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
            <div class="text-caption text-medium-emphasis mb-1">{{ t('filterBar.recent') }}</div>
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
            <p class="text-body-2 text-medium-emphasis mt-2">{{ t('filterBar.noSavedFilters') }}</p>
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
            {{ t('filterBar.clear') }}
          </v-btn>
          <v-spacer></v-spacer>
          <v-btn
            size="small"
            variant="text"
            @click="openFilterManager"
          >
            {{ t('filterBar.manage') }}
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
        {{ t('filterBar.saveCurrentFilter') }}
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
        {{ t('filterBar.clearAllFilters') }}
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
import { useI18n } from 'vue-i18n'
import { FILTER_TYPES } from '@/stores/filtersStore'
import SaveFilterDialog from './SaveFilterDialog.vue'
import FilterManager from './FilterManager.vue'
import useFilterBarData from '@/composables/useFilterBarData'

const { t } = useI18n()

const props = defineProps({
  filterType: {
    type: String,
    default: 'dashboard',
    validator: (value) => Object.keys(FILTER_TYPES).includes(value)
  }
})

const emit = defineEmits(['filter-change'])

const {
  dateRangeOptions,
  clients, selectedClientId, selectedShifts,
  dateRangeType, customStartDate, customEndDate,
  showSaveDialog, showFilterManager,
  activeFilter, hasActiveFilter, recentFilters,
  filtersByTypeFiltered, savedFiltersCount,
  currentClientName, hasDateFilter, hasAnyFilter,
  canSaveFilter, suggestedFilterType,
  dateRangeLabel, currentFilterConfig,
  applyDateRange, applyCustomDateRange,
  onClientChange, clearClientFilter, clearDateFilter,
  clearShiftFilter, clearFilter, clearAllFilters,
  applySavedFilter, applyRecentFilter,
  openSaveDialog, openFilterManager,
  onFilterSaved, onFilterAppliedFromManager,
  formatFilterPreview, formatTimeAgo
} = useFilterBarData(props, emit)
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
