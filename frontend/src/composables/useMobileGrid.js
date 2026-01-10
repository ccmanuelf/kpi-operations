import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useResponsive } from './useResponsive'

/**
 * Mobile-Optimized Grid Configuration Composable
 *
 * Provides touch-friendly AG Grid configuration for mobile and tablet devices.
 * Implements:
 * - Larger touch targets (56px row height on mobile)
 * - Single click edit for touch devices
 * - Swipe gesture support
 * - Responsive column sizing
 * - Touch-friendly cell styles
 *
 * @returns {Object} Grid options, column defaults, and responsive utilities
 */
export function useMobileGrid() {
  const {
    isMobile,
    isTablet,
    isDesktop,
    isTouchDevice,
    screenWidth,
    screenHeight
  } = useResponsive()

  // Track orientation for optimal grid configuration
  const isLandscape = ref(false)

  const updateOrientation = () => {
    isLandscape.value = window.innerWidth > window.innerHeight
  }

  onMounted(() => {
    updateOrientation()
    window.addEventListener('orientationchange', updateOrientation)
    window.addEventListener('resize', updateOrientation)
  })

  onUnmounted(() => {
    window.removeEventListener('orientationchange', updateOrientation)
    window.removeEventListener('resize', updateOrientation)
  })

  /**
   * Mobile-optimized grid options
   * Configures AG Grid for optimal touch interaction
   */
  const gridOptions = computed(() => ({
    // Larger touch targets for mobile - minimum 44px per iOS/Android guidelines
    rowHeight: isMobile.value ? 56 : isTablet.value ? 48 : 40,
    headerHeight: isMobile.value ? 52 : isTablet.value ? 48 : 44,

    // Touch-friendly selection settings
    suppressCellSelection: isMobile.value,
    enableCellTextSelection: !isMobile.value,

    // Single click edit on mobile/tablet for faster data entry
    singleClickEdit: isMobile.value || isTablet.value,

    // Larger fonts for mobile to improve readability
    cellStyle: isMobile.value ? {
      fontSize: '16px', // 16px prevents iOS zoom on input focus
      padding: '12px',
      lineHeight: '1.4'
    } : isTablet.value ? {
      fontSize: '15px',
      padding: '10px',
      lineHeight: '1.3'
    } : null,

    // Swipe gesture support - allow touch scrolling
    suppressRowClickSelection: isMobile.value,
    suppressTouch: false,

    // Disable features that interfere with touch
    suppressContextMenu: isTouchDevice(),
    suppressMenuHide: true,

    // Enable smooth scrolling on touch devices
    suppressAnimationFrame: false,
    animateRows: !isMobile.value, // Disable on mobile for performance

    // Mobile-specific optimizations
    ...(isMobile.value && {
      // Disable range selection on mobile - interferes with touch scrolling
      enableRangeSelection: false,
      // Enable fill handle for quick data entry
      enableFillHandle: true,
      // Suppress column movement on mobile
      suppressMovableColumns: true,
      // Disable column virtualization on mobile for smoother scrolling
      suppressColumnVirtualisation: true,
      // Show loading overlay on slow devices
      suppressLoadingOverlay: false
    }),

    // Tablet-specific optimizations
    ...(isTablet.value && {
      enableRangeSelection: true,
      enableFillHandle: true,
      suppressMovableColumns: false,
      suppressColumnVirtualisation: false
    })
  }))

  /**
   * Default column definition with responsive settings
   */
  const columnDefaults = computed(() => ({
    // Minimum width larger on mobile for touch targets
    minWidth: isMobile.value ? 120 : isTablet.value ? 110 : 100,

    // Maximum width to ensure columns fit on mobile
    maxWidth: isMobile.value ? 200 : undefined,

    // Disable resize handle on mobile - difficult to use with touch
    resizable: !isMobile.value,

    // Allow sorting on all devices
    sortable: true,

    // Simplified filter on mobile
    filter: isMobile.value ? 'agTextColumnFilter' : true,

    // Suppress column fitting on mobile to maintain minimum widths
    suppressSizeToFit: isMobile.value,

    // Editable by default for data entry
    editable: true,

    // Cell class for responsive styling
    cellClass: isMobile.value ? 'mobile-cell' : isTablet.value ? 'tablet-cell' : 'desktop-cell',

    // Header class for responsive styling
    headerClass: isMobile.value ? 'mobile-header' : isTablet.value ? 'tablet-header' : 'desktop-header',

    // Value formatter for mobile truncation
    valueFormatter: undefined, // Can be set per column

    // Cell style responsive configuration
    cellStyle: (params) => {
      const baseStyle = {
        display: 'flex',
        alignItems: 'center',
        justifyContent: params.colDef.type === 'numericColumn' ? 'flex-end' : 'flex-start'
      }

      if (isMobile.value) {
        return {
          ...baseStyle,
          fontSize: '16px',
          padding: '8px 12px',
          minHeight: '44px'
        }
      }

      if (isTablet.value) {
        return {
          ...baseStyle,
          fontSize: '15px',
          padding: '6px 10px',
          minHeight: '40px'
        }
      }

      return baseStyle
    }
  }))

  /**
   * Get optimal visible columns for current screen size
   * @param {Array} allColumns - Array of all column definitions
   * @param {Object} options - Configuration options
   * @returns {Array} Filtered column definitions for current viewport
   */
  const getVisibleColumns = (allColumns, options = {}) => {
    const {
      priorityField = 'priority',
      maxMobileColumns = 4,
      maxTabletColumns = 6
    } = options

    if (!isMobile.value && !isTablet.value) {
      return allColumns
    }

    // Sort by priority if available
    const sortedColumns = [...allColumns].sort((a, b) => {
      const priorityA = a[priorityField] ?? 999
      const priorityB = b[priorityField] ?? 999
      return priorityA - priorityB
    })

    const maxColumns = isMobile.value ? maxMobileColumns : maxTabletColumns
    return sortedColumns.slice(0, maxColumns)
  }

  /**
   * Get responsive column width based on content type
   * @param {string} type - Column type (text, number, date, action)
   * @returns {Object} Width configuration
   */
  const getColumnWidth = (type = 'text') => {
    const widths = {
      text: {
        mobile: { minWidth: 120, maxWidth: 180 },
        tablet: { minWidth: 120, maxWidth: 200 },
        desktop: { minWidth: 150 }
      },
      number: {
        mobile: { minWidth: 80, maxWidth: 120 },
        tablet: { minWidth: 90, maxWidth: 140 },
        desktop: { minWidth: 100 }
      },
      date: {
        mobile: { minWidth: 100, maxWidth: 130 },
        tablet: { minWidth: 110, maxWidth: 150 },
        desktop: { minWidth: 120 }
      },
      action: {
        mobile: { minWidth: 80, maxWidth: 100 },
        tablet: { minWidth: 90, maxWidth: 120 },
        desktop: { minWidth: 100 }
      },
      status: {
        mobile: { minWidth: 80, maxWidth: 100 },
        tablet: { minWidth: 90, maxWidth: 110 },
        desktop: { minWidth: 100 }
      }
    }

    const typeWidths = widths[type] || widths.text

    if (isMobile.value) return typeWidths.mobile
    if (isTablet.value) return typeWidths.tablet
    return typeWidths.desktop
  }

  /**
   * Get grid container style for current viewport
   * @param {Object} options - Style options
   * @returns {Object} Container style object
   */
  const getContainerStyle = (options = {}) => {
    const { minHeight = '300px', maxHeight = '80vh' } = options

    return computed(() => ({
      width: '100%',
      height: isMobile.value ? 'calc(100vh - 200px)' : isTablet.value ? 'calc(100vh - 180px)' : '600px',
      minHeight,
      maxHeight,
      // Enable momentum scrolling on iOS
      WebkitOverflowScrolling: 'touch',
      // Prevent body scroll when scrolling grid
      overscrollBehavior: 'contain',
      // Enable horizontal scroll on mobile
      overflowX: isMobile.value ? 'auto' : 'hidden',
      overflowY: 'auto'
    }))
  }

  /**
   * Touch event handlers for swipe gestures
   */
  const touchHandlers = {
    startX: 0,
    startY: 0,

    onTouchStart(event) {
      this.startX = event.touches[0].clientX
      this.startY = event.touches[0].clientY
    },

    onTouchEnd(event, callbacks = {}) {
      if (!event.changedTouches[0]) return

      const deltaX = event.changedTouches[0].clientX - this.startX
      const deltaY = event.changedTouches[0].clientY - this.startY

      // Determine swipe direction (minimum 50px swipe)
      if (Math.abs(deltaX) > 50 && Math.abs(deltaX) > Math.abs(deltaY)) {
        if (deltaX > 0 && callbacks.onSwipeRight) {
          callbacks.onSwipeRight()
        } else if (deltaX < 0 && callbacks.onSwipeLeft) {
          callbacks.onSwipeLeft()
        }
      }
    }
  }

  /**
   * Mobile-optimized cell editor configuration
   * @param {string} type - Editor type (text, number, date, select)
   * @returns {Object} Cell editor params
   */
  const getCellEditorParams = (type = 'text') => {
    const baseParams = {
      // Prevent iOS zoom on focus
      style: isMobile.value ? 'font-size: 16px; padding: 12px;' : undefined
    }

    const editorConfigs = {
      text: {
        cellEditor: 'agTextCellEditor',
        cellEditorParams: {
          ...baseParams,
          maxLength: 255
        }
      },
      number: {
        cellEditor: 'agNumberCellEditor',
        cellEditorParams: {
          ...baseParams,
          precision: 2,
          step: 0.01
        }
      },
      date: {
        cellEditor: 'agDateCellEditor',
        cellEditorParams: {
          ...baseParams
        }
      },
      select: {
        cellEditor: 'agSelectCellEditor',
        cellEditorParams: {
          ...baseParams,
          values: [] // Should be provided by caller
        }
      },
      largeText: {
        cellEditor: 'agLargeTextCellEditor',
        cellEditorParams: {
          ...baseParams,
          maxLength: 1000,
          rows: isMobile.value ? 3 : 5,
          cols: isMobile.value ? 30 : 50
        }
      }
    }

    return editorConfigs[type] || editorConfigs.text
  }

  /**
   * Get pagination options for current viewport
   * @returns {Object} Pagination configuration
   */
  const getPaginationOptions = computed(() => ({
    pagination: true,
    paginationPageSize: isMobile.value ? 10 : isTablet.value ? 20 : 50,
    paginationPageSizeSelector: isMobile.value
      ? [10, 20, 50]
      : [20, 50, 100, 200],
    suppressPaginationPanel: false
  }))

  /**
   * CSS class names for responsive styling
   */
  const cssClasses = computed(() => ({
    grid: [
      'ag-theme-material',
      isMobile.value ? 'mobile-grid' : '',
      isTablet.value ? 'tablet-grid' : '',
      isDesktop.value ? 'desktop-grid' : '',
      isTouchDevice() ? 'touch-device' : '',
      isLandscape.value ? 'landscape' : 'portrait'
    ].filter(Boolean).join(' ')
  }))

  return {
    // Responsive state
    isMobile,
    isTablet,
    isDesktop,
    isLandscape,
    isTouchDevice,
    screenWidth,
    screenHeight,

    // Grid configuration
    gridOptions,
    columnDefaults,
    getPaginationOptions,

    // Helper functions
    getVisibleColumns,
    getColumnWidth,
    getContainerStyle,
    getCellEditorParams,

    // Touch support
    touchHandlers,

    // Styling
    cssClasses
  }
}

/**
 * Default export for convenient importing
 */
export default useMobileGrid
