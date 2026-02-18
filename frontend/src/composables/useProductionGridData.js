/**
 * Composable for ProductionEntryGrid script logic.
 *
 * Encapsulates reactive state, column definitions, CRUD operations,
 * paste handling, filters, summary statistics, and read-back confirmation
 * for the production entry grid.
 *
 * Store dependency: useProductionDataStore (productionDataStore)
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProductionDataStore } from '@/stores/productionDataStore'
import { format } from 'date-fns'

export default function useProductionGridData() {
  const { t } = useI18n()
  const kpiStore = useProductionDataStore()
  const gridRef = ref(null)
  const unsavedChanges = ref(new Set())
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
  const pasteGridColumns = ref([])

  // Filters
  const dateFilter = ref(null)
  const productFilter = ref(null)
  const shiftFilter = ref(null)

  const entries = computed(() => kpiStore.productionEntries)
  const products = computed(() => kpiStore.products)
  const shifts = computed(() => kpiStore.shifts)
  const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

  // Filtered entries
  const filteredEntries = ref([])

  // Summary statistics
  const totalUnits = computed(() => {
    return filteredEntries.value.reduce((sum, e) => sum + (e.units_produced || 0), 0)
  })

  const totalRuntime = computed(() => {
    const total = filteredEntries.value.reduce((sum, e) => sum + (Number(e.run_time_hours) || 0), 0)
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

  // Field configuration for confirmation dialog
  const confirmationFieldConfig = computed(() => {
    const productName = products.value.find(p => p.product_id === pendingData.value.product_id)?.product_name || 'N/A'
    const shiftName = shifts.value.find(s => s.shift_id === pendingData.value.shift_id)?.shift_name || 'N/A'

    return [
      { key: 'production_date', label: 'Production Date', type: 'date' },
      { key: 'product_id', label: 'Product', type: 'text', displayValue: productName },
      { key: 'shift_id', label: 'Shift', type: 'text', displayValue: shiftName },
      { key: 'work_order_id', label: 'Work Order', type: 'text' },
      { key: 'units_produced', label: 'Units Produced', type: 'number' },
      { key: 'run_time_hours', label: 'Runtime (hours)', type: 'number' },
      { key: 'employees_assigned', label: 'Employees Assigned', type: 'number' },
      { key: 'defect_count', label: 'Defects', type: 'number' },
      { key: 'scrap_count', label: 'Scrap', type: 'number' }
    ]
  })

  // Column definitions
  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.date'),
      field: 'production_date',
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
      headerName: t('grids.columns.product'),
      field: 'product_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: products.value.map(p => p.product_id)
      }),
      valueFormatter: (params) => {
        const product = products.value.find(p => p.product_id === params.value)
        return product?.product_name || `ID: ${params.value}`
      },
      width: 200
    },
    {
      headerName: t('grids.columns.shift'),
      field: 'shift_id',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: shifts.value.map(s => s.shift_id)
      }),
      valueFormatter: (params) => {
        const shift = shifts.value.find(s => s.shift_id === params.value)
        return shift?.shift_name || `ID: ${params.value}`
      },
      width: 120
    },
    {
      headerName: t('grids.columns.workOrder'),
      field: 'work_order_id',
      editable: true,
      width: 150
    },
    {
      headerName: t('grids.columns.unitsProduced'),
      field: 'units_produced',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      valueFormatter: (params) => {
        return params.value ? params.value.toLocaleString() : '0'
      },
      cellStyle: (params) => {
        return params.value > 0
          ? { color: '#2e7d32', fontWeight: 'bold' }
          : { color: '#c62828' }
      },
      width: 160
    },
    {
      headerName: t('grids.columns.runtimeHrs'),
      field: 'run_time_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, max: 24, precision: 2 },
      valueFormatter: (params) => {
        const val = Number(params.value)
        return !isNaN(val) ? val.toFixed(2) : '0.00'
      },
      width: 140
    },
    {
      headerName: t('grids.columns.employees'),
      field: 'employees_assigned',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 1, precision: 0 },
      width: 130
    },
    {
      headerName: t('grids.columns.defects'),
      field: 'defect_count',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      cellStyle: (params) => {
        return params.value > 0 ? { backgroundColor: '#ffebee', color: '#c62828' } : {}
      },
      width: 110
    },
    {
      headerName: t('grids.columns.scrap'),
      field: 'scrap_count',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 0 },
      cellStyle: (params) => {
        return params.value > 0 ? { backgroundColor: '#ffebee', color: '#c62828' } : {}
      },
      width: 110
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
          deleteEntry(params.data)
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
    const rowId = event.data.entry_id || event.node.id
    unsavedChanges.value.add(rowId)
    event.data._hasChanges = true
    event.api.refreshCells({ rowNodes: [event.node], force: true })
  }

  const addNewEntry = () => {
    const newEntry = {
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
      _hasChanges: true
    }

    const api = gridRef.value?.gridApi
    if (api) {
      api.applyTransaction({ add: [newEntry], addIndex: 0 })
      unsavedChanges.value.add(newEntry.entry_id)

      setTimeout(() => {
        api.startEditingCell({ rowIndex: 0, colKey: 'production_date' })
      }, 100)
    }
  }

  const deleteEntry = async (rowData) => {
    if (!confirm(t('grids.deleteConfirm'))) return

    const api = gridRef.value?.gridApi
    if (!api) return

    if (rowData._isNew) {
      api.applyTransaction({ remove: [rowData] })
      unsavedChanges.value.delete(rowData.entry_id)
      showSnackbar(t('grids.entryRemoved'), 'info')
      return
    }

    try {
      await kpiStore.deleteProductionEntry(rowData.entry_id)
      api.applyTransaction({ remove: [rowData] })
      unsavedChanges.value.delete(rowData.entry_id)
      showSnackbar(t('grids.entryDeleted'), 'success')
    } catch (error) {
      showSnackbar(t('grids.deleteError') + ': ' + error.message, 'error')
    }
  }

  const saveChanges = async () => {
    const api = gridRef.value?.gridApi
    if (!api) return

    const rowsToSave = []
    api.forEachNode(node => {
      if (node.data._hasChanges) {
        rowsToSave.push(node.data)
      }
    })

    if (rowsToSave.length === 0) {
      showSnackbar(t('grids.noChanges'), 'info')
      return
    }

    pendingRows.value = rowsToSave
    pendingData.value = rowsToSave[0]
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
          product_id: row.product_id,
          shift_id: row.shift_id,
          production_date: row.production_date,
          work_order_id: row.work_order_id || '',
          units_produced: row.units_produced || 0,
          run_time_hours: row.run_time_hours || 0,
          employees_assigned: row.employees_assigned || 1,
          defect_count: row.defect_count || 0,
          scrap_count: row.scrap_count || 0
        }

        try {
          if (row._isNew) {
            const result = await kpiStore.createProductionEntry(data)
            if (result.success) {
              row.entry_id = result.data.entry_id
              row._isNew = false
              successCount++
            } else {
              errorCount++
            }
          } else {
            const result = await kpiStore.updateProductionEntry(row.entry_id, data)
            if (result.success) {
              successCount++
            } else {
              errorCount++
            }
          }

          row._hasChanges = false
          unsavedChanges.value.delete(row.entry_id)
        } catch (err) {
          errorCount++
          console.error('Error saving row:', err)
        }
      }

      await kpiStore.fetchProductionEntries()
      applyFilters()

      if (errorCount === 0) {
        showSnackbar(t('grids.entriesSaved', { count: successCount }), 'success')
      } else {
        showSnackbar(`${successCount} ${t('success.saved')}, ${errorCount} ${t('dataEntry.rowsInvalid')}`, 'warning')
      }
    } catch (error) {
      showSnackbar('Error saving changes: ' + error.message, 'error')
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

  const applyFilters = () => {
    let filtered = [...entries.value]

    if (dateFilter.value) {
      filtered = filtered.filter(e => e.production_date === dateFilter.value)
    }
    if (productFilter.value) {
      filtered = filtered.filter(e => e.product_id === productFilter.value)
    }
    if (shiftFilter.value) {
      filtered = filtered.filter(e => e.shift_id === shiftFilter.value)
    }

    filteredEntries.value = filtered
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
    pasteGridColumns.value = pasteData.gridColumns
    showPasteDialog.value = true
  }

  const onPasteConfirm = (rowsToAdd) => {
    showPasteDialog.value = false

    if (!rowsToAdd || rowsToAdd.length === 0) {
      showSnackbar(t('paste.noValidRows'), 'warning')
      return
    }

    const preparedRows = rowsToAdd.map((row, idx) => ({
      ...row,
      entry_id: `temp_paste_${Date.now()}_${idx}`,
      _isNew: true,
      _hasChanges: true
    }))

    const api = gridRef.value?.gridApi
    if (api) {
      api.applyTransaction({ add: preparedRows, addIndex: 0 })
      preparedRows.forEach(row => {
        unsavedChanges.value.add(row.entry_id)
      })
      showSnackbar(t('paste.rowsAdded', { count: preparedRows.length }), 'success')
    }

    parsedPasteData.value = null
    convertedPasteRows.value = []
    pasteValidationResult.value = null
    pasteColumnMapping.value = null
  }

  const onPasteCancel = () => {
    showPasteDialog.value = false
    parsedPasteData.value = null
    convertedPasteRows.value = []
    pasteValidationResult.value = null
    pasteColumnMapping.value = null
  }

  // Watchers & lifecycle
  watch(entries, () => {
    applyFilters()
  }, { immediate: true })

  onMounted(async () => {
    await kpiStore.fetchReferenceData()
    await kpiStore.fetchProductionEntries()
    applyFilters()
  })

  return {
    // Refs
    gridRef,
    unsavedChanges,
    saving,
    snackbar,
    // Confirmation
    showConfirmDialog,
    pendingData,
    confirmationFieldConfig,
    // Paste
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    pasteGridColumns,
    // Filters
    dateFilter,
    productFilter,
    shiftFilter,
    products,
    shifts,
    // Data
    filteredEntries,
    hasUnsavedChanges,
    columnDefs,
    // Stats
    totalUnits,
    totalRuntime,
    avgEfficiency,
    // Methods
    onGridReady,
    onCellValueChanged,
    addNewEntry,
    saveChanges,
    onConfirmSave,
    onCancelSave,
    applyFilters,
    onRowsPasted,
    onPasteConfirm,
    onPasteCancel
  }
}
