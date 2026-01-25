/**
 * Centralized Error Handler
 *
 * Provides consistent error handling across the application.
 * Logs errors for debugging and shows user-friendly notifications.
 */

import { useNotificationStore } from '@/stores/notificationStore'

/**
 * Handle API errors consistently
 * @param {Error} error - The error object from axios or other sources
 * @param {Object} options - Handler options
 * @param {boolean} options.silent - If true, don't show notification
 * @param {string} options.fallbackMessage - Custom fallback message
 * @param {string} options.context - Context for logging (e.g., 'QualityEntry')
 * @returns {Object} - { success: false, error: string }
 */
export function handleApiError(error, options = {}) {
  const {
    silent = false,
    fallbackMessage = 'An error occurred. Please try again.',
    context = 'API'
  } = options

  // Extract the error message
  let message = fallbackMessage

  if (error.response) {
    // Server responded with error status
    const data = error.response.data
    message = data?.detail || data?.message || data?.error || fallbackMessage

    // Log detailed error for debugging
    console.error(`[${context}] API Error ${error.response.status}:`, {
      status: error.response.status,
      data: error.response.data,
      url: error.config?.url
    })
  } else if (error.request) {
    // Request made but no response (network error)
    message = 'Network error. Please check your connection.'
    console.error(`[${context}] Network Error:`, error.message)
  } else {
    // Something else went wrong
    message = error.message || fallbackMessage
    console.error(`[${context}] Error:`, error)
  }

  // Show notification unless silent mode
  if (!silent) {
    try {
      const notifications = useNotificationStore()
      notifications.showError(message)
    } catch (storeError) {
      // Fallback if store not available (e.g., during initialization)
      console.error('Could not show notification:', storeError)
    }
  }

  return { success: false, error: message }
}

/**
 * Handle form validation errors
 * @param {Object} errors - Validation errors object
 * @param {Object} options - Handler options
 * @returns {Object} - { success: false, errors: Object }
 */
export function handleValidationError(errors, options = {}) {
  const { silent = false, context = 'Validation' } = options

  console.warn(`[${context}] Validation errors:`, errors)

  if (!silent) {
    try {
      const notifications = useNotificationStore()
      const errorCount = Object.keys(errors).length
      notifications.showWarning(`Please fix ${errorCount} validation error${errorCount > 1 ? 's' : ''}`)
    } catch (storeError) {
      console.error('Could not show notification:', storeError)
    }
  }

  return { success: false, errors }
}

/**
 * Wrap an async function with error handling
 * @param {Function} fn - Async function to wrap
 * @param {Object} options - Error handler options
 * @returns {Function} - Wrapped function that handles errors
 */
export function withErrorHandling(fn, options = {}) {
  return async (...args) => {
    try {
      return await fn(...args)
    } catch (error) {
      return handleApiError(error, options)
    }
  }
}

/**
 * Show success notification
 * @param {string} message - Success message
 */
export function showSuccess(message) {
  try {
    const notifications = useNotificationStore()
    notifications.showSuccess(message)
  } catch (error) {
    console.log('Success:', message)
  }
}

/**
 * Show info notification
 * @param {string} message - Info message
 */
export function showInfo(message) {
  try {
    const notifications = useNotificationStore()
    notifications.showInfo(message)
  } catch (error) {
    console.log('Info:', message)
  }
}

export default {
  handleApiError,
  handleValidationError,
  withErrorHandling,
  showSuccess,
  showInfo
}
