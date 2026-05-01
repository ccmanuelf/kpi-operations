/**
 * Composable for DowntimeEntryGrid script logic — reactive state,
 * column definitions, CRUD, paste handling, filters, summary stats,
 * read-back confirmation.
 *
 * Backend alignment: payload matches backend/schemas/downtime.py
 * DowntimeEventCreate. client_id derived from authStore (operators)
 * or kpiSelectionStore.selectedClient (admin). Reasons use the
 * canonical DowntimeReasonEnum codes; legacy UI categories were
 * removed in the 2026-05-01 entry-audit migration.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/authStore'
import { useKPIStore } from '@/stores/kpi'
import { useProductionDataStore } from '@/stores/productionDataStore'
import { format } from 'date-fns'

export interface DowntimeRow {
  downtime_entry_id?: string | number
  client_id?: string
  shift_date?: string
  work_order_id?: string | number | null
  line_id?: string | number | null
  downtime_reason?: string
  downtime_duration_minutes?: number
  machine_id?: string | null
  equipment_code?: string | null
  root_cause_category?: string | null
  corrective_action?: string | null
  notes?: string | null
  _hasChanges?: boolean
  _isNew?: boolean
  [key: string]: unknown
}

export interface WorkOrderRef {
  work_order_id?: string | number
  work_order_number?: string
  [key: string]: unknown
}

interface AGGridApi {
  sizeColumnsToFit: () => void
  applyTransaction: (params: { add?: DowntimeRow[]; remove?: DowntimeRow[]; addIndex?: number }) => void
  startEditingCell: (params: { rowIndex: number; colKey: string }) => void
  refreshCells: (params?: { rowNodes?: unknown[]; force?: boolean }) => void
  forEachNode: (cb: (node: { data: DowntimeRow }) => void) => void
}

interface AGGridRef {
  gridApi?: AGGridApi
}

interface CellValueChangedEvent {
  data: DowntimeRow
  node: { id: string }
  api: AGGridApi
}

interface SnackbarState {
  show: boolean
  message: string
  color: string
}

interface PasteData {
  parsedData: unknown
  convertedRows: DowntimeRow[]
  validationResult: unknown
  columnMapping: unknown
  [key: string]: unknown
}

export interface ConfirmationField {
  key: string
  label: string
  type: 'date' | 'text' | 'number'
  displayValue?: string | number
}

// Canonical DowntimeReasonEnum codes (mirrors backend/schemas/downtime.py:13-22).
export const DOWNTIME_REASON_CODES: string[] = [
  'EQUIPMENT_FAILURE',
  'MATERIAL_SHORTAGE',
  'SETUP_CHANGEOVER',
  'QUALITY_HOLD',
  'MAINTENANCE',
  'POWER_OUTAGE',
  'OTHER',
]

const DEFAULT_REASON = 'OTHER'

export default function useDowntimeGridData() {
  const { t } = useI18n()
  const authStore = useAuthStore()
  const kpiSelectionStore = useKPIStore()
  const kpiStore = useProductionDataStore()
  const gridRef = ref<AGGridRef | null>(null)
  const unsavedChanges = ref<Set<string | number>>(new Set())
  const saving = ref(false)
  const snackbar = ref<SnackbarState>({ show: false, message: '', color: 'success' })

  const showConfirmDialog = ref(false)
  const pendingData = ref<DowntimeRow>({})
  const pendingRows = ref<DowntimeRow[]>([])

  const showPasteDialog = ref(false)
  const parsedPasteData = ref<unknown | null>(null)
  const convertedPasteRows = ref<DowntimeRow[]>([])
  const pasteValidationResult = ref<unknown | null>(null)
  const pasteColumnMapping = ref<unknown | null>(null)

  const pendingRowsCount = computed(() => pendingRows.value.length)

  const dateFilter = ref<string | null>(null)
  const reasonFilter = ref<string | null>(null)
  const lineFilter = ref<string | number | null>(null)

  // Operators inherit client_id from auth; admin users fall back to KPI store selection.
  const activeClientId = (): string | number | null => {
    return authStore.user?.client_id_assigned ?? kpiSelectionStore.selectedClient ?? null
  }

  const entries = computed<DowntimeRow[]>(
    () => (kpiStore.downtimeEntries as DowntimeRow[]) || [],
  )
  const workOrders = computed<WorkOrderRef[]>(
    () => (kpiStore.workOrders as WorkOrderRef[]) || [],
  )
  const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

  const filteredEntries = ref<DowntimeRow[]>([])

  const totalHours = computed(() =>
    filteredEntries.value.reduce(
      (sum, e) => sum + (e.downtime_duration_minutes || 0) / 60,
      0,
    ),
  )

  const totalMinutes = computed(() =>
    filteredEntries.value.reduce(
      (sum, e) => sum + (e.downtime_duration_minutes || 0),
      0,
    ),
  )

  const eventCount = computed(() => filteredEntries.value.length)

  const confirmationFieldConfig = computed<ConfirmationField[]>(() => {
    const workOrderNumber =
      workOrders.value.find((w) => w.work_order_id === pendingData.value.work_order_id)
        ?.work_order_number || 'N/A'

    return [
      { key: 'shift_date', label: t('grids.columns.shiftDate'), type: 'date' },
      {
        key: 'work_order_id',
        label: t('grids.columns.workOrder'),
        type: 'text',
        displayValue: workOrderNumber,
      },
      { key: 'downtime_reason', label: t('grids.columns.reason'), type: 'text' },
      {
        key: 'downtime_duration_minutes',
        label: t('grids.columns.durationMin'),
        type: 'number',
      },
      { key: 'machine_id', label: t('grids.columns.machineId'), type: 'text' },
      { key: 'equipment_code', label: t('grids.columns.equipmentCode'), type: 'text' },
      {
        key: 'root_cause_category',
        label: t('grids.columns.rootCauseCategory'),
        type: 'text',
      },
      {
        key: 'corrective_action',
        label: t('grids.columns.correctiveAction'),
        type: 'text',
      },
      { key: 'notes', label: t('grids.columns.notes'), type: 'text' },
    ]
  })

  const showSnackbar = (message: string, color: string = 'success'): void => {
    snackbar.value = { show: true, message, color }
  }

  const deleteEntry = async (rowData: DowntimeRow): Promise<void> => {
    if (!confirm(t('grids.downtime.confirmDelete'))) return

    const api = gridRef.value?.gridApi
    if (!api) return

    if (rowData._isNew) {
      api.applyTransaction({ remove: [rowData] })
      if (rowData.downtime_entry_id !== undefined)
        unsavedChanges.value.delete(rowData.downtime_entry_id)
      showSnackbar(t('grids.downtime.entryRemoved'), 'info')
      return
    }

    if (rowData.downtime_entry_id === undefined) return

    try {
      await kpiStore.deleteDowntimeEntry(rowData.downtime_entry_id)
      api.applyTransaction({ remove: [rowData] })
      unsavedChanges.value.delete(rowData.downtime_entry_id)
      showSnackbar(t('grids.downtime.deleteSuccess'), 'success')
    } catch (error) {
      const ax = error as { message?: string }
      showSnackbar(t('grids.downtime.deleteError', { error: ax?.message || '' }), 'error')
    }
  }

  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.shiftDate'),
      field: 'shift_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      valueFormatter: (params: { value?: string }) =>
        params.value ? format(new Date(params.value), 'MMM dd, yyyy') : '',
      cellClass: 'font-weight-bold',
      pinned: 'left' as const,
      width: 140,
      sort: 'desc' as const,
    },
    {
      headerName: t('grids.columns.workOrder'),
      field: 'work_order_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: workOrders.value.map((w) => w.work_order_id),
      }),
      valueFormatter: (params: { value?: string | number }) => {
        const wo = workOrders.value.find((w) => w.work_order_id === params.value)
        return wo?.work_order_number || (params.value as string) || ''
      },
      width: 150,
    },
    {
      headerName: t('grids.columns.reason'),
      field: 'downtime_reason',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: DOWNTIME_REASON_CODES },
      cellClass: (params: { value?: string }) => {
        const classes: Record<string, string> = {
          EQUIPMENT_FAILURE: 'ag-cell-error ag-cell-bold',
          MATERIAL_SHORTAGE: 'ag-cell-warning',
          SETUP_CHANGEOVER: 'ag-cell-warning-light',
          QUALITY_HOLD: 'ag-cell-pink',
          MAINTENANCE: 'ag-cell-info',
          POWER_OUTAGE: 'ag-cell-error ag-cell-bold',
          OTHER: 'ag-cell-purple',
        }
        return classes[params.value || ''] || ''
      },
      width: 180,
    },
    {
      headerName: t('grids.columns.durationMin'),
      field: 'downtime_duration_minutes',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 1, max: 1440, precision: 0 },
      valueFormatter: (params: { value?: number }) =>
        params.value !== undefined && params.value !== null ? String(params.value) : '0',
      cellClass: (params: { value?: number }) => {
        const minutes = params.value || 0
        if (minutes >= 240) return 'ag-cell-error ag-cell-bold'
        if (minutes >= 120) return 'ag-cell-warning'
        return ''
      },
      width: 140,
    },
    {
      headerName: t('grids.columns.machineId'),
      field: 'machine_id',
      editable: true,
      width: 140,
    },
    {
      headerName: t('grids.columns.equipmentCode'),
      field: 'equipment_code',
      editable: true,
      width: 140,
    },
    {
      headerName: t('grids.columns.rootCauseCategory'),
      field: 'root_cause_category',
      editable: true,
      width: 160,
    },
    {
      headerName: t('grids.columns.correctiveAction'),
      field: 'corrective_action',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      width: 220,
    },
    {
      headerName: t('grids.columns.notes'),
      field: 'notes',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      width: 200,
    },
    {
      headerName: t('grids.columns.actions'),
      field: 'actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params: { data: DowntimeRow }) => {
        const div = document.createElement('div')
        div.innerHTML = `
          <button class="ag-grid-delete-btn" style="
            background: #c62828;
            color: white;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
          ">${t('common.delete')}</button>
        `
        div
          .querySelector('.ag-grid-delete-btn')
          ?.addEventListener('click', () => deleteEntry(params.data))
        return div
      },
      width: 100,
      pinned: 'right' as const,
    },
  ])

  const onGridReady = (params: { api: AGGridApi }): void => {
    setTimeout(() => params.api.sizeColumnsToFit(), 100)
  }

  const onCellValueChanged = (event: CellValueChangedEvent): void => {
    const rowId = event.data.downtime_entry_id || event.node.id
    if (rowId !== undefined) unsavedChanges.value.add(rowId)
    event.data._hasChanges = true
    event.api.refreshCells({ rowNodes: [event.node], force: true })
  }

  const addNewEntry = (): void => {
    const newEntry: DowntimeRow = {
      downtime_entry_id: `temp_${Date.now()}`,
      shift_date: format(new Date(), 'yyyy-MM-dd'),
      work_order_id: workOrders.value[0]?.work_order_id || null,
      downtime_reason: DEFAULT_REASON,
      downtime_duration_minutes: 0,
      machine_id: null,
      equipment_code: null,
      root_cause_category: null,
      corrective_action: null,
      notes: null,
      _isNew: true,
      _hasChanges: true,
    }

    const api = gridRef.value?.gridApi
    if (api && newEntry.downtime_entry_id !== undefined) {
      api.applyTransaction({ add: [newEntry], addIndex: 0 })
      unsavedChanges.value.add(newEntry.downtime_entry_id)

      setTimeout(() => {
        api.startEditingCell({ rowIndex: 0, colKey: 'shift_date' })
      }, 100)
    }
  }

  const applyFilters = (): void => {
    let filtered = [...entries.value]

    if (dateFilter.value) {
      filtered = filtered.filter((e) => {
        if (!e.shift_date) return false
        const entryDate = new Date(e.shift_date).toISOString().split('T')[0]
        return entryDate === dateFilter.value
      })
    }
    if (reasonFilter.value) {
      filtered = filtered.filter((e) => e.downtime_reason === reasonFilter.value)
    }
    if (lineFilter.value) {
      filtered = filtered.filter((e) => e.line_id === lineFilter.value)
    }

    filteredEntries.value = filtered
  }

  const buildPayload = (
    row: DowntimeRow,
    clientId: string | number,
  ): Record<string, unknown> => ({
    client_id: String(clientId),
    work_order_id: row.work_order_id || undefined,
    line_id: row.line_id ? Number(row.line_id) : undefined,
    shift_date: row.shift_date,
    downtime_reason: row.downtime_reason || DEFAULT_REASON,
    downtime_duration_minutes: row.downtime_duration_minutes || 0,
    machine_id: row.machine_id || undefined,
    equipment_code: row.equipment_code || undefined,
    root_cause_category: row.root_cause_category || undefined,
    corrective_action: row.corrective_action || undefined,
    notes: row.notes || undefined,
  })

  const saveChanges = async (): Promise<void> => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const rowsToSave: DowntimeRow[] = []
    gridApi.forEachNode((node) => {
      if (node.data._hasChanges) rowsToSave.push(node.data)
    })

    if (rowsToSave.length === 0) {
      showSnackbar(t('grids.downtime.noChanges'), 'info')
      return
    }

    if (!activeClientId()) {
      showSnackbar(t('grids.downtime.errors.noClient'), 'error')
      return
    }

    pendingRows.value = rowsToSave
    pendingData.value = rowsToSave[0]
    showConfirmDialog.value = true
  }

  const onConfirmSave = async (): Promise<void> => {
    showConfirmDialog.value = false
    saving.value = true

    let successCount = 0
    let errorCount = 0

    const clientId = activeClientId()
    if (!clientId) {
      saving.value = false
      pendingRows.value = []
      pendingData.value = {}
      showSnackbar(t('grids.downtime.errors.noClient'), 'error')
      return
    }

    try {
      for (const row of pendingRows.value) {
        const data = buildPayload(row, clientId)

        try {
          if (row._isNew) {
            const result = await kpiStore.createDowntimeEntry(data)
            if (result.success && result.data) {
              row.downtime_entry_id =
                (result.data as DowntimeRow).downtime_entry_id ?? row.downtime_entry_id
              row._isNew = false
              successCount++
            } else {
              errorCount++
            }
          } else if (row.downtime_entry_id !== undefined) {
            const result = await kpiStore.updateDowntimeEntry(row.downtime_entry_id, data)
            if (result.success) {
              successCount++
            } else {
              errorCount++
            }
          } else {
            errorCount++
            continue
          }

          row._hasChanges = false
          if (row.downtime_entry_id !== undefined)
            unsavedChanges.value.delete(row.downtime_entry_id)
        } catch (err) {
          errorCount++
          // eslint-disable-next-line no-console
          console.error('Error saving row:', err)
        }
      }

      await kpiStore.fetchDowntimeEntries()
      applyFilters()

      if (errorCount === 0) {
        showSnackbar(t('grids.downtime.saveSuccess', { count: successCount }), 'success')
      } else {
        showSnackbar(
          t('grids.downtime.savePartial', {
            success: successCount,
            failed: errorCount,
          }),
          'warning',
        )
      }
    } catch (error) {
      const ax = error as { message?: string }
      showSnackbar(t('grids.downtime.saveError', { error: ax?.message || '' }), 'error')
    } finally {
      saving.value = false
      pendingRows.value = []
      pendingData.value = {}
    }
  }

  const onCancelSave = (): void => {
    showConfirmDialog.value = false
    pendingRows.value = []
    pendingData.value = {}
    showSnackbar(t('grids.downtime.saveCancelled'), 'info')
  }

  const onRowsPasted = (pasteData: PasteData): void => {
    parsedPasteData.value = pasteData.parsedData
    convertedPasteRows.value = pasteData.convertedRows
    pasteValidationResult.value = pasteData.validationResult
    pasteColumnMapping.value = pasteData.columnMapping
    showPasteDialog.value = true
  }

  const onPasteConfirm = (rowsToAdd: Partial<DowntimeRow>[]): void => {
    const api = gridRef.value?.gridApi
    if (!api) return

    const preparedRows: DowntimeRow[] = rowsToAdd.map((row) => ({
      downtime_entry_id: `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      shift_date: row.shift_date || format(new Date(), 'yyyy-MM-dd'),
      work_order_id: row.work_order_id || workOrders.value[0]?.work_order_id || null,
      downtime_reason: row.downtime_reason || DEFAULT_REASON,
      downtime_duration_minutes: row.downtime_duration_minutes ?? 0,
      machine_id: row.machine_id || null,
      equipment_code: row.equipment_code || null,
      root_cause_category: row.root_cause_category || null,
      corrective_action: row.corrective_action || null,
      notes: row.notes || null,
      _isNew: true,
      _hasChanges: true,
    }))

    api.applyTransaction({ add: preparedRows, addIndex: 0 })
    preparedRows.forEach((row) => {
      if (row.downtime_entry_id !== undefined)
        unsavedChanges.value.add(row.downtime_entry_id)
    })
    showPasteDialog.value = false
    showSnackbar(t('paste.rowsAdded', { count: preparedRows.length }), 'success')
  }

  const onPasteCancel = (): void => {
    showPasteDialog.value = false
    parsedPasteData.value = null
    convertedPasteRows.value = []
    pasteValidationResult.value = null
    pasteColumnMapping.value = null
  }

  watch(entries, () => applyFilters(), { immediate: true })

  onMounted(async () => {
    await kpiStore.fetchReferenceData()
    await kpiStore.fetchDowntimeEntries()
    applyFilters()
  })

  return {
    gridRef,
    unsavedChanges,
    saving,
    snackbar,
    showConfirmDialog,
    pendingData,
    pendingRowsCount,
    confirmationFieldConfig,
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    dateFilter,
    reasonFilter,
    lineFilter,
    reasons: DOWNTIME_REASON_CODES,
    filteredEntries,
    hasUnsavedChanges,
    columnDefs,
    totalHours,
    totalMinutes,
    eventCount,
    onGridReady,
    onCellValueChanged,
    addNewEntry,
    saveChanges,
    onConfirmSave,
    onCancelSave,
    applyFilters,
    onRowsPasted,
    onPasteConfirm,
    onPasteCancel,
  }
}
