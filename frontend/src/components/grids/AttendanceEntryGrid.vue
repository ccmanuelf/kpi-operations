<template>
  <v-card>
    <v-card-title class="bg-primary">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-account-clock</v-icon>
        <span class="text-h5">{{ $t('grids.attendance.title') }}</span>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Date and Shift Selector -->
      <v-row class="mb-3">
        <v-col cols="12" md="3">
          <v-text-field
            v-model="selectedDate"
            type="date"
            :label="$t('grids.attendance.attendanceDate')"
            variant="outlined"
            density="compact"
            :disabled="loading"
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="selectedShift"
            :items="shifts"
            item-title="shift_name"
            item-value="shift_id"
            :label="$t('filters.shift')"
            variant="outlined"
            density="compact"
            :disabled="loading"
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-btn
            color="primary"
            @click="loadEmployees"
            :loading="loading"
            :disabled="!selectedDate || !selectedShift"
            block
          >
            <v-icon left>mdi-account-multiple</v-icon>
            {{ $t('grids.attendance.loadEmployees') }}
          </v-btn>
        </v-col>
        <v-col cols="12" md="3">
          <v-btn
            color="success"
            @click="bulkSetStatus"
            :disabled="attendanceData.length === 0"
            block
          >
            <v-icon left>mdi-check-all</v-icon>
            {{ $t('grids.attendance.markAllPresent') }}
          </v-btn>
        </v-col>
      </v-row>

      <!-- Quick Stats -->
      <v-row class="mb-3" v-if="attendanceData.length > 0">
        <v-col cols="12" md="2">
          <v-chip color="success" label>
            <v-icon left small>mdi-check</v-icon>
            {{ $t('grids.attendance.present') }}: {{ statusCounts.present }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="2">
          <v-chip color="error" label>
            <v-icon left small>mdi-close</v-icon>
            {{ $t('grids.attendance.absent') }}: {{ statusCounts.absent }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="2">
          <v-chip color="warning" label>
            <v-icon left small>mdi-clock-alert</v-icon>
            {{ $t('grids.attendance.late') }}: {{ statusCounts.late }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="2">
          <v-chip color="info" label>
            <v-icon left small>mdi-calendar-remove</v-icon>
            {{ $t('grids.attendance.leave') }}: {{ statusCounts.leave }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="2">
          <v-chip color="purple" label>
            <v-icon left small>mdi-briefcase-clock</v-icon>
            {{ $t('grids.attendance.halfDay') }}: {{ statusCounts.halfDay }}
          </v-chip>
        </v-col>
        <v-col cols="12" md="2">
          <v-chip label>
            {{ $t('grids.attendance.total') }}: {{ attendanceData.length }}
          </v-chip>
        </v-col>
      </v-row>

      <!-- Info Alert -->
      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        <strong>{{ $t('grids.bulkEntryTips') }}:</strong>
        {{ $t('grids.bulkEntryHints') }}
      </v-alert>

      <AGGridBase
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="attendanceData"
        height="600px"
        :pagination="true"
        :paginationPageSize="100"
        entry-type="attendance"
        @cell-value-changed="markRowAsChanged"
        @grid-ready="onGridReady"
        @rows-pasted="onRowsPasted"
      />

      <v-btn
        color="success"
        @click="saveAttendance"
        class="mt-3"
        :loading="saving"
        :disabled="!hasChanges"
        size="large"
        block
      >
        <v-icon left>mdi-content-save</v-icon>
        {{ $t('grids.attendance.saveRecords', { count: changedRowsCount }) }}
      </v-btn>
    </v-card-text>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      :title="$t('grids.attendance.confirmTitle')"
      :subtitle="$t('grids.attendance.confirmSubtitle')"
      :data="pendingData"
      :field-config="confirmationFieldConfig"
      :loading="saving"
      :warning-message="pendingRowsCount > 1 ? $t('grids.attendance.confirmWarning', { count: pendingRowsCount }) : ''"
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

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.message }}
    </v-snackbar>
  </v-card>
</template>

<script setup>
import AGGridBase from './AGGridBase.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'
import PastePreviewDialog from '@/components/dialogs/PastePreviewDialog.vue'
import TimePickerCellEditor from './editors/TimePickerCellEditor.vue'
import useAttendanceGridData from '@/composables/useAttendanceGridData'

const {
  gridRef,
  selectedDate,
  selectedShift,
  shifts,
  attendanceData,
  loading,
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
  statusCounts,
  columnDefs,
  onGridReady,
  loadEmployees,
  markRowAsChanged,
  bulkSetStatus,
  saveAttendance,
  onConfirmSave,
  onCancelSave,
  onRowsPasted,
  onPasteConfirm,
  onPasteCancel
} = useAttendanceGridData({ TimePickerCellEditor })
</script>

<style scoped>
/* Component-specific styles */
</style>
