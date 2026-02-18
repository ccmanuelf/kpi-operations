/**
 * Composable for FilterManager dialog actions.
 * Handles: edit, duplicate, delete, set-default, clear-history,
 * plus formatting helpers (filter summary, time-ago, type icons).
 */
import { ref, computed } from 'vue'
import { useFiltersStore, FILTER_TYPES } from '@/stores/filtersStore'
import { formatDistanceToNow } from 'date-fns'

export default function useFilterManagerActions(emit) {
  const filtersStore = useFiltersStore()

  // ---------- Edit state ----------
  const showEditDialog = ref(false)
  const editingFilter = ref({})
  const originalFilter = ref(null)

  // ---------- Duplicate state ----------
  const showDuplicateDialog = ref(false)
  const duplicatingFilter = ref(null)
  const duplicateName = ref('')

  // ---------- Delete state ----------
  const showDeleteDialog = ref(false)
  const deletingFilter = ref(null)

  // ---------- Clear-history state ----------
  const showClearHistoryDialog = ref(false)

  // ---------- Loading states ----------
  const isSaving = ref(false)
  const isDeleting = ref(false)

  // ---------- Computed ----------
  const filterTypeOptions = computed(() => {
    return Object.entries(FILTER_TYPES).map(([value, label]) => ({
      value,
      label
    }))
  })

  // ---------- Formatting helpers ----------
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

  // ---------- Actions ----------
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

  return {
    // Edit state
    showEditDialog,
    editingFilter,
    // Duplicate state
    showDuplicateDialog,
    duplicatingFilter,
    duplicateName,
    // Delete state
    showDeleteDialog,
    deletingFilter,
    // Clear-history state
    showClearHistoryDialog,
    // Loading
    isSaving,
    isDeleting,
    // Computed
    filterTypeOptions,
    // Formatters
    getTypeIcon,
    formatFilterSummary,
    formatTimeAgo,
    // Actions
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
    executeClearHistory
  }
}
