/**
 * Composable for ProductionEntryGrid script logic — reactive
 * state, column definitions, CRUD, paste handling, filters,
 * summary statistics, read-back confirmation.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProductionDataStore } from '@/stores/productionDataStore'
import { format } from 'date-fns'

export interface ProductionRow {
  entry_id?: string | number
  production_date?: string
  product_id?: string | number | null
  shift_id?: string | number | null
  work_order_id?: string | number
  units_produced?: number
  run_time_hours?: number
  employees_assigned?: number
  defect_count?: number
  scrap_count?: number
  line_id?: string | number
  _hasChanges?: boolean
  _isNew?: boolean
  [key: string]: unknown
}

export interface ProductRef {
  product_id?: string | number
  product_name?: string
  [key: string]: unknown
}

export interface ShiftRef {
  shift_id?: string | number
  shift_name?: string
  [key: string]: unknown
}

interface AGGridApi {
  sizeColumnsToFit: () => void
  applyTransaction: (params: { add?: ProductionRow[]; remove?: ProductionRow[]; addIndex?: number }) => void
  startEditingCell: (params: { rowIndex: number; colKey: string }) => void
  refreshCells: (params?: { rowNodes?: unknown[]; force?: boolean }) => void
  forEachNode: (cb: (node: { data: ProductionRow }) => void) => void
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
  convertedRows: ProductionRow[]
  validationResult: unknown
  columnMapping: unknown
  gridColumns?: unknown[]
  [key: string]: unknown
}

export interface ConfirmationField {
  key: string
  label: string
  type: 'date' | 'text' | 'number'
  displayValue?: string | number
}

export default function useProductionGridData() {
  const { t } = useI18n()
  const kpiStore = useProductionDataStore()
  const gridRef = ref<AGGridRef | null>(null)
  const unsavedChanges = ref<Set<string | number>>(new Set())
  const saving = ref(false)
  const snackbar = ref<SnackbarState>({ show: false, message: '', color: 'success' })

  const showConfirmDialog = ref(false)
  const pendingData = ref<ProductionRow>({})
  const pendingRows = ref<ProductionRow[]>([])

  const showPasteDialog = ref(false)
  const parsedPasteData = ref<unknown | null>(null)
  const convertedPasteRows = ref<ProductionRow[]>([])
  const pasteValidationResult = ref<unknown | null>(null)
  const pasteColumnMapping = ref<unknown | null>(null)
  const pasteGridColumns = ref<unknown[]>([])

  const dateFilter = ref<string | null>(null)
  const productFilter = ref<string | number | null>(null)
  const shiftFilter = ref<string | number | null>(null)
  const lineFilter = ref<string | number | null>(null)

  const entries = computed<ProductionRow[]>(
    () => (kpiStore.productionEntries as ProductionRow[]) || [],
  )
  const products = computed<ProductRef[]>(
    () => (kpiStore.products as ProductRef[]) || [],
  )
  const shifts = computed<ShiftRef[]>(() => (kpiStore.shifts as ShiftRef[]) || [])
  const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

  const filteredEntries = ref<ProductionRow[]>([])

  const totalUnits = computed(() =>
    filteredEntries.value.reduce((sum, e) => sum + (e.units_produced || 0), 0),
  )

  const totalRuntime = computed(() => {
    const total = filteredEntries.value.reduce(
      (sum, e) => sum + (Number(e.run_time_hours) || 0),
      0,
    )
    return Number(total) || 0
  })

  const avgEfficiency = computed(() => {
    if (filteredEntries.value.length === 0) return 0
    const totalEff = filteredEntries.value.reduce((sum, e) => {
      const units = Number(e.units_produced) || 0
      const runtime = Number(e.run_time_hours) || 1
      const employees = Number(e.employees_assigned) || 1
      const efficiency = units / (runtime * employees)
      return sum + efficiency
    }, 0)
    return Number((totalEff / filteredEntries.value.length) * 100) || 0
  })

  const confirmationFieldConfig = computed<ConfirmationField[]>(() => {
    const productName =
      products.value.find((p) => p.product_id === pendingData.value.product_id)
        ?.product_name || 'N/A'
    const shiftName =
      shifts.value.find((s) => s.shift_id === pendingData.value.shift_id)?.shift_name ||
      'N/A'

    return [
      { key: 'production_date', label: 'Production Date', type: 'date' },
      { key: 'product_id', label: 'Product', type: 'text', displayValue: productName },
      { key: 'shift_id', label: 'Shift', type: 'text', displayValue: shiftName },
      { key: 'work_order_id', label: 'Work Order', type: 'text' },
      { key: 'units_produced', label: 'Units Produced', type: 'number' },
      { key: 'run_time_hours', label: 'Runtime (hours)', type: 'number' },
      { key: 'employees_assigned', label: 'Employees Assigned', type: 'number' },
      { key: 'defect_count', label: 'Defects', type: 'number' },
      { key: 'scrap_count', label: 'Scrap', type: 'number' },
    ]
  })

  const showSnackbar = (message: string, color: string = 'success'): void => {
    snackbar.value = { show: true, message, color }
  }

  const deleteEntry = async (rowData: ProductionRow): Promise<void> => {
    if (!confirm(t('grids.deleteConfirm'))) return

    const api = gridRef.value?.gridApi
    if (!api) return

    if (rowData._isNew) {
      api.applyTransaction({ remove: [rowData] })
      if (rowData.entry_id !== undefined) unsavedChanges.value.delete(rowData.entry_id)
      showSnackbar(t('grids.entryRemoved'), 'info')
      return
    }

    if (rowData.entry_id === undefined) return

    try {
      await kpiStore.deleteProductionEntry(rowData.entry_id)
      api.applyTransaction({ remove: [rowData] })
      unsavedChanges.value.delete(rowData.entry_id)
      showSnackbar(t('grids.entryDeleted'), 'success')
    } catch (error) {
      const ax = error as { message?: string }
      showSnackbar(t('grids.deleteError') + ': ' + (ax?.message || ''), 'error')
    }
  }

  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.date'),
      field: 'production_date',
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
      headerName: t('grids.columns.product'),
      field: 'product_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({ values: products.value.map((p) => p.product_id) }),
      valueFormatter: (params: { value?: string | number }) => {
        const product = products.value.find((p) => p.product_id === params.value)
        return product?.product_name || `ID: ${params.value}`
      },
      width: 200,
    },
    {
      headerName: t('grids.columns.shift'),
      field: 'shift_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({ values: shifts.value.map((s) => s.shift_id) }),
      valueFormatter: (params: { value?: string | number }) => {
        const shift = shifts.value.find((s) => s.shift_id === params.value)
        return shift?.shift_name || `ID: ${params.value}`
      },
      width: 120,
    },
    {
      headerName: t('grids.columns.workOrder'),
      field: 'work_order_id',
      editable: true,
      width: 150,
    },
    {
      headerName: t('grids.columns.unitsProduced'),
      field: 'units_produced',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      valueFormatter: (params: { value?: number }) =>
        params.value ? params.value.toLocaleString() : '0',
      cellClass: (params: { value?: number }) =>
        (params.value ?? 0) > 0 ? 'ag-cell-success ag-cell-bold' : 'ag-cell-error',
      width: 160,
    },
    {
      headerName: t('grids.columns.runtimeHrs'),
      field: 'run_time_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 24, precision: 2 },
      valueFormatter: (params: { value?: number | string }) => {
        const val = Number(params.value)
        return !isNaN(val) ? val.toFixed(2) : '0.00'
      },
      width: 140,
    },
    {
      headerName: t('grids.columns.employees'),
      field: 'employees_assigned',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 1, precision: 0 },
      width: 130,
    },
    {
      headerName: t('grids.columns.defects'),
      field: 'defect_count',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      cellClass: (params: { value?: number }) =>
        (params.value ?? 0) > 0 ? 'ag-cell-error' : '',
      width: 110,
    },
    {
      headerName: t('grids.columns.scrap'),
      field: 'scrap_count',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      cellClass: (params: { value?: number }) =>
        (params.value ?? 0) > 0 ? 'ag-cell-error' : '',
      width: 110,
    },
    {
      headerName: t('grids.columns.actions'),
      field: 'actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params: { data: ProductionRow }) => {
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

  const onCellValueChanged = (event: {
    data: ProductionRow
    node: { id: string }
    api: AGGridApi
  }): void => {
    const rowId = event.data.entry_id || event.node.id
    if (rowId !== undefined) unsavedChanges.value.add(rowId)
    event.data._hasChanges = true
    event.api.refreshCells({ rowNodes: [event.node], force: true })
  }

  const addNewEntry = (): void => {
    const newEntry: ProductionRow = {
      entry_id: `temp_${Date.now()}`,
      production_date: format(new Date(), 'yyyy-MM-dd'),
      product_id: products.value[0]?.product_id || null,
      shift_id: shifts.value[0]?.shift_id || null,
      work_order_id: '',
      units_produced: 0,
      run_time_hours: 0,
      employees_assigned: 1,
      defect_count: 0,
      scrap_count: 0,
      _isNew: true,
      _hasChanges: true,
    }

    const api = gridRef.value?.gridApi
    if (api && newEntry.entry_id !== undefined) {
      api.applyTransaction({ add: [newEntry], addIndex: 0 })
      unsavedChanges.value.add(newEntry.entry_id)

      setTimeout(() => {
        api.startEditingCell({ rowIndex: 0, colKey: 'production_date' })
      }, 100)
    }
  }

  const applyFilters = (): void => {
    let filtered = [...entries.value]

    if (dateFilter.value) {
      filtered = filtered.filter((e) => e.production_date === dateFilter.value)
    }
    if (productFilter.value) {
      filtered = filtered.filter((e) => e.product_id === productFilter.value)
    }
    if (shiftFilter.value) {
      filtered = filtered.filter((e) => e.shift_id === shiftFilter.value)
    }
    if (lineFilter.value) {
      filtered = filtered.filter((e) => e.line_id === lineFilter.value)
    }

    filteredEntries.value = filtered
  }

  const saveChanges = async (): Promise<void> => {
    const api = gridRef.value?.gridApi
    if (!api) return

    const rowsToSave: ProductionRow[] = []
    api.forEachNode((node) => {
      if (node.data._hasChanges) rowsToSave.push(node.data)
    })

    if (rowsToSave.length === 0) {
      showSnackbar(t('grids.noChanges'), 'info')
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
          product_id: row.product_id,
          shift_id: row.shift_id,
          production_date: row.production_date,
          work_order_id: row.work_order_id || '',
          units_produced: row.units_produced || 0,
          run_time_hours: row.run_time_hours || 0,
          employees_assigned: row.employees_assigned || 1,
          defect_count: row.defect_count || 0,
          scrap_count: row.scrap_count || 0,
        }

        try {
          if (row._isNew) {
            const result = await kpiStore.createProductionEntry(data)
            if (result.success && result.data) {
              row.entry_id = (result.data as ProductionRow).entry_id
              row._isNew = false
              successCount++
            } else {
              errorCount++
            }
          } else if (row.entry_id !== undefined) {
            const result = await kpiStore.updateProductionEntry(row.entry_id, data)
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
          if (row.entry_id !== undefined) unsavedChanges.value.delete(row.entry_id)
        } catch (err) {
          errorCount++
          // eslint-disable-next-line no-console
          console.error('Error saving row:', err)
        }
      }

      await kpiStore.fetchProductionEntries()
      applyFilters()

      if (errorCount === 0) {
        showSnackbar(t('grids.entriesSaved', { count: successCount }), 'success')
      } else {
        showSnackbar(
          `${successCount} ${t('success.saved')}, ${errorCount} ${t('dataEntry.rowsInvalid')}`,
          'warning',
        )
      }
    } catch (error) {
      const ax = error as { message?: string }
      showSnackbar('Error saving changes: ' + (ax?.message || ''), 'error')
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
    pasteGridColumns.value = pasteData.gridColumns || []
    showPasteDialog.value = true
  }

  const onPasteConfirm = (rowsToAdd: Partial<ProductionRow>[]): void => {
    showPasteDialog.value = false

    if (!rowsToAdd || rowsToAdd.length === 0) {
      showSnackbar(t('paste.noValidRows'), 'warning')
      return
    }

    const preparedRows: ProductionRow[] = rowsToAdd.map((row, idx) => ({
      ...row,
      entry_id: `temp_paste_${Date.now()}_${idx}`,
      _isNew: true,
      _hasChanges: true,
    }))

    const api = gridRef.value?.gridApi
    if (api) {
      api.applyTransaction({ add: preparedRows, addIndex: 0 })
      preparedRows.forEach((row) => {
        if (row.entry_id !== undefined) unsavedChanges.value.add(row.entry_id)
      })
      showSnackbar(t('paste.rowsAdded', { count: preparedRows.length }), 'success')
    }

    parsedPasteData.value = null
    convertedPasteRows.value = []
    pasteValidationResult.value = null
    pasteColumnMapping.value = null
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
    await kpiStore.fetchProductionEntries()
    applyFilters()
  })

  return {
    gridRef,
    unsavedChanges,
    saving,
    snackbar,
    showConfirmDialog,
    pendingData,
    confirmationFieldConfig,
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    pasteGridColumns,
    dateFilter,
    productFilter,
    shiftFilter,
    lineFilter,
    products,
    shifts,
    filteredEntries,
    hasUnsavedChanges,
    columnDefs,
    totalUnits,
    totalRuntime,
    avgEfficiency,
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
