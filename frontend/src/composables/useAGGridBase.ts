/**
 * Composable for AG Grid base configuration, event handling, and
 * Excel paste logic.
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
  entrySchemas,
  type ParsedClipboard,
  type GridColumnDef,
  type GridRow,
  type ValidationResult,
  type MapColumnsResult,
} from '@/utils/clipboardParser'

type EmitFn = (event: string, payload?: unknown) => void

interface RowSelectionConfig {
  mode: 'singleRow' | 'multiRow'
  enableClickSelection?: boolean
  checkboxes?: boolean
  headerCheckbox?: boolean
}

export interface AGGridBaseProps {
  enableExcelPaste?: boolean
  height?: string | number
  rowSelection?: 'single' | 'multi' | RowSelectionConfig
  columnDefs: GridColumnDef[]
  gridOptions?: Record<string, unknown>
  pagination?: boolean
  paginationPageSize?: number
  entryType?: string
}

interface SnackbarState {
  show: boolean
  text: string
  color: string
}

interface GridApi {
  sizeColumnsToFit: () => void
  exportDataAsCsv: (params: { fileName: string }) => void
  exportDataAsExcel: (params: { fileName: string }) => void
  deselectAll: () => void
  getSelectedRows: () => GridRow[]
  refreshCells: () => void
  applyTransaction: (params: { add: GridRow[]; addIndex?: number }) => void
  getGridOptions?: () => { context?: { eGridDiv?: HTMLElement } }
}

export function useAGGridBase(props: AGGridBaseProps, emit: EmitFn) {
  const { t } = useI18n()
  const {
    isMobile,
    isTablet,
    isDesktop,
    getGridHeight,
    getRowHeight,
    isTouchDevice,
  } = useResponsive()

  const gridApi = ref<GridApi | null>(null)
  const columnApi = ref<unknown | null>(null)

  const pasteLoading = ref(false)
  const lastPasteCount = ref(0)
  const showPasteDialog = ref(false)
  const parsedPasteData = ref<ParsedClipboard | null>(null)
  const convertedPasteRows = ref<GridRow[]>([])
  const pasteValidationResult = ref<ValidationResult | null>(null)
  const pasteColumnMapping = ref<MapColumnsResult | null>(null)
  const snackbar = ref<SnackbarState>({ show: false, text: '', color: 'info' })

  const toolbarHeight = computed(() => (props.enableExcelPaste ? 56 : 0))

  const gridStyle = computed(() => {
    const totalHeight = props.height || getGridHeight()
    const heightValue = parseInt(String(totalHeight), 10) || 600
    const gridHeight = heightValue - toolbarHeight.value

    return {
      width: '100%',
      height: `${gridHeight}px`,
    }
  })

  const rowSelectionConfig = computed<RowSelectionConfig>(() => {
    if (typeof props.rowSelection === 'object') {
      return props.rowSelection
    }

    const mode = props.rowSelection === 'single' ? 'singleRow' : 'multiRow'

    return {
      mode,
      enableClickSelection: false,
      checkboxes: false,
      headerCheckbox: false,
    }
  })

  const defaultColDef = computed(() => ({
    sortable: true,
    filter: true,
    resizable: !isMobile.value,
    editable: true,
    minWidth: isMobile.value ? 80 : 100,
    maxWidth: isMobile.value ? 200 : undefined,
    cellStyle: {
      fontFamily: 'Roboto, sans-serif',
      fontSize: isMobile.value ? '13px' : isTablet.value ? '14px' : '14px',
    },
    enableCellChangeFlash: true,
    suppressKeyboardEvent: (params: { event: KeyboardEvent }) => {
      const keyCode = params.event.keyCode
      const ctrlPressed = params.event.ctrlKey || params.event.metaKey

      if (ctrlPressed && (keyCode === 67 || keyCode === 86)) return false
      if (keyCode === 46) return false

      return false
    },
  }))

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

    navigateToNextCell: (params: {
      key: number
      nextCellPosition: unknown
      previousCellPosition: { rowIndex: number; column: unknown }
    }) => {
      const suggestedNextCell = params.nextCellPosition

      if (params.key === 9) {
        return suggestedNextCell
      }

      if (params.key === 13) {
        return {
          rowIndex: params.previousCellPosition.rowIndex + 1,
          column: params.previousCellPosition.column,
        }
      }

      return suggestedNextCell
    },

    ...(isMobile.value && {
      suppressMenuHide: false,
      suppressMovableColumns: true,
      suppressRowClickSelection: false,
    }),
  }))

  const onGridReady = (params: { api: GridApi; columnApi?: unknown }): void => {
    gridApi.value = params.api
    columnApi.value = params.columnApi ?? null

    params.api.sizeColumnsToFit()

    if (isTouchDevice()) {
      const eGridDiv = params.api.getGridOptions?.()?.context?.eGridDiv
      if (eGridDiv) {
        ;(eGridDiv.style as CSSStyleDeclaration & {
          webkitOverflowScrolling?: string
        }).webkitOverflowScrolling = 'touch'
      }
    }

    emit('grid-ready', params)
  }

  const handleCellValueChanged = (event: unknown): void => {
    emit('cell-value-changed', event)
  }

  const handleRowEditingStarted = (event: unknown): void => {
    emit('row-editing-started', event)
  }

  const handleRowEditingStopped = (event: unknown): void => {
    emit('row-editing-stopped', event)
  }

  const handleCellClicked = (event: unknown): void => {
    emit('cell-clicked', event)
  }

  const handlePasteStart = (event: unknown): void => {
    emit('paste-start', event)
  }

  const handlePasteEnd = (event: unknown): void => {
    emit('paste-end', event)
  }

  const handlePasteFromExcel = async (): Promise<void> => {
    pasteLoading.value = true

    try {
      const clipboardText = await readClipboard()

      if (!clipboardText || clipboardText.trim() === '') {
        snackbar.value = {
          show: true,
          text: t('paste.emptyClipboard'),
          color: 'warning',
        }
        return
      }

      const parsed = parseClipboardData(clipboardText)

      if (parsed.error || parsed.rows.length === 0) {
        snackbar.value = {
          show: true,
          text: t('paste.parseError'),
          color: 'error',
        }
        return
      }

      parsedPasteData.value = parsed

      let columnMapping: MapColumnsResult = {
        mapping: {},
        unmappedClipboard: [],
        unmappedGrid: [],
      }

      if (parsed.hasHeaders && parsed.headers.length > 0) {
        columnMapping = mapColumnsToGrid(parsed.headers, props.columnDefs)
      } else {
        const editableColumns = props.columnDefs.filter(
          (c) => c.field && c.field !== 'actions',
        )
        editableColumns.forEach((col, idx) => {
          if (idx < (parsed.totalColumns || 0)) {
            if (col.field) columnMapping.mapping[idx] = col.field
          }
        })
      }

      pasteColumnMapping.value = columnMapping

      const converted = convertToGridRows(
        parsed.rows,
        columnMapping.mapping,
        props.columnDefs,
      )
      convertedPasteRows.value = converted

      const schema =
        entrySchemas[props.entryType ?? 'production'] || entrySchemas.production
      const validation = validateRows(converted, schema)
      pasteValidationResult.value = validation

      emit('rows-pasted', {
        parsedData: parsed,
        convertedRows: converted,
        validationResult: validation,
        columnMapping,
        gridColumns: props.columnDefs,
      })

      if (validation.isValid) {
        lastPasteCount.value = converted.length
      } else {
        lastPasteCount.value = validation.totalValid
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('Paste error:', error)
      snackbar.value = {
        show: true,
        text: t('paste.accessDenied'),
        color: 'error',
      }
    } finally {
      pasteLoading.value = false
    }
  }

  const handleKeyboardPaste = (event: KeyboardEvent): void => {
    if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key === 'V') {
      event.preventDefault()
      handlePasteFromExcel()
    }
  }

  onMounted(() => {
    if (props.enableExcelPaste) {
      document.addEventListener('keydown', handleKeyboardPaste)
    }
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyboardPaste)
  })

  const exportToCsv = (filename: string = 'export.csv'): void => {
    gridApi.value?.exportDataAsCsv({ fileName: filename })
  }

  const exportToExcel = (filename: string = 'export.xlsx'): void => {
    gridApi.value?.exportDataAsExcel({ fileName: filename })
  }

  const clearSelection = (): void => {
    gridApi.value?.deselectAll()
  }

  const getSelectedRows = (): GridRow[] => gridApi.value?.getSelectedRows() ?? []

  const refreshCells = (): void => {
    gridApi.value?.refreshCells()
  }

  const addRowsToGrid = (rows: GridRow[]): boolean => {
    if (gridApi.value && rows.length > 0) {
      gridApi.value.applyTransaction({ add: rows, addIndex: 0 })
      lastPasteCount.value = rows.length
      return true
    }
    return false
  }

  return {
    isMobile,
    isTablet,
    isDesktop,
    gridApi,
    columnApi,
    pasteLoading,
    lastPasteCount,
    showPasteDialog,
    parsedPasteData,
    convertedPasteRows,
    pasteValidationResult,
    pasteColumnMapping,
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
    exportToCsv,
    exportToExcel,
    clearSelection,
    getSelectedRows,
    refreshCells,
    addRowsToGrid,
  }
}
