<template>
  <v-dialog v-model="isOpen" max-width="900" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center pa-4 bg-primary">
        <v-icon class="mr-2">mdi-filter-cog</v-icon>
        <span class="text-h5">Manage Saved Filters</span>
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
          placeholder="Search filters..."
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
          Clear History
        </v-btn>
      </div>

      <!-- Tabs for Filter Types -->
      <v-tabs v-model="activeTab" bg-color="grey-lighten-4" density="compact">
        <v-tab value="all">
          <v-icon start size="small">mdi-filter-multiple</v-icon>
          All
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
                  Default
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
                  Used {{ filter.usage_count }} time{{ filter.usage_count !== 1 ? 's' : '' }}
                </span>
                <span v-if="filter.last_used_at">
                  <v-icon size="x-small">mdi-clock-outline</v-icon>
                  Last used {{ formatTimeAgo(filter.last_used_at) }}
                </span>
                <span v-else-if="filter.created_at">
                  <v-icon size="x-small">mdi-calendar-plus</v-icon>
                  Created {{ formatTimeAgo(filter.created_at) }}
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
                    <v-tooltip activator="parent" location="top">Apply</v-tooltip>
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
                        <v-list-item-title>Edit</v-list-item-title>
                      </v-list-item>

                      <v-list-item @click="duplicateFilter(filter)">
                        <template #prepend>
                          <v-icon size="small">mdi-content-copy</v-icon>
                        </template>
                        <v-list-item-title>Duplicate</v-list-item-title>
                      </v-list-item>

                      <v-list-item
                        v-if="!filter.is_default"
                        @click="setAsDefault(filter)"
                      >
                        <template #prepend>
                          <v-icon size="small">mdi-star</v-icon>
                        </template>
                        <v-list-item-title>Set as Default</v-list-item-title>
                      </v-list-item>

                      <v-list-item
                        v-else
                        @click="removeDefault(filter)"
                      >
                        <template #prepend>
                          <v-icon size="small">mdi-star-off</v-icon>
                        </template>
                        <v-list-item-title>Remove Default</v-list-item-title>
                      </v-list-item>

                      <v-divider class="my-1"></v-divider>

                      <v-list-item
                        class="text-error"
                        @click="confirmDelete(filter)"
                      >
                        <template #prepend>
                          <v-icon size="small" color="error">mdi-delete</v-icon>
                        </template>
                        <v-list-item-title>Delete</v-list-item-title>
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
          <h3 class="text-h6 text-grey mt-4">No Filters Found</h3>
          <p class="text-body-2 text-medium-emphasis mt-2">
            {{ searchQuery ? 'No filters match your search criteria.' : 'You haven\'t saved any filters yet.' }}
          </p>
          <v-btn
            v-if="searchQuery"
            variant="text"
            color="primary"
            class="mt-4"
            @click="searchQuery = ''"
          >
            Clear Search
          </v-btn>
        </div>
      </v-card-text>

      <v-divider></v-divider>

      <v-card-actions class="pa-4">
        <v-btn variant="text" @click="close">
          Close
        </v-btn>
        <v-spacer></v-spacer>
        <v-btn
          color="primary"
          variant="flat"
          :disabled="!activeFilter"
          @click="close"
        >
          Done
        </v-btn>
      </v-card-actions>
    </v-card>

    <!-- Edit Filter Dialog -->
    <v-dialog v-model="showEditDialog" max-width="500" persistent>
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon class="mr-2">mdi-pencil</v-icon>
          Edit Filter
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
          <v-btn variant="text" @click="cancelEdit">Cancel</v-btn>
          <v-spacer></v-spacer>
          <v-btn
            color="primary"
            variant="flat"
            :loading="isSaving"
            @click="saveEdit"
          >
            Save Changes
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Duplicate Filter Dialog -->
    <v-dialog v-model="showDuplicateDialog" max-width="400" persistent>
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon class="mr-2">mdi-content-copy</v-icon>
          Duplicate Filter
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
          <v-btn variant="text" @click="cancelDuplicate">Cancel</v-btn>
          <v-spacer></v-spacer>
          <v-btn
            color="primary"
            variant="flat"
            :loading="isSaving"
            :disabled="!duplicateName"
            @click="saveDuplicate"
          >
            Duplicate
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="showDeleteDialog" max-width="400">
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon class="mr-2" color="error">mdi-delete-alert</v-icon>
          Delete Filter
        </v-card-title>

        <v-card-text class="pa-4">
          <p>Are you sure you want to delete <strong>{{ deletingFilter?.filter_name }}</strong>?</p>
          <p class="text-caption text-medium-emphasis mt-2">This action cannot be undone.</p>
        </v-card-text>

        <v-card-actions class="pa-4">
          <v-btn variant="text" @click="cancelDelete">Cancel</v-btn>
          <v-spacer></v-spacer>
          <v-btn
            color="error"
            variant="flat"
            :loading="isDeleting"
            @click="executeDelete"
          >
            Delete
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Clear History Confirmation -->
    <v-dialog v-model="showClearHistoryDialog" max-width="400">
      <v-card>
        <v-card-title class="d-flex align-center pa-4">
          <v-icon class="mr-2" color="warning">mdi-history</v-icon>
          Clear Filter History
        </v-card-title>

        <v-card-text class="pa-4">
          <p>Are you sure you want to clear your filter history?</p>
          <p class="text-caption text-medium-emphasis mt-2">
            This will remove {{ filterHistory.length }} recent filter(s) from your history.
            Saved filters will not be affected.
          </p>
        </v-card-text>

        <v-card-actions class="pa-4">
          <v-btn variant="text" @click="showClearHistoryDialog = false">Cancel</v-btn>
          <v-spacer></v-spacer>
          <v-btn
            color="warning"
            variant="flat"
            @click="executeClearHistory"
          >
            Clear History
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
import { formatDistanceToNow } from 'date-fns'

const { t } = useI18n()

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'filter-applied'])

const filtersStore = useFiltersStore()

// Dialog state
const isOpen = ref(props.modelValue)
const activeTab = ref('all')
const searchQuery = ref('')

// Edit state
const showEditDialog = ref(false)
const editingFilter = ref({})
const originalFilter = ref(null)

// Duplicate state
const showDuplicateDialog = ref(false)
const duplicatingFilter = ref(null)
const duplicateName = ref('')

// Delete state
const showDeleteDialog = ref(false)
const deletingFilter = ref(null)

// Clear history state
const showClearHistoryDialog = ref(false)

// Loading states
const isSaving = ref(false)
const isDeleting = ref(false)

// Computed
const activeFilter = computed(() => filtersStore.activeFilter)
const filtersByType = computed(() => filtersStore.filtersByType)
const filterHistory = computed(() => filtersStore.filterHistory)
const savedFilters = computed(() => filtersStore.savedFilters)

const totalFiltersCount = computed(() => savedFilters.value.length)

const getTypeCount = (type) => {
  return filtersByType.value[type]?.length || 0
}

const filterTypeOptions = computed(() => {
  return Object.entries(FILTER_TYPES).map(([value, label]) => ({
    value,
    label
  }))
})

const filteredList = computed(() => {
  let filters = savedFilters.value

  // Filter by tab
  if (activeTab.value !== 'all') {
    filters = filters.filter(f => f.filter_type === activeTab.value)
  }

  // Filter by search
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filters = filters.filter(f =>
      f.filter_name.toLowerCase().includes(query) ||
      f.filter_type.toLowerCase().includes(query)
    )
  }

  // Sort: defaults first, then by usage count, then by name
  return [...filters].sort((a, b) => {
    if (a.is_default && !b.is_default) return -1
    if (!a.is_default && b.is_default) return 1
    if ((b.usage_count || 0) !== (a.usage_count || 0)) {
      return (b.usage_count || 0) - (a.usage_count || 0)
    }
    return a.filter_name.localeCompare(b.filter_name)
  })
})

// Methods
const getTypeIcon = (type) => {
  const icons = {
    dashboard: 'mdi-view-dashboard',
    production: 'mdi-factory',
    quality: 'mdi-check-decagram',
    attendance: 'mdi-account-clock',
    downtime: 'mdi-clock-alert',
    hold: 'mdi-pause-circle',
    coverage: 'mdi-shield-check'
  }
  return icons[type] || 'mdi-filter'
}

const formatFilterSummary = (config) => {
  const parts = []

  if (config.date_range?.type === 'relative' && config.date_range.relative_days) {
    parts.push(`Last ${config.date_range.relative_days} days`)
  } else if (config.date_range?.type === 'absolute') {
    parts.push('Custom date range')
  }

  if (config.client_id) {
    parts.push('Specific client')
  }

  if (config.shift_ids?.length) {
    parts.push(`${config.shift_ids.length} shift(s)`)
  }

  if (config.product_ids?.length) {
    parts.push(`${config.product_ids.length} product(s)`)
  }

  return parts.length > 0 ? parts.join(' | ') : 'All data'
}

const formatTimeAgo = (dateString) => {
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
  } catch {
    return ''
  }
}

const applyFilter = async (filter) => {
  await filtersStore.applyFilter(filter)
  emit('filter-applied', filter)
}

const editFilter = (filter) => {
  originalFilter.value = filter
  editingFilter.value = {
    filter_name: filter.filter_name,
    filter_type: filter.filter_type,
    is_default: filter.is_default
  }
  showEditDialog.value = true
}

const cancelEdit = () => {
  showEditDialog.value = false
  editingFilter.value = {}
  originalFilter.value = null
}

const saveEdit = async () => {
  if (!originalFilter.value) return

  isSaving.value = true
  try {
    await filtersStore.updateFilter(originalFilter.value.filter_id, {
      filter_name: editingFilter.value.filter_name,
      filter_type: editingFilter.value.filter_type,
      is_default: editingFilter.value.is_default
    })
    showEditDialog.value = false
    editingFilter.value = {}
    originalFilter.value = null
  } catch (e) {
    console.error('Failed to update filter:', e)
  } finally {
    isSaving.value = false
  }
}

const duplicateFilter = (filter) => {
  duplicatingFilter.value = filter
  duplicateName.value = `Copy of ${filter.filter_name}`
  showDuplicateDialog.value = true
}

const cancelDuplicate = () => {
  showDuplicateDialog.value = false
  duplicatingFilter.value = null
  duplicateName.value = ''
}

const saveDuplicate = async () => {
  if (!duplicatingFilter.value || !duplicateName.value) return

  isSaving.value = true
  try {
    await filtersStore.duplicateFilter(
      duplicatingFilter.value.filter_id,
      duplicateName.value
    )
    showDuplicateDialog.value = false
    duplicatingFilter.value = null
    duplicateName.value = ''
  } catch (e) {
    console.error('Failed to duplicate filter:', e)
  } finally {
    isSaving.value = false
  }
}

const setAsDefault = async (filter) => {
  try {
    await filtersStore.setDefaultFilter(filter.filter_id, filter.filter_type)
  } catch (e) {
    console.error('Failed to set default filter:', e)
  }
}

const removeDefault = async (filter) => {
  try {
    await filtersStore.updateFilter(filter.filter_id, {
      is_default: false
    })
  } catch (e) {
    console.error('Failed to remove default:', e)
  }
}

const confirmDelete = (filter) => {
  deletingFilter.value = filter
  showDeleteDialog.value = true
}

const cancelDelete = () => {
  showDeleteDialog.value = false
  deletingFilter.value = null
}

const executeDelete = async () => {
  if (!deletingFilter.value) return

  isDeleting.value = true
  try {
    await filtersStore.deleteFilter(deletingFilter.value.filter_id)
    showDeleteDialog.value = false
    deletingFilter.value = null
  } catch (e) {
    console.error('Failed to delete filter:', e)
  } finally {
    isDeleting.value = false
  }
}

const confirmClearHistory = () => {
  showClearHistoryDialog.value = true
}

const executeClearHistory = async () => {
  await filtersStore.clearHistory()
  showClearHistoryDialog.value = false
}

const close = () => {
  isOpen.value = false
}

// Watch dialog visibility
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
