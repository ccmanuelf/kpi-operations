/**
 * Composable for KPI Dashboard saved filter management.
 * Handles: saving filters, applying quick filters, filter form state.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useFiltersStore } from '@/stores/filtersStore'

export function useKPIFilters(showSnackbar, handleFilterChange, getSelectedClient, getDateRange) {
  const { t } = useI18n()
  const filtersStore = useFiltersStore()

  // Save filter dialog state
  const showSaveFilterDialog = ref(false)
  const saveFilterForm = ref(null)
  const saveFilterFormValid = ref(false)
  const newFilterName = ref('')
  const newFilterType = ref('dashboard')
  const newFilterIsDefault = ref(false)
  const savingFilter = ref(false)
  const filterTypeOptions = [
    { title: 'Dashboard', value: 'dashboard' },
    { title: 'Production', value: 'production' },
    { title: 'Quality', value: 'quality' },
    { title: 'Attendance', value: 'attendance' },
    { title: 'Downtime', value: 'downtime' }
  ]

  // Filter manager dialog
  const showFilterManager = ref(false)

  const applyQuickSavedFilter = async (filter) => {
    try {
      const filterConfig = await filtersStore.applyFilter(filter)
      handleFilterChange(filterConfig)
      showSnackbar(`${t('success.filterApplied')}: ${filter.filter_name}`, 'success')
    } catch (error) {
      console.error('Error applying filter:', error)
      showSnackbar(t('success.filterApplyFailed'), 'error')
    }
  }

  const saveCurrentFilter = async () => {
    if (!saveFilterFormValid.value || !newFilterName.value) {
      showSnackbar(t('success.pleaseEnterFilterName'), 'warning')
      return
    }

    savingFilter.value = true
    try {
      const dateRange = getDateRange()
      const filterConfig = filtersStore.createFilterConfig({
        client_id: getSelectedClient(),
        date_range: dateRange && dateRange.length === 2 ? {
          type: 'absolute',
          start_date: format(dateRange[0], 'yyyy-MM-dd'),
          end_date: format(dateRange[1], 'yyyy-MM-dd')
        } : { type: 'relative', relative_days: 30 }
      })

      const newFilter = await filtersStore.createFilter({
        filter_name: newFilterName.value,
        filter_type: newFilterType.value,
        filter_config: filterConfig,
        is_default: newFilterIsDefault.value
      })

      if (newFilter) {
        showSnackbar(`"${newFilterName.value}" ${t('success.filterSaved')}`, 'success')
        showSaveFilterDialog.value = false
        newFilterName.value = ''
        newFilterIsDefault.value = false
      } else {
        showSnackbar(t('success.filterSaveFailed'), 'error')
      }
    } catch (error) {
      console.error('Error saving filter:', error)
      showSnackbar(t('success.filterSaveFailed'), 'error')
    } finally {
      savingFilter.value = false
    }
  }

  return {
    // State
    showSaveFilterDialog,
    saveFilterForm,
    saveFilterFormValid,
    newFilterName,
    newFilterType,
    newFilterIsDefault,
    savingFilter,
    filterTypeOptions,
    showFilterManager,
    // Methods
    applyQuickSavedFilter,
    saveCurrentFilter
  }
}
