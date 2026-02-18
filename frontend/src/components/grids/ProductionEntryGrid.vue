<template>
  <v-card>
    <v-card-title class="d-flex justify-space-between align-center bg-primary">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-factory</v-icon>
        <span class="text-h5">{{ $t('production.entry') }}</span>
      </div>
      <div>
        <v-btn color="white" variant="outlined" @click="addNewEntry" class="mr-2">
          <v-icon left>mdi-plus</v-icon>
          {{ $t('dataEntry.addRow') }}
        </v-btn>
        <v-btn
          color="success"
          @click="saveChanges"
          :disabled="!hasUnsavedChanges"
          :loading="saving"
        >
          <v-icon left>mdi-content-save</v-icon>
          {{ $t('common.save') }} ({{ unsavedChanges.size }})
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
            v-model="productFilter"
            :items="products"
            item-title="product_name"
            item-value="product_id"
            :label="$t('grids.filterByProduct')"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-select
            v-model="shiftFilter"
            :items="shifts"
            item-title="shift_name"
            item-value="shift_id"
            :label="$t('grids.filterByShift')"
            variant="outlined"
            density="compact"
            clearable
            hide-details
          />
        </v-col>
        <v-col cols="12" md="3">
          <v-btn color="primary" @click="applyFilters" block>
            <v-icon left>mdi-filter</v-icon>
            {{ $t('filters.apply') }}
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
        :enable-excel-paste="true"
        entry-type="production"
        @grid-ready="onGridReady"
        @cell-value-changed="onCellValueChanged"
        @rows-pasted="onRowsPasted"
      />

      <!-- Summary stats -->
      <v-row class="mt-3">
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.totalEntries') }}</div>
              <div class="text-h6">{{ filteredEntries.length }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('kpi.totalUnits') }}</div>
              <div class="text-h6">{{ totalUnits.toLocaleString() }}</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.totalRuntime') }}</div>
              <div class="text-h6">{{ totalRuntime.toFixed(1) }} hrs</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="3">
          <v-card variant="outlined">
            <v-card-text>
              <div class="text-caption">{{ $t('grids.avgEfficiency') }}</div>
              <div class="text-h6">{{ avgEfficiency.toFixed(1) }}%</div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- Read-Back Confirmation Dialog -->
    <ReadBackConfirmation
      v-model="showConfirmDialog"
      :title="$t('grids.production.confirmTitle')"
      :subtitle="$t('grids.production.confirmSubtitle')"
      :data="pendingData"
      :field-config="confirmationFieldConfig"
      :loading="saving"
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
      :grid-columns="pasteGridColumns"
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
/**
 * ProductionEntryGrid - Editable data grid for production entry records.
 *
 * Provides inline editing of production data (date, product, shift, units,
 * runtime, employees, defects, scrap) with AG Grid. Supports clipboard paste
 * from spreadsheets, read-back confirmation before save, date/product/shift
 * filtering, and summary statistics (total units, runtime, avg efficiency).
 *
 * Store dependency: useProductionDataStore (productionDataStore)
 * No props or emits -- all state managed via store.
 */
import AGGridBase from './AGGridBase.vue'
import ReadBackConfirmation from '@/components/dialogs/ReadBackConfirmation.vue'
import PastePreviewDialog from '@/components/dialogs/PastePreviewDialog.vue'
import useProductionGridData from '@/composables/useProductionGridData'

const {
  gridRef,
  unsavedChanges,
  saving,
  snackbar,
  showConfirmDialog,
  pendingData,
  confirmationFieldConfig,
  showPasteDialog,
  parsedPasteData,
  convertedPasteRows,
  pasteValidationResult,
  pasteColumnMapping,
  pasteGridColumns,
  dateFilter,
  productFilter,
  shiftFilter,
  products,
  shifts,
  filteredEntries,
  hasUnsavedChanges,
  columnDefs,
  totalUnits,
  totalRuntime,
  avgEfficiency,
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
} = useProductionGridData()
</script>

<style scoped>
/* Component-specific styles */
</style>
