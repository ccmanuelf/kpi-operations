/**
 * Composable for QualityEntryGrid script logic — reactive state,
 * column definitions, CRUD, paste handling, summary stats (FPY,
 * PPM), read-back confirmation.
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { format } from 'date-fns'

export interface QualityRow {
  inspection_id?: string | number
  inspection_date?: string
  work_order_id?: string | number
  product_id?: string | number | null
  inspected_quantity?: number
  defect_quantity?: number
  defect_type_id?: string | number | null
  severity?: string
  disposition?: string
  inspector_id?: string | number
  defect_description?: string
  _hasChanges?: boolean
  _isNew?: boolean
  [key: string]: unknown
}

export interface ProductRef {
  product_id?: string | number
  product_name?: string
  [key: string]: unknown
}

export interface DefectTypeRef {
  defect_type_id?: string | number
  defect_name?: string
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

  const gridRef = ref<AGGridRef | null>(null)
  const qualityData = ref<QualityRow[]>([])
  const products = ref<ProductRef[]>([])
  const defectTypes = ref<DefectTypeRef[]>([])
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

  const confirmationFieldConfig = computed<ConfirmationField[]>(() => {
    const productName =
      products.value.find((p) => p.product_id === pendingData.value.product_id)
        ?.product_name || 'N/A'
    const defectTypeName =
      defectTypes.value.find((d) => d.defect_type_id === pendingData.value.defect_type_id)
        ?.defect_name || 'N/A'

    const inspected = pendingData.value.inspected_quantity || 0
    const defects = pendingData.value.defect_quantity || 0
    const fpy = inspected > 0 ? ((1 - defects / inspected) * 100).toFixed(2) : '0.00'
    const ppm = inspected > 0 ? Math.round((defects / inspected) * 1000000) : 0

    return [
      { key: 'inspection_date', label: 'Inspection Date', type: 'date' },
      { key: 'work_order_id', label: 'Work Order', type: 'text' },
      { key: 'product_id', label: 'Product', type: 'text', displayValue: productName },
      { key: 'inspected_quantity', label: 'Inspected Quantity', type: 'number' },
      { key: 'defect_quantity', label: 'Defect Quantity', type: 'number' },
      { key: 'fpy_calculated', label: 'FPY %', type: 'percentage', displayValue: fpy },
      {
        key: 'ppm_calculated',
        label: 'PPM',
        type: 'number',
        displayValue: ppm.toLocaleString(),
      },
      {
        key: 'defect_type_id',
        label: 'Defect Type',
        type: 'text',
        displayValue: defectTypeName,
      },
      { key: 'severity', label: 'Severity', type: 'text' },
      { key: 'disposition', label: 'Disposition', type: 'text' },
      { key: 'inspector_id', label: 'Inspector ID', type: 'text' },
    ]
  })

  const hasChanges = computed(() => qualityData.value.some((row) => row._hasChanges))

  const changedRowsCount = computed(
    () => qualityData.value.filter((row) => row._hasChanges).length,
  )

  const totalInspected = computed(() =>
    qualityData.value.reduce((sum, row) => sum + (row.inspected_quantity || 0), 0),
  )

  const totalDefects = computed(() =>
    qualityData.value.reduce((sum, row) => sum + (row.defect_quantity || 0), 0),
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
      headerName: t('grids.columns.inspectionDate'),
      field: 'inspection_date',
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
      headerName: t('grids.columns.product'),
      field: 'product_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({ values: products.value.map((p) => p.product_id) }),
      valueFormatter: (params: { value?: string | number }) => {
        const product = products.value.find((p) => p.product_id === params.value)
        return product?.product_name || (params.value as string) || 'N/A'
      },
      width: 200,
    },
    {
      headerName: t('grids.columns.inspectedQty'),
      field: 'inspected_quantity',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      valueFormatter: (params: { value?: number }) =>
        params.value ? params.value.toLocaleString() : '0',
      width: 140,
    },
    {
      headerName: t('grids.columns.defectQty'),
      field: 'defect_quantity',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      cellClass: (params: { value?: number }) =>
        (params.value ?? 0) > 0 ? 'ag-cell-error ag-cell-bold' : '',
      width: 130,
    },
    {
      headerName: t('grids.columns.fpyPercent'),
      field: 'fpy',
      editable: false,
      valueGetter: (params: { data: QualityRow }) => {
        const inspected = params.data.inspected_quantity || 0
        const defects = params.data.defect_quantity || 0
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
        const inspected = params.data.inspected_quantity || 0
        const defects = params.data.defect_quantity || 0
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
      headerName: t('grids.columns.defectType'),
      field: 'defect_type_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: defectTypes.value.map((d) => d.defect_type_id),
      }),
      valueFormatter: (params: { value?: string | number }) => {
        const defectType = defectTypes.value.find(
          (d) => d.defect_type_id === params.value,
        )
        return defectType?.defect_name || (params.value as string) || 'N/A'
      },
      width: 150,
    },
    {
      headerName: t('grids.columns.severity'),
      field: 'severity',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: ['Critical', 'Major', 'Minor', 'Cosmetic'] },
      cellClass: (params: { value?: string }) => {
        const classes: Record<string, string> = {
          Critical: 'ag-cell-error ag-cell-bold',
          Major: 'ag-cell-warning ag-cell-bold',
          Minor: 'ag-cell-warning-light',
          Cosmetic: 'ag-cell-info',
        }
        return classes[params.value || ''] || ''
      },
      width: 120,
    },
    {
      headerName: t('grids.columns.disposition'),
      field: 'disposition',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: ['Accept', 'Reject', 'Rework', 'Use As Is', 'Return to Supplier', 'Scrap'],
      },
      cellClass: (params: { value?: string }) => {
        const classes: Record<string, string> = {
          Accept: 'ag-cell-success',
          Reject: 'ag-cell-error',
          Rework: 'ag-cell-warning',
          Scrap: 'ag-cell-error',
        }
        return classes[params.value || ''] || ''
      },
      width: 150,
    },
    {
      headerName: t('grids.columns.inspector'),
      field: 'inspector_id',
      editable: true,
      width: 130,
    },
    {
      headerName: t('grids.columns.notes'),
      field: 'defect_description',
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

    if (event.column.colId === 'inspected_quantity' || event.column.colId === 'defect_quantity') {
      event.api.refreshCells({
        rowNodes: [event.node],
        columns: ['fpy', 'ppm'],
        force: true,
      })
    }
  }

  const addRow = (): void => {
    const newRow: QualityRow = {
      inspection_id: `temp_${Date.now()}`,
      inspection_date: format(new Date(), 'yyyy-MM-dd'),
      work_order_id: '',
      product_id: products.value[0]?.product_id || null,
      inspected_quantity: 0,
      defect_quantity: 0,
      defect_type_id: defectTypes.value[0]?.defect_type_id || null,
      severity: 'Minor',
      disposition: 'Accept',
      inspector_id: '',
      defect_description: '',
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

    pendingRows.value = changedRows
    pendingData.value = changedRows[0]
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
          inspection_date: row.inspection_date,
          work_order_id: row.work_order_id,
          product_id: row.product_id,
          inspected_quantity: row.inspected_quantity || 0,
          defect_quantity: row.defect_quantity || 0,
          defect_type_id: row.defect_type_id,
          severity: row.severity,
          disposition: row.disposition,
          inspector_id: row.inspector_id,
          defect_description: row.defect_description || '',
        }

        try {
          if (row._isNew) {
            await api.createQualityEntry(data)
            successCount++
          } else if (row.inspection_id !== undefined) {
            await api.updateQualityEntry(row.inspection_id, data)
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
      inspection_id: `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      inspection_date: row.inspection_date || format(new Date(), 'yyyy-MM-dd'),
      work_order_id: row.work_order_id || '',
      product_id: row.product_id || products.value[0]?.product_id || null,
      inspected_quantity: row.inspected_quantity || 0,
      defect_quantity: row.defect_quantity || 0,
      defect_type_id: row.defect_type_id || defectTypes.value[0]?.defect_type_id || null,
      severity: row.severity || 'Minor',
      disposition: row.disposition || 'Accept',
      inspector_id: row.inspector_id || '',
      defect_description: row.defect_description || '',
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
      const [productsRes, defectTypesRes] = await Promise.all([
        api.getProducts(),
        api.getDefectTypes(),
      ])

      products.value = productsRes.data
      defectTypes.value = defectTypesRes.data

      const qualityRes = await api.getQualityEntries()
      qualityData.value = (qualityRes.data as QualityRow[]).map((entry) => ({
        ...entry,
        _hasChanges: false,
        _isNew: false,
      }))
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Error loading reference data:', error)
      showSnackbar('Error loading data', 'error')
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
