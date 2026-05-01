/**
 * Composable for QualityEntryGrid script logic — reactive state,
 * column definitions, CRUD, paste handling, summary stats (FPY,
 * PPM), read-back confirmation.
 *
 * Backend alignment: payload matches backend/schemas/quality.py
 * QualityInspectionCreate. client_id derived from authStore (operators)
 * or kpiStore.selectedClient (admin). shift_date is the user-entered
 * row date and also drives inspection_date by default.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/authStore'
import { useKPIStore } from '@/stores/kpi'
import api from '@/services/api'
import { format } from 'date-fns'

export interface QualityRow {
  quality_entry_id?: string | number
  shift_date?: string
  work_order_id?: string | number
  units_inspected?: number
  units_passed?: number
  units_defective?: number
  total_defects_count?: number
  inspection_stage?: string
  units_scrapped?: number
  units_reworked?: number
  notes?: string
  _hasChanges?: boolean
  _isNew?: boolean
  [key: string]: unknown
}

interface AGGridApi {
  sizeColumnsToFit: () => void
  applyTransaction: (params: { add?: QualityRow[]; remove?: QualityRow[]; addIndex?: number }) => void
  startEditingCell: (params: { rowIndex: number; colKey: string }) => void
  refreshCells: (params?: { rowNodes?: unknown[]; columns?: string[]; force?: boolean }) => void
  forEachNode: (cb: (node: { data: QualityRow }) => void) => void
}

interface AGGridRef {
  gridApi?: AGGridApi
}

interface SnackbarState {
  show: boolean
  message: string
  color: string
}

interface PasteData {
  parsedData: unknown
  convertedRows: QualityRow[]
  validationResult: unknown
  columnMapping: unknown
  [key: string]: unknown
}

export interface ConfirmationField {
  key: string
  label: string
  type: 'date' | 'text' | 'number' | 'percentage'
  displayValue?: string | number
}

export default function useQualityGridData() {
  const { t } = useI18n()
  const authStore = useAuthStore()
  const kpiStore = useKPIStore()

  const gridRef = ref<AGGridRef | null>(null)
  const qualityData = ref<QualityRow[]>([])
  const saving = ref(false)
  const snackbar = ref<SnackbarState>({ show: false, message: '', color: 'success' })

  const showConfirmDialog = ref(false)
  const pendingData = ref<QualityRow>({})
  const pendingRows = ref<QualityRow[]>([])

  const showPasteDialog = ref(false)
  const parsedPasteData = ref<unknown | null>(null)
  const convertedPasteRows = ref<QualityRow[]>([])
  const pasteValidationResult = ref<unknown | null>(null)
  const pasteColumnMapping = ref<unknown | null>(null)

  const pendingRowsCount = computed(() => pendingRows.value.length)

  // Operators inherit client_id from auth; admin users fall back to KPI store selection.
  const activeClientId = (): string | number | null => {
    return authStore.user?.client_id_assigned ?? kpiStore.selectedClient ?? null
  }

  const computeUnitsPassed = (row: QualityRow): number => {
    const inspected = row.units_inspected ?? 0
    const defective = row.units_defective ?? 0
    return Math.max(0, inspected - defective)
  }

  const confirmationFieldConfig = computed<ConfirmationField[]>(() => {
    const inspected = pendingData.value.units_inspected || 0
    const defects = pendingData.value.units_defective || 0
    const fpy = inspected > 0 ? ((1 - defects / inspected) * 100).toFixed(2) : '0.00'
    const ppm = inspected > 0 ? Math.round((defects / inspected) * 1000000) : 0

    return [
      { key: 'shift_date', label: t('grids.columns.shiftDate'), type: 'date' },
      { key: 'work_order_id', label: t('grids.columns.workOrder'), type: 'text' },
      { key: 'units_inspected', label: t('grids.columns.inspectedQty'), type: 'number' },
      { key: 'units_defective', label: t('grids.columns.defectQty'), type: 'number' },
      { key: 'total_defects_count', label: t('grids.columns.totalDefectsCount'), type: 'number' },
      { key: 'fpy_calculated', label: t('grids.columns.fpyPercent'), type: 'percentage', displayValue: fpy },
      { key: 'ppm_calculated', label: t('grids.columns.ppm'), type: 'number', displayValue: ppm.toLocaleString() },
      { key: 'inspection_stage', label: t('grids.columns.inspectionStage'), type: 'text' },
      { key: 'notes', label: t('grids.columns.notes'), type: 'text' },
    ]
  })

  const hasChanges = computed(() => qualityData.value.some((row) => row._hasChanges))

  const changedRowsCount = computed(
    () => qualityData.value.filter((row) => row._hasChanges).length,
  )

  const totalInspected = computed(() =>
    qualityData.value.reduce((sum, row) => sum + (row.units_inspected || 0), 0),
  )

  const totalDefects = computed(() =>
    qualityData.value.reduce((sum, row) => sum + (row.units_defective || 0), 0),
  )

  const avgFPY = computed(() => {
    if (totalInspected.value === 0) return 0
    return ((totalInspected.value - totalDefects.value) / totalInspected.value) * 100
  })

  const avgPPM = computed(() => {
    if (totalInspected.value === 0) return 0
    return (totalDefects.value / totalInspected.value) * 1000000
  })

  const showSnackbar = (message: string, color: string = 'success'): void => {
    snackbar.value = { show: true, message, color }
  }

  const deleteRow = (rowData: QualityRow): void => {
    if (!confirm(t('grids.quality.deleteConfirm'))) return

    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    gridApi.applyTransaction({ remove: [rowData] })
    showSnackbar(t('grids.quality.inspectionRemoved'), 'info')
  }

  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.shiftDate'),
      field: 'shift_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      valueFormatter: (params: { value?: string }) =>
        params.value ? format(new Date(params.value), 'MMM dd, yyyy') : '',
      width: 140,
    },
    {
      headerName: t('grids.columns.workOrder'),
      field: 'work_order_id',
      editable: true,
      width: 150,
    },
    {
      headerName: t('grids.columns.inspectedQty'),
      field: 'units_inspected',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 1, precision: 0 },
      valueFormatter: (params: { value?: number }) =>
        params.value ? params.value.toLocaleString() : '0',
      width: 130,
    },
    {
      headerName: t('grids.columns.passedQty'),
      field: 'units_passed',
      editable: false,
      type: 'numericColumn',
      valueGetter: (params: { data: QualityRow }) => computeUnitsPassed(params.data),
      valueFormatter: (params: { value?: number }) =>
        params.value !== undefined ? params.value.toLocaleString() : '0',
      width: 110,
    },
    {
      headerName: t('grids.columns.defectQty'),
      field: 'units_defective',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      cellClass: (params: { value?: number }) =>
        (params.value ?? 0) > 0 ? 'ag-cell-error ag-cell-bold' : '',
      width: 120,
    },
    {
      headerName: t('grids.columns.totalDefectsCount'),
      field: 'total_defects_count',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      width: 130,
    },
    {
      headerName: t('grids.columns.fpyPercent'),
      field: 'fpy',
      editable: false,
      valueGetter: (params: { data: QualityRow }) => {
        const inspected = params.data.units_inspected || 0
        const defects = params.data.units_defective || 0
        if (inspected === 0) return 0
        return ((1 - defects / inspected) * 100).toFixed(2)
      },
      cellClass: (params: { value?: string | number }) => {
        const fpy = parseFloat(String(params.value ?? 0))
        if (fpy >= 99) return 'ag-cell-success ag-cell-bold'
        if (fpy >= 95) return 'ag-cell-warning ag-cell-bold'
        return 'ag-cell-error ag-cell-bold'
      },
      width: 110,
    },
    {
      headerName: t('grids.columns.ppm'),
      field: 'ppm',
      editable: false,
      valueGetter: (params: { data: QualityRow }) => {
        const inspected = params.data.units_inspected || 0
        const defects = params.data.units_defective || 0
        if (inspected === 0) return 0
        return Math.round((defects / inspected) * 1000000)
      },
      valueFormatter: (params: { value?: number }) =>
        params.value ? params.value.toLocaleString() : '0',
      cellClass: (params: { value?: number }) => {
        const ppm = params.value || 0
        if (ppm === 0) return 'ag-cell-success'
        if (ppm <= 10000) return 'ag-cell-warning'
        return 'ag-cell-error'
      },
      width: 110,
    },
    {
      headerName: t('grids.columns.inspectionStage'),
      field: 'inspection_stage',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: ['Incoming', 'In-Process', 'Final'] },
      width: 130,
    },
    {
      headerName: t('grids.columns.scrapped'),
      field: 'units_scrapped',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      width: 110,
    },
    {
      headerName: t('grids.columns.reworked'),
      field: 'units_reworked',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      width: 110,
    },
    {
      headerName: t('grids.columns.notes'),
      field: 'notes',
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
      cellRenderer: (params: { data: QualityRow }) => {
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
          ?.addEventListener('click', () => deleteRow(params.data))
        return div
      },
      width: 100,
      pinned: 'right' as const,
    },
  ])

  const onGridReady = (params: { api: AGGridApi }): void => {
    setTimeout(() => params.api.sizeColumnsToFit(), 100)
  }

  const onCellValueChanged = (event: {
    data: QualityRow
    column: { colId: string }
    node: unknown
    api: AGGridApi
  }): void => {
    event.data._hasChanges = true

    if (event.column.colId === 'units_inspected' || event.column.colId === 'units_defective') {
      event.api.refreshCells({
        rowNodes: [event.node],
        columns: ['units_passed', 'fpy', 'ppm'],
        force: true,
      })
      // Default total_defects_count to units_defective when defects entered for the first time.
      if (event.column.colId === 'units_defective' && (event.data.total_defects_count ?? 0) === 0) {
        event.data.total_defects_count = event.data.units_defective ?? 0
        event.api.refreshCells({
          rowNodes: [event.node],
          columns: ['total_defects_count'],
          force: true,
        })
      }
    }
  }

  const addRow = (): void => {
    const newRow: QualityRow = {
      quality_entry_id: `temp_${Date.now()}`,
      shift_date: format(new Date(), 'yyyy-MM-dd'),
      work_order_id: '',
      units_inspected: 0,
      units_defective: 0,
      total_defects_count: 0,
      inspection_stage: 'Final',
      units_scrapped: 0,
      units_reworked: 0,
      notes: '',
      _hasChanges: true,
      _isNew: true,
    }

    const gridApi = gridRef.value?.gridApi
    if (gridApi) {
      gridApi.applyTransaction({ add: [newRow], addIndex: 0 })

      setTimeout(() => {
        gridApi.startEditingCell({ rowIndex: 0, colKey: 'work_order_id' })
      }, 100)
    }
  }

  const buildPayload = (row: QualityRow, clientId: string | number) => {
    const unitsInspected = row.units_inspected ?? 0
    const unitsDefective = row.units_defective ?? 0
    return {
      client_id: String(clientId),
      work_order_id: String(row.work_order_id ?? ''),
      shift_date: row.shift_date,
      inspection_date: row.shift_date,
      units_inspected: unitsInspected,
      units_passed: computeUnitsPassed(row),
      units_defective: unitsDefective,
      total_defects_count: row.total_defects_count ?? unitsDefective,
      inspection_stage: row.inspection_stage || undefined,
      units_scrapped: row.units_scrapped ?? 0,
      units_reworked: row.units_reworked ?? 0,
      notes: row.notes || '',
    }
  }

  const saveInspections = async (): Promise<void> => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const changedRows: QualityRow[] = []
    gridApi.forEachNode((node) => {
      if (node.data._hasChanges) changedRows.push(node.data)
    })

    if (changedRows.length === 0) {
      showSnackbar(t('grids.noChanges'), 'info')
      return
    }

    if (!activeClientId()) {
      showSnackbar(t('grids.quality.errors.noClient'), 'error')
      return
    }

    pendingRows.value = changedRows
    pendingData.value = changedRows[0]
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
      showSnackbar(t('grids.quality.errors.noClient'), 'error')
      return
    }

    try {
      for (const row of pendingRows.value) {
        const data = buildPayload(row, clientId)
        try {
          if (row._isNew) {
            await api.createQualityEntry(data)
            successCount++
          } else if (row.quality_entry_id !== undefined) {
            await api.updateQualityEntry(row.quality_entry_id, data)
            successCount++
          }
          row._hasChanges = false
          row._isNew = false
        } catch (err) {
          errorCount++
          // eslint-disable-next-line no-console
          console.error('Error saving inspection:', err)
        }
      }

      if (errorCount === 0) {
        showSnackbar(
          t('grids.quality.savedInspections', { count: successCount }),
          'success',
        )
      } else {
        showSnackbar(
          t('grids.attendance.savedWithErrors', {
            success: successCount,
            failed: errorCount,
          }),
          'warning',
        )
      }
    } catch (error) {
      const ax = error as { message?: string }
      showSnackbar('Error saving inspections: ' + (ax?.message || ''), 'error')
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
    showSnackbar(t('grids.saveCancelled'), 'info')
  }

  const onRowsPasted = (pasteData: PasteData): void => {
    parsedPasteData.value = pasteData.parsedData
    convertedPasteRows.value = pasteData.convertedRows
    pasteValidationResult.value = pasteData.validationResult
    pasteColumnMapping.value = pasteData.columnMapping
    showPasteDialog.value = true
  }

  const onPasteConfirm = (rowsToAdd: Partial<QualityRow>[]): void => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const preparedRows: QualityRow[] = rowsToAdd.map((row) => ({
      quality_entry_id: `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      shift_date: row.shift_date || format(new Date(), 'yyyy-MM-dd'),
      work_order_id: row.work_order_id || '',
      units_inspected: row.units_inspected || 0,
      units_defective: row.units_defective || 0,
      total_defects_count: row.total_defects_count ?? row.units_defective ?? 0,
      inspection_stage: row.inspection_stage || 'Final',
      units_scrapped: row.units_scrapped || 0,
      units_reworked: row.units_reworked || 0,
      notes: row.notes || '',
      _hasChanges: true,
      _isNew: true,
    }))

    gridApi.applyTransaction({ add: preparedRows, addIndex: 0 })
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

  onMounted(async () => {
    try {
      const qualityRes = await api.getQualityEntries()
      qualityData.value = (qualityRes.data as QualityRow[]).map((entry) => ({
        ...entry,
        // Backend serialises shift_date as ISO datetime; normalise to YYYY-MM-DD for the date editor.
        shift_date:
          typeof entry.shift_date === 'string' ? entry.shift_date.slice(0, 10) : entry.shift_date,
        _hasChanges: false,
        _isNew: false,
      }))
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading quality data:', error)
      showSnackbar(t('grids.quality.errors.loadData'), 'error')
    }
  })

  return {
    gridRef,
    qualityData,
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
    hasChanges,
    changedRowsCount,
    columnDefs,
    totalInspected,
    totalDefects,
    avgFPY,
    avgPPM,
    onGridReady,
    onCellValueChanged,
    addRow,
    saveInspections,
    onConfirmSave,
    onCancelSave,
    onRowsPasted,
    onPasteConfirm,
    onPasteCancel,
  }
}
