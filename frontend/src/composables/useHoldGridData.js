/**
 * Composable for Hold Entry Grid data, column definitions, filters, and display helpers.
 * Handles: reactive state, entries, work orders, filters, summary stats,
 *          AG Grid column definitions, status formatting/styling.
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProductionDataStore } from '@/stores/productionDataStore'
import { format, differenceInDays } from 'date-fns'

export const HOLD_REASONS = [
  'Quality Issue',
  'Material Defect',
  'Process Non-Conformance',
  'Customer Request',
  'Engineering Change',
  'Inspection Failure',
  'Supplier Issue',
  'Other'
]

export function useHoldGridData() {
  const { t } = useI18n()
  const kpiStore = useProductionDataStore()

  // Core refs
  const gridRef = ref(null)
  const unsavedChanges = ref(new Set())
  const saving = ref(false)
  const snackbar = ref({ show: false, message: '', color: 'success' })

  // Filters
  const dateFilter = ref(null)
  const statusFilter = ref(null)
  const reasonFilter = ref(null)

  // Filtered entries (mutable, set by applyFilters)
  const filteredEntries = ref([])

  // Hold status options for the filter - matches backend HoldStatus enum
  const holdStatusOptions = computed(() => [
    { label: t('grids.holds.approvalWorkflow.pendingHold'), value: 'PENDING_HOLD_APPROVAL' },
    { label: t('grids.holds.active'), value: 'ON_HOLD' },
    { label: t('grids.holds.approvalWorkflow.pendingResume'), value: 'PENDING_RESUME_APPROVAL' },
    { label: t('grids.holds.resumed'), value: 'RESUMED' },
    { label: t('grids.holds.cancelled'), value: 'CANCELLED' }
  ])

  // Store-derived computeds
  const entries = computed(() => kpiStore.holdEntries || [])
  const workOrders = computed(() => kpiStore.workOrders || [])
  const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

  // Summary statistics
  const activeCount = computed(() => {
    return entries.value.filter(e => e.hold_status === 'ON_HOLD' || (!e.actual_resume_date && !e.hold_status)).length
  })

  const resumedCount = computed(() => {
    return entries.value.filter(e => e.hold_status === 'RESUMED' || e.actual_resume_date).length
  })

  const pendingHoldApprovalsCount = computed(() => {
    return entries.value.filter(e => e.hold_status === 'PENDING_HOLD_APPROVAL').length
  })

  const pendingResumeApprovalsCount = computed(() => {
    return entries.value.filter(e => e.hold_status === 'PENDING_RESUME_APPROVAL').length
  })

  const pendingApprovalsCount = computed(() => {
    return pendingHoldApprovalsCount.value + pendingResumeApprovalsCount.value
  })

  const avgDaysOnHold = computed(() => {
    if (filteredEntries.value.length === 0) return 0

    const totalDays = filteredEntries.value.reduce((sum, e) => {
      const startDate = new Date(e.placed_on_hold_date)
      const endDate = e.actual_resume_date ? new Date(e.actual_resume_date) : new Date()
      return sum + differenceInDays(endDate, startDate)
    }, 0)

    return totalDays / filteredEntries.value.length
  })

  // Filter logic
  const applyFilters = () => {
    let filtered = [...entries.value]

    if (dateFilter.value) {
      filtered = filtered.filter(e => {
        const entryDate = new Date(e.placed_on_hold_date).toISOString().split('T')[0]
        return entryDate === dateFilter.value
      })
    }

    if (statusFilter.value) {
      filtered = filtered.filter(e => {
        if (e.hold_status) {
          return e.hold_status === statusFilter.value
        }
        // Fallback for legacy data without hold_status
        if (statusFilter.value === 'ON_HOLD') {
          return !e.actual_resume_date
        } else if (statusFilter.value === 'RESUMED') {
          return !!e.actual_resume_date
        }
        return false
      })
    }

    if (reasonFilter.value) {
      filtered = filtered.filter(e => e.hold_reason === reasonFilter.value)
    }

    filteredEntries.value = filtered
  }

  // Snackbar utility
  const showSnackbar = (message, color = 'success') => {
    snackbar.value = { show: true, message, color }
  }

  // Column definitions
  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.holdDate'),
      field: 'placed_on_hold_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      valueFormatter: (params) => {
        return params.value ? format(new Date(params.value), 'MMM dd, yyyy') : ''
      },
      cellClass: 'font-weight-bold',
      pinned: 'left',
      width: 140,
      sort: 'desc'
    },
    {
      headerName: t('grids.columns.workOrder'),
      field: 'work_order_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: workOrders.value.map(w => w.work_order_id)
      }),
      valueFormatter: (params) => {
        const wo = workOrders.value.find(w => w.work_order_id === params.value)
        return wo?.work_order_number || params.value || 'N/A'
      },
      width: 150
    },
    {
      headerName: t('grids.columns.holdReason'),
      field: 'hold_reason',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: HOLD_REASONS
      },
      width: 200
    },
    {
      headerName: t('grids.columns.status'),
      field: 'hold_status',
      editable: false,
      valueGetter: (params) => {
        const status = params.data.hold_status || (params.data.actual_resume_date ? 'RESUMED' : 'ON_HOLD')
        const statusLabels = {
          'PENDING_HOLD_APPROVAL': t('grids.holds.approvalWorkflow.pendingHold'),
          'ON_HOLD': t('grids.holds.active'),
          'PENDING_RESUME_APPROVAL': t('grids.holds.approvalWorkflow.pendingResume'),
          'RESUMED': t('grids.holds.resumed'),
          'CANCELLED': t('grids.holds.cancelled')
        }
        return statusLabels[status] || status
      },
      cellStyle: (params) => {
        const status = params.data.hold_status || (params.data.actual_resume_date ? 'RESUMED' : 'ON_HOLD')
        const styles = {
          'PENDING_HOLD_APPROVAL': { backgroundColor: '#fff3e0', color: '#e65100', fontWeight: 'bold' },
          'ON_HOLD': { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' },
          'PENDING_RESUME_APPROVAL': { backgroundColor: '#f3e5f5', color: '#7b1fa2', fontWeight: 'bold' },
          'RESUMED': { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' },
          'CANCELLED': { backgroundColor: '#eceff1', color: '#546e7a', fontWeight: 'bold' }
        }
        return styles[status] || {}
      },
      width: 160
    },
    {
      headerName: t('grids.columns.expectedResume'),
      field: 'expected_resume_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      valueFormatter: (params) => {
        return params.value ? format(new Date(params.value), 'MMM dd, yyyy') : ''
      },
      width: 150
    },
    {
      headerName: t('grids.columns.actualResume'),
      field: 'actual_resume_date',
      editable: false,
      valueFormatter: (params) => {
        return params.value ? format(new Date(params.value), 'MMM dd, yyyy HH:mm') : t('grids.holds.notYetResumed')
      },
      cellStyle: (params) => {
        return params.value ? { backgroundColor: '#e8f5e9', color: '#2e7d32' } : {}
      },
      width: 180
    },
    {
      headerName: t('grids.columns.daysOnHold'),
      field: 'days_on_hold',
      editable: false,
      valueGetter: (params) => {
        const startDate = new Date(params.data.placed_on_hold_date)
        const endDate = params.data.actual_resume_date
          ? new Date(params.data.actual_resume_date)
          : new Date()
        return differenceInDays(endDate, startDate)
      },
      cellStyle: (params) => {
        const days = params.value || 0
        if (days > 7) return { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' }
        if (days > 3) return { backgroundColor: '#fff3e0', color: '#f57c00' }
        return {}
      },
      width: 130
    },
    {
      headerName: t('grids.columns.resumedBy'),
      field: 'resumed_by_user_id',
      editable: false,
      width: 130
    },
    {
      headerName: t('grids.columns.holdApproved'),
      field: 'hold_approved_at',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      valueFormatter: (params) => {
        return params.value ? format(new Date(params.value), 'MMM dd HH:mm') : t('grids.holds.pending')
      },
      width: 150
    },
    {
      headerName: t('grids.columns.resumeApproved'),
      field: 'resume_approved_at',
      editable: false,
      valueFormatter: (params) => {
        return params.value ? format(new Date(params.value), 'MMM dd HH:mm') : 'N/A'
      },
      width: 150
    }
  ])

  // Watch for store data changes and re-apply filters
  watch(entries, () => {
    applyFilters()
  }, { immediate: true })

  return {
    // Store
    kpiStore,
    // Core refs
    gridRef,
    unsavedChanges,
    saving,
    snackbar,
    // Filters
    dateFilter,
    statusFilter,
    reasonFilter,
    holdReasons: HOLD_REASONS,
    holdStatusOptions,
    // Data
    entries,
    workOrders,
    filteredEntries,
    hasUnsavedChanges,
    // Summary stats
    activeCount,
    resumedCount,
    pendingHoldApprovalsCount,
    pendingResumeApprovalsCount,
    pendingApprovalsCount,
    avgDaysOnHold,
    // Column definitions (without actions — added by component)
    columnDefs,
    // Methods
    applyFilters,
    showSnackbar
  }
}
