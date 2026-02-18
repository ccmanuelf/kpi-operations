<template>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center bg-primary">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-alert-circle</v-icon>
        <span class="text-h5">{{ $t('grids.downtime.title') }}</span>
      </div>
      <div>
        <v-btn color="white" variant="outlined" @click="addNewEntry" class="mr-2">
          <v-icon left>mdi-plus</v-icon>
          {{ $t('grids.downtime.addDowntime') }}
        </v-btn>
        <v-btn
          color="success"
          @click="saveChanges"
          :disabled="!hasUnsavedChanges"
          :loading="saving"
        >
          <v-icon left>mdi-content-save</v-icon>
          {{ $t('grids.downtime.saveAll') }} ({{ unsavedChanges.size }})
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
            v-model="categoryFilter"
            :items="categories"
            :label="$t('grids.filterByCategory')"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="statusFilter"
            :items="['Resolved', 'Unresolved']"
            :label="$t('grids.filterByStatus')"
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
        entry-type="downtime"
        @grid-ready="onGridReady"
        @cell-value-changed="onCellValueChanged"
        @rows-pasted="onRowsPasted"
      />

      <!-- Summary stats -->
      <v-row class="mt-3">
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.downtime.totalDowntimeEntries') }}</div>
              <div class="text-h6">{{ filteredEntries.length }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" color="error">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.downtime.totalHoursLost') }}</div>
              <div class="text-h6">{{ totalHours.toFixed(1) }} hrs</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" color="warning">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.downtime.unresolvedIssues') }}</div>
              <div class="text-h6">{{ unresolvedCount }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" color="success">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.downtime.resolvedIssues') }}</div>
              <div class="text-h6">{{ resolvedCount }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      :title="$t('grids.downtime.confirmTitle')"
      :subtitle="$t('grids.downtime.confirmSubtitle')"
      :data="pendingData"
      :field-config="confirmationFieldConfig"
      :loading="saving"
      :warning-message="pendingRowsCount > 1 ? $t('grids.downtime.confirmWarning', { count: pendingRowsCount }) : ''"
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
import AGGridBase from './AGGridBase.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'
import PastePreviewDialog from '@/components/dialogs/PastePreviewDialog.vue'
import useDowntimeGridData from '@/composables/useDowntimeGridData'

const {
  gridRef,
  unsavedChanges,
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
  dateFilter,
  categoryFilter,
  statusFilter,
  categories,
  filteredEntries,
  hasUnsavedChanges,
  columnDefs,
  totalHours,
  unresolvedCount,
  resolvedCount,
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
} = useDowntimeGridData()
</script>

<style scoped>
/* Component-specific styles */
</style>
