<template>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center bg-primary">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-pause-circle</v-icon>
        <span class="text-h5">{{ $t('grids.holds.title') }}</span>
      </div>
      <div>
        <v-btn color="white" variant="outlined" @click="addNewHold" class="mr-2">
          <v-icon left>mdi-plus</v-icon>
          {{ $t('grids.holds.addHold') }}
        </v-btn>
        <v-btn
          color="success"
          @click="saveChanges"
          :disabled="!hasUnsavedChanges"
          :loading="saving"
        >
          <v-icon left>mdi-content-save</v-icon>
          {{ $t('grids.holds.saveAll') }} ({{ unsavedChanges.size }})
        </v-btn>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Keyboard shortcuts help -->
      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-keyboard</v-icon>
          <div>
            <strong>{{ $t('grids.keyboardShortcuts') }}:</strong>
            {{ $t('grids.shortcutsList') }}
          </div>
        </div>
      </v-alert>

      <!-- Filter controls -->
      <v-row class="mb-3">
        <v-col cols="12" md="3">
          <v-text-field
            v-model="dateFilter"
            type="date"
            :label="$t('grids.filterByDate')"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="statusFilter"
            :items="holdStatusOptions"
            :label="$t('grids.filterByStatus')"
            variant="outlined"
            density="compact"
            clearable
            hide-details
            item-title="label"
            item-value="value"
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="reasonFilter"
            :items="holdReasons"
            :label="$t('grids.filterByReason')"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-btn color="primary" @click="applyFilters" block>
            <v-icon left>mdi-filter</v-icon>
            {{ $t('grids.applyFilters') }}
          </v-btn>
        </v-col>
      </v-row>

      <AGGridBase
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="filteredEntries"
        height="600px"
        :pagination="true"
        :paginationPageSize="50"
        entry-type="hold"
        @grid-ready="onGridReady"
        @cell-value-changed="onCellValueChanged"
        @rows-pasted="onRowsPasted"
      />

      <!-- Pending Approvals Alert -->
      <v-alert
        v-if="pendingApprovalsCount > 0"
        type="warning"
        variant="tonal"
        density="compact"
        class="mb-3"
        prominent
      >
        <div class="d-flex align-center justify-space-between">
          <div>
            <v-icon class="mr-2">mdi-alert-circle</v-icon>
            <strong>{{ $t('grids.holds.approvalWorkflow.pendingApprovals', { count: pendingApprovalsCount }) }}</strong>
            <span class="ml-2">
              ({{ pendingHoldApprovalsCount }} {{ $t('grids.holds.approvalWorkflow.pendingHold') }},
              {{ pendingResumeApprovalsCount }} {{ $t('grids.holds.approvalWorkflow.pendingResume') }})
            </span>
          </div>
          <v-btn
            size="small"
            color="warning"
            variant="flat"
            @click="filterPendingApprovals"
          >
            {{ $t('grids.holds.approvalWorkflow.viewPending') }}
          </v-btn>
        </div>
      </v-alert>

      <!-- Summary stats -->
      <v-row class="mt-3">
        <v-col cols="12" md="2">
          <v-card variant="outlined">
            <v-card-text class="text-center pa-2">
              <div class="text-caption">{{ $t('grids.holds.totalHolds') }}</div>
              <div class="text-h6">{{ filteredEntries.length }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="2">
          <v-card variant="outlined" color="warning">
            <v-card-text class="text-center pa-2">
              <div class="text-caption">{{ $t('grids.holds.activeHolds') }}</div>
              <div class="text-h6">{{ activeCount }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="2">
          <v-card variant="outlined" color="success">
            <v-card-text class="text-center pa-2">
              <div class="text-caption">{{ $t('grids.holds.resumedHolds') }}</div>
              <div class="text-h6">{{ resumedCount }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="2">
          <v-card variant="outlined" color="info">
            <v-card-text class="text-center pa-2">
              <div class="text-caption">{{ $t('grids.holds.avgDaysOnHold') }}</div>
              <div class="text-h6">{{ avgDaysOnHold.toFixed(1) }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="2">
          <v-card variant="outlined" color="deep-orange">
            <v-card-text class="text-center pa-2">
              <div class="text-caption">{{ $t('grids.holds.approvalWorkflow.pendingHold') }}</div>
              <div class="text-h6">{{ pendingHoldApprovalsCount }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="2">
          <v-card variant="outlined" color="purple">
            <v-card-text class="text-center pa-2">
              <div class="text-caption">{{ $t('grids.holds.approvalWorkflow.pendingResume') }}</div>
              <div class="text-h6">{{ pendingResumeApprovalsCount }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- Resume Hold Dialog -->
    <v-dialog v-model="resumeDialog.show" max-width="600">
      <v-card>
        <v-card-title class="bg-primary">
          {{ $t('grids.holds.resumeDialog.title') }} - {{ resumeDialog.hold?.work_order_number }}
        </v-card-title>
        <v-card-text class="pt-4">
          <v-row>
            <v-col cols="12">
              <v-text-field
                v-model="resumeDialog.actual_resume_date"
                type="datetime-local"
                :label="$t('grids.holds.resumeDialog.resumeDateTime') + ' *'"
                variant="outlined"
                density="compact"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="resumeDialog.resumed_by_user_id"
                :label="$t('grids.holds.resumeDialog.resumedByUserId') + ' *'"
                variant="outlined"
                density="compact"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="resumeDialog.resume_approved_at"
                type="datetime-local"
                :label="$t('grids.holds.resumeDialog.resumeApprovedAt')"
                variant="outlined"
                density="compact"
              />
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="resumeDialog.show = false">{{ $t('common.cancel') }}</v-btn>
          <v-btn color="success" @click="confirmResume">{{ $t('grids.holds.resumeDialog.confirm') }}</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      :title="$t('grids.holds.confirmTitle')"
      :subtitle="$t('grids.holds.confirmSubtitle')"
      :data="pendingData"
      :field-config="confirmationFieldConfig"
      :loading="saving"
      :warning-message="pendingRowsCount > 1 ? $t('grids.holds.confirmWarning', { count: pendingRowsCount }) : ''"
      @confirm="onConfirmSave"
      @cancel="onCancelSave"
    />

    <!-- Paste Preview Dialog -->
    <PastePreviewDialog
      v-model="showPasteDialog"
      :parsed-data="parsedPasteData"
      :converted-rows="convertedPasteRows"
      :validation-result="pasteValidationResult"
      :column-mapping="pasteColumnMapping"
      :grid-columns="columnDefs"
      @confirm="onPasteConfirm"
      @cancel="onPasteCancel"
    />

    <!-- Snackbar for notifications -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useProductionDataStore } from '@/stores/productionDataStore'
import { format, differenceInDays } from 'date-fns'
import AGGridBase from './AGGridBase.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'
import PastePreviewDialog from '@/components/dialogs/PastePreviewDialog.vue'

const { t } = useI18n()

const kpiStore = useProductionDataStore()
const gridRef = ref(null)
const unsavedChanges = ref(new Set())
const saving = ref(false)
const snackbar = ref({ show: false, message: '', color: 'success' })
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

// Paste preview state
const showPasteDialog = ref(false)
const parsedPasteData = ref(null)
const convertedPasteRows = ref([])
const pasteValidationResult = ref(null)
const pasteColumnMapping = ref(null)

const pendingRowsCount = computed(() => pendingRows.value.length)

// Field configuration for confirmation dialog
const confirmationFieldConfig = computed(() => {
  const workOrderNumber = workOrders.value.find(w => w.work_order_id === pendingData.value.work_order_id)?.work_order_number || 'N/A'

  // Calculate days on hold
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

// Filters
const dateFilter = ref(null)
const statusFilter = ref(null)
const reasonFilter = ref(null)

const holdReasons = [
  'Quality Issue',
  'Material Defect',
  'Process Non-Conformance',
  'Customer Request',
  'Engineering Change',
  'Inspection Failure',
  'Supplier Issue',
  'Other'
]

// Hold status options for the filter - matches backend HoldStatus enum
const holdStatusOptions = computed(() => [
  { label: t('grids.holds.approvalWorkflow.pendingHold'), value: 'PENDING_HOLD_APPROVAL' },
  { label: t('grids.holds.active'), value: 'ON_HOLD' },
  { label: t('grids.holds.approvalWorkflow.pendingResume'), value: 'PENDING_RESUME_APPROVAL' },
  { label: t('grids.holds.resumed'), value: 'RESUMED' },
  { label: t('grids.holds.cancelled'), value: 'CANCELLED' }
])

// Approval workflow state
const approving = ref(false)

const entries = computed(() => kpiStore.holdEntries || [])
const workOrders = computed(() => kpiStore.workOrders || [])
const hasUnsavedChanges = computed(() => unsavedChanges.value.size > 0)

// Filtered entries
const filteredEntries = ref([])

// Summary statistics
const activeCount = computed(() => {
  return entries.value.filter(e => e.hold_status === 'ON_HOLD' || (!e.actual_resume_date && !e.hold_status)).length
})

const resumedCount = computed(() => {
  return entries.value.filter(e => e.hold_status === 'RESUMED' || e.actual_resume_date).length
})

// Pending approvals counts
const pendingHoldApprovalsCount = computed(() => {
  return entries.value.filter(e => e.hold_status === 'PENDING_HOLD_APPROVAL').length
})

const pendingResumeApprovalsCount = computed(() => {
  return entries.value.filter(e => e.hold_status === 'PENDING_RESUME_APPROVAL').length
})

const pendingApprovalsCount = computed(() => {
  return pendingHoldApprovalsCount.value + pendingResumeApprovalsCount.value
})

const avgDaysOnHold = computed(() => {
  if (filteredEntries.value.length === 0) return 0

  const totalDays = filteredEntries.value.reduce((sum, e) => {
    const startDate = new Date(e.placed_on_hold_date)
    const endDate = e.actual_resume_date ? new Date(e.actual_resume_date) : new Date()
    return sum + differenceInDays(endDate, startDate)
  }, 0)

  return totalDays / filteredEntries.value.length
})

// Column definitions
const columnDefs = computed(() => [
  {
    headerName: t('grids.columns.holdDate'),
    field: 'placed_on_hold_date',
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
    headerName: t('grids.columns.holdReason'),
    field: 'hold_reason',
    editable: true,
    cellEditor: 'agSelectCellEditor',
    cellEditorParams: {
      values: holdReasons
    },
    width: 200
  },
  {
    headerName: t('grids.columns.status'),
    field: 'hold_status',
    editable: false,
    valueGetter: (params) => {
      const status = params.data.hold_status || (params.data.actual_resume_date ? 'RESUMED' : 'ON_HOLD')
      const statusLabels = {
        'PENDING_HOLD_APPROVAL': t('grids.holds.approvalWorkflow.pendingHold'),
        'ON_HOLD': t('grids.holds.active'),
        'PENDING_RESUME_APPROVAL': t('grids.holds.approvalWorkflow.pendingResume'),
        'RESUMED': t('grids.holds.resumed'),
        'CANCELLED': t('grids.holds.cancelled')
      }
      return statusLabels[status] || status
    },
    cellStyle: (params) => {
      const status = params.data.hold_status || (params.data.actual_resume_date ? 'RESUMED' : 'ON_HOLD')
      const styles = {
        'PENDING_HOLD_APPROVAL': { backgroundColor: '#fff3e0', color: '#e65100', fontWeight: 'bold' },
        'ON_HOLD': { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' },
        'PENDING_RESUME_APPROVAL': { backgroundColor: '#f3e5f5', color: '#7b1fa2', fontWeight: 'bold' },
        'RESUMED': { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' },
        'CANCELLED': { backgroundColor: '#eceff1', color: '#546e7a', fontWeight: 'bold' }
      }
      return styles[status] || {}
    },
    width: 160
  },
  {
    headerName: t('grids.columns.expectedResume'),
    field: 'expected_resume_date',
    editable: true,
    cellEditor: 'agDateStringCellEditor',
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd, yyyy') : ''
    },
    width: 150
  },
  {
    headerName: t('grids.columns.actualResume'),
    field: 'actual_resume_date',
    editable: false,
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd, yyyy HH:mm') : t('grids.holds.notYetResumed')
    },
    cellStyle: (params) => {
      return params.value ? { backgroundColor: '#e8f5e9', color: '#2e7d32' } : {}
    },
    width: 180
  },
  {
    headerName: t('grids.columns.daysOnHold'),
    field: 'days_on_hold',
    editable: false,
    valueGetter: (params) => {
      const startDate = new Date(params.data.placed_on_hold_date)
      const endDate = params.data.actual_resume_date
        ? new Date(params.data.actual_resume_date)
        : new Date()
      return differenceInDays(endDate, startDate)
    },
    cellStyle: (params) => {
      const days = params.value || 0
      if (days > 7) return { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' }
      if (days > 3) return { backgroundColor: '#fff3e0', color: '#f57c00' }
      return {}
    },
    width: 130
  },
  {
    headerName: t('grids.columns.resumedBy'),
    field: 'resumed_by_user_id',
    editable: false,
    width: 130
  },
  {
    headerName: t('grids.columns.holdApproved'),
    field: 'hold_approved_at',
    editable: true,
    cellEditor: 'agDateStringCellEditor',
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd HH:mm') : t('grids.holds.pending')
    },
    width: 150
  },
  {
    headerName: t('grids.columns.resumeApproved'),
    field: 'resume_approved_at',
    editable: false,
    valueFormatter: (params) => {
      return params.value ? format(new Date(params.value), 'MMM dd HH:mm') : 'N/A'
    },
    width: 150
  },
  {
    headerName: t('grids.columns.actions'),
    field: 'actions',
    editable: false,
    sortable: false,
    filter: false,
    cellRenderer: (params) => {
      const div = document.createElement('div')
      const status = params.data.hold_status || (params.data.actual_resume_date ? 'RESUMED' : 'ON_HOLD')

      const btnStyle = (bg) => `
        background: ${bg};
        color: white;
        border: none;
        padding: 4px 8px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 11px;
        white-space: nowrap;
      `

      let buttons = ''

      // PENDING_HOLD_APPROVAL - Show "Approve Hold" button (supervisors)
      if (status === 'PENDING_HOLD_APPROVAL') {
        buttons += `<button class="ag-grid-approve-hold-btn" style="${btnStyle('#ff9800')}">${t('grids.holds.approvalWorkflow.approveHold')}</button>`
      }

      // ON_HOLD - Show "Request Resume" button
      if (status === 'ON_HOLD') {
        buttons += `<button class="ag-grid-request-resume-btn" style="${btnStyle('#2196f3')}">${t('grids.holds.approvalWorkflow.requestResume')}</button>`
      }

      // PENDING_RESUME_APPROVAL - Show "Approve Resume" button (supervisors)
      if (status === 'PENDING_RESUME_APPROVAL') {
        buttons += `<button class="ag-grid-approve-resume-btn" style="${btnStyle('#9c27b0')}">${t('grids.holds.approvalWorkflow.approveResume')}</button>`
      }

      // Always show delete button
      buttons += `<button class="ag-grid-delete-btn" style="${btnStyle('#c62828')}">${t('common.delete')}</button>`

      div.innerHTML = `<div style="display: flex; gap: 4px; flex-wrap: wrap;">${buttons}</div>`

      // Add event listeners
      const approveHoldBtn = div.querySelector('.ag-grid-approve-hold-btn')
      if (approveHoldBtn) {
        approveHoldBtn.addEventListener('click', () => approveHold(params.data))
      }

      const requestResumeBtn = div.querySelector('.ag-grid-request-resume-btn')
      if (requestResumeBtn) {
        requestResumeBtn.addEventListener('click', () => requestResume(params.data))
      }

      const approveResumeBtn = div.querySelector('.ag-grid-approve-resume-btn')
      if (approveResumeBtn) {
        approveResumeBtn.addEventListener('click', () => approveResume(params.data))
      }

      div.querySelector('.ag-grid-delete-btn').addEventListener('click', () => {
        deleteEntry(params.data)
      })

      return div
    },
    width: 200,
    pinned: 'right'
  }
])

const onGridReady = (params) => {
  // Auto-fit columns initially
  setTimeout(() => {
    params.api.sizeColumnsToFit()
  }, 100)
}

const onCellValueChanged = (event) => {
  // Mark row as unsaved
  const rowId = event.data.hold_id || event.node.id
  unsavedChanges.value.add(rowId)

  // Mark row data as changed
  event.data._hasChanges = true

  // Refresh cell to show visual indicator
  event.api.refreshCells({ rowNodes: [event.node], force: true })
}

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

    // Start editing the first cell
    setTimeout(() => {
      api.startEditingCell({
        rowIndex: 0,
        colKey: 'work_order_id'
      })
    }, 100)
  }
}

// Approval workflow methods
const filterPendingApprovals = () => {
  statusFilter.value = null // Clear first to show both pending types
  applyFilters()
  // Filter to show only pending approvals
  filteredEntries.value = filteredEntries.value.filter(e =>
    e.hold_status === 'PENDING_HOLD_APPROVAL' || e.hold_status === 'PENDING_RESUME_APPROVAL'
  )
}

const approveHold = async (holdEntry) => {
  if (!confirm(t('grids.holds.approvalWorkflow.confirmApproveHold'))) return

  approving.value = true
  try {
    const response = await fetch(`/api/holds/${holdEntry.hold_entry_id}/approve-hold`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      }
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to approve hold')
    }

    showSnackbar(t('grids.holds.approvalWorkflow.holdApproved'), 'success')
    await kpiStore.fetchHoldEntries()
    applyFilters()
  } catch (error) {
    console.error('Error approving hold:', error)
    showSnackbar(t('common.error') + ': ' + error.message, 'error')
  } finally {
    approving.value = false
  }
}

const requestResume = async (holdEntry) => {
  if (!confirm(t('grids.holds.approvalWorkflow.confirmRequestResume'))) return

  approving.value = true
  try {
    const response = await fetch(`/api/holds/${holdEntry.hold_entry_id}/request-resume`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      }
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to request resume')
    }

    showSnackbar(t('grids.holds.approvalWorkflow.resumeRequested'), 'success')
    await kpiStore.fetchHoldEntries()
    applyFilters()
  } catch (error) {
    console.error('Error requesting resume:', error)
    showSnackbar(t('common.error') + ': ' + error.message, 'error')
  } finally {
    approving.value = false
  }
}

const approveResume = async (holdEntry) => {
  if (!confirm(t('grids.holds.approvalWorkflow.confirmApproveResume'))) return

  approving.value = true
  try {
    const response = await fetch(`/api/holds/${holdEntry.hold_entry_id}/approve-resume`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      }
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to approve resume')
    }

    showSnackbar(t('grids.holds.approvalWorkflow.resumeApproved'), 'success')
    await kpiStore.fetchHoldEntries()
    applyFilters()
  } catch (error) {
    console.error('Error approving resume:', error)
    showSnackbar(t('common.error') + ': ' + error.message, 'error')
  } finally {
    approving.value = false
  }
}

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

  // Update the hold data
  hold.actual_resume_date = actual_resume_date
  hold.resumed_by_user_id = resumed_by_user_id
  hold.resume_approved_at = resume_approved_at
  hold._hasChanges = true

  unsavedChanges.value.add(hold.hold_id)

  // Refresh grid
  const api = gridRef.value?.gridApi
  if (api) {
    api.refreshCells({ force: true })
  }

  resumeDialog.value.show = false
  showSnackbar(t('grids.holds.resumeDialog.markedForResume'), 'info')
}

const deleteEntry = async (rowData) => {
  if (!confirm(t('grids.holds.deleteConfirm'))) return

  const api = gridRef.value?.gridApi
  if (!api) return

  // If it's a new unsaved entry, just remove it
  if (rowData._isNew) {
    api.applyTransaction({ remove: [rowData] })
    unsavedChanges.value.delete(rowData.hold_id)
    showSnackbar(t('grids.entryRemoved'), 'info')
    return
  }

  // Delete from backend
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

  // Store pending rows and show confirmation for first row
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

    // Refresh grid data from store
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

  // Prepare rows with required fields
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

const applyFilters = () => {
  let filtered = [...entries.value]

  if (dateFilter.value) {
    filtered = filtered.filter(e => {
      const entryDate = new Date(e.placed_on_hold_date).toISOString().split('T')[0]
      return entryDate === dateFilter.value
    })
  }

  if (statusFilter.value) {
    // Filter by actual hold_status field if available, otherwise fall back to computed status
    filtered = filtered.filter(e => {
      if (e.hold_status) {
        return e.hold_status === statusFilter.value
      }
      // Fallback for legacy data without hold_status
      if (statusFilter.value === 'ON_HOLD') {
        return !e.actual_resume_date
      } else if (statusFilter.value === 'RESUMED') {
        return !!e.actual_resume_date
      }
      return false
    })
  }

  if (reasonFilter.value) {
    filtered = filtered.filter(e => e.hold_reason === reasonFilter.value)
  }

  filteredEntries.value = filtered
}

const showSnackbar = (message, color = 'success') => {
  snackbar.value = { show: true, message, color }
}

// Watch for changes in store data
watch(entries, () => {
  applyFilters()
}, { immediate: true })

onMounted(async () => {
  await kpiStore.fetchReferenceData()
  await kpiStore.fetchHoldEntries()
  applyFilters()
})
</script>

<style scoped>
/* Component-specific styles */
</style>
