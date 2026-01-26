/**
 * Toast Notification Composable
 *
 * Provides consistent toast/snackbar notifications across the application.
 * Follows IBM Carbon Design System notification patterns.
 *
 * Usage:
 * const { showSuccess, showError, showWarning, showInfo } = useToast()
 * showSuccess('Data saved successfully')
 */

import { ref, readonly } from 'vue'

// Shared state across all component instances
const toasts = ref([])
let toastId = 0

// Default durations by type (in milliseconds)
const DEFAULT_DURATIONS = {
  success: 4000,
  error: 6000,
  warning: 5000,
  info: 4000
}

export function useToast() {
  /**
   * Show a toast notification
   * @param {Object} options - Toast configuration
   * @param {string} options.message - The message to display
   * @param {string} options.type - Type: 'success' | 'error' | 'warning' | 'info'
   * @param {number} options.duration - Duration in ms (0 for persistent)
   * @param {string} options.action - Optional action button text
   * @param {Function} options.onAction - Callback when action clicked
   */
  const showToast = ({
    message,
    type = 'info',
    duration = DEFAULT_DURATIONS[type],
    action = '',
    onAction = null
  }) => {
    const id = ++toastId
    const toast = {
      id,
      message,
      type,
      color: getColor(type),
      icon: getIcon(type),
      action,
      onAction,
      visible: true
    }

    toasts.value.push(toast)

    // Auto-dismiss unless persistent
    if (duration > 0) {
      setTimeout(() => {
        dismissToast(id)
      }, duration)
    }

    return id
  }

  /**
   * Dismiss a specific toast
   * @param {number} id - Toast ID to dismiss
   */
  const dismissToast = (id) => {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index !== -1) {
      toasts.value[index].visible = false
      // Remove after animation
      setTimeout(() => {
        toasts.value = toasts.value.filter(t => t.id !== id)
      }, 300)
    }
  }

  /**
   * Dismiss all toasts
   */
  const dismissAll = () => {
    toasts.value.forEach(t => {
      t.visible = false
    })
    setTimeout(() => {
      toasts.value = []
    }, 300)
  }

  // Convenience methods
  const showSuccess = (message, options = {}) =>
    showToast({ ...options, message, type: 'success' })

  const showError = (message, options = {}) =>
    showToast({ ...options, message, type: 'error' })

  const showWarning = (message, options = {}) =>
    showToast({ ...options, message, type: 'warning' })

  const showInfo = (message, options = {}) =>
    showToast({ ...options, message, type: 'info' })

  return {
    toasts: readonly(toasts),
    showToast,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    dismissToast,
    dismissAll
  }
}

// Helper functions
function getColor(type) {
  const colors = {
    success: 'success',
    error: 'error',
    warning: 'warning',
    info: 'info'
  }
  return colors[type] || 'info'
}

function getIcon(type) {
  const icons = {
    success: 'mdi-check-circle',
    error: 'mdi-alert-circle',
    warning: 'mdi-alert',
    info: 'mdi-information'
  }
  return icons[type] || 'mdi-information'
}

export default useToast
