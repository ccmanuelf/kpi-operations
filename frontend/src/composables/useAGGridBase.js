/**
 * Composable for AG Grid base configuration, event handling, and Excel paste logic.
 * Extracted from AGGridBase.vue to keep component under 500 lines.
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
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

export function useAGGridBase(props, emit) {
  const { t } = useI18n()
  const {
    isMobile,
    isTablet,
    isDesktop,
    getGridHeight,
    getColumnWidth,
    getRowHeight,
    isTouchDevice
  } = useResponsive()

  // Grid API refs
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
  const snackbar = ref({ show: false, text: '', color: 'info' })

  // Calculate toolbar height (approximately 56px when visible including margin)
  const toolbarHeight = computed(() => props.enableExcelPaste ? 56 : 0)

  // AG Grid requires explicit dimensions directly on the ag-grid-vue component
  const gridStyle = computed(() => {
    const totalHeight = props.height || getGridHeight()
    const heightValue = parseInt(totalHeight, 10) || 600
    const gridHeight = heightValue - toolbarHeight.value

    return {
      width: '100%',
      height: `${gridHeight}px`
    }
  })

  // AG Grid v32.2+ requires object format for rowSelection
  const rowSelectionConfig = computed(() => {
    if (typeof props.rowSelection === 'object') {
      return props.rowSelection
    }

    const mode = props.rowSelection === 'single' ? 'singleRow' : 'multiRow'

    return {
      mode,
      enableClickSelection: false,
      checkboxes: false,
      headerCheckbox: false
    }
  })

  // Default column configuration for Excel-like behavior with responsive adjustments
  const defaultColDef = computed(() => ({
    sortable: true,
    filter: true,
    resizable: !isMobile.value,
    editable: true,
    minWidth: isMobile.value ? 80 : 100,
    maxWidth: isMobile.value ? 200 : undefined,
    cellStyle: {
      fontFamily: 'Roboto, sans-serif',
      fontSize: isMobile.value ? '13px' : isTablet.value ? '14px' : '14px'
    },
    enableCellChangeFlash: true,
    suppressKeyboardEvent: (params) => {
      const keyCode = params.event.keyCode
      const ctrlPressed = params.event.ctrlKey || params.event.metaKey

      if (ctrlPressed && (keyCode === 67 || keyCode === 86)) return false
      if (keyCode === 46) return false

      return false
    }
  }))

  // Merge user grid options with defaults and responsive settings
  const mergedGridOptions = computed(() => ({
    ...props.gridOptions,
    theme: 'legacy',
    pagination: props.pagination,
    paginationPageSize: props.paginationPageSize,

    rowHeight: getRowHeight(),
    headerHeight: isMobile.value ? 40 : isTablet.value ? 44 : 48,

    suppressTouch: false,
    suppressContextMenu: isTouchDevice(),

    suppressHorizontalScroll: false,
    suppressColumnVirtualisation: isMobile.value,
    singleClickEdit: isMobile.value || isTouchDevice(),

    navigateToNextCell: (params) => {
      const suggestedNextCell = params.nextCellPosition

      if (params.key === 9) {
        return suggestedNextCell
      }

      if (params.key === 13) {
        return {
          rowIndex: params.previousCellPosition.rowIndex + 1,
          column: params.previousCellPosition.column
        }
      }

      return suggestedNextCell
    },

    ...(isMobile.value && {
      suppressMenuHide: false,
      suppressMovableColumns: true,
      suppressRowClickSelection: false
    })
  }))

  // Event handlers
  const onGridReady = (params) => {
    gridApi.value = params.api
    columnApi.value = params.columnApi

    params.api.sizeColumnsToFit()

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
      const clipboardText = await readClipboard()

      if (!clipboardText || clipboardText.trim() === '') {
        snackbar.value = {
          show: true,
          text: t('paste.emptyClipboard'),
          color: 'warning'
        }
        return
      }

      const parsed = parseClipboardData(clipboardText)

      if (parsed.error || parsed.rows.length === 0) {
        snackbar.value = {
          show: true,
          text: t('paste.parseError'),
          color: 'error'
        }
        return
      }

      parsedPasteData.value = parsed

      let columnMapping = { mapping: {}, unmappedClipboard: [], unmappedGrid: [] }

      if (parsed.hasHeaders && parsed.headers.length > 0) {
        columnMapping = mapColumnsToGrid(parsed.headers, props.columnDefs)
      } else {
        const editableColumns = props.columnDefs.filter(c => c.field && c.field !== 'actions')
        editableColumns.forEach((col, idx) => {
          if (idx < parsed.totalColumns) {
            columnMapping.mapping[idx] = col.field
          }
        })
      }

      pasteColumnMapping.value = columnMapping

      const converted = convertToGridRows(parsed.rows, columnMapping.mapping, props.columnDefs)
      convertedPasteRows.value = converted

      const schema = entrySchemas[props.entryType] || entrySchemas.production
      const validation = validateRows(converted, schema)
      pasteValidationResult.value = validation

      emit('rows-pasted', {
        parsedData: parsed,
        convertedRows: converted,
        validationResult: validation,
        columnMapping,
        gridColumns: props.columnDefs
      })

      if (validation.isValid) {
        lastPasteCount.value = converted.length
      } else {
        lastPasteCount.value = validation.totalValid
      }

    } catch (error) {
      console.error('Paste error:', error)
      snackbar.value = {
        show: true,
        text: t('paste.accessDenied'),
        color: 'error'
      }
    } finally {
      pasteLoading.value = false
    }
  }

  // Handle keyboard shortcut for paste
  const handleKeyboardPaste = (event) => {
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

  const addRowsToGrid = (rows) => {
    if (gridApi.value && rows.length > 0) {
      gridApi.value.applyTransaction({ add: rows, addIndex: 0 })
      lastPasteCount.value = rows.length
      return true
    }
    return false
  }

  return {
    // Responsive refs (needed by template)
    isMobile,
    isTablet,
    isDesktop,
    // Grid API refs
    gridApi,
    columnApi,
    // Paste state
    pasteLoading,
    lastPasteCount,
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
    snackbar,
    // Computed
    gridStyle,
    rowSelectionConfig,
    defaultColDef,
    mergedGridOptions,
    // Event handlers
    onGridReady,
    handleCellValueChanged,
    handleRowEditingStarted,
    handleRowEditingStopped,
    handleCellClicked,
    handlePasteStart,
    handlePasteEnd,
    handlePasteFromExcel,
    // Public methods
    exportToCsv,
    exportToExcel,
    clearSelection,
    getSelectedRows,
    refreshCells,
    addRowsToGrid
  }
}
