import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Notification Store
 * Centralized notification management for user feedback
 */
export const useNotificationStore = defineStore('notification', () => {
  // State
  const notifications = ref([])
  const snackbar = ref({
    show: false,
    message: '',
    color: 'info',
    timeout: 4000
  })

  // Counter for unique IDs
  let nextId = 1

  /**
   * Show a notification
   * @param {Object} options - Notification options
   * @param {string} options.message - Message to display
   * @param {string} options.type - Type: 'success', 'error', 'warning', 'info'
   * @param {number} options.timeout - Auto-dismiss timeout in ms (0 for persistent)
   */
  function show({ message, type = 'info', timeout = 4000 }) {
    const colorMap = {
      success: 'success',
      error: 'error',
      warning: 'warning',
      info: 'info'
    }

    snackbar.value = {
      show: true,
      message,
      color: colorMap[type] || 'info',
      timeout
    }

    // Also add to notifications array for history
    const notification = {
      id: nextId++,
      message,
      type,
      timestamp: new Date().toISOString()
    }
    notifications.value.unshift(notification)

    // Keep only last 50 notifications
    if (notifications.value.length > 50) {
      notifications.value = notifications.value.slice(0, 50)
    }
  }

  /**
   * Show success notification
   * @param {string} message - Success message
   */
  function showSuccess(message) {
    show({ message, type: 'success' })
  }

  /**
   * Show error notification
   * @param {string} message - Error message
   */
  function showError(message) {
    show({ message, type: 'error', timeout: 6000 })
  }

  /**
   * Show warning notification
   * @param {string} message - Warning message
   */
  function showWarning(message) {
    show({ message, type: 'warning' })
  }

  /**
   * Show info notification
   * @param {string} message - Info message
   */
  function showInfo(message) {
    show({ message, type: 'info' })
  }

  /**
   * Hide the current snackbar
   */
  function hide() {
    snackbar.value.show = false
  }

  /**
   * Clear all notification history
   */
  function clearHistory() {
    notifications.value = []
  }

  return {
    // State
    notifications,
    snackbar,
    // Actions
    show,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    hide,
    clearHistory
  }
})
