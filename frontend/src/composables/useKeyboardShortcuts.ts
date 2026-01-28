/**
 * Keyboard Shortcuts Composable
 * Provides common keyboard shortcuts for data entry operations
 *
 * Usage:
 * ```ts
 * const { registerShortcut, unregisterShortcut } = useKeyboardShortcuts()
 *
 * // Register Ctrl+S for save
 * registerShortcut('ctrl+s', handleSave)
 *
 * // Register Escape for cancel
 * registerShortcut('escape', handleCancel)
 * ```
 */
import { onMounted, onUnmounted, ref } from 'vue'

type ShortcutHandler = (event: KeyboardEvent) => void

interface ShortcutConfig {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  meta?: boolean
  handler: ShortcutHandler
  preventDefault?: boolean
}

export function useKeyboardShortcuts() {
  const shortcuts = ref<Map<string, ShortcutConfig>>(new Map())

  // Parse shortcut string like "ctrl+s" or "ctrl+shift+s"
  const parseShortcut = (shortcut: string): Omit<ShortcutConfig, 'handler' | 'preventDefault'> => {
    const parts = shortcut.toLowerCase().split('+')
    const key = parts[parts.length - 1]
    return {
      key,
      ctrl: parts.includes('ctrl') || parts.includes('control'),
      shift: parts.includes('shift'),
      alt: parts.includes('alt'),
      meta: parts.includes('meta') || parts.includes('cmd')
    }
  }

  // Generate a unique key for the shortcut map
  const getShortcutKey = (config: Omit<ShortcutConfig, 'handler' | 'preventDefault'>): string => {
    const modifiers = [
      config.ctrl ? 'ctrl' : '',
      config.shift ? 'shift' : '',
      config.alt ? 'alt' : '',
      config.meta ? 'meta' : ''
    ].filter(Boolean).join('+')
    return modifiers ? `${modifiers}+${config.key}` : config.key
  }

  // Check if event matches shortcut config
  const matchesShortcut = (event: KeyboardEvent, config: ShortcutConfig): boolean => {
    const key = event.key.toLowerCase()
    return (
      key === config.key &&
      !!event.ctrlKey === !!config.ctrl &&
      !!event.shiftKey === !!config.shift &&
      !!event.altKey === !!config.alt &&
      !!event.metaKey === !!config.meta
    )
  }

  // Global keydown handler
  const handleKeydown = (event: KeyboardEvent) => {
    // Skip if user is typing in an input/textarea (unless it's a save shortcut)
    const target = event.target as HTMLElement
    const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable

    for (const config of shortcuts.value.values()) {
      if (matchesShortcut(event, config)) {
        // Allow Ctrl+S even in inputs (common save pattern)
        if (isInput && !(config.ctrl && config.key === 's')) {
          continue
        }

        if (config.preventDefault !== false) {
          event.preventDefault()
        }
        config.handler(event)
        return
      }
    }
  }

  // Register a keyboard shortcut
  const registerShortcut = (
    shortcut: string,
    handler: ShortcutHandler,
    options: { preventDefault?: boolean } = {}
  ) => {
    const parsed = parseShortcut(shortcut)
    const key = getShortcutKey(parsed)
    shortcuts.value.set(key, {
      ...parsed,
      handler,
      preventDefault: options.preventDefault ?? true
    })
  }

  // Unregister a keyboard shortcut
  const unregisterShortcut = (shortcut: string) => {
    const parsed = parseShortcut(shortcut)
    const key = getShortcutKey(parsed)
    shortcuts.value.delete(key)
  }

  // Clear all shortcuts
  const clearShortcuts = () => {
    shortcuts.value.clear()
  }

  // Setup/teardown event listener
  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
    shortcuts.value.clear()
  })

  return {
    registerShortcut,
    unregisterShortcut,
    clearShortcuts
  }
}

// Pre-configured shortcuts for common operations
export function useDataEntryShortcuts(options: {
  onSave?: () => void
  onCancel?: () => void
  onNew?: () => void
  onDelete?: () => void
}) {
  const { registerShortcut } = useKeyboardShortcuts()

  // Ctrl+S - Save
  if (options.onSave) {
    registerShortcut('ctrl+s', options.onSave)
  }

  // Escape - Cancel
  if (options.onCancel) {
    registerShortcut('escape', options.onCancel)
  }

  // Ctrl+N - New entry
  if (options.onNew) {
    registerShortcut('ctrl+n', options.onNew)
  }

  // Delete - Delete entry (with confirmation)
  if (options.onDelete) {
    registerShortcut('delete', options.onDelete)
  }
}

export default useKeyboardShortcuts
