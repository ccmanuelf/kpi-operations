/**
 * Composable for DowntimeEntryGrid script logic.
 *
 * Encapsulates reactive state, column definitions, CRUD operations,
 * paste handling, filters, summary statistics, and read-back confirmation
 * for the downtime entry grid.
 *
 * Store dependency: useProductionDataStore (productionDataStore)
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProductionDataStore } from '@/stores/productionDataStore'
import { format } from 'date-fns'

export default function useDowntimeGridData() {
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

  const pendingRowsCount = computed(() => pendingRows.value.length)

  // Filters
  const dateFilter = ref(null)
  const categoryFilter = ref(null)
  const statusFilter = ref(null)

  const categories = [
    'Planned Maintenance',
    'Unplanned Breakdown',
    'Changeover',
    'Material Shortage',
    'Quality Issue',
    'Operator Absence',
    'Other'
  ]

  const entries = computed(() => kpiStore.downtimeEntries || [])
  const workOrders = computed(() => kpiStore.workOrders || [])
  const downtimeReasons = computed(() => kpiStore.downtimeReasons || [])
  const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

  // Filtered entries
  const filteredEntries = ref([])

  // Summary statistics
  const totalHours = computed(() => {
    return filteredEntries.value.reduce((sum, e) => sum + (e.duration_hours || 0), 0)
  })

  const unresolvedCount = computed(() => {
    return filteredEntries.value.filter(e => !e.is_resolved).length
  })

  const resolvedCount = computed(() => {
    return filteredEntries.value.filter(e => e.is_resolved).length
  })

  // Field configuration for confirmation dialog
  const confirmationFieldConfig = computed(() => {
    const workOrderNumber = workOrders.value.find(w => w.work_order_id === pendingData.value.work_order_id)?.work_order_number || 'N/A'

    return [
      { key: 'downtime_start_time', label: t('grids.columns.startTime'), type: 'datetime' },
      { key: 'work_order_id', label: t('grids.columns.workOrder'), type: 'text', displayValue: workOrderNumber },
      { key: 'downtime_reason', label: t('grids.columns.reason'), type: 'text' },
      { key: 'category', label: t('grids.columns.category'), type: 'text' },
      { key: 'duration_hours', label: t('grids.columns.duration'), type: 'number' },
      { key: 'impact_on_wip_hours', label: t('grids.columns.wipImpact'), type: 'number' },
      { key: 'is_resolved', label: t('grids.columns.resolved'), type: 'boolean' },
      { key: 'resolution_notes', label: t('grids.columns.resolutionNotes'), type: 'text' }
    ]
  })

  // Column definitions
  const columnDefs = computed(() => [
    {
      headerName: t('grids.columns.startTime'),
      field: 'downtime_start_time',
      editable: true,
      cellEditor: 'agDateStringCellEditor',
      valueFormatter: (params) => {
        return params.value ? format(new Date(params.value), 'MMM dd, yyyy HH:mm') : ''
      },
      cellClass: 'font-weight-bold',
      pinned: 'left',
      width: 180,
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
      headerName: t('grids.columns.reason'),
      field: 'downtime_reason',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: () => ({
        values: downtimeReasons.value.map(r => r.reason_name)
      }),
      width: 200
    },
    {
      headerName: t('grids.columns.category'),
      field: 'category',
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: categories },
      cellStyle: (params) => {
        const categoryColors = {
          'Planned Maintenance': { backgroundColor: '#e3f2fd', color: '#1976d2' },
          'Unplanned Breakdown': { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' },
          'Changeover': { backgroundColor: '#fff9c4', color: '#f57f17' },
          'Material Shortage': { backgroundColor: '#fff3e0', color: '#f57c00' },
          'Quality Issue': { backgroundColor: '#fce4ec', color: '#c2185b' },
          'Operator Absence': { backgroundColor: '#f3e5f5', color: '#7b1fa2' }
        }
        return categoryColors[params.value] || {}
      },
      width: 180
    },
    {
      headerName: t('grids.columns.durationHrs'),
      field: 'duration_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      valueFormatter: (params) => {
        return params.value ? params.value.toFixed(2) : '0.00'
      },
      cellStyle: (params) => {
        const hours = params.value || 0
        if (hours >= 4) return { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' }
        if (hours >= 2) return { backgroundColor: '#fff3e0', color: '#f57c00' }
        return {}
      },
      width: 140
    },
    {
      headerName: t('grids.columns.wipImpactHrs'),
      field: 'impact_on_wip_hours',
      editable: true,
      type: 'numericColumn',
      cellEditor: 'agNumberCellEditor',
      cellEditorParams: { min: 0, precision: 2 },
      valueFormatter: (params) => {
        return params.value ? params.value.toFixed(2) : '0.00'
      },
      width: 150
    },
    {
      headerName: t('grids.columns.status'),
      field: 'is_resolved',
      editable: true,
      cellRenderer: (params) => {
        return params.value ? t('grids.downtime.resolved') : t('grids.downtime.unresolved')
      },
      cellEditor: 'agCheckboxCellEditor',
      cellStyle: (params) => {
        return params.value
          ? { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' }
          : { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' }
      },
      width: 130
    },
    {
      headerName: t('grids.columns.resolutionNotes'),
      field: 'resolution_notes',
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
    const rowId = event.data.downtime_id || event.node.id
    unsavedChanges.value.add(rowId)
    event.data._hasChanges = true
    event.api.refreshCells({ rowNodes: [event.node], force: true })
  }

  const addNewEntry = () => {
    const newEntry = {
      downtime_id: `temp_${Date.now()}`,
      downtime_start_time: new Date().toISOString(),
      work_order_id: workOrders.value[0]?.work_order_id || null,
      downtime_reason: downtimeReasons.value[0]?.reason_name || '',
      category: 'Unplanned Breakdown',
      duration_hours: 0,
      impact_on_wip_hours: 0,
      is_resolved: false,
      resolution_notes: '',
      _isNew: true,
      _hasChanges: true
    }

    const api = gridRef.value?.gridApi
    if (api) {
      api.applyTransaction({ add: [newEntry], addIndex: 0 })
      unsavedChanges.value.add(newEntry.downtime_id)

      setTimeout(() => {
        api.startEditingCell({ rowIndex: 0, colKey: 'downtime_start_time' })
      }, 100)
    }
  }

  const deleteEntry = async (rowData) => {
    if (!confirm(t('grids.downtime.confirmDelete'))) return

    const api = gridRef.value?.gridApi
    if (!api) return

    if (rowData._isNew) {
      api.applyTransaction({ remove: [rowData] })
      unsavedChanges.value.delete(rowData.downtime_id)
      showSnackbar(t('grids.downtime.entryRemoved'), 'info')
      return
    }

    try {
      await kpiStore.deleteDowntimeEntry(rowData.downtime_id)
      api.applyTransaction({ remove: [rowData] })
      unsavedChanges.value.delete(rowData.downtime_id)
      showSnackbar(t('grids.downtime.deleteSuccess'), 'success')
    } catch (error) {
      showSnackbar(t('grids.downtime.deleteError', { error: error.message }), 'error')
    }
  }

  const saveChanges = async () => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const rowsToSave = []
    gridApi.forEachNode(node => {
      if (node.data._hasChanges) {
        rowsToSave.push(node.data)
      }
    })

    if (rowsToSave.length === 0) {
      showSnackbar(t('grids.downtime.noChanges'), 'info')
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
          work_order_id: row.work_order_id,
          downtime_start_time: row.downtime_start_time,
          downtime_reason: row.downtime_reason,
          category: row.category,
          duration_hours: row.duration_hours || 0,
          impact_on_wip_hours: row.impact_on_wip_hours || 0,
          is_resolved: row.is_resolved || false,
          resolution_notes: row.resolution_notes || ''
        }

        try {
          if (row._isNew) {
            const result = await kpiStore.createDowntimeEntry(data)
            if (result.success) {
              row.downtime_id = result.data.downtime_id
              row._isNew = false
              successCount++
            } else {
              errorCount++
            }
          } else {
            const result = await kpiStore.updateDowntimeEntry(row.downtime_id, data)
            if (result.success) {
              successCount++
            } else {
              errorCount++
            }
          }

          row._hasChanges = false
          unsavedChanges.value.delete(row.downtime_id)
        } catch (err) {
          errorCount++
          console.error('Error saving row:', err)
        }
      }

      await kpiStore.fetchDowntimeEntries()
      applyFilters()

      if (errorCount === 0) {
        showSnackbar(t('grids.downtime.saveSuccess', { count: successCount }), 'success')
      } else {
        showSnackbar(t('grids.downtime.savePartial', { success: successCount, failed: errorCount }), 'warning')
      }
    } catch (error) {
      showSnackbar(t('grids.downtime.saveError', { error: error.message }), 'error')
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
    showSnackbar(t('grids.downtime.saveCancelled'), 'info')
  }

  const applyFilters = () => {
    let filtered = [...entries.value]

    if (dateFilter.value) {
      filtered = filtered.filter(e => {
        const entryDate = new Date(e.downtime_start_time).toISOString().split('T')[0]
        return entryDate === dateFilter.value
      })
    }
    if (categoryFilter.value) {
      filtered = filtered.filter(e => e.category === categoryFilter.value)
    }
    if (statusFilter.value) {
      const isResolved = statusFilter.value === 'Resolved'
      filtered = filtered.filter(e => e.is_resolved === isResolved)
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
    showPasteDialog.value = true
  }

  const onPasteConfirm = (rowsToAdd) => {
    const api = gridRef.value?.gridApi
    if (!api) return

    const preparedRows = rowsToAdd.map(row => ({
      downtime_id: `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      downtime_start_time: row.downtime_start_time || new Date().toISOString(),
      work_order_id: row.work_order_id || workOrders.value[0]?.work_order_id || null,
      downtime_reason: row.downtime_reason || downtimeReasons.value[0]?.reason_name || '',
      category: row.category || 'Unplanned Breakdown',
      duration_hours: row.duration_hours || 0,
      impact_on_wip_hours: row.impact_on_wip_hours || 0,
      is_resolved: row.is_resolved || false,
      resolution_notes: row.resolution_notes || '',
      _isNew: true,
      _hasChanges: true
    }))

    api.applyTransaction({ add: preparedRows, addIndex: 0 })
    preparedRows.forEach(row => unsavedChanges.value.add(row.downtime_id))
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

  // Watchers & lifecycle
  watch(entries, () => {
    applyFilters()
  }, { immediate: true })

  onMounted(async () => {
    await kpiStore.fetchReferenceData()
    await kpiStore.fetchDowntimeEntries()
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
    pendingRowsCount,
    confirmationFieldConfig,
    // Paste
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    // Filters
    dateFilter,
    categoryFilter,
    statusFilter,
    categories,
    // Data
    filteredEntries,
    hasUnsavedChanges,
    columnDefs,
    // Stats
    totalHours,
    unresolvedCount,
    resolvedCount,
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
