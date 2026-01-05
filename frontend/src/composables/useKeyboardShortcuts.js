import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'

/**
 * Keyboard shortcuts composable for global and context-aware shortcuts
 * Supports Mac (Cmd) and Windows/Linux (Ctrl) modifiers
 */
export function useKeyboardShortcuts(options = {}) {
  const router = useRouter()
  const activeShortcuts = ref(new Map())
  const shortcutHistory = ref([])
  const isHelpModalOpen = ref(false)

  // Detect platform
  const isMac = computed(() =>
    typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0
  )

  const modifierKey = computed(() => isMac.value ? 'Meta' : 'Control')
  const modifierSymbol = computed(() => isMac.value ? '⌘' : 'Ctrl')

  /**
   * Normalize keyboard event to handle cross-platform modifiers
   */
  const normalizeEvent = (event) => {
    const ctrl = event.ctrlKey || event.metaKey
    const shift = event.shiftKey
    const alt = event.altKey
    const key = event.key.toLowerCase()

    return { ctrl, shift, alt, key, originalEvent: event }
  }

  /**
   * Check if event matches shortcut definition
   */
  const matchesShortcut = (event, shortcut) => {
    const normalized = normalizeEvent(event)

    return (
      (shortcut.ctrl === undefined || shortcut.ctrl === normalized.ctrl) &&
      (shortcut.shift === undefined || shortcut.shift === normalized.shift) &&
      (shortcut.alt === undefined || shortcut.alt === normalized.alt) &&
      shortcut.key.toLowerCase() === normalized.key
    )
  }

  /**
   * Format shortcut for display
   */
  const formatShortcut = (shortcut) => {
    const keys = []
    if (shortcut.ctrl) keys.push(modifierSymbol.value)
    if (shortcut.shift) keys.push('Shift')
    if (shortcut.alt) keys.push('Alt')
    keys.push(shortcut.key.toUpperCase())
    return keys.join('+')
  }

  /**
   * Register a keyboard shortcut
   */
  const registerShortcut = (id, config) => {
    const {
      key,
      ctrl = false,
      shift = false,
      alt = false,
      description,
      category = 'General',
      handler,
      context = null,
      preventDefault = true,
      enabled = true
    } = config

    const shortcut = {
      id,
      key: key.toLowerCase(),
      ctrl,
      shift,
      alt,
      description,
      category,
      handler,
      context,
      preventDefault,
      enabled,
      displayKey: formatShortcut({ key, ctrl, shift, alt })
    }

    activeShortcuts.value.set(id, shortcut)
    return () => unregisterShortcut(id)
  }

  /**
   * Unregister a keyboard shortcut
   */
  const unregisterShortcut = (id) => {
    activeShortcuts.value.delete(id)
  }

  /**
   * Handle keyboard event
   */
  const handleKeyboardEvent = (event) => {
    // Skip if user is typing in input fields (unless explicitly allowed)
    const target = event.target
    const isInput = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
    const isContentEditable = target.isContentEditable

    for (const [id, shortcut] of activeShortcuts.value.entries()) {
      if (!shortcut.enabled) continue

      // Check context if specified
      if (shortcut.context && !shortcut.context()) continue

      if (matchesShortcut(event, shortcut)) {
        // Skip input fields unless shortcut explicitly allows it
        if ((isInput || isContentEditable) && !shortcut.allowInInputs) {
          continue
        }

        if (shortcut.preventDefault) {
          event.preventDefault()
          event.stopPropagation()
        }

        // Add to history
        shortcutHistory.value.unshift({
          id,
          timestamp: Date.now(),
          key: shortcut.displayKey
        })
        if (shortcutHistory.value.length > 50) {
          shortcutHistory.value.pop()
        }

        // Execute handler
        try {
          shortcut.handler(event)
        } catch (error) {
          console.error(`Error executing shortcut ${id}:`, error)
        }

        return
      }
    }
  }

  /**
   * Get shortcuts by category
   */
  const getShortcutsByCategory = () => {
    const categories = {}

    for (const shortcut of activeShortcuts.value.values()) {
      if (!categories[shortcut.category]) {
        categories[shortcut.category] = []
      }
      categories[shortcut.category].push(shortcut)
    }

    return categories
  }

  /**
   * Toggle help modal
   */
  const toggleHelpModal = () => {
    isHelpModalOpen.value = !isHelpModalOpen.value
  }

  /**
   * Register global shortcuts
   */
  const registerGlobalShortcuts = () => {
    // Save
    registerShortcut('global-save', {
      key: 's',
      ctrl: true,
      description: 'Save current form/grid',
      category: 'Global',
      handler: () => {
        const event = new CustomEvent('keyboard-shortcut:save')
        window.dispatchEvent(event)
      }
    })

    // New Entry
    registerShortcut('global-new', {
      key: 'n',
      ctrl: true,
      description: 'Create new entry',
      category: 'Global',
      handler: () => {
        const event = new CustomEvent('keyboard-shortcut:new')
        window.dispatchEvent(event)
      }
    })

    // Search/Find
    registerShortcut('global-search', {
      key: 'f',
      ctrl: true,
      description: 'Focus search field',
      category: 'Global',
      handler: () => {
        const searchInput = document.querySelector('input[type="search"], input[placeholder*="search" i]')
        if (searchInput) {
          searchInput.focus()
          searchInput.select()
        }
      }
    })

    // Command Palette
    registerShortcut('global-command', {
      key: 'k',
      ctrl: true,
      description: 'Open command palette',
      category: 'Global',
      handler: () => {
        // Trigger command palette (to be implemented)
        console.log('Command palette triggered')
      }
    })

    // Help
    registerShortcut('global-help', {
      key: '/',
      ctrl: true,
      description: 'Show keyboard shortcuts help',
      category: 'Global',
      handler: toggleHelpModal
    })

    // Navigation shortcuts
    registerShortcut('nav-dashboard', {
      key: 'd',
      ctrl: true,
      description: 'Navigate to Dashboard',
      category: 'Navigation',
      handler: () => router.push('/')
    })

    registerShortcut('nav-production', {
      key: 'p',
      ctrl: true,
      description: 'Navigate to Production Entry',
      category: 'Navigation',
      handler: () => router.push('/production-entry')
    })

    registerShortcut('nav-quality', {
      key: 'q',
      ctrl: true,
      description: 'Navigate to Quality Entry',
      category: 'Navigation',
      handler: () => router.push('/data-entry/quality')
    })

    registerShortcut('nav-attendance', {
      key: 'a',
      ctrl: true,
      description: 'Navigate to Attendance',
      category: 'Navigation',
      handler: () => router.push('/data-entry/attendance')
    })

    registerShortcut('nav-downtime', {
      key: 't',
      ctrl: true,
      description: 'Navigate to Downtime Entry',
      category: 'Navigation',
      handler: () => router.push('/data-entry/downtime')
    })

    // Escape key
    registerShortcut('global-escape', {
      key: 'escape',
      description: 'Close modals/cancel editing',
      category: 'Global',
      handler: () => {
        const event = new CustomEvent('keyboard-shortcut:escape')
        window.dispatchEvent(event)
      },
      preventDefault: false
    })

    // Refresh
    registerShortcut('global-refresh', {
      key: 'r',
      ctrl: true,
      description: 'Refresh current data',
      category: 'Global',
      handler: (event) => {
        event.preventDefault()
        const refreshEvent = new CustomEvent('keyboard-shortcut:refresh')
        window.dispatchEvent(refreshEvent)
      }
    })
  }

  // Lifecycle
  onMounted(() => {
    window.addEventListener('keydown', handleKeyboardEvent)

    if (options.registerGlobal !== false) {
      registerGlobalShortcuts()
    }
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeyboardEvent)
    activeShortcuts.value.clear()
  })

  return {
    registerShortcut,
    unregisterShortcut,
    getShortcutsByCategory,
    toggleHelpModal,
    isHelpModalOpen,
    shortcutHistory,
    activeShortcuts,
    isMac,
    modifierSymbol,
    formatShortcut
  }
}
