<template>
  <v-card>
    <v-card-title class="bg-primary">
      <div class="d-flex align-center justify-space-between" style="width: 100%;">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-clipboard-check</v-icon>
          <span class="text-h5">{{ $t('grids.quality.title') }}</span>
        </div>
        <div>
          <v-btn
            color="white"
            variant="outlined"
            @click="addRow"
            class="mr-2"
          >
            <v-icon left>mdi-plus</v-icon>
            {{ $t('grids.quality.addInspection') }}
          </v-btn>
          <v-btn
            color="success"
            @click="saveInspections"
            :loading="saving"
            :disabled="!hasChanges"
          >
            <v-icon left>mdi-content-save</v-icon>
            {{ $t('grids.quality.saveAll') }} ({{ changedRowsCount }})
          </v-btn>
        </div>
      </div>
    </v-card-title>

    <v-card-text>
      <!-- Quick Stats -->
      <v-row class="mb-3">
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.quality.totalInspected') }}</div>
              <div class="text-h6">{{ totalInspected.toLocaleString() }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.quality.totalDefects') }}</div>
              <div class="text-h6 error--text">{{ totalDefects.toLocaleString() }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined" :color="avgFPY >= 99 ? 'success' : avgFPY >= 95 ? 'warning' : 'error'">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.quality.avgFpy') }}</div>
              <div class="text-h6">{{ avgFPY.toFixed(2) }}%</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.quality.avgPpm') }}</div>
              <div class="text-h6">{{ avgPPM.toLocaleString() }}</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Info Alert -->
      <v-alert type="info" variant="tonal" density="compact" class="mb-3">
        {{ $t('grids.quality.metricsInfo') }}
      </v-alert>

      <AGGridBase
        ref="gridRef"
        :columnDefs="columnDefs"
        :rowData="qualityData"
        height="600px"
        :pagination="true"
        :paginationPageSize="50"
        entry-type="quality"
        @cell-value-changed="onCellValueChanged"
        @grid-ready="onGridReady"
        @rows-pasted="onRowsPasted"
      />
    </v-card-text>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      :title="$t('grids.quality.confirmTitle')"
      :subtitle="$t('grids.quality.confirmSubtitle')"
      :data="pendingData"
      :field-config="confirmationFieldConfig"
      :loading="saving"
      :warning-message="pendingRowsCount > 1 ? $t('grids.quality.confirmWarning', { count: pendingRowsCount }) : ''"
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
import useQualityGridData from '@/composables/useQualityGridData'

const {
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
  onPasteCancel
} = useQualityGridData()
</script>

<style scoped>
/* Component-specific styles */
</style>
