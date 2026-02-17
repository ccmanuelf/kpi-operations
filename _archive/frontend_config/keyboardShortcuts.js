/**
 * Keyboard Shortcuts Configuration
 * Centralized configuration for all keyboard shortcuts in the application
 */

export const SHORTCUT_CATEGORIES = {
  GLOBAL: 'Global',
  NAVIGATION: 'Navigation',
  GRID_NAVIGATION: 'Grid Navigation',
  GRID_EDITING: 'Grid Editing',
  GRID_CLIPBOARD: 'Grid Clipboard',
  GRID_SELECTION: 'Grid Selection',
  FORM_ACTIONS: 'Form Actions',
  FORM_NAVIGATION: 'Form Navigation',
  FORM_EDITING: 'Form Editing'
}

/**
 * Global shortcuts configuration
 */
export const GLOBAL_SHORTCUTS = [
  {
    id: 'global-save',
    key: 's',
    ctrl: true,
    description: 'Save current form/grid',
    category: SHORTCUT_CATEGORIES.GLOBAL,
    icon: 'mdi-content-save'
  },
  {
    id: 'global-new',
    key: 'n',
    ctrl: true,
    description: 'Create new entry',
    category: SHORTCUT_CATEGORIES.GLOBAL,
    icon: 'mdi-plus'
  },
  {
    id: 'global-search',
    key: 'f',
    ctrl: true,
    description: 'Focus search field',
    category: SHORTCUT_CATEGORIES.GLOBAL,
    icon: 'mdi-magnify'
  },
  {
    id: 'global-command',
    key: 'k',
    ctrl: true,
    description: 'Open command palette',
    category: SHORTCUT_CATEGORIES.GLOBAL,
    icon: 'mdi-palette'
  },
  {
    id: 'global-help',
    key: '/',
    ctrl: true,
    description: 'Show keyboard shortcuts help',
    category: SHORTCUT_CATEGORIES.GLOBAL,
    icon: 'mdi-help-circle'
  },
  {
    id: 'global-escape',
    key: 'escape',
    description: 'Close modals/cancel editing',
    category: SHORTCUT_CATEGORIES.GLOBAL,
    icon: 'mdi-close'
  },
  {
    id: 'global-refresh',
    key: 'r',
    ctrl: true,
    description: 'Refresh current data',
    category: SHORTCUT_CATEGORIES.GLOBAL,
    icon: 'mdi-refresh'
  }
]

/**
 * Navigation shortcuts configuration
 */
export const NAVIGATION_SHORTCUTS = [
  {
    id: 'nav-dashboard',
    key: 'd',
    ctrl: true,
    description: 'Navigate to Dashboard',
    category: SHORTCUT_CATEGORIES.NAVIGATION,
    route: '/',
    icon: 'mdi-view-dashboard'
  },
  {
    id: 'nav-production',
    key: 'p',
    ctrl: true,
    description: 'Navigate to Production Entry',
    category: SHORTCUT_CATEGORIES.NAVIGATION,
    route: '/production-entry',
    icon: 'mdi-factory'
  },
  {
    id: 'nav-quality',
    key: 'q',
    ctrl: true,
    description: 'Navigate to Quality Entry',
    category: SHORTCUT_CATEGORIES.NAVIGATION,
    route: '/data-entry/quality',
    icon: 'mdi-quality-high'
  },
  {
    id: 'nav-attendance',
    key: 'a',
    ctrl: true,
    description: 'Navigate to Attendance',
    category: SHORTCUT_CATEGORIES.NAVIGATION,
    route: '/data-entry/attendance',
    icon: 'mdi-account-group'
  },
  {
    id: 'nav-downtime',
    key: 't',
    ctrl: true,
    description: 'Navigate to Downtime Entry',
    category: SHORTCUT_CATEGORIES.NAVIGATION,
    route: '/data-entry/downtime',
    icon: 'mdi-clock-alert'
  }
]

/**
 * Grid shortcuts configuration
 */
export const GRID_SHORTCUTS = [
  // Navigation
  {
    id: 'grid-tab-next',
    key: 'tab',
    description: 'Move to next editable cell',
    category: SHORTCUT_CATEGORIES.GRID_NAVIGATION
  },
  {
    id: 'grid-tab-prev',
    key: 'tab',
    shift: true,
    description: 'Move to previous editable cell',
    category: SHORTCUT_CATEGORIES.GRID_NAVIGATION
  },
  {
    id: 'grid-first-cell',
    key: 'home',
    ctrl: true,
    description: 'Go to first cell',
    category: SHORTCUT_CATEGORIES.GRID_NAVIGATION
  },
  {
    id: 'grid-last-cell',
    key: 'end',
    ctrl: true,
    description: 'Go to last cell',
    category: SHORTCUT_CATEGORIES.GRID_NAVIGATION
  },
  {
    id: 'grid-page-up',
    key: 'pageup',
    description: 'Scroll page up',
    category: SHORTCUT_CATEGORIES.GRID_NAVIGATION
  },
  {
    id: 'grid-page-down',
    key: 'pagedown',
    description: 'Scroll page down',
    category: SHORTCUT_CATEGORIES.GRID_NAVIGATION
  },

  // Editing
  {
    id: 'grid-enter-edit',
    key: 'enter',
    description: 'Edit cell / Confirm edit',
    category: SHORTCUT_CATEGORIES.GRID_EDITING
  },
  {
    id: 'grid-escape-cancel',
    key: 'escape',
    description: 'Cancel cell edit',
    category: SHORTCUT_CATEGORIES.GRID_EDITING
  },
  {
    id: 'grid-delete',
    key: 'delete',
    description: 'Clear cell content',
    category: SHORTCUT_CATEGORIES.GRID_EDITING
  },
  {
    id: 'grid-backspace',
    key: 'backspace',
    description: 'Clear cell content',
    category: SHORTCUT_CATEGORIES.GRID_EDITING
  },
  {
    id: 'grid-undo',
    key: 'z',
    ctrl: true,
    description: 'Undo last action',
    category: SHORTCUT_CATEGORIES.GRID_EDITING
  },
  {
    id: 'grid-redo',
    key: 'y',
    ctrl: true,
    description: 'Redo last undone action',
    category: SHORTCUT_CATEGORIES.GRID_EDITING
  },

  // Clipboard
  {
    id: 'grid-copy',
    key: 'c',
    ctrl: true,
    description: 'Copy selected cells',
    category: SHORTCUT_CATEGORIES.GRID_CLIPBOARD
  },
  {
    id: 'grid-paste',
    key: 'v',
    ctrl: true,
    description: 'Paste data',
    category: SHORTCUT_CATEGORIES.GRID_CLIPBOARD
  },
  {
    id: 'grid-cut',
    key: 'x',
    ctrl: true,
    description: 'Cut selected cells',
    category: SHORTCUT_CATEGORIES.GRID_CLIPBOARD
  },

  // Selection
  {
    id: 'grid-select-all',
    key: 'a',
    ctrl: true,
    description: 'Select all rows',
    category: SHORTCUT_CATEGORIES.GRID_SELECTION
  },
  {
    id: 'grid-select-column',
    key: ' ',
    ctrl: true,
    description: 'Select current column',
    category: SHORTCUT_CATEGORIES.GRID_SELECTION
  },
  {
    id: 'grid-select-row',
    key: ' ',
    shift: true,
    description: 'Select current row',
    category: SHORTCUT_CATEGORIES.GRID_SELECTION
  }
]

/**
 * Form shortcuts configuration
 */
export const FORM_SHORTCUTS = [
  // Actions
  {
    id: 'form-save',
    key: 's',
    ctrl: true,
    description: 'Save form',
    category: SHORTCUT_CATEGORIES.FORM_ACTIONS
  },
  {
    id: 'form-save-alt',
    key: 'enter',
    ctrl: true,
    description: 'Save form (alternative)',
    category: SHORTCUT_CATEGORIES.FORM_ACTIONS
  },
  {
    id: 'form-cancel',
    key: 'escape',
    description: 'Cancel form editing',
    category: SHORTCUT_CATEGORIES.FORM_ACTIONS
  },
  {
    id: 'form-reset',
    key: 'r',
    ctrl: true,
    shift: true,
    description: 'Reset form to initial values',
    category: SHORTCUT_CATEGORIES.FORM_ACTIONS
  },

  // Navigation
  {
    id: 'form-next-field',
    key: 'arrowdown',
    ctrl: true,
    description: 'Move to next form field',
    category: SHORTCUT_CATEGORIES.FORM_NAVIGATION
  },
  {
    id: 'form-prev-field',
    key: 'arrowup',
    ctrl: true,
    description: 'Move to previous form field',
    category: SHORTCUT_CATEGORIES.FORM_NAVIGATION
  },
  {
    id: 'form-first-field',
    key: 'home',
    ctrl: true,
    description: 'Focus first form field',
    category: SHORTCUT_CATEGORIES.FORM_NAVIGATION
  },
  {
    id: 'form-last-field',
    key: 'end',
    ctrl: true,
    description: 'Focus last form field',
    category: SHORTCUT_CATEGORIES.FORM_NAVIGATION
  },
  {
    id: 'form-first-error',
    key: 'e',
    ctrl: true,
    description: 'Focus first invalid field',
    category: SHORTCUT_CATEGORIES.FORM_NAVIGATION
  },

  // Editing
  {
    id: 'form-clear-field',
    key: 'backspace',
    ctrl: true,
    description: 'Clear current field',
    category: SHORTCUT_CATEGORIES.FORM_EDITING
  },
  {
    id: 'form-select-all',
    key: 'a',
    ctrl: true,
    description: 'Select all text in field',
    category: SHORTCUT_CATEGORIES.FORM_EDITING
  }
]

/**
 * Get all shortcuts
 */
export const getAllShortcuts = () => {
  return [
    ...GLOBAL_SHORTCUTS,
    ...NAVIGATION_SHORTCUTS,
    ...GRID_SHORTCUTS,
    ...FORM_SHORTCUTS
  ]
}

/**
 * Get shortcuts by category
 */
export const getShortcutsByCategory = (category) => {
  return getAllShortcuts().filter(shortcut => shortcut.category === category)
}

/**
 * Get shortcut by ID
 */
export const getShortcutById = (id) => {
  return getAllShortcuts().find(shortcut => shortcut.id === id)
}

/**
 * Format shortcut for display
 */
export const formatShortcutDisplay = (shortcut, isMac = false) => {
  const keys = []
  const modifierSymbol = isMac ? '⌘' : 'Ctrl'

  if (shortcut.ctrl) keys.push(modifierSymbol)
  if (shortcut.shift) keys.push('Shift')
  if (shortcut.alt) keys.push('Alt')
  keys.push(shortcut.key.toUpperCase())

  return keys.join('+')
}
