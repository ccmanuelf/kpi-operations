/**
 * Composable for Hold Entry Grid form handling and CRUD operations.
 * Handles: resume dialog, confirmation dialog, paste preview,
 *          add/delete/save entries, approval workflow actions,
 *          grid event handlers (cell changed, grid ready, paste).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { format, differenceInDays } from 'date-fns'

/**
 * @param {Object} options
 * @param {import('vue').Ref} options.gridRef - AG Grid ref
 * @param {import('vue').Ref} options.unsavedChanges - Set of unsaved row IDs
 * @param {import('vue').Ref} options.saving - Saving loading state
 * @param {import('vue').ComputedRef} options.workOrders - Work orders list
 * @param {Object} options.kpiStore - Production data store instance
 * @param {Function} options.applyFilters - Reapply current filters
 * @param {Function} options.showSnackbar - Show notification
 */
export function useHoldGridForms({
  gridRef,
  unsavedChanges,
  saving,
  workOrders,
  kpiStore,
  applyFilters,
  showSnackbar
}) {
  const { t } = useI18n()

  // Resume dialog state
  const resumeDialog = ref({
    show: false,
    hold: null,
    actual_resume_date: null,
    resumed_by_user_id: '',
    resume_approved_at: null
  })

  // Read-back confirmation state
  const showConfirmDialog = ref(false)
  const pendingData = ref({})
  const pendingRows = ref([])
  const pendingRowsCount = computed(() => pendingRows.value.length)

  // Paste preview state
  const showPasteDialog = ref(false)
  const parsedPasteData = ref(null)
  const convertedPasteRows = ref([])
  const pasteValidationResult = ref(null)
  const pasteColumnMapping = ref(null)

  // Approval workflow loading
  const approving = ref(false)

  // Field configuration for confirmation dialog
  const confirmationFieldConfig = computed(() => {
    const workOrderNumber = workOrders.value.find(w => w.work_order_id === pendingData.value.work_order_id)?.work_order_number || 'N/A'

    const startDate = pendingData.value.placed_on_hold_date ? new Date(pendingData.value.placed_on_hold_date) : null
    const endDate = pendingData.value.actual_resume_date ? new Date(pendingData.value.actual_resume_date) : new Date()
    const daysOnHold = startDate ? differenceInDays(endDate, startDate) : 0

    return [
      { key: 'placed_on_hold_date', label: 'Hold Date', type: 'date' },
      { key: 'work_order_id', label: 'Work Order', type: 'text', displayValue: workOrderNumber },
      { key: 'hold_reason', label: 'Hold Reason', type: 'text' },
      { key: 'status_computed', label: 'Status', type: 'text', displayValue: pendingData.value.actual_resume_date ? 'RESUMED' : 'ACTIVE' },
      { key: 'expected_resume_date', label: 'Expected Resume', type: 'date' },
      { key: 'actual_resume_date', label: 'Actual Resume', type: 'datetime' },
      { key: 'days_on_hold_computed', label: 'Days on Hold', type: 'number', displayValue: daysOnHold },
      { key: 'resumed_by_user_id', label: 'Resumed By', type: 'text' },
      { key: 'hold_approved_at', label: 'Hold Approved', type: 'datetime' },
      { key: 'resume_approved_at', label: 'Resume Approved', type: 'datetime' }
    ]
  })

  // --- Grid event handlers ---

  const onGridReady = (params) => {
    setTimeout(() => {
      params.api.sizeColumnsToFit()
    }, 100)
  }

  const onCellValueChanged = (event) => {
    const rowId = event.data.hold_id || event.node.id
    unsavedChanges.value.add(rowId)
    event.data._hasChanges = true
    event.api.refreshCells({ rowNodes: [event.node], force: true })
  }

  // --- CRUD operations ---

  const addNewHold = () => {
    const newHold = {
      hold_id: `temp_${Date.now()}`,
      work_order_id: workOrders.value[0]?.work_order_id || null,
      placed_on_hold_date: format(new Date(), 'yyyy-MM-dd'),
      hold_reason: 'Quality Issue',
      expected_resume_date: null,
      actual_resume_date: null,
      resumed_by_user_id: null,
      hold_approved_at: null,
      resume_approved_at: null,
      _isNew: true,
      _hasChanges: true
    }

    const api = gridRef.value?.gridApi
    if (api) {
      api.applyTransaction({ add: [newHold], addIndex: 0 })
      unsavedChanges.value.add(newHold.hold_id)

      setTimeout(() => {
        api.startEditingCell({
          rowIndex: 0,
          colKey: 'work_order_id'
        })
      }, 100)
    }
  }

  const deleteEntry = async (rowData) => {
    if (!confirm(t('grids.holds.deleteConfirm'))) return

    const api = gridRef.value?.gridApi
    if (!api) return

    if (rowData._isNew) {
      api.applyTransaction({ remove: [rowData] })
      unsavedChanges.value.delete(rowData.hold_id)
      showSnackbar(t('grids.entryRemoved'), 'info')
      return
    }

    try {
      await kpiStore.deleteHoldEntry(rowData.hold_id)
      api.applyTransaction({ remove: [rowData] })
      unsavedChanges.value.delete(rowData.hold_id)
      showSnackbar(t('grids.entryDeleted'), 'success')
    } catch (error) {
      showSnackbar('Error deleting entry: ' + error.message, 'error')
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
          work_order_id: row.work_order_id,
          placed_on_hold_date: row.placed_on_hold_date,
          hold_reason: row.hold_reason,
          expected_resume_date: row.expected_resume_date,
          actual_resume_date: row.actual_resume_date,
          resumed_by_user_id: row.resumed_by_user_id,
          hold_approved_at: row.hold_approved_at,
          resume_approved_at: row.resume_approved_at
        }

        try {
          if (row._isNew) {
            const result = await kpiStore.createHoldEntry(data)
            if (result.success) {
              row.hold_id = result.data.hold_id
              row._isNew = false
              successCount++
            } else {
              errorCount++
            }
          } else {
            const result = await kpiStore.updateHoldEntry(row.hold_id, data)
            if (result.success) {
              successCount++
            } else {
              errorCount++
            }
          }

          row._hasChanges = false
          unsavedChanges.value.delete(row.hold_id)
        } catch (err) {
          errorCount++
          console.error('Error saving row:', err)
        }
      }

      await kpiStore.fetchHoldEntries()
      applyFilters()

      if (errorCount === 0) {
        showSnackbar(t('grids.holds.savedEntries', { count: successCount }), 'success')
      } else {
        showSnackbar(t('grids.attendance.savedWithErrors', { success: successCount, failed: errorCount }), 'warning')
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

  // --- Resume dialog ---

  const openResumeDialog = (hold) => {
    resumeDialog.value = {
      show: true,
      hold,
      actual_resume_date: format(new Date(), "yyyy-MM-dd'T'HH:mm"),
      resumed_by_user_id: '',
      resume_approved_at: format(new Date(), "yyyy-MM-dd'T'HH:mm")
    }
  }

  const confirmResume = () => {
    const { hold, actual_resume_date, resumed_by_user_id, resume_approved_at } = resumeDialog.value

    if (!resumed_by_user_id) {
      showSnackbar(t('grids.holds.resumeDialog.enterUserId'), 'warning')
      return
    }

    hold.actual_resume_date = actual_resume_date
    hold.resumed_by_user_id = resumed_by_user_id
    hold.resume_approved_at = resume_approved_at
    hold._hasChanges = true

    unsavedChanges.value.add(hold.hold_id)

    const api = gridRef.value?.gridApi
    if (api) {
      api.refreshCells({ force: true })
    }

    resumeDialog.value.show = false
    showSnackbar(t('grids.holds.resumeDialog.markedForResume'), 'info')
  }

  // --- Approval workflow ---

  const _approvalRequest = async (holdEntry, endpoint, successMsg) => {
    approving.value = true
    try {
      const response = await fetch(`/api/holds/${holdEntry.hold_entry_id}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || `Failed to ${endpoint.replace('-', ' ')}`)
      }

      showSnackbar(t(successMsg), 'success')
      await kpiStore.fetchHoldEntries()
      applyFilters()
    } catch (error) {
      console.error(`Error during ${endpoint}:`, error)
      showSnackbar(t('common.error') + ': ' + error.message, 'error')
    } finally {
      approving.value = false
    }
  }

  const approveHold = async (holdEntry) => {
    if (!confirm(t('grids.holds.approvalWorkflow.confirmApproveHold'))) return
    await _approvalRequest(holdEntry, 'approve-hold', 'grids.holds.approvalWorkflow.holdApproved')
  }

  const requestResume = async (holdEntry) => {
    if (!confirm(t('grids.holds.approvalWorkflow.confirmRequestResume'))) return
    await _approvalRequest(holdEntry, 'request-resume', 'grids.holds.approvalWorkflow.resumeRequested')
  }

  const approveResume = async (holdEntry) => {
    if (!confirm(t('grids.holds.approvalWorkflow.confirmApproveResume'))) return
    await _approvalRequest(holdEntry, 'approve-resume', 'grids.holds.approvalWorkflow.resumeApproved')
  }

  // --- Paste handlers ---

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
      hold_id: `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      work_order_id: row.work_order_id || workOrders.value[0]?.work_order_id || null,
      placed_on_hold_date: row.placed_on_hold_date || format(new Date(), 'yyyy-MM-dd'),
      hold_reason: row.hold_reason || 'Quality Issue',
      expected_resume_date: row.expected_resume_date || null,
      actual_resume_date: row.actual_resume_date || null,
      resumed_by_user_id: row.resumed_by_user_id || null,
      hold_approved_at: row.hold_approved_at || null,
      resume_approved_at: row.resume_approved_at || null,
      _isNew: true,
      _hasChanges: true
    }))

    api.applyTransaction({ add: preparedRows, addIndex: 0 })
    preparedRows.forEach(row => unsavedChanges.value.add(row.hold_id))
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

  return {
    // Resume dialog
    resumeDialog,
    openResumeDialog,
    confirmResume,
    // Confirmation dialog
    showConfirmDialog,
    pendingData,
    pendingRows,
    pendingRowsCount,
    confirmationFieldConfig,
    // Paste preview
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    // Approval
    approving,
    approveHold,
    requestResume,
    approveResume,
    // Grid events
    onGridReady,
    onCellValueChanged,
    // CRUD
    addNewHold,
    deleteEntry,
    saveChanges,
    onConfirmSave,
    onCancelSave,
    // Paste
    onRowsPasted,
    onPasteConfirm,
    onPasteCancel
  }
}
