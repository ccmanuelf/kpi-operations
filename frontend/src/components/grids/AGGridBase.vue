<template>
  <div :class="`ag-theme-material ag-grid-container ${customClass}`" :style="containerStyle">
    <!-- Paste from Excel Toolbar -->
    <div v-if="enableExcelPaste" class="paste-toolbar d-flex align-center ga-2 mb-2">
      <v-btn
        color="primary"
        variant="outlined"
        size="small"
        @click="handlePasteFromExcel"
        :loading="pasteLoading"
      >
        <v-icon left>mdi-microsoft-excel</v-icon>
        {{ $t('paste.pasteFromExcel') }}
      </v-btn>
      <v-chip v-if="lastPasteCount > 0" size="small" color="success" variant="tonal">
        {{ $t('paste.lastPasted', { count: lastPasteCount }) }}
      </v-chip>
      <v-spacer />
      <span class="text-caption text-grey">{{ $t('paste.shortcutHint') }}</span>
    </div>

    <ag-grid-vue
      :style="gridStyle"
      :columnDefs="columnDefs"
      :rowData="rowData"
      :defaultColDef="defaultColDef"
      :gridOptions="mergedGridOptions"
      :rowSelection="rowSelection"
      :suppressRowClickSelection="true"
      :enableRangeSelection="true"
      :enableFillHandle="true"
      :enableClipboard="true"
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
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { useI18n } from 'vue-i18n'
import { useResponsive } from '@/composables/useResponsive'
import {
  parseClipboardData,
  mapColumnsToGrid,
  convertToGridRows,
  validateRows,
  readClipboard,
  entrySchemas
} from '@/utils/clipboardParser'

// Responsive utilities
const {
  isMobile,
  isTablet,
  isDesktop,
  getGridHeight,
  getColumnWidth,
  getRowHeight,
  isTouchDevice
} = useResponsive()

const { t } = useI18n()

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
    type: String,
    default: 'multiple'
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

const gridApi = ref(null)
const columnApi = ref(null)

// Excel paste state
const pasteLoading = ref(false)
const lastPasteCount = ref(0)
const showPasteDialog = ref(false)
const parsedPasteData = ref(null)
const convertedPasteRows = ref([])
const pasteValidationResult = ref(null)
const pasteColumnMapping = ref(null)

const containerStyle = computed(() => ({
  height: props.height || getGridHeight(),
  width: '100%',
  overflowX: isMobile.value ? 'auto' : 'visible'
}))

// AG Grid v35+ needs explicit dimensions on the grid element for proper rendering
const gridStyle = computed(() => ({
  width: '100%',
  height: '100%'
}))

// Default column configuration for Excel-like behavior with responsive adjustments
const defaultColDef = computed(() => ({
  sortable: true,
  filter: true,
  resizable: !isMobile.value, // Disable resize on mobile
  editable: true,
  minWidth: isMobile.value ? 80 : 100,
  maxWidth: isMobile.value ? 200 : undefined,
  cellStyle: {
    fontFamily: 'Roboto, sans-serif',
    fontSize: isMobile.value ? '13px' : isTablet.value ? '14px' : '14px'
  },
  // Enable copy/paste
  enableCellChangeFlash: true,
  suppressKeyboardEvent: (params) => {
    // Allow Ctrl+C, Ctrl+V, Delete
    const keyCode = params.event.keyCode
    const ctrlPressed = params.event.ctrlKey || params.event.metaKey

    // Allow copy/paste/delete
    if (ctrlPressed && (keyCode === 67 || keyCode === 86)) return false
    if (keyCode === 46) return false

    return false
  }
}))

// Merge user grid options with defaults and responsive settings
const mergedGridOptions = computed(() => ({
  ...props.gridOptions,
  pagination: props.pagination,
  paginationPageSize: props.paginationPageSize,

  // Responsive row height
  rowHeight: getRowHeight(),
  headerHeight: isMobile.value ? 40 : isTablet.value ? 44 : 48,

  // Touch gesture support for mobile
  suppressTouch: false,
  suppressContextMenu: isTouchDevice(),

  // Enable horizontal scrolling on mobile
  suppressHorizontalScroll: false,

  // Adjust column virtualization for mobile
  suppressColumnVirtualisation: isMobile.value,

  // Mobile-friendly single click edit
  singleClickEdit: isMobile.value || isTouchDevice(),

  // Excel-like keyboard shortcuts
  navigateToNextCell: (params) => {
    const suggestedNextCell = params.nextCellPosition

    // Tab navigation
    if (params.key === 9) { // Tab key
      return suggestedNextCell
    }

    // Enter moves down
    if (params.key === 13) { // Enter key
      return {
        rowIndex: params.previousCellPosition.rowIndex + 1,
        column: params.previousCellPosition.column
      }
    }

    return suggestedNextCell
  },

  // Handle range selection for multi-cell operations
  fillOperation: (params) => {
    return params.initialValues[0]
  },

  // Mobile-specific options
  ...(isMobile.value && {
    suppressMenuHide: false,
    suppressMovableColumns: true,
    enableRangeSelection: false, // Disable range selection on mobile
    suppressRowClickSelection: false
  })
}))

const onGridReady = (params) => {
  gridApi.value = params.api
  columnApi.value = params.columnApi

  // Auto-size columns based on screen size
  if (isMobile.value) {
    // On mobile, reduce column widths to fit more columns
    params.api.sizeColumnsToFit()
  } else if (isTablet.value) {
    // On tablet, balance between content and fit
    params.api.sizeColumnsToFit()
  } else {
    // On desktop, auto-size to content
    params.api.sizeColumnsToFit()
  }

  // Enable touch scrolling for mobile
  if (isTouchDevice()) {
    const eGridDiv = params.api.getGridOptions().context?.eGridDiv
    if (eGridDiv) {
      eGridDiv.style.webkitOverflowScrolling = 'touch'
    }
  }

  emit('grid-ready', params)
}

const handleCellValueChanged = (event) => {
  emit('cell-value-changed', event)
}

const handleRowEditingStarted = (event) => {
  emit('row-editing-started', event)
}

const handleRowEditingStopped = (event) => {
  emit('row-editing-stopped', event)
}

const handleCellClicked = (event) => {
  emit('cell-clicked', event)
}

const handlePasteStart = (event) => {
  emit('paste-start', event)
}

const handlePasteEnd = (event) => {
  emit('paste-end', event)
}

// Excel paste functionality
const handlePasteFromExcel = async () => {
  pasteLoading.value = true

  try {
    // Read clipboard
    const clipboardText = await readClipboard()

    if (!clipboardText || clipboardText.trim() === '') {
      alert(t('paste.emptyClipboard'))
      return
    }

    // Parse clipboard data
    const parsed = parseClipboardData(clipboardText)

    if (parsed.error || parsed.rows.length === 0) {
      alert(t('paste.parseError'))
      return
    }

    parsedPasteData.value = parsed

    // Map columns if headers detected
    let columnMapping = { mapping: {}, unmappedClipboard: [], unmappedGrid: [] }

    if (parsed.hasHeaders && parsed.headers.length > 0) {
      columnMapping = mapColumnsToGrid(parsed.headers, props.columnDefs)
    } else {
      // Auto-map by column order if no headers
      const editableColumns = props.columnDefs.filter(c => c.field && c.field !== 'actions')
      editableColumns.forEach((col, idx) => {
        if (idx < parsed.totalColumns) {
          columnMapping.mapping[idx] = col.field
        }
      })
    }

    pasteColumnMapping.value = columnMapping

    // Convert rows to grid format
    const converted = convertToGridRows(parsed.rows, columnMapping.mapping, props.columnDefs)
    convertedPasteRows.value = converted

    // Validate rows
    const schema = entrySchemas[props.entryType] || entrySchemas.production
    const validation = validateRows(converted, schema)
    pasteValidationResult.value = validation

    // Emit event with paste data for parent to handle
    emit('rows-pasted', {
      parsedData: parsed,
      convertedRows: converted,
      validationResult: validation,
      columnMapping,
      gridColumns: props.columnDefs
    })

    // Show success feedback
    if (validation.isValid) {
      lastPasteCount.value = converted.length
    } else {
      lastPasteCount.value = validation.totalValid
    }

  } catch (error) {
    console.error('Paste error:', error)
    alert(t('paste.accessDenied'))
  } finally {
    pasteLoading.value = false
  }
}

// Handle keyboard shortcut for paste
const handleKeyboardPaste = (event) => {
  // Check for Ctrl+Shift+V (custom paste from Excel)
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key === 'V') {
    event.preventDefault()
    handlePasteFromExcel()
  }
}

// Set up keyboard listener
onMounted(() => {
  if (props.enableExcelPaste) {
    document.addEventListener('keydown', handleKeyboardPaste)
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyboardPaste)
})

// Public methods for parent components
const exportToCsv = (filename = 'export.csv') => {
  if (gridApi.value) {
    gridApi.value.exportDataAsCsv({ fileName: filename })
  }
}

const exportToExcel = (filename = 'export.xlsx') => {
  if (gridApi.value) {
    gridApi.value.exportDataAsExcel({ fileName: filename })
  }
}

const clearSelection = () => {
  if (gridApi.value) {
    gridApi.value.deselectAll()
  }
}

const getSelectedRows = () => {
  if (gridApi.value) {
    return gridApi.value.getSelectedRows()
  }
  return []
}

const refreshCells = () => {
  if (gridApi.value) {
    gridApi.value.refreshCells()
  }
}

// Add rows to grid (for paste functionality)
const addRowsToGrid = (rows) => {
  if (gridApi.value && rows.length > 0) {
    gridApi.value.applyTransaction({ add: rows, addIndex: 0 })
    lastPasteCount.value = rows.length
    return true
  }
  return false
}

// Expose grid API and helper methods for parent components
defineExpose({
  gridApi,
  columnApi,
  exportToCsv,
  exportToExcel,
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

/* Ensure proper height distribution between toolbar and grid */
.ag-grid-container {
  display: flex;
  flex-direction: column;
}

.ag-grid-container > :deep(.ag-root-wrapper) {
  flex: 1;
  min-height: 0;
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
  background-color: #fff9c4 !important;
  box-shadow: inset 0 0 0 2px #1a237e;
}

/* Highlight cells with unsaved changes */
:deep(.ag-cell-data-changed) {
  background-color: #fff3e0 !important;
}

/* Better focus indication */
:deep(.ag-cell-focus) {
  border: 2px solid #1a237e !important;
}

/* Range selection styling */
:deep(.ag-cell-range-selected) {
  background-color: rgba(26, 35, 126, 0.1) !important;
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
