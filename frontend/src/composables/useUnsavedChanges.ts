/**
 * Unsaved Changes Composable
 * Provides warning when users try to navigate away with unsaved changes
 *
 * Usage:
 * ```ts
 * const { hasUnsavedChanges, markDirty, markClean, confirmNavigation } = useUnsavedChanges()
 *
 * // Mark form as having unsaved changes
 * watch(formData, () => markDirty(), { deep: true })
 *
 * // Clear after successful save
 * const handleSave = async () => {
 *   await saveData()
 *   markClean()
 * }
 * ```
 */
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'

export interface UnsavedChangesOptions {
  message?: string
  enabled?: boolean
}

export function useUnsavedChanges(options: UnsavedChangesOptions = {}) {
  const {
    message = 'You have unsaved changes. Are you sure you want to leave?',
    enabled = true
  } = options

  const hasUnsavedChanges = ref(false)
  const isEnabled = ref(enabled)

  // Handle browser navigation (back button, close tab, refresh)
  const handleBeforeUnload = (event: BeforeUnloadEvent) => {
    if (hasUnsavedChanges.value && isEnabled.value) {
      event.preventDefault()
      // Most browsers ignore custom messages and show their own
      event.returnValue = message
      return message
    }
  }

  // Register/unregister browser event
  onMounted(() => {
    window.addEventListener('beforeunload', handleBeforeUnload)
  })

  onUnmounted(() => {
    window.removeEventListener('beforeunload', handleBeforeUnload)
  })

  // Handle Vue Router navigation
  onBeforeRouteLeave((to, from, next) => {
    if (hasUnsavedChanges.value && isEnabled.value) {
      const confirmed = window.confirm(message)
      if (confirmed) {
        hasUnsavedChanges.value = false
        next()
      } else {
        next(false)
      }
    } else {
      next()
    }
  })

  // Mark form as having unsaved changes
  const markDirty = () => {
    hasUnsavedChanges.value = true
  }

  // Mark form as clean (after save)
  const markClean = () => {
    hasUnsavedChanges.value = false
  }

  // Toggle the warning functionality
  const setEnabled = (value: boolean) => {
    isEnabled.value = value
  }

  // Programmatic navigation check
  const confirmNavigation = (): boolean => {
    if (hasUnsavedChanges.value && isEnabled.value) {
      return window.confirm(message)
    }
    return true
  }

  // Watch a reactive value and auto-mark dirty
  const watchForChanges = <T>(source: () => T, initialValue?: T) => {
    let isInitialized = false

    watch(source, (newVal) => {
      if (!isInitialized) {
        isInitialized = true
        return
      }
      markDirty()
    }, { deep: true })
  }

  return {
    hasUnsavedChanges,
    isEnabled,
    markDirty,
    markClean,
    setEnabled,
    confirmNavigation,
    watchForChanges
  }
}

export default useUnsavedChanges
