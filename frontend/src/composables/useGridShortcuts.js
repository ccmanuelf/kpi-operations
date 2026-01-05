import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useKeyboardShortcuts } from './useKeyboardShortcuts'

/**
 * Grid-specific keyboard shortcuts for AG Grid
 * Handles navigation, editing, clipboard operations, and selection
 */
export function useGridShortcuts(gridApi, options = {}) {
  const { registerShortcut } = useKeyboardShortcuts({ registerGlobal: false })
  const clipboardData = ref(null)
  const undoStack = ref([])
  const redoStack = ref([])
  const isGridFocused = ref(false)

  /**
   * Check if grid is focused
   */
  const checkGridFocus = () => {
    if (!gridApi.value) return false
    const activeElement = document.activeElement
    const gridElement = gridApi.value.getGridElement?.()
    return gridElement?.contains(activeElement) || isGridFocused.value
  }

  /**
   * Get current selection
   */
  const getCurrentSelection = () => {
    if (!gridApi.value) return null
    const selectedNodes = gridApi.value.getSelectedNodes()
    const focusedCell = gridApi.value.getFocusedCell()
    return { selectedNodes, focusedCell }
  }

  /**
   * Save state for undo
   */
  const saveStateForUndo = (action, data) => {
    undoStack.value.push({ action, data, timestamp: Date.now() })
    if (undoStack.value.length > 50) {
      undoStack.value.shift()
    }
    redoStack.value = [] // Clear redo stack on new action
  }

  /**
   * Register grid shortcuts
   */
  const registerGridShortcuts = () => {
    // Arrow key navigation (already handled by AG Grid, but we can enhance)
    // No need to register, AG Grid handles this natively

    // Tab navigation
    registerShortcut('grid-tab-next', {
      key: 'tab',
      description: 'Move to next editable cell',
      category: 'Grid Navigation',
      context: checkGridFocus,
      preventDefault: false, // Let AG Grid handle it
      handler: () => {
        // AG Grid handles tab navigation natively
      }
    })

    registerShortcut('grid-tab-prev', {
      key: 'tab',
      shift: true,
      description: 'Move to previous editable cell',
      category: 'Grid Navigation',
      context: checkGridFocus,
      preventDefault: false,
      handler: () => {
        // AG Grid handles shift+tab natively
      }
    })

    // Enter to edit/confirm
    registerShortcut('grid-enter-edit', {
      key: 'enter',
      description: 'Edit cell / Confirm edit',
      category: 'Grid Editing',
      context: checkGridFocus,
      preventDefault: false,
      handler: () => {
        if (!gridApi.value) return
        const focusedCell = gridApi.value.getFocusedCell()
        if (focusedCell) {
          gridApi.value.startEditingCell({
            rowIndex: focusedCell.rowIndex,
            colKey: focusedCell.column.getId()
          })
        }
      }
    })

    // Escape to cancel
    registerShortcut('grid-escape-cancel', {
      key: 'escape',
      description: 'Cancel cell edit',
      category: 'Grid Editing',
      context: checkGridFocus,
      preventDefault: true,
      handler: () => {
        if (!gridApi.value) return
        gridApi.value.stopEditing(true) // Cancel editing
      }
    })

    // Copy
    registerShortcut('grid-copy', {
      key: 'c',
      ctrl: true,
      description: 'Copy selected cells',
      category: 'Grid Clipboard',
      context: checkGridFocus,
      handler: () => {
        if (!gridApi.value) return
        const selectedData = gridApi.value.getSelectedRows()
        const focusedCell = gridApi.value.getFocusedCell()

        if (selectedData.length > 0) {
          clipboardData.value = {
            type: 'rows',
            data: JSON.parse(JSON.stringify(selectedData))
          }
          // Also copy to system clipboard
          gridApi.value.copySelectedRowsToClipboard()
        } else if (focusedCell) {
          const cellValue = gridApi.value.getValue(
            focusedCell.column.getId(),
            gridApi.value.getDisplayedRowAtIndex(focusedCell.rowIndex)
          )
          clipboardData.value = {
            type: 'cell',
            data: cellValue
          }
        }
      }
    })

    // Cut
    registerShortcut('grid-cut', {
      key: 'x',
      ctrl: true,
      description: 'Cut selected cells',
      category: 'Grid Clipboard',
      context: checkGridFocus,
      handler: () => {
        if (!gridApi.value) return
        const selectedData = gridApi.value.getSelectedRows()

        if (selectedData.length > 0) {
          clipboardData.value = {
            type: 'rows',
            data: JSON.parse(JSON.stringify(selectedData))
          }

          // Save for undo
          saveStateForUndo('cut', { rows: selectedData })

          // Clear the data
          selectedData.forEach(row => {
            const rowNode = gridApi.value.getRowNode(row.id || row.entry_id)
            if (rowNode) {
              // Clear all editable fields
              const columns = gridApi.value.getColumns()
              columns.forEach(col => {
                if (col.editable) {
                  rowNode.setDataValue(col.getId(), null)
                }
              })
            }
          })
        }
      }
    })

    // Paste
    registerShortcut('grid-paste', {
      key: 'v',
      ctrl: true,
      description: 'Paste data',
      category: 'Grid Clipboard',
      context: checkGridFocus,
      handler: () => {
        if (!gridApi.value || !clipboardData.value) return

        const focusedCell = gridApi.value.getFocusedCell()
        if (clipboardData.value.type === 'cell' && focusedCell) {
          // Paste single cell
          const rowNode = gridApi.value.getDisplayedRowAtIndex(focusedCell.rowIndex)
          gridApi.value.getValue(focusedCell.column.getId(), rowNode)
          rowNode.setDataValue(focusedCell.column.getId(), clipboardData.value.data)
        }
        // Note: Multi-cell paste would require custom implementation
      }
    })

    // Undo
    registerShortcut('grid-undo', {
      key: 'z',
      ctrl: true,
      description: 'Undo last action',
      category: 'Grid Editing',
      context: checkGridFocus,
      handler: () => {
        if (undoStack.value.length === 0) return

        const lastAction = undoStack.value.pop()
        redoStack.value.push(lastAction)

        // Implement undo logic based on action type
        if (lastAction.action === 'cut') {
          // Restore cut data
          lastAction.data.rows.forEach(row => {
            const rowNode = gridApi.value.getRowNode(row.id || row.entry_id)
            if (rowNode) {
              rowNode.setData(row)
            }
          })
        }
      }
    })

    // Redo
    registerShortcut('grid-redo', {
      key: 'y',
      ctrl: true,
      description: 'Redo last undone action',
      category: 'Grid Editing',
      context: checkGridFocus,
      handler: () => {
        if (redoStack.value.length === 0) return

        const action = redoStack.value.pop()
        undoStack.value.push(action)

        // Re-apply the action
        // Implementation depends on action type
      }
    })

    // Delete/Clear
    registerShortcut('grid-delete', {
      key: 'delete',
      description: 'Clear cell content',
      category: 'Grid Editing',
      context: checkGridFocus,
      handler: () => {
        if (!gridApi.value) return
        const focusedCell = gridApi.value.getFocusedCell()

        if (focusedCell) {
          const rowNode = gridApi.value.getDisplayedRowAtIndex(focusedCell.rowIndex)
          saveStateForUndo('delete', {
            cell: {
              rowIndex: focusedCell.rowIndex,
              colId: focusedCell.column.getId(),
              value: gridApi.value.getValue(focusedCell.column.getId(), rowNode)
            }
          })
          rowNode.setDataValue(focusedCell.column.getId(), null)
        }
      }
    })

    // Backspace (same as delete)
    registerShortcut('grid-backspace', {
      key: 'backspace',
      description: 'Clear cell content',
      category: 'Grid Editing',
      context: checkGridFocus,
      handler: () => {
        if (!gridApi.value) return
        const focusedCell = gridApi.value.getFocusedCell()

        if (focusedCell) {
          const rowNode = gridApi.value.getDisplayedRowAtIndex(focusedCell.rowIndex)
          rowNode.setDataValue(focusedCell.column.getId(), null)
        }
      }
    })

    // Select All
    registerShortcut('grid-select-all', {
      key: 'a',
      ctrl: true,
      description: 'Select all rows',
      category: 'Grid Selection',
      context: checkGridFocus,
      handler: () => {
        if (!gridApi.value) return
        gridApi.value.selectAll()
      }
    })

    // Select Column
    registerShortcut('grid-select-column', {
      key: ' ',
      ctrl: true,
      description: 'Select current column',
      category: 'Grid Selection',
      context: checkGridFocus,
      handler: () => {
        if (!gridApi.value) return
        const focusedCell = gridApi.value.getFocusedCell()
        if (focusedCell) {
          // Select all cells in column
          const colId = focusedCell.column.getId()
          gridApi.value.selectAll()
          // Note: AG Grid doesn't have native column selection
          // This would require custom implementation
        }
      }
    })

    // Select Row
    registerShortcut('grid-select-row', {
      key: ' ',
      shift: true,
      description: 'Select current row',
      category: 'Grid Selection',
      context: checkGridFocus,
      handler: () => {
        if (!gridApi.value) return
        const focusedCell = gridApi.value.getFocusedCell()
        if (focusedCell) {
          const rowNode = gridApi.value.getDisplayedRowAtIndex(focusedCell.rowIndex)
          rowNode.setSelected(true)
        }
      }
    })

    // Go to first cell
    registerShortcut('grid-first-cell', {
      key: 'home',
      ctrl: true,
      description: 'Go to first cell',
      category: 'Grid Navigation',
      context: checkGridFocus,
      handler: () => {
        if (!gridApi.value) return
        const firstCol = gridApi.value.getColumns()?.[0]
        if (firstCol) {
          gridApi.value.setFocusedCell(0, firstCol.getId())
          gridApi.value.ensureIndexVisible(0)
        }
      }
    })

    // Go to last cell
    registerShortcut('grid-last-cell', {
      key: 'end',
      ctrl: true,
      description: 'Go to last cell',
      category: 'Grid Navigation',
      context: checkGridFocus,
      handler: () => {
        if (!gridApi.value) return
        const rowCount = gridApi.value.getDisplayedRowCount()
        const columns = gridApi.value.getColumns()
        const lastCol = columns?.[columns.length - 1]

        if (lastCol && rowCount > 0) {
          gridApi.value.setFocusedCell(rowCount - 1, lastCol.getId())
          gridApi.value.ensureIndexVisible(rowCount - 1)
        }
      }
    })

    // Page Up
    registerShortcut('grid-page-up', {
      key: 'pageup',
      description: 'Scroll page up',
      category: 'Grid Navigation',
      context: checkGridFocus,
      preventDefault: true,
      handler: () => {
        if (!gridApi.value) return
        const focusedCell = gridApi.value.getFocusedCell()
        if (focusedCell) {
          const newIndex = Math.max(0, focusedCell.rowIndex - 10)
          gridApi.value.setFocusedCell(newIndex, focusedCell.column.getId())
          gridApi.value.ensureIndexVisible(newIndex)
        }
      }
    })

    // Page Down
    registerShortcut('grid-page-down', {
      key: 'pagedown',
      description: 'Scroll page down',
      category: 'Grid Navigation',
      context: checkGridFocus,
      preventDefault: true,
      handler: () => {
        if (!gridApi.value) return
        const focusedCell = gridApi.value.getFocusedCell()
        const rowCount = gridApi.value.getDisplayedRowCount()

        if (focusedCell) {
          const newIndex = Math.min(rowCount - 1, focusedCell.rowIndex + 10)
          gridApi.value.setFocusedCell(newIndex, focusedCell.column.getId())
          gridApi.value.ensureIndexVisible(newIndex)
        }
      }
    })
  }

  /**
   * Track grid focus
   */
  const setupFocusTracking = () => {
    if (!gridApi.value) return

    const gridElement = gridApi.value.getGridElement?.()
    if (gridElement) {
      gridElement.addEventListener('focusin', () => {
        isGridFocused.value = true
      })
      gridElement.addEventListener('focusout', (e) => {
        // Check if focus moved outside grid
        if (!gridElement.contains(e.relatedTarget)) {
          isGridFocused.value = false
        }
      })
    }
  }

  // Watch for gridApi changes
  watch(() => gridApi.value, (newApi) => {
    if (newApi) {
      registerGridShortcuts()
      setupFocusTracking()
    }
  }, { immediate: true })

  return {
    clipboardData,
    undoStack,
    redoStack,
    isGridFocused,
    registerGridShortcuts
  }
}
