<template>
  <v-dialog v-model="isOpen" max-width="900" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center pa-4 bg-primary">
        <v-icon class="mr-2">mdi-filter-cog</v-icon>
        <span class="text-h5">{{ t('filterManager.title') }}</span>
        <v-spacer></v-spacer>
        <v-btn icon variant="text" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <!-- Search and Actions Bar -->
      <div class="pa-4 border-b d-flex align-center gap-3">
        <v-text-field
          v-model="searchQuery"
          prepend-inner-icon="mdi-magnify"
          :placeholder="t('filterManager.searchPlaceholder')"
          variant="outlined"
          density="compact"
          hide-details
          clearable
          style="max-width: 300px"
        ></v-text-field>

        <v-spacer></v-spacer>

        <v-btn
          v-if="filterHistory.length > 0"
          variant="text"
          color="error"
          size="small"
          @click="confirmClearHistory"
        >
          <v-icon start size="small">mdi-history</v-icon>
          {{ t('filterManager.clearHistory') }}
        </v-btn>
      </div>

      <!-- Tabs for Filter Types -->
      <v-tabs v-model="activeTab" bg-color="grey-lighten-4" density="compact">
        <v-tab value="all">
          <v-icon start size="small">mdi-filter-multiple</v-icon>
          {{ t('filterManager.all') }}
          <v-badge
            v-if="totalFiltersCount > 0"
            :content="totalFiltersCount"
            color="primary"
            inline
            class="ml-2"
          ></v-badge>
        </v-tab>
        <v-tab
          v-for="(label, type) in FILTER_TYPES"
          :key="type"
          :value="type"
        >
          <v-icon start size="small">{{ getTypeIcon(type) }}</v-icon>
          {{ label }}
          <v-badge
            v-if="getTypeCount(type) > 0"
            :content="getTypeCount(type)"
            color="grey"
            inline
            class="ml-2"
          ></v-badge>
        </v-tab>
      </v-tabs>

      <v-divider></v-divider>

      <!-- Filter List -->
      <v-card-text class="pa-0" style="min-height: 400px; max-height: 60vh; overflow-y: auto">
        <v-list v-if="filteredList.length > 0" lines="three">
          <template v-for="(filter, index) in filteredList" :key="filter.filter_id">
            <v-list-item
              :class="{ 'bg-primary-lighten-5': activeFilter?.filter_id === filter.filter_id }"
            >
              <template #prepend>
                <v-avatar
                  :color="filter.is_default ? 'primary' : 'grey-lighten-2'"
                  size="40"
                >
                  <v-icon :color="filter.is_default ? 'white' : 'grey-darken-1'">
                    {{ getTypeIcon(filter.filter_type) }}
                  </v-icon>
                </v-avatar>
              </template>

              <v-list-item-title class="font-weight-medium">
                {{ filter.filter_name }}
                <v-chip
                  v-if="filter.is_default"
                  size="x-small"
                  color="primary"
                  variant="flat"
                  class="ml-2"
                >
                  {{ t('filterManager.default') }}
                </v-chip>
              </v-list-item-title>

              <v-list-item-subtitle>
                <v-chip
                  size="x-small"
                  variant="tonal"
                  class="mr-2"
                >
                  {{ FILTER_TYPES[filter.filter_type] }}
                </v-chip>
                {{ formatFilterSummary(filter.filter_config) }}
              </v-list-item-subtitle>

              <v-list-item-subtitle class="text-caption mt-1">
                <span v-if="filter.usage_count" class="mr-3">
                  <v-icon size="x-small">mdi-chart-line</v-icon>
                  {{ t('filterManager.usedCount', { count: filter.usage_count }) }}
                </span>
                <span v-if="filter.last_used_at">
                  <v-icon size="x-small">mdi-clock-outline</v-icon>
                  {{ t('filterManager.lastUsed', { time: formatTimeAgo(filter.last_used_at) }) }}
                </span>
                <span v-else-if="filter.created_at">
                  <v-icon size="x-small">mdi-calendar-plus</v-icon>
                  {{ t('filterManager.created', { time: formatTimeAgo(filter.created_at) }) }}
                </span>
              </v-list-item-subtitle>

              <template #append>
                <div class="d-flex align-center gap-1">
                  <!-- Apply Button -->
                  <v-btn
                    icon
                    size="small"
                    variant="text"
                    color="primary"
                    @click="applyFilter(filter)"
                  >
                    <v-icon>mdi-play</v-icon>
                    <v-tooltip activator="parent" location="top">{{ t('filterManager.apply') }}</v-tooltip>
                  </v-btn>

                  <!-- Actions Menu -->
                  <v-menu location="bottom end">
                    <template #activator="{ props }">
                      <v-btn
                        v-bind="props"
                        icon
                        size="small"
                        variant="text"
                      >
                        <v-icon>mdi-dots-vertical</v-icon>
                      </v-btn>
                    </template>
                    <v-list density="compact" nav>
                      <v-list-item @click="editFilter(filter)">
                        <template #prepend>
                          <v-icon size="small">mdi-pencil</v-icon>
                        </template>
                        <v-list-item-title>{{ t('filterManager.edit') }}</v-list-item-title>
                      </v-list-item>

                      <v-list-item @click="duplicateFilter(filter)">
                        <template #prepend>
                          <v-icon size="small">mdi-content-copy</v-icon>
                        </template>
                        <v-list-item-title>{{ t('filterManager.duplicate') }}</v-list-item-title>
                      </v-list-item>

                      <v-list-item
                        v-if="!filter.is_default"
                        @click="setAsDefault(filter)"
                      >
                        <template #prepend>
                          <v-icon size="small">mdi-star</v-icon>
                        </template>
                        <v-list-item-title>{{ t('filterManager.setAsDefault') }}</v-list-item-title>
                      </v-list-item>

                      <v-list-item
                        v-else
                        @click="removeDefault(filter)"
                      >
                        <template #prepend>
                          <v-icon size="small">mdi-star-off</v-icon>
                        </template>
                        <v-list-item-title>{{ t('filterManager.removeDefault') }}</v-list-item-title>
                      </v-list-item>

                      <v-divider class="my-1"></v-divider>

                      <v-list-item
                        class="text-error"
                        @click="confirmDelete(filter)"
                      >
                        <template #prepend>
                          <v-icon size="small" color="error">mdi-delete</v-icon>
                        </template>
                        <v-list-item-title>{{ t('common.delete') }}</v-list-item-title>
                      </v-list-item>
                    </v-list>
                  </v-menu>
                </div>
              </template>
            </v-list-item>
            <v-divider v-if="index < filteredList.length - 1"></v-divider>
          </template>
        </v-list>

        <!-- Empty State -->
        <div v-else class="pa-8 text-center">
          <v-icon size="80" color="grey-lighten-1">mdi-filter-off-outline</v-icon>
          <h3 class="text-h6 text-grey mt-4">{{ t('filterManager.noFiltersFound') }}</h3>
          <p class="text-body-2 text-medium-emphasis mt-2">
            {{ searchQuery ? t('filterManager.noFiltersMatchSearch') : t('filterManager.noFiltersSaved') }}
          </p>
          <v-btn
            v-if="searchQuery"
            variant="text"
            color="primary"
            class="mt-4"
            @click="searchQuery = ''"
          >
            {{ t('filterManager.clearSearch') }}
          </v-btn>
        </div>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions class="pa-4">
        <v-btn variant="text" @click="close">
          {{ t('common.close') }}
        </v-btn>
        <v-spacer></v-spacer>
        <v-btn
          color="primary"
          variant="flat"
          :disabled="!activeFilter"
          @click="close"
        >
          {{ t('filterManager.done') }}
        </v-btn>
      </v-card-actions>
    </v-card>

    <!-- Edit Filter Dialog -->
    <v-dialog v-model="showEditDialog" max-width="500" persistent>
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon class="mr-2">mdi-pencil</v-icon>
          {{ t('filterManager.editFilter') }}
        </v-card-title>

        <v-card-text class="pa-4">
          <v-text-field
            v-model="editingFilter.filter_name"
            :label="t('filters.filterName')"
            variant="outlined"
            density="comfortable"
          ></v-text-field>

          <v-select
            v-model="editingFilter.filter_type"
            :items="filterTypeOptions"
            item-title="label"
            item-value="value"
            :label="t('filters.filterType')"
            variant="outlined"
            density="comfortable"
            class="mt-4"
          ></v-select>

          <v-checkbox
            v-model="editingFilter.is_default"
            :label="t('filters.setAsDefault')"
            density="compact"
            class="mt-2"
          ></v-checkbox>
        </v-card-text>

        <v-card-actions class="pa-4">
          <v-btn variant="text" @click="cancelEdit">{{ t('common.cancel') }}</v-btn>
          <v-spacer></v-spacer>
          <v-btn
            color="primary"
            variant="flat"
            :loading="isSaving"
            @click="saveEdit"
          >
            {{ t('filterManager.saveChanges') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Duplicate Filter Dialog -->
    <v-dialog v-model="showDuplicateDialog" max-width="400" persistent>
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon class="mr-2">mdi-content-copy</v-icon>
          {{ t('filterManager.duplicateFilter') }}
        </v-card-title>

        <v-card-text class="pa-4">
          <v-text-field
            v-model="duplicateName"
            :label="t('filters.filterName')"
            variant="outlined"
            density="comfortable"
            :placeholder="`Copy of ${duplicatingFilter?.filter_name || ''}`"
          ></v-text-field>
        </v-card-text>

        <v-card-actions class="pa-4">
          <v-btn variant="text" @click="cancelDuplicate">{{ t('common.cancel') }}</v-btn>
          <v-spacer></v-spacer>
          <v-btn
            color="primary"
            variant="flat"
            :loading="isSaving"
            :disabled="!duplicateName"
            @click="saveDuplicate"
          >
            {{ t('filterManager.duplicate') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon class="mr-2" color="error">mdi-delete-alert</v-icon>
          {{ t('filterManager.deleteFilter') }}
        </v-card-title>

        <v-card-text class="pa-4">
          <p>{{ t('filterManager.deleteConfirm', { name: deletingFilter?.filter_name }) }}</p>
          <p class="text-caption text-medium-emphasis mt-2">{{ t('filterManager.deleteWarning') }}</p>
        </v-card-text>

        <v-card-actions class="pa-4">
          <v-btn variant="text" @click="cancelDelete">{{ t('common.cancel') }}</v-btn>
          <v-spacer></v-spacer>
          <v-btn
            color="error"
            variant="flat"
            :loading="isDeleting"
            @click="executeDelete"
          >
            {{ t('common.delete') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Clear History Confirmation -->
    <v-dialog v-model="showClearHistoryDialog" max-width="400">
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon class="mr-2" color="warning">mdi-history</v-icon>
          {{ t('filterManager.clearFilterHistory') }}
        </v-card-title>

        <v-card-text class="pa-4">
          <p>{{ t('filterManager.clearHistoryConfirm') }}</p>
          <p class="text-caption text-medium-emphasis mt-2">
            {{ t('filterManager.clearHistoryDetail', { count: filterHistory.length }) }}
          </p>
        </v-card-text>

        <v-card-actions class="pa-4">
          <v-btn variant="text" @click="showClearHistoryDialog = false">{{ t('common.cancel') }}</v-btn>
          <v-spacer></v-spacer>
          <v-btn
            color="warning"
            variant="flat"
            @click="executeClearHistory"
          >
            {{ t('filterManager.clearHistory') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFiltersStore, FILTER_TYPES } from '@/stores/filtersStore'
import useFilterManagerActions from '@/composables/useFilterManagerActions'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'filter-applied'])

const filtersStore = useFiltersStore()

// Actions composable (edit, duplicate, delete, clear-history, formatters)
const {
  showEditDialog, editingFilter,
  showDuplicateDialog, duplicatingFilter, duplicateName,
  showDeleteDialog, deletingFilter,
  showClearHistoryDialog,
  isSaving, isDeleting,
  filterTypeOptions,
  getTypeIcon, formatFilterSummary, formatTimeAgo,
  applyFilter, editFilter, cancelEdit, saveEdit,
  duplicateFilter, cancelDuplicate, saveDuplicate,
  setAsDefault, removeDefault,
  confirmDelete, cancelDelete, executeDelete,
  confirmClearHistory, executeClearHistory
} = useFilterManagerActions(emit)

// Dialog state
const isOpen = ref(props.modelValue)
const activeTab = ref('all')
const searchQuery = ref('')

// Store-derived computed
const activeFilter = computed(() => filtersStore.activeFilter)
const filtersByType = computed(() => filtersStore.filtersByType)
const filterHistory = computed(() => filtersStore.filterHistory)
const savedFilters = computed(() => filtersStore.savedFilters)
const totalFiltersCount = computed(() => savedFilters.value.length)

const getTypeCount = (type) => {
  return filtersByType.value[type]?.length || 0
}

const filteredList = computed(() => {
  let filters = savedFilters.value
  if (activeTab.value !== 'all') {
    filters = filters.filter(f => f.filter_type === activeTab.value)
  }
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filters = filters.filter(f =>
      f.filter_name.toLowerCase().includes(query) ||
      f.filter_type.toLowerCase().includes(query)
    )
  }
  return [...filters].sort((a, b) => {
    if (a.is_default && !b.is_default) return -1
    if (!a.is_default && b.is_default) return 1
    if ((b.usage_count || 0) !== (a.usage_count || 0)) {
      return (b.usage_count || 0) - (a.usage_count || 0)
    }
    return a.filter_name.localeCompare(b.filter_name)
  })
})

const close = () => {
  isOpen.value = false
}

watch(() => props.modelValue, (newValue) => {
  isOpen.value = newValue
})

watch(isOpen, (newValue) => {
  emit('update:modelValue', newValue)
})
</script>

<style scoped>
.border-b {
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.gap-1 {
  gap: 4px;
}

.gap-3 {
  gap: 12px;
}

.bg-primary-lighten-5 {
  background-color: rgba(var(--v-theme-primary), 0.05) !important;
}
</style>
