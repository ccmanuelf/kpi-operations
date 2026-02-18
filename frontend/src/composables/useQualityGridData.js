/**
 * Composable for QualityEntryGrid script logic.
 *
 * Encapsulates reactive state, column definitions, CRUD operations,
 * paste handling, summary statistics (FPY, PPM), and read-back
 * confirmation for the quality inspection entry grid.
 *
 * API dependency: @/services/api (direct, no store)
 */
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { format } from 'date-fns'

export default function useQualityGridData() {
  const { t } = useI18n()

  const gridRef = ref(null)
  const qualityData = ref([])
  const products = ref([])
  const defectTypes = ref([])
  const saving = ref(false)
  const snackbar = ref({ show: false, message: '', color: 'success' })

  // Read-back confirmation state
  const showConfirmDialog = ref(false)
  const pendingData = ref({})
  const pendingRows = ref([])

  // Paste preview state
  const showPasteDialog = ref(false)
  const parsedPasteData = ref(null)
  const convertedPasteRows = ref([])
  const pasteValidationResult = ref(null)
  const pasteColumnMapping = ref(null)

  const pendingRowsCount = computed(() => pendingRows.value.length)

  // Field configuration for confirmation dialog
  const confirmationFieldConfig = computed(() => {
    const productName = products.value.find(p => p.product_id === pendingData.value.product_id)?.product_name || 'N/A'
    const defectTypeName = defectTypes.value.find(d => d.defect_type_id === pendingData.value.defect_type_id)?.defect_name || 'N/A'

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
      { key: 'ppm_calculated', label: 'PPM', type: 'number', displayValue: ppm.toLocaleString() },
      { key: 'defect_type_id', label: 'Defect Type', type: 'text', displayValue: defectTypeName },
      { key: 'severity', label: 'Severity', type: 'text' },
      { key: 'disposition', label: 'Disposition', type: 'text' },
      { key: 'inspector_id', label: 'Inspector ID', type: 'text' }
    ]
  })

  // Computed properties
  const hasChanges = computed(() => {
    return qualityData.value.some(row => row._hasChanges)
  })

  const changedRowsCount = computed(() => {
    return qualityData.value.filter(row => row._hasChanges).length
  })

  const totalInspected = computed(() => {
    return qualityData.value.reduce((sum, row) => sum + (row.inspected_quantity || 0), 0)
  })

  const totalDefects = computed(() => {
    return qualityData.value.reduce((sum, row) => sum + (row.defect_quantity || 0), 0)
  })

  const avgFPY = computed(() => {
    if (totalInspected.value === 0) return 0
    return ((totalInspected.value - totalDefects.value) / totalInspected.value) * 100
  })

  const avgPPM = computed(() => {
    if (totalInspected.value === 0) return 0
    return (totalDefects.value / totalInspected.value) * 1000000
  })

  // Column definitions
  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.inspectionDate'),
      field: 'inspection_date',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      valueFormatter: (params) => {
        return params.value ? format(new Date(params.value), 'MMM dd, yyyy') : ''
      },
      width: 140
    },
    {
      headerName: t('grids.columns.workOrder'),
      field: 'work_order_id',
      editable: true,
      width: 150
    },
    {
      headerName: t('grids.columns.product'),
      field: 'product_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: products.value.map(p => p.product_id)
      }),
      valueFormatter: (params) => {
        const product = products.value.find(p => p.product_id === params.value)
        return product?.product_name || params.value || 'N/A'
      },
      width: 200
    },
    {
      headerName: t('grids.columns.inspectedQty'),
      field: 'inspected_quantity',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      valueFormatter: (params) => {
        return params.value ? params.value.toLocaleString() : '0'
      },
      width: 140
    },
    {
      headerName: t('grids.columns.defectQty'),
      field: 'defect_quantity',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      cellStyle: (params) => {
        return params.value > 0 ? { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' } : {}
      },
      width: 130
    },
    {
      headerName: t('grids.columns.fpyPercent'),
      field: 'fpy',
      editable: false,
      valueGetter: (params) => {
        const inspected = params.data.inspected_quantity || 0
        const defects = params.data.defect_quantity || 0
        if (inspected === 0) return 0
        return ((1 - defects / inspected) * 100).toFixed(2)
      },
      cellStyle: (params) => {
        const fpy = parseFloat(params.value)
        if (fpy >= 99) return { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' }
        if (fpy >= 95) return { backgroundColor: '#fff3e0', color: '#f57c00', fontWeight: 'bold' }
        return { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' }
      },
      width: 110
    },
    {
      headerName: t('grids.columns.ppm'),
      field: 'ppm',
      editable: false,
      valueGetter: (params) => {
        const inspected = params.data.inspected_quantity || 0
        const defects = params.data.defect_quantity || 0
        if (inspected === 0) return 0
        return Math.round((defects / inspected) * 1000000)
      },
      valueFormatter: (params) => {
        return params.value ? params.value.toLocaleString() : '0'
      },
      cellStyle: (params) => {
        const ppm = params.value || 0
        if (ppm === 0) return { backgroundColor: '#e8f5e9', color: '#2e7d32' }
        if (ppm <= 10000) return { backgroundColor: '#fff3e0', color: '#f57c00' }
        return { backgroundColor: '#ffebee', color: '#c62828' }
      },
      width: 110
    },
    {
      headerName: t('grids.columns.defectType'),
      field: 'defect_type_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: defectTypes.value.map(d => d.defect_type_id)
      }),
      valueFormatter: (params) => {
        const defectType = defectTypes.value.find(d => d.defect_type_id === params.value)
        return defectType?.defect_name || params.value || 'N/A'
      },
      width: 150
    },
    {
      headerName: t('grids.columns.severity'),
      field: 'severity',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: ['Critical', 'Major', 'Minor', 'Cosmetic'] },
      cellStyle: (params) => {
        const severityColors = {
          'Critical': { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' },
          'Major': { backgroundColor: '#fff3e0', color: '#f57c00', fontWeight: 'bold' },
          'Minor': { backgroundColor: '#fff9c4', color: '#f57f17' },
          'Cosmetic': { backgroundColor: '#e3f2fd', color: '#1976d2' }
        }
        return severityColors[params.value] || {}
      },
      width: 120
    },
    {
      headerName: t('grids.columns.disposition'),
      field: 'disposition',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: ['Accept', 'Reject', 'Rework', 'Use As Is', 'Return to Supplier', 'Scrap']
      },
      cellStyle: (params) => {
        const dispositionColors = {
          'Accept': { backgroundColor: '#e8f5e9', color: '#2e7d32' },
          'Reject': { backgroundColor: '#ffebee', color: '#c62828' },
          'Rework': { backgroundColor: '#fff3e0', color: '#f57c00' },
          'Scrap': { backgroundColor: '#ffebee', color: '#c62828' }
        }
        return dispositionColors[params.value] || {}
      },
      width: 150
    },
    {
      headerName: t('grids.columns.inspector'),
      field: 'inspector_id',
      editable: true,
      width: 130
    },
    {
      headerName: t('grids.columns.notes'),
      field: 'defect_description',
      editable: true,
      cellEditor: 'agLargeTextCellEditor',
      cellEditorPopup: true,
      width: 250
    },
    {
      headerName: t('grids.columns.actions'),
      field: 'actions',
      editable: false,
      sortable: false,
      filter: false,
      cellRenderer: (params) => {
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
        div.querySelector('.ag-grid-delete-btn').addEventListener('click', () => {
          deleteRow(params.data)
        })
        return div
      },
      width: 100,
      pinned: 'right'
    }
  ])

  // --- Methods ---

  const onGridReady = (params) => {
    setTimeout(() => {
      params.api.sizeColumnsToFit()
    }, 100)
  }

  const onCellValueChanged = (event) => {
    event.data._hasChanges = true

    if (event.column.colId === 'inspected_quantity' || event.column.colId === 'defect_quantity') {
      event.api.refreshCells({
        rowNodes: [event.node],
        columns: ['fpy', 'ppm'],
        force: true
      })
    }
  }

  const addRow = () => {
    const newRow = {
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
      _isNew: true
    }

    const gridApi = gridRef.value?.gridApi
    if (gridApi) {
      gridApi.applyTransaction({ add: [newRow], addIndex: 0 })

      setTimeout(() => {
        gridApi.startEditingCell({ rowIndex: 0, colKey: 'work_order_id' })
      }, 100)
    }
  }

  const deleteRow = (rowData) => {
    if (!confirm(t('grids.quality.deleteConfirm'))) return

    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    gridApi.applyTransaction({ remove: [rowData] })
    showSnackbar(t('grids.quality.inspectionRemoved'), 'info')
  }

  const saveInspections = async () => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const changedRows = []
    gridApi.forEachNode(node => {
      if (node.data._hasChanges) {
        changedRows.push(node.data)
      }
    })

    if (changedRows.length === 0) {
      showSnackbar(t('grids.noChanges'), 'info')
      return
    }

    pendingRows.value = changedRows
    pendingData.value = changedRows[0]
    showConfirmDialog.value = true
  }

  const onConfirmSave = async () => {
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
          defect_description: row.defect_description || ''
        }

        try {
          if (row._isNew) {
            await api.createQualityEntry(data)
            successCount++
          } else if (row.inspection_id) {
            await api.updateQualityEntry(row.inspection_id, data)
            successCount++
          }

          row._hasChanges = false
          row._isNew = false
        } catch (err) {
          errorCount++
          console.error('Error saving inspection:', err)
        }
      }

      if (errorCount === 0) {
        showSnackbar(t('grids.quality.savedInspections', { count: successCount }), 'success')
      } else {
        showSnackbar(t('grids.attendance.savedWithErrors', { success: successCount, failed: errorCount }), 'warning')
      }
    } catch (error) {
      showSnackbar('Error saving inspections: ' + error.message, 'error')
    } finally {
      saving.value = false
      pendingRows.value = []
      pendingData.value = {}
    }
  }

  const onCancelSave = () => {
    showConfirmDialog.value = false
    pendingRows.value = []
    pendingData.value = {}
    showSnackbar(t('grids.saveCancelled'), 'info')
  }

  const showSnackbar = (message, color = 'success') => {
    snackbar.value = { show: true, message, color }
  }

  // Paste handlers
  const onRowsPasted = (pasteData) => {
    parsedPasteData.value = pasteData.parsedData
    convertedPasteRows.value = pasteData.convertedRows
    pasteValidationResult.value = pasteData.validationResult
    pasteColumnMapping.value = pasteData.columnMapping
    showPasteDialog.value = true
  }

  const onPasteConfirm = (rowsToAdd) => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const preparedRows = rowsToAdd.map(row => ({
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
      _isNew: true
    }))

    gridApi.applyTransaction({ add: preparedRows, addIndex: 0 })
    showPasteDialog.value = false
    showSnackbar(t('paste.rowsAdded', { count: preparedRows.length }), 'success')
  }

  const onPasteCancel = () => {
    showPasteDialog.value = false
    parsedPasteData.value = null
    convertedPasteRows.value = []
    pasteValidationResult.value = null
    pasteColumnMapping.value = null
  }

  // Lifecycle
  onMounted(async () => {
    try {
      const [productsRes, defectTypesRes] = await Promise.all([
        api.getProducts(),
        api.getDefectTypes()
      ])

      products.value = productsRes.data
      defectTypes.value = defectTypesRes.data

      const qualityRes = await api.getQualityEntries()
      qualityData.value = qualityRes.data.map(entry => ({
        ...entry,
        _hasChanges: false,
        _isNew: false
      }))
    } catch (error) {
      console.error('Error loading reference data:', error)
      showSnackbar('Error loading data', 'error')
    }
  })

  return {
    // Refs
    gridRef,
    qualityData,
    saving,
    snackbar,
    // Confirmation
    showConfirmDialog,
    pendingData,
    pendingRowsCount,
    confirmationFieldConfig,
    // Paste
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    // Data
    hasChanges,
    changedRowsCount,
    columnDefs,
    // Stats
    totalInspected,
    totalDefects,
    avgFPY,
    avgPPM,
    // Methods
    onGridReady,
    onCellValueChanged,
    addRow,
    saveInspections,
    onConfirmSave,
    onCancelSave,
    onRowsPasted,
    onPasteConfirm,
    onPasteCancel
  }
}
