<template>
  <div class="ag-grid-wrapper">
    <!-- Toolbar (paste-from-Excel + CSV import + export) -->
    <div
      v-if="enableExcelPaste || enableCsvImport || enableExport"
      class="paste-toolbar d-flex align-center ga-2 mb-2"
    >
      <v-btn
        v-if="enableExcelPaste"
        color="primary"
        variant="outlined"
        size="small"
        :loading="pasteLoading"
        @click="handlePasteFromExcel"
      >
        <v-icon left>mdi-microsoft-excel</v-icon>
        {{ $t('paste.pasteFromExcel') }}
      </v-btn>
      <v-btn
        v-if="enableCsvImport"
        color="primary"
        variant="outlined"
        size="small"
        :aria-label="$t('csv.importAria')"
        :loading="pasteLoading"
        @click="triggerCsvFilePicker"
      >
        <v-icon left>mdi-file-upload-outline</v-icon>
        {{ $t('csv.importCsv') }}
      </v-btn>
      <input
        ref="csvFileInput"
        type="file"
        accept=".csv,text/csv"
        style="display: none"
        @change="onCsvFileSelected"
      />
      <v-chip v-if="lastPasteCount > 0" size="small" color="success" variant="tonal">
        {{ $t('paste.lastPasted', { count: lastPasteCount }) }}
      </v-chip>
      <v-spacer />
      <v-btn
        v-if="enableExport"
        color="secondary"
        variant="outlined"
        size="small"
        :aria-label="$t('grids.exportCsvAria')"
        @click="exportCsvFromToolbar"
      >
        <v-icon left>mdi-file-delimited-outline</v-icon>
        {{ $t('grids.exportCsv') }}
      </v-btn>
      <span v-if="enableExcelPaste" class="text-caption text-grey">{{ $t('paste.shortcutHint') }}</span>
    </div>

    <div :class="`ag-theme-material ${customClass}`" :style="gridStyle">
      <ag-grid-vue
        style="width: 100%; height: 100%;"
      :columnDefs="columnDefs"
      :rowData="rowData"
      :defaultColDef="defaultColDef"
      :gridOptions="mergedGridOptions"
      :rowSelection="rowSelectionConfig"
      :enableCellTextSelection="true"
      :singleClickEdit="true"
      :enterMovesDownAfterEdit="true"
      :enterNavigatesVertically="true"
      :enterNavigatesVerticallyAfterEdit="true"
      :stopEditingWhenCellsLoseFocus="true"
      :animateRows="true"
      :suppressMenuHide="false"
      :undoRedoCellEditing="true"
      :undoRedoCellEditingLimit="20"
      @grid-ready="onGridReady"
      @cell-value-changed="handleCellValueChanged"
      @row-editing-started="handleRowEditingStarted"
      @row-editing-stopped="handleRowEditingStopped"
      @cell-clicked="handleCellClicked"
      @paste-start="handlePasteStart"
      @paste-end="handlePasteEnd"
      />
    </div>

    <!-- Snackbar -->
    <v-snackbar
      v-model="snackbar.show"
      :color="snackbar.color"
      :timeout="3000"
    >
      {{ snackbar.text }}
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { useAGGridBase } from '@/composables/useAGGridBase'

const props = defineProps({
  columnDefs: {
    type: Array,
    required: true
  },
  rowData: {
    type: Array,
    default: () => []
  },
  height: {
    type: String,
    default: '600px'
  },
  customClass: {
    type: String,
    default: ''
  },
  rowSelection: {
    type: [String, Object],
    default: 'multiRow'
  },
  gridOptions: {
    type: Object,
    default: () => ({})
  },
  enableRangeSelection: {
    type: Boolean,
    default: true
  },
  pagination: {
    type: Boolean,
    default: false
  },
  paginationPageSize: {
    type: Number,
    default: 50
  },
  enableExcelPaste: {
    type: Boolean,
    default: true
  },
  // Toolbar CSV-file import button. Default true so every migrated
  // entry surface satisfies the Spreadsheet Standard's "Every entry
  // surface supports CSV import" requirement (entry-ui-standard.md
  // §1, §1.bulk). Pass `:enableCsvImport="false"` on surfaces where
  // file import isn't applicable (read-only summaries, master-detail
  // child grids that share a parent's import path).
  enableCsvImport: {
    type: Boolean,
    default: true
  },
  // Toolbar Export-to-CSV button. Default true so every migrated entry
  // surface satisfies the Spreadsheet Standard's "round-trip safe CSV
  // export" requirement automatically. Pass `:enableExport="false"` for
  // surfaces where export isn't appropriate (e.g. read-only summaries).
  enableExport: {
    type: Boolean,
    default: true
  },
  exportFilename: {
    type: String,
    default: ''
  },
  entryType: {
    type: String,
    default: 'production',
    validator: (v) => ['production', 'quality', 'attendance', 'downtime', 'hold'].includes(v)
  }
})

const emit = defineEmits([
  'grid-ready',
  'cell-value-changed',
  'row-editing-started',
  'row-editing-stopped',
  'cell-clicked',
  'paste-start',
  'paste-end',
  'rows-pasted'
])

const {
  gridApi,
  columnApi,
  pasteLoading,
  lastPasteCount,
  snackbar,
  gridStyle,
  rowSelectionConfig,
  defaultColDef,
  mergedGridOptions,
  onGridReady,
  handleCellValueChanged,
  handleRowEditingStarted,
  handleRowEditingStopped,
  handleCellClicked,
  handlePasteStart,
  handlePasteEnd,
  handlePasteFromExcel,
  handleCsvFileImport,
  exportToCsv,
  exportToExcel,
  clearSelection,
  getSelectedRows,
  refreshCells,
  addRowsToGrid
} = useAGGridBase(props, emit)

// Toolbar export — uses AG Grid's native exportDataAsCsv via the
// composable helper. Filename precedence: explicit `exportFilename`
// prop → `<entryType>_export_<yyyy-mm-dd>.csv`.
const exportCsvFromToolbar = () => {
  const stamp = new Date().toISOString().slice(0, 10)
  const filename = props.exportFilename || `${props.entryType}_export_${stamp}.csv`
  exportToCsv(filename)
}

// CSV file-picker plumbing for the toolbar Import-CSV button.
const csvFileInput = ref(null)
const triggerCsvFilePicker = () => {
  csvFileInput.value?.click()
}
const onCsvFileSelected = (event) => {
  const file = event.target?.files?.[0]
  if (!file) return
  handleCsvFileImport(file)
  // Reset so re-importing the same file fires `change` again.
  if (event.target) event.target.value = ''
}

// Expose grid API and helper methods for parent components
defineExpose({
  gridApi,
  columnApi,
  exportToCsv,
  exportToExcel,
  handleCsvFileImport,
  clearSelection,
  getSelectedRows,
  refreshCells,
  addRowsToGrid,
  handlePasteFromExcel
})
</script>

<style scoped>
/* AG Grid Material Theme is imported globally in main.js */
/* Component-specific overrides can be added here */

/* Wrapper for the entire grid component including toolbar */
.ag-grid-wrapper {
  width: 100%;
}

.paste-toolbar {
  padding: 8px 12px;
  background-color: rgba(var(--v-theme-surface-variant), 0.3);
  border-radius: 4px;
}

.ga-2 {
  gap: 8px;
}

.ag-theme-material {
  font-family: 'Roboto', sans-serif;
}

/* Highlight cells being edited */
:deep(.ag-cell-inline-editing) {
  background-color: var(--cds-yellow-10, #fcf4d6) !important;
  box-shadow: inset 0 0 0 2px var(--cds-focus, #0f62fe);
}

/* Highlight cells with unsaved changes */
:deep(.ag-cell-data-changed) {
  background-color: var(--cds-yellow-20, #fddc69) !important;
}

/* Better focus indication */
:deep(.ag-cell-focus) {
  border: 2px solid var(--cds-focus, #0f62fe) !important;
}

/* Range selection styling */
:deep(.ag-cell-range-selected) {
  background-color: rgba(15, 98, 254, 0.1) !important;
}

/* Mobile-specific styles */
@media (max-width: 767px) {
  .ag-theme-material {
    font-size: 13px;
  }

  :deep(.ag-header-cell) {
    padding: 8px 4px;
    font-size: 12px;
  }

  :deep(.ag-cell) {
    padding: 4px;
  }

  :deep(.ag-row) {
    min-height: 36px;
  }

  /* Enable horizontal scrolling */
  :deep(.ag-body-horizontal-scroll) {
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
  }

  /* Touch-friendly cell editing */
  :deep(.ag-cell-edit-input) {
    font-size: 16px !important; /* Prevents iOS zoom */
    padding: 8px;
  }

  /* Larger touch targets for filters */
  :deep(.ag-filter) {
    min-height: 44px;
  }

  /* Hide column menu on mobile */
  :deep(.ag-header-cell-menu-button) {
    display: none;
  }
}

/* Tablet-specific styles */
@media (min-width: 768px) and (max-width: 1023px) {
  .ag-theme-material {
    font-size: 14px;
  }

  :deep(.ag-header-cell) {
    padding: 10px 6px;
    font-size: 13px;
  }

  :deep(.ag-cell) {
    padding: 6px;
  }

  :deep(.ag-row) {
    min-height: 40px;
  }
}

/* Desktop-specific styles */
@media (min-width: 1024px) {
  :deep(.ag-header-cell) {
    padding: 12px 8px;
  }

  :deep(.ag-cell) {
    padding: 8px;
  }

  :deep(.ag-row) {
    min-height: 44px;
  }
}

/* Touch device optimizations */
@media (hover: none) and (pointer: coarse) {
  /* Larger tap targets */
  :deep(.ag-cell) {
    min-height: 44px;
  }

  :deep(.ag-header-cell) {
    min-height: 44px;
  }

  /* Better touch scrolling */
  :deep(.ag-body-viewport) {
    -webkit-overflow-scrolling: touch;
  }

  /* Disable hover effects on touch */
  :deep(.ag-row-hover) {
    background-color: transparent !important;
  }
}
</style>
