/**
 * Composable for KPI Dashboard saved-filter management.
 * Saving filters, applying quick filters, filter form state.
 */
import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useFiltersStore, type FilterConfig, type SavedFilter, type FilterType } from '@/stores/filtersStore'

export interface FilterTypeOption {
  title: string
  value: FilterType
}

type SnackbarFn = (message: string, color?: string) => void
type FilterChangeFn = (config: FilterConfig) => void
type SelectedClientGetter = () => string | number | null
type DateRangeGetter = () => Date[] | null | undefined

interface SaveFilterFormHandle {
  validate?: () => Promise<{ valid: boolean }>
  resetValidation?: () => void
}

export function useKPIFilters(
  showSnackbar: SnackbarFn,
  handleFilterChange: FilterChangeFn,
  getSelectedClient: SelectedClientGetter,
  getDateRange: DateRangeGetter,
) {
  const { t } = useI18n()
  const filtersStore = useFiltersStore()

  const showSaveFilterDialog = ref(false)
  const saveFilterForm: Ref<SaveFilterFormHandle | null> = ref(null)
  const saveFilterFormValid = ref(false)
  const newFilterName = ref('')
  const newFilterType = ref<FilterType>('dashboard')
  const newFilterIsDefault = ref(false)
  const savingFilter = ref(false)
  const filterTypeOptions: FilterTypeOption[] = [
    { title: 'Dashboard', value: 'dashboard' },
    { title: 'Production', value: 'production' },
    { title: 'Quality', value: 'quality' },
    { title: 'Attendance', value: 'attendance' },
    { title: 'Downtime', value: 'downtime' },
  ]

  const showFilterManager = ref(false)

  const applyQuickSavedFilter = async (filter: SavedFilter): Promise<void> => {
    try {
      const filterConfig = await filtersStore.applyFilter(filter)
      handleFilterChange(filterConfig)
      showSnackbar(`${t('success.filterApplied')}: ${filter.filter_name}`, 'success')
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error applying filter:', error)
      showSnackbar(t('success.filterApplyFailed'), 'error')
    }
  }

  const saveCurrentFilter = async (): Promise<void> => {
    if (!saveFilterFormValid.value || !newFilterName.value) {
      showSnackbar(t('success.pleaseEnterFilterName'), 'warning')
      return
    }

    savingFilter.value = true
    try {
      const dateRange = getDateRange()
      const filterConfig = filtersStore.createFilterConfig({
        client_id: getSelectedClient(),
        date_range:
          dateRange && dateRange.length === 2
            ? {
                type: 'absolute',
                start_date: format(dateRange[0], 'yyyy-MM-dd'),
                end_date: format(dateRange[1], 'yyyy-MM-dd'),
              }
            : { type: 'relative', relative_days: 30 },
      })

      const newFilter = await filtersStore.createFilter({
        filter_name: newFilterName.value,
        filter_type: newFilterType.value,
        filter_config: filterConfig,
        is_default: newFilterIsDefault.value,
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
      // eslint-disable-next-line no-console
      console.error('Error saving filter:', error)
      showSnackbar(t('success.filterSaveFailed'), 'error')
    } finally {
      savingFilter.value = false
    }
  }

  return {
    showSaveFilterDialog,
    saveFilterForm,
    saveFilterFormValid,
    newFilterName,
    newFilterType,
    newFilterIsDefault,
    savingFilter,
    filterTypeOptions,
    showFilterManager,
    applyQuickSavedFilter,
    saveCurrentFilter,
  }
}
