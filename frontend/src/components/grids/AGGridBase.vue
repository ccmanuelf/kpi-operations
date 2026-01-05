<template>
  <div :class="`ag-theme-material ${customClass}`" :style="containerStyle">
    <ag-grid-vue
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
import { ref, computed } from 'vue'
import { AgGridVue } from 'ag-grid-vue3'
import { useResponsive } from '@/composables/useResponsive'

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
  }
})

const emit = defineEmits([
  'grid-ready',
  'cell-value-changed',
  'row-editing-started',
  'row-editing-stopped',
  'cell-clicked',
  'paste-start',
  'paste-end'
])

const gridApi = ref(null)
const columnApi = ref(null)

const containerStyle = computed(() => ({
  height: props.height || getGridHeight(),
  width: '100%',
  overflowX: isMobile.value ? 'auto' : 'visible'
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

// Expose grid API and helper methods for parent components
defineExpose({
  gridApi,
  columnApi,
  exportToCsv,
  exportToExcel,
  clearSelection,
  getSelectedRows,
  refreshCells
})
</script>

<style scoped>
/* AG Grid Material Theme is imported globally in main.js */
/* Component-specific overrides can be added here */

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
