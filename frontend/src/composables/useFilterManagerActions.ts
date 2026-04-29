/**
 * Composable for FilterManager dialog actions — edit, duplicate,
 * delete, set-default, clear-history. Plus formatting helpers
 * (filter summary, time-ago, type icons).
 */
import { ref, computed } from 'vue'
import {
  useFiltersStore,
  FILTER_TYPES,
  type FilterType,
  type SavedFilter,
  type FilterConfig,
} from '@/stores/filtersStore'
import { formatDistanceToNow } from 'date-fns'

export interface FilterTypeOption {
  value: FilterType
  label: string
}

interface EditingFilterState {
  filter_name?: string
  filter_type?: FilterType
  is_default?: boolean
}

type EmitFn = (event: string, payload: unknown) => void

export default function useFilterManagerActions(emit: EmitFn) {
  const filtersStore = useFiltersStore()

  const showEditDialog = ref(false)
  const editingFilter = ref<EditingFilterState>({})
  const originalFilter = ref<SavedFilter | null>(null)

  const showDuplicateDialog = ref(false)
  const duplicatingFilter = ref<SavedFilter | null>(null)
  const duplicateName = ref('')

  const showDeleteDialog = ref(false)
  const deletingFilter = ref<SavedFilter | null>(null)

  const showClearHistoryDialog = ref(false)

  const isSaving = ref(false)
  const isDeleting = ref(false)

  const filterTypeOptions = computed<FilterTypeOption[]>(() =>
    Object.entries(FILTER_TYPES).map(([value, label]) => ({
      value: value as FilterType,
      label,
    })),
  )

  const getTypeIcon = (type: FilterType | string): string => {
    const icons: Record<string, string> = {
      dashboard: 'mdi-view-dashboard',
      production: 'mdi-factory',
      quality: 'mdi-check-decagram',
      attendance: 'mdi-account-clock',
      downtime: 'mdi-clock-alert',
      hold: 'mdi-pause-circle',
      coverage: 'mdi-shield-check',
    }
    return icons[type] || 'mdi-filter'
  }

  const formatFilterSummary = (config: FilterConfig): string => {
    const parts: string[] = []

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

  const formatTimeAgo = (dateString: string | null | undefined): string => {
    if (!dateString) return ''
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true })
    } catch {
      return ''
    }
  }

  const applyFilter = async (filter: SavedFilter): Promise<void> => {
    await filtersStore.applyFilter(filter)
    emit('filter-applied', filter)
  }

  const editFilter = (filter: SavedFilter): void => {
    originalFilter.value = filter
    editingFilter.value = {
      filter_name: filter.filter_name,
      filter_type: filter.filter_type,
      is_default: filter.is_default,
    }
    showEditDialog.value = true
  }

  const cancelEdit = (): void => {
    showEditDialog.value = false
    editingFilter.value = {}
    originalFilter.value = null
  }

  const saveEdit = async (): Promise<void> => {
    if (!originalFilter.value || !originalFilter.value.filter_id) return

    isSaving.value = true
    try {
      await filtersStore.updateFilter(originalFilter.value.filter_id, {
        filter_name: editingFilter.value.filter_name,
        filter_type: editingFilter.value.filter_type,
        is_default: editingFilter.value.is_default,
      })
      showEditDialog.value = false
      editingFilter.value = {}
      originalFilter.value = null
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to update filter:', e)
    } finally {
      isSaving.value = false
    }
  }

  const duplicateFilter = (filter: SavedFilter): void => {
    duplicatingFilter.value = filter
    duplicateName.value = `Copy of ${filter.filter_name}`
    showDuplicateDialog.value = true
  }

  const cancelDuplicate = (): void => {
    showDuplicateDialog.value = false
    duplicatingFilter.value = null
    duplicateName.value = ''
  }

  const saveDuplicate = async (): Promise<void> => {
    if (
      !duplicatingFilter.value ||
      !duplicatingFilter.value.filter_id ||
      !duplicateName.value
    )
      return

    isSaving.value = true
    try {
      await filtersStore.duplicateFilter(
        duplicatingFilter.value.filter_id,
        duplicateName.value,
      )
      showDuplicateDialog.value = false
      duplicatingFilter.value = null
      duplicateName.value = ''
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to duplicate filter:', e)
    } finally {
      isSaving.value = false
    }
  }

  const setAsDefault = async (filter: SavedFilter): Promise<void> => {
    if (!filter.filter_id || !filter.filter_type) return
    try {
      await filtersStore.setDefaultFilter(filter.filter_id, filter.filter_type)
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to set default filter:', e)
    }
  }

  const removeDefault = async (filter: SavedFilter): Promise<void> => {
    if (!filter.filter_id) return
    try {
      await filtersStore.updateFilter(filter.filter_id, {
        is_default: false,
      })
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to remove default:', e)
    }
  }

  const confirmDelete = (filter: SavedFilter): void => {
    deletingFilter.value = filter
    showDeleteDialog.value = true
  }

  const cancelDelete = (): void => {
    showDeleteDialog.value = false
    deletingFilter.value = null
  }

  const executeDelete = async (): Promise<void> => {
    if (!deletingFilter.value || !deletingFilter.value.filter_id) return

    isDeleting.value = true
    try {
      await filtersStore.deleteFilter(deletingFilter.value.filter_id)
      showDeleteDialog.value = false
      deletingFilter.value = null
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to delete filter:', e)
    } finally {
      isDeleting.value = false
    }
  }

  const confirmClearHistory = (): void => {
    showClearHistoryDialog.value = true
  }

  const executeClearHistory = async (): Promise<void> => {
    await filtersStore.clearHistory()
    showClearHistoryDialog.value = false
  }

  return {
    showEditDialog,
    editingFilter,
    showDuplicateDialog,
    duplicatingFilter,
    duplicateName,
    showDeleteDialog,
    deletingFilter,
    showClearHistoryDialog,
    isSaving,
    isDeleting,
    filterTypeOptions,
    getTypeIcon,
    formatFilterSummary,
    formatTimeAgo,
    applyFilter,
    editFilter,
    cancelEdit,
    saveEdit,
    duplicateFilter,
    cancelDuplicate,
    saveDuplicate,
    setAsDefault,
    removeDefault,
    confirmDelete,
    cancelDelete,
    executeDelete,
    confirmClearHistory,
    executeClearHistory,
  }
}
