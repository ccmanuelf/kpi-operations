/**
 * Composable for DowntimeEntryGrid script logic — reactive state,
 * column definitions, CRUD, paste handling, filters, summary stats,
 * read-back confirmation.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProductionDataStore } from '@/stores/productionDataStore'
import { format } from 'date-fns'

export interface DowntimeRow {
  downtime_id?: string | number
  downtime_start_time?: string
  work_order_id?: string | number
  downtime_reason?: string
  category?: string
  duration_hours?: number
  impact_on_wip_hours?: number
  is_resolved?: boolean
  resolution_notes?: string
  line_id?: string | number
  _hasChanges?: boolean
  _isNew?: boolean
  [key: string]: unknown
}

export interface WorkOrderRef {
  work_order_id?: string | number
  work_order_number?: string
  [key: string]: unknown
}

export interface DowntimeReasonRef {
  reason_name?: string
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
  type: 'datetime' | 'text' | 'number' | 'boolean'
  displayValue?: string | number
}

export default function useDowntimeGridData() {
  const { t } = useI18n()
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
  const categoryFilter = ref<string | null>(null)
  const statusFilter = ref<'Resolved' | 'Unresolved' | null>(null)
  const lineFilter = ref<string | number | null>(null)

  const categories: string[] = [
    'Planned Maintenance',
    'Unplanned Breakdown',
    'Changeover',
    'Material Shortage',
    'Quality Issue',
    'Operator Absence',
    'Other',
  ]

  const entries = computed<DowntimeRow[]>(
    () => (kpiStore.downtimeEntries as DowntimeRow[]) || [],
  )
  const workOrders = computed<WorkOrderRef[]>(
    () => (kpiStore.workOrders as WorkOrderRef[]) || [],
  )
  const downtimeReasons = computed<DowntimeReasonRef[]>(
    () => (kpiStore.downtimeReasons as DowntimeReasonRef[]) || [],
  )
  const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

  const filteredEntries = ref<DowntimeRow[]>([])

  const totalHours = computed(() =>
    filteredEntries.value.reduce((sum, e) => sum + (e.duration_hours || 0), 0),
  )

  const unresolvedCount = computed(
    () => filteredEntries.value.filter((e) => !e.is_resolved).length,
  )

  const resolvedCount = computed(
    () => filteredEntries.value.filter((e) => e.is_resolved).length,
  )

  const confirmationFieldConfig = computed<ConfirmationField[]>(() => {
    const workOrderNumber =
      workOrders.value.find((w) => w.work_order_id === pendingData.value.work_order_id)
        ?.work_order_number || 'N/A'

    return [
      { key: 'downtime_start_time', label: t('grids.columns.startTime'), type: 'datetime' },
      {
        key: 'work_order_id',
        label: t('grids.columns.workOrder'),
        type: 'text',
        displayValue: workOrderNumber,
      },
      { key: 'downtime_reason', label: t('grids.columns.reason'), type: 'text' },
      { key: 'category', label: t('grids.columns.category'), type: 'text' },
      { key: 'duration_hours', label: t('grids.columns.duration'), type: 'number' },
      { key: 'impact_on_wip_hours', label: t('grids.columns.wipImpact'), type: 'number' },
      { key: 'is_resolved', label: t('grids.columns.resolved'), type: 'boolean' },
      {
        key: 'resolution_notes',
        label: t('grids.columns.resolutionNotes'),
        type: 'text',
      },
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
      if (rowData.downtime_id !== undefined)
        unsavedChanges.value.delete(rowData.downtime_id)
      showSnackbar(t('grids.downtime.entryRemoved'), 'info')
      return
    }

    if (rowData.downtime_id === undefined) return

    try {
      await kpiStore.deleteDowntimeEntry(rowData.downtime_id)
      api.applyTransaction({ remove: [rowData] })
      unsavedChanges.value.delete(rowData.downtime_id)
      showSnackbar(t('grids.downtime.deleteSuccess'), 'success')
    } catch (error) {
      const ax = error as { message?: string }
      showSnackbar(t('grids.downtime.deleteError', { error: ax?.message || '' }), 'error')
    }
  }

  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.startTime'),
      field: 'downtime_start_time',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      valueFormatter: (params: { value?: string }) =>
        params.value ? format(new Date(params.value), 'MMM dd, yyyy HH:mm') : '',
      cellClass: 'font-weight-bold',
      pinned: 'left' as const,
      width: 180,
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
        return wo?.work_order_number || (params.value as string) || 'N/A'
      },
      width: 150,
    },
    {
      headerName: t('grids.columns.reason'),
      field: 'downtime_reason',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: downtimeReasons.value.map((r) => r.reason_name),
      }),
      width: 200,
    },
    {
      headerName: t('grids.columns.category'),
      field: 'category',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: categories },
      cellClass: (params: { value?: string }) => {
        const classes: Record<string, string> = {
          'Planned Maintenance': 'ag-cell-info',
          'Unplanned Breakdown': 'ag-cell-error ag-cell-bold',
          Changeover: 'ag-cell-warning-light',
          'Material Shortage': 'ag-cell-warning',
          'Quality Issue': 'ag-cell-pink',
          'Operator Absence': 'ag-cell-purple',
        }
        return classes[params.value || ''] || ''
      },
      width: 180,
    },
    {
      headerName: t('grids.columns.durationHrs'),
      field: 'duration_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      valueFormatter: (params: { value?: number }) =>
        params.value ? params.value.toFixed(2) : '0.00',
      cellClass: (params: { value?: number }) => {
        const hours = params.value || 0
        if (hours >= 4) return 'ag-cell-error ag-cell-bold'
        if (hours >= 2) return 'ag-cell-warning'
        return ''
      },
      width: 140,
    },
    {
      headerName: t('grids.columns.wipImpactHrs'),
      field: 'impact_on_wip_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      valueFormatter: (params: { value?: number }) =>
        params.value ? params.value.toFixed(2) : '0.00',
      width: 150,
    },
    {
      headerName: t('grids.columns.status'),
      field: 'is_resolved',
      editable: true,
      cellRenderer: (params: { value?: boolean }) =>
        params.value ? t('grids.downtime.resolved') : t('grids.downtime.unresolved'),
      cellEditor: 'agCheckboxCellEditor',
      cellClass: (params: { value?: boolean }) =>
        params.value ? 'ag-cell-success ag-cell-bold' : 'ag-cell-error ag-cell-bold',
      width: 130,
    },
    {
      headerName: t('grids.columns.resolutionNotes'),
      field: 'resolution_notes',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      width: 250,
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
    const rowId = event.data.downtime_id || event.node.id
    if (rowId !== undefined) unsavedChanges.value.add(rowId)
    event.data._hasChanges = true
    event.api.refreshCells({ rowNodes: [event.node], force: true })
  }

  const addNewEntry = (): void => {
    const newEntry: DowntimeRow = {
      downtime_id: `temp_${Date.now()}`,
      downtime_start_time: new Date().toISOString(),
      work_order_id: workOrders.value[0]?.work_order_id || undefined,
      downtime_reason: downtimeReasons.value[0]?.reason_name || '',
      category: 'Unplanned Breakdown',
      duration_hours: 0,
      impact_on_wip_hours: 0,
      is_resolved: false,
      resolution_notes: '',
      _isNew: true,
      _hasChanges: true,
    }

    const api = gridRef.value?.gridApi
    if (api && newEntry.downtime_id !== undefined) {
      api.applyTransaction({ add: [newEntry], addIndex: 0 })
      unsavedChanges.value.add(newEntry.downtime_id)

      setTimeout(() => {
        api.startEditingCell({ rowIndex: 0, colKey: 'downtime_start_time' })
      }, 100)
    }
  }

  const applyFilters = (): void => {
    let filtered = [...entries.value]

    if (dateFilter.value) {
      filtered = filtered.filter((e) => {
        if (!e.downtime_start_time) return false
        const entryDate = new Date(e.downtime_start_time).toISOString().split('T')[0]
        return entryDate === dateFilter.value
      })
    }
    if (categoryFilter.value) {
      filtered = filtered.filter((e) => e.category === categoryFilter.value)
    }
    if (statusFilter.value) {
      const isResolved = statusFilter.value === 'Resolved'
      filtered = filtered.filter((e) => e.is_resolved === isResolved)
    }
    if (lineFilter.value) {
      filtered = filtered.filter((e) => e.line_id === lineFilter.value)
    }

    filteredEntries.value = filtered
  }

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

    pendingRows.value = rowsToSave
    pendingData.value = rowsToSave[0]
    showConfirmDialog.value = true
  }

  const onConfirmSave = async (): Promise<void> => {
    showConfirmDialog.value = false
    saving.value = true

    let successCount = 0
    let errorCount = 0

    try {
      for (const row of pendingRows.value) {
        const data = {
          work_order_id: row.work_order_id,
          downtime_start_time: row.downtime_start_time,
          downtime_reason: row.downtime_reason,
          category: row.category,
          duration_hours: row.duration_hours || 0,
          impact_on_wip_hours: row.impact_on_wip_hours || 0,
          is_resolved: row.is_resolved || false,
          resolution_notes: row.resolution_notes || '',
        }

        try {
          if (row._isNew) {
            const result = await kpiStore.createDowntimeEntry(data)
            if (result.success && result.data) {
              row.downtime_id = (result.data as DowntimeRow).downtime_id
              row._isNew = false
              successCount++
            } else {
              errorCount++
            }
          } else if (row.downtime_id !== undefined) {
            const result = await kpiStore.updateDowntimeEntry(row.downtime_id, data)
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
          if (row.downtime_id !== undefined) unsavedChanges.value.delete(row.downtime_id)
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
      downtime_id: `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      downtime_start_time: row.downtime_start_time || new Date().toISOString(),
      work_order_id: row.work_order_id || workOrders.value[0]?.work_order_id || undefined,
      downtime_reason: row.downtime_reason || downtimeReasons.value[0]?.reason_name || '',
      category: row.category || 'Unplanned Breakdown',
      duration_hours: row.duration_hours || 0,
      impact_on_wip_hours: row.impact_on_wip_hours || 0,
      is_resolved: row.is_resolved || false,
      resolution_notes: row.resolution_notes || '',
      _isNew: true,
      _hasChanges: true,
    }))

    api.applyTransaction({ add: preparedRows, addIndex: 0 })
    preparedRows.forEach((row) => {
      if (row.downtime_id !== undefined) unsavedChanges.value.add(row.downtime_id)
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
    categoryFilter,
    statusFilter,
    lineFilter,
    categories,
    filteredEntries,
    hasUnsavedChanges,
    columnDefs,
    totalHours,
    unresolvedCount,
    resolvedCount,
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
