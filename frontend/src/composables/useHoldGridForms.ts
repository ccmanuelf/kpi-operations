/**
 * Composable for Hold Entry Grid form handling and CRUD.
 * Confirmation dialog, paste preview, add/delete/save entries,
 * approval workflow actions, grid event handlers.
 *
 * Backend alignment: payload matches backend/schemas/hold.py
 * WIPHoldCreate. client_id derived from authStore (operators) or
 * kpiSelectionStore.selectedClient (admin). Server-controlled fields
 * (resume_date, hold_initiated_by, hold_approved_by, resumed_by) are
 * NOT sent on create — they are set by the approval workflow endpoints
 * (approve-hold, request-resume, approve-resume).
 */
import { ref, computed, type Ref, type ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/authStore'
import { useKPIStore } from '@/stores/kpi'
import { format, differenceInDays } from 'date-fns'
import type { HoldEntry, WorkOrderRef } from './useHoldGridData'
import { HOLD_REASON_CODES } from './useHoldGridData'

interface AGGridApi {
  sizeColumnsToFit: () => void
  applyTransaction: (params: { add?: HoldEntry[]; remove?: HoldEntry[]; addIndex?: number }) => void
  startEditingCell: (params: { rowIndex: number; colKey: string }) => void
  refreshCells: (params: { rowNodes?: unknown[]; force?: boolean }) => void
  forEachNode: (cb: (node: { data: HoldEntry }) => void) => void
}

interface AGGridRef {
  gridApi?: AGGridApi
}

interface CellValueChangedEvent {
  data: HoldEntry & { _hasChanges?: boolean }
  node: { id: string }
  api: AGGridApi
}

interface PasteData {
  parsedData: unknown
  convertedRows: HoldEntry[]
  validationResult: unknown
  columnMapping: unknown
  [key: string]: unknown
}

export interface ConfirmationField {
  key: string
  label: string
  type: 'date' | 'text' | 'datetime' | 'number'
  displayValue?: string | number
}

interface KPIStoreLike {
  deleteHoldEntry: (id: string | number) => Promise<unknown>
  createHoldEntry: (data: Partial<HoldEntry>) => Promise<{ success: boolean; data?: HoldEntry }>
  updateHoldEntry: (
    id: string | number,
    data: Partial<HoldEntry>,
  ) => Promise<{ success: boolean; data?: HoldEntry }>
  fetchHoldEntries: () => Promise<unknown>
}

export interface UseHoldGridFormsOptions {
  gridRef: Ref<AGGridRef | null>
  unsavedChanges: Ref<Set<string | number>>
  saving: Ref<boolean>
  workOrders: ComputedRef<WorkOrderRef[]>
  kpiStore: KPIStoreLike
  applyFilters: () => void
  showSnackbar: (message: string, color?: string) => void
}

export function useHoldGridForms({
  gridRef,
  unsavedChanges,
  saving,
  workOrders,
  kpiStore,
  applyFilters,
  showSnackbar,
}: UseHoldGridFormsOptions) {
  const { t } = useI18n()
  const authStore = useAuthStore()
  const kpiSelectionStore = useKPIStore()

  // Operators inherit client_id from auth; admin users fall back to KPI store selection.
  const activeClientId = (): string | number | null => {
    return authStore.user?.client_id_assigned ?? kpiSelectionStore.selectedClient ?? null
  }

  const showConfirmDialog = ref(false)
  const pendingData = ref<HoldEntry & Record<string, unknown>>({} as HoldEntry)
  const pendingRows = ref<HoldEntry[]>([])
  const pendingRowsCount = computed(() => pendingRows.value.length)

  const showPasteDialog = ref(false)
  const parsedPasteData = ref<unknown | null>(null)
  const convertedPasteRows = ref<HoldEntry[]>([])
  const pasteValidationResult = ref<unknown | null>(null)
  const pasteColumnMapping = ref<unknown | null>(null)

  const approving = ref(false)

  const confirmationFieldConfig = computed<ConfirmationField[]>(() => {
    const workOrderNumber =
      workOrders.value.find((w) => w.work_order_id === pendingData.value.work_order_id)
        ?.work_order_number || 'N/A'

    const startDate = pendingData.value.hold_date
      ? new Date(pendingData.value.hold_date)
      : null
    const endDate = pendingData.value.resume_date
      ? new Date(pendingData.value.resume_date)
      : new Date()
    const daysOnHold = startDate ? differenceInDays(endDate, startDate) : 0

    return [
      { key: 'hold_date', label: t('grids.columns.holdDate'), type: 'date' },
      {
        key: 'work_order_id',
        label: t('grids.columns.workOrder'),
        type: 'text',
        displayValue: workOrderNumber,
      },
      { key: 'hold_reason', label: t('grids.columns.holdReason'), type: 'text' },
      {
        key: 'hold_reason_description',
        label: t('grids.columns.holdReasonDescription'),
        type: 'text',
      },
      { key: 'expected_resolution_date', label: t('grids.columns.expectedResolution'), type: 'date' },
      {
        key: 'days_on_hold_computed',
        label: t('grids.columns.daysOnHold'),
        type: 'number',
        displayValue: daysOnHold,
      },
      { key: 'notes', label: t('grids.columns.notes'), type: 'text' },
    ]
  })

  const onGridReady = (params: { api: AGGridApi }): void => {
    setTimeout(() => {
      params.api.sizeColumnsToFit()
    }, 100)
  }

  const onCellValueChanged = (event: CellValueChangedEvent): void => {
    const rowId = event.data.id || event.node.id
    if (rowId !== undefined) unsavedChanges.value.add(rowId)
    event.data._hasChanges = true
    event.api.refreshCells({ rowNodes: [event.node], force: true })
  }

  const addNewHold = (): void => {
    const newHold: HoldEntry & { _isNew?: boolean; _hasChanges?: boolean } = {
      id: `temp_${Date.now()}`,
      work_order_id: workOrders.value[0]?.work_order_id || undefined,
      hold_date: format(new Date(), 'yyyy-MM-dd'),
      hold_reason: HOLD_REASON_CODES[0],
      hold_reason_description: '',
      expected_resolution_date: null,
      notes: '',
      _isNew: true,
      _hasChanges: true,
    }

    const api = gridRef.value?.gridApi
    if (api && newHold.id !== undefined) {
      api.applyTransaction({ add: [newHold], addIndex: 0 })
      unsavedChanges.value.add(newHold.id)

      setTimeout(() => {
        api.startEditingCell({
          rowIndex: 0,
          colKey: 'work_order_id',
        })
      }, 100)
    }
  }

  const deleteEntry = async (
    rowData: HoldEntry & { _isNew?: boolean },
  ): Promise<void> => {
    if (!confirm(t('grids.holds.deleteConfirm'))) return

    const api = gridRef.value?.gridApi
    if (!api) return

    if (rowData._isNew) {
      api.applyTransaction({ remove: [rowData] })
      if (rowData.id !== undefined) unsavedChanges.value.delete(rowData.id)
      showSnackbar(t('grids.entryRemoved'), 'info')
      return
    }

    if (rowData.id === undefined) return

    try {
      await kpiStore.deleteHoldEntry(rowData.id)
      api.applyTransaction({ remove: [rowData] })
      unsavedChanges.value.delete(rowData.id)
      showSnackbar(t('grids.entryDeleted'), 'success')
    } catch (error) {
      const ax = error as { message?: string }
      showSnackbar('Error deleting entry: ' + (ax?.message || ''), 'error')
    }
  }

  const buildPayload = (
    row: HoldEntry,
    clientId: string | number,
  ): Partial<HoldEntry> => ({
    client_id: String(clientId),
    work_order_id: row.work_order_id,
    hold_date: row.hold_date,
    hold_reason: row.hold_reason,
    hold_reason_description: row.hold_reason_description || undefined,
    expected_resolution_date: row.expected_resolution_date || undefined,
    notes: row.notes || undefined,
  })

  const saveChanges = async (): Promise<void> => {
    const gridApi = gridRef.value?.gridApi
    if (!gridApi) return

    const rowsToSave: HoldEntry[] = []
    gridApi.forEachNode((node) => {
      if ((node.data as HoldEntry & { _hasChanges?: boolean })._hasChanges) {
        rowsToSave.push(node.data)
      }
    })

    if (rowsToSave.length === 0) {
      showSnackbar(t('grids.noChanges'), 'info')
      return
    }

    if (!activeClientId()) {
      showSnackbar(t('grids.holds.errors.noClient'), 'error')
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
      pendingData.value = {} as HoldEntry
      showSnackbar(t('grids.holds.errors.noClient'), 'error')
      return
    }

    try {
      for (const row of pendingRows.value) {
        const data = buildPayload(row, clientId)

        try {
          const r = row as HoldEntry & {
            _isNew?: boolean
            _hasChanges?: boolean
          }
          if (r._isNew) {
            const result = await kpiStore.createHoldEntry(data)
            if (result.success && result.data) {
              row.id = result.data.id ?? result.data.hold_entry_id
              r._isNew = false
              successCount++
            } else {
              errorCount++
            }
          } else {
            if (row.id === undefined) {
              errorCount++
              continue
            }
            const result = await kpiStore.updateHoldEntry(row.id, data)
            if (result.success) {
              successCount++
            } else {
              errorCount++
            }
          }

          r._hasChanges = false
          if (row.id !== undefined) unsavedChanges.value.delete(row.id)
        } catch (err) {
          errorCount++
          // eslint-disable-next-line no-console
          console.error('Error saving row:', err)
        }
      }

      await kpiStore.fetchHoldEntries()
      applyFilters()

      if (errorCount === 0) {
        showSnackbar(t('grids.holds.savedEntries', { count: successCount }), 'success')
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
      showSnackbar('Error saving changes: ' + (ax?.message || ''), 'error')
    } finally {
      saving.value = false
      pendingRows.value = []
      pendingData.value = {} as HoldEntry
    }
  }

  const onCancelSave = (): void => {
    showConfirmDialog.value = false
    pendingRows.value = []
    pendingData.value = {} as HoldEntry
    showSnackbar(t('grids.saveCancelled'), 'info')
  }

  const _approvalRequest = async (
    holdEntry: HoldEntry & { hold_entry_id?: string | number },
    endpoint: string,
    successMsg: string,
  ): Promise<void> => {
    approving.value = true
    try {
      const response = await fetch(`/api/holds/${holdEntry.hold_entry_id}/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (!response.ok) {
        const error = (await response.json()) as { detail?: string }
        throw new Error(error.detail || `Failed to ${endpoint.replace('-', ' ')}`)
      }

      showSnackbar(t(successMsg), 'success')
      await kpiStore.fetchHoldEntries()
      applyFilters()
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error(`Error during ${endpoint}:`, error)
      const ax = error as { message?: string }
      showSnackbar(t('common.error') + ': ' + (ax?.message || ''), 'error')
    } finally {
      approving.value = false
    }
  }

  const approveHold = async (
    holdEntry: HoldEntry & { hold_entry_id?: string | number },
  ): Promise<void> => {
    if (!confirm(t('grids.holds.approvalWorkflow.confirmApproveHold'))) return
    await _approvalRequest(
      holdEntry,
      'approve-hold',
      'grids.holds.approvalWorkflow.holdApproved',
    )
  }

  const requestResume = async (
    holdEntry: HoldEntry & { hold_entry_id?: string | number },
  ): Promise<void> => {
    if (!confirm(t('grids.holds.approvalWorkflow.confirmRequestResume'))) return
    await _approvalRequest(
      holdEntry,
      'request-resume',
      'grids.holds.approvalWorkflow.resumeRequested',
    )
  }

  const approveResume = async (
    holdEntry: HoldEntry & { hold_entry_id?: string | number },
  ): Promise<void> => {
    if (!confirm(t('grids.holds.approvalWorkflow.confirmApproveResume'))) return
    await _approvalRequest(
      holdEntry,
      'approve-resume',
      'grids.holds.approvalWorkflow.resumeApproved',
    )
  }

  const onRowsPasted = (pasteData: PasteData): void => {
    parsedPasteData.value = pasteData.parsedData
    convertedPasteRows.value = pasteData.convertedRows
    pasteValidationResult.value = pasteData.validationResult
    pasteColumnMapping.value = pasteData.columnMapping
    showPasteDialog.value = true
  }

  const onPasteConfirm = (rowsToAdd: Partial<HoldEntry>[]): void => {
    const api = gridRef.value?.gridApi
    if (!api) return

    const preparedRows: HoldEntry[] = rowsToAdd.map((row) => ({
      id: `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      work_order_id: row.work_order_id || workOrders.value[0]?.work_order_id || undefined,
      hold_date: row.hold_date || format(new Date(), 'yyyy-MM-dd'),
      hold_reason: row.hold_reason || HOLD_REASON_CODES[0],
      hold_reason_description: row.hold_reason_description || '',
      expected_resolution_date: row.expected_resolution_date || null,
      notes: row.notes || '',
      _isNew: true,
      _hasChanges: true,
    }))

    api.applyTransaction({ add: preparedRows, addIndex: 0 })
    preparedRows.forEach((row) => {
      if (row.id !== undefined) unsavedChanges.value.add(row.id)
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

  return {
    showConfirmDialog,
    pendingData,
    pendingRows,
    pendingRowsCount,
    confirmationFieldConfig,
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    approving,
    approveHold,
    requestResume,
    approveResume,
    onGridReady,
    onCellValueChanged,
    addNewHold,
    deleteEntry,
    saveChanges,
    onConfirmSave,
    onCancelSave,
    onRowsPasted,
    onPasteConfirm,
    onPasteCancel,
  }
}
