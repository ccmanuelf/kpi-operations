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
        :columnDefs="allColumnDefs"
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
      :grid-columns="allColumnDefs"
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
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AGGridBase from './AGGridBase.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'
import PastePreviewDialog from '@/components/dialogs/PastePreviewDialog.vue'
import { useHoldGridData } from '@/composables/useHoldGridData'
import { useHoldGridForms } from '@/composables/useHoldGridForms'

const { t } = useI18n()

// --- Data composable: state, filters, columns, stats ---
const {
  kpiStore,
  gridRef,
  unsavedChanges,
  saving,
  snackbar,
  dateFilter,
  statusFilter,
  reasonFilter,
  holdReasons,
  holdStatusOptions,
  entries,
  workOrders,
  filteredEntries,
  hasUnsavedChanges,
  activeCount,
  resumedCount,
  pendingHoldApprovalsCount,
  pendingResumeApprovalsCount,
  pendingApprovalsCount,
  avgDaysOnHold,
  columnDefs,
  applyFilters,
  showSnackbar
} = useHoldGridData()

// --- Forms composable: CRUD, dialogs, approval workflow ---
const {
  resumeDialog,
  confirmResume,
  showConfirmDialog,
  pendingData,
  pendingRowsCount,
  confirmationFieldConfig,
  showPasteDialog,
  parsedPasteData,
  convertedPasteRows,
  pasteValidationResult,
  pasteColumnMapping,
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
  onPasteCancel
} = useHoldGridForms({
  gridRef,
  unsavedChanges,
  saving,
  workOrders,
  kpiStore,
  applyFilters,
  showSnackbar
})

// Actions column — bridges data columns with form methods
const actionsColumn = computed(() => ({
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

    if (status === 'PENDING_HOLD_APPROVAL') {
      buttons += `<button class="ag-grid-approve-hold-btn" style="${btnStyle('#ff9800')}">${t('grids.holds.approvalWorkflow.approveHold')}</button>`
    }

    if (status === 'ON_HOLD') {
      buttons += `<button class="ag-grid-request-resume-btn" style="${btnStyle('#2196f3')}">${t('grids.holds.approvalWorkflow.requestResume')}</button>`
    }

    if (status === 'PENDING_RESUME_APPROVAL') {
      buttons += `<button class="ag-grid-approve-resume-btn" style="${btnStyle('#9c27b0')}">${t('grids.holds.approvalWorkflow.approveResume')}</button>`
    }

    buttons += `<button class="ag-grid-delete-btn" style="${btnStyle('#c62828')}">${t('common.delete')}</button>`

    div.innerHTML = `<div style="display: flex; gap: 4px; flex-wrap: wrap;">${buttons}</div>`

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
}))

// Merge base columns + actions column
const allColumnDefs = computed(() => [...columnDefs.value, actionsColumn.value])

// Filter pending approvals — bridges statusFilter (data) with filteredEntries
const filterPendingApprovals = () => {
  statusFilter.value = null
  applyFilters()
  filteredEntries.value = filteredEntries.value.filter(e =>
    e.hold_status === 'PENDING_HOLD_APPROVAL' || e.hold_status === 'PENDING_RESUME_APPROVAL'
  )
}

onMounted(async () => {
  await kpiStore.fetchReferenceData()
  await kpiStore.fetchHoldEntries()
  applyFilters()
})
</script>

<style scoped>
/* Component-specific styles */
</style>
