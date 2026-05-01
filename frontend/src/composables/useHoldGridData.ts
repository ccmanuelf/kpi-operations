/**
 * Composable for Hold Entry Grid data, column definitions,
 * filters, and display helpers.
 *
 * Backend alignment: field names match backend/schemas/hold.py
 * WIPHoldResponse / WIPHoldCreate. `hold_date` (not placed_on_hold_date),
 * `expected_resolution_date` (not expected_resume_date), `resumed_by`
 * (not resumed_by_user_id). Reasons use the canonical
 * HOLD_REASON_CATALOG codes; legacy UI labels were removed in the
 * 2026-05-01 entry-audit migration.
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProductionDataStore } from '@/stores/productionDataStore'
import { format, differenceInDays } from 'date-fns'

export type HoldStatus =
  | 'PENDING_HOLD_APPROVAL'
  | 'ON_HOLD'
  | 'PENDING_RESUME_APPROVAL'
  | 'RESUMED'
  | 'CANCELLED'

export interface HoldEntry {
  id?: string | number
  hold_entry_id?: string | number
  client_id?: string
  hold_status?: HoldStatus | string
  hold_reason?: string
  hold_reason_category?: string
  hold_reason_description?: string
  work_order_id?: string | number
  hold_date?: string
  resume_date?: string | null
  expected_resolution_date?: string | null
  hold_initiated_by?: string | null
  hold_approved_by?: string | null
  resumed_by?: string | null
  notes?: string | null
  [key: string]: unknown
}

export interface WorkOrderRef {
  id?: string | number
  work_order_id?: string | number
  work_order_number?: string
  [key: string]: unknown
}

export interface HoldStatusOption {
  label: string
  value: HoldStatus
}

interface SnackbarState {
  show: boolean
  message: string
  color: string
}

interface ColumnDef {
  headerName: string
  field?: string
  editable?: boolean
  cellEditor?: string
  cellEditorParams?: unknown
  valueFormatter?: (params: { value?: unknown; data?: unknown }) => string
  valueGetter?: (params: { value?: unknown; data: HoldEntry }) => unknown
  cellClass?: string | ((params: { value?: unknown; data: HoldEntry }) => string)
  pinned?: 'left' | 'right'
  width?: number
  sort?: 'asc' | 'desc'
}

// Canonical HOLD_REASON_CATALOG codes (mirrors backend/schemas/hold.py:56-71).
// The set is enforced server-side per-client via validate_hold_reason_for_client.
export const HOLD_REASON_CODES: string[] = [
  'QUALITY_ISSUE',
  'MATERIAL_INSPECTION',
  'ENGINEERING_REVIEW',
  'CUSTOMER_REQUEST',
  'MISSING_SPECIFICATION',
  'EQUIPMENT_UNAVAILABLE',
  'CAPACITY_CONSTRAINT',
  'OTHER',
]

export function useHoldGridData() {
  const { t } = useI18n()
  const kpiStore = useProductionDataStore()

  const gridRef = ref<unknown>(null)
  const unsavedChanges = ref<Set<string | number>>(new Set())
  const saving = ref(false)
  const snackbar = ref<SnackbarState>({ show: false, message: '', color: 'success' })

  const dateFilter = ref<string | null>(null)
  const statusFilter = ref<HoldStatus | null>(null)
  const reasonFilter = ref<string | null>(null)

  const filteredEntries = ref<HoldEntry[]>([])

  const holdStatusOptions = computed<HoldStatusOption[]>(() => [
    { label: t('grids.holds.approvalWorkflow.pendingHold'), value: 'PENDING_HOLD_APPROVAL' },
    { label: t('grids.holds.active'), value: 'ON_HOLD' },
    { label: t('grids.holds.approvalWorkflow.pendingResume'), value: 'PENDING_RESUME_APPROVAL' },
    { label: t('grids.holds.resumed'), value: 'RESUMED' },
    { label: t('grids.holds.cancelled'), value: 'CANCELLED' },
  ])

  const entries = computed<HoldEntry[]>(
    () => (kpiStore.holdEntries as HoldEntry[]) || [],
  )
  const workOrders = computed<WorkOrderRef[]>(
    () => (kpiStore.workOrders as WorkOrderRef[]) || [],
  )
  const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

  const activeCount = computed(
    () =>
      entries.value.filter(
        (e) => e.hold_status === 'ON_HOLD' || (!e.resume_date && !e.hold_status),
      ).length,
  )

  const resumedCount = computed(
    () =>
      entries.value.filter((e) => e.hold_status === 'RESUMED' || e.resume_date)
        .length,
  )

  const pendingHoldApprovalsCount = computed(
    () => entries.value.filter((e) => e.hold_status === 'PENDING_HOLD_APPROVAL').length,
  )

  const pendingResumeApprovalsCount = computed(
    () => entries.value.filter((e) => e.hold_status === 'PENDING_RESUME_APPROVAL').length,
  )

  const pendingApprovalsCount = computed(
    () => pendingHoldApprovalsCount.value + pendingResumeApprovalsCount.value,
  )

  const avgDaysOnHold = computed<number>(() => {
    if (filteredEntries.value.length === 0) return 0

    const totalDays = filteredEntries.value.reduce((sum, e) => {
      if (!e.hold_date) return sum
      const startDate = new Date(e.hold_date)
      const endDate = e.resume_date ? new Date(e.resume_date) : new Date()
      return sum + differenceInDays(endDate, startDate)
    }, 0)

    return totalDays / filteredEntries.value.length
  })

  const applyFilters = (): void => {
    let filtered = [...entries.value]

    if (dateFilter.value) {
      filtered = filtered.filter((e) => {
        if (!e.hold_date) return false
        const entryDate = new Date(e.hold_date).toISOString().split('T')[0]
        return entryDate === dateFilter.value
      })
    }

    if (statusFilter.value) {
      filtered = filtered.filter((e) => {
        if (e.hold_status) {
          return e.hold_status === statusFilter.value
        }
        if (statusFilter.value === 'ON_HOLD') {
          return !e.resume_date
        } else if (statusFilter.value === 'RESUMED') {
          return !!e.resume_date
        }
        return false
      })
    }

    if (reasonFilter.value) {
      filtered = filtered.filter((e) => e.hold_reason === reasonFilter.value)
    }

    filteredEntries.value = filtered
  }

  const showSnackbar = (message: string, color: string = 'success'): void => {
    snackbar.value = { show: true, message, color }
  }

  const columnDefs = computed<ColumnDef[]>(() => [
    {
      headerName: t('grids.columns.holdDate'),
      field: 'hold_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      valueFormatter: (params) =>
        params.value ? format(new Date(params.value as string), 'MMM dd, yyyy') : '',
      cellClass: 'font-weight-bold',
      pinned: 'left',
      width: 140,
      sort: 'desc',
    },
    {
      headerName: t('grids.columns.workOrder'),
      field: 'work_order_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: workOrders.value.map((w) => w.work_order_id),
      }),
      valueFormatter: (params) => {
        const wo = workOrders.value.find((w) => w.work_order_id === params.value)
        return wo?.work_order_number || (params.value as string) || 'N/A'
      },
      width: 150,
    },
    {
      headerName: t('grids.columns.holdReason'),
      field: 'hold_reason',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: HOLD_REASON_CODES },
      width: 200,
    },
    {
      headerName: t('grids.columns.holdReasonDescription'),
      field: 'hold_reason_description',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      width: 220,
    },
    {
      headerName: t('grids.columns.status'),
      field: 'hold_status',
      editable: false,
      valueGetter: (params) => {
        const status =
          params.data.hold_status ||
          (params.data.resume_date ? 'RESUMED' : 'ON_HOLD')
        const statusLabels: Record<string, string> = {
          PENDING_HOLD_APPROVAL: t('grids.holds.approvalWorkflow.pendingHold'),
          ON_HOLD: t('grids.holds.active'),
          PENDING_RESUME_APPROVAL: t('grids.holds.approvalWorkflow.pendingResume'),
          RESUMED: t('grids.holds.resumed'),
          CANCELLED: t('grids.holds.cancelled'),
        }
        return statusLabels[status as string] || status
      },
      cellClass: (params) => {
        const status =
          params.data.hold_status ||
          (params.data.resume_date ? 'RESUMED' : 'ON_HOLD')
        const classes: Record<string, string> = {
          PENDING_HOLD_APPROVAL: 'ag-cell-warning ag-cell-bold',
          ON_HOLD: 'ag-cell-error ag-cell-bold',
          PENDING_RESUME_APPROVAL: 'ag-cell-purple ag-cell-bold',
          RESUMED: 'ag-cell-success ag-cell-bold',
          CANCELLED: 'ag-cell-neutral ag-cell-bold',
        }
        return classes[status as string] || ''
      },
      width: 160,
    },
    {
      headerName: t('grids.columns.expectedResolution'),
      field: 'expected_resolution_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      valueFormatter: (params) =>
        params.value ? format(new Date(params.value as string), 'MMM dd, yyyy') : '',
      width: 150,
    },
    {
      headerName: t('grids.columns.resumeDate'),
      field: 'resume_date',
      editable: false,
      valueFormatter: (params) =>
        params.value
          ? format(new Date(params.value as string), 'MMM dd, yyyy HH:mm')
          : t('grids.holds.notYetResumed'),
      cellClass: (params) => (params.value ? 'ag-cell-success' : ''),
      width: 180,
    },
    {
      headerName: t('grids.columns.daysOnHold'),
      field: 'days_on_hold',
      editable: false,
      valueGetter: (params) => {
        if (!params.data.hold_date) return 0
        const startDate = new Date(params.data.hold_date)
        const endDate = params.data.resume_date
          ? new Date(params.data.resume_date)
          : new Date()
        return differenceInDays(endDate, startDate)
      },
      cellClass: (params) => {
        const days = (params.value as number) || 0
        if (days > 7) return 'ag-cell-error ag-cell-bold'
        if (days > 3) return 'ag-cell-warning'
        return ''
      },
      width: 130,
    },
    {
      headerName: t('grids.columns.holdInitiatedBy'),
      field: 'hold_initiated_by',
      editable: false,
      width: 140,
    },
    {
      headerName: t('grids.columns.holdApprovedBy'),
      field: 'hold_approved_by',
      editable: false,
      width: 140,
    },
    {
      headerName: t('grids.columns.resumedBy'),
      field: 'resumed_by',
      editable: false,
      width: 130,
    },
    {
      headerName: t('grids.columns.notes'),
      field: 'notes',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      width: 200,
    },
  ])

  watch(entries, () => applyFilters(), { immediate: true })

  return {
    kpiStore,
    gridRef,
    unsavedChanges,
    saving,
    snackbar,
    dateFilter,
    statusFilter,
    reasonFilter,
    holdReasons: HOLD_REASON_CODES,
    holdStatusOptions,
    entries,
    workOrders,
    filteredEntries,
    hasUnsavedChanges,
    activeCount,
    resumedCount,
    pendingHoldApprovalsCount,
    pendingResumeApprovalsCount,
    pendingApprovalsCount,
    avgDaysOnHold,
    columnDefs,
    applyFilters,
    showSnackbar,
  }
}
