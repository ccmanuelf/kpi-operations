/**
 * Centralized error handler — consistent error → user notification
 * across the app. Logs for debugging, shows toast unless silenced.
 */

import { useNotificationStore } from '@/stores/notificationStore'

export interface ErrorHandlerOptions {
  silent?: boolean
  fallbackMessage?: string
  context?: string
}

export interface ErrorResult {
  success: false
  error: string
}

export interface ValidationErrorResult {
  success: false
  errors: Record<string, unknown>
}

// Axios-shaped error narrowing — duck-typed so tests can pass plain
// `{ response: ..., config: ... }` objects without an `isAxiosError`
// flag. Matches the JS behavior the call sites and tests assume.
interface AxiosLikeError {
  response?: {
    status?: number
    data?: { detail?: string; message?: string; error?: string }
  }
  request?: unknown
  message?: string
  config?: { url?: string }
}

const asAxiosLike = (e: unknown): AxiosLikeError | null =>
  typeof e === 'object' && e !== null ? (e as AxiosLikeError) : null

export function handleApiError(error: unknown, options: ErrorHandlerOptions = {}): ErrorResult {
  const {
    silent = false,
    fallbackMessage = 'An error occurred. Please try again.',
    context = 'API',
  } = options

  let message = fallbackMessage
  const ax = asAxiosLike(error)

  if (ax?.response) {
    const data = ax.response.data
    message = data?.detail || data?.message || data?.error || fallbackMessage

    // eslint-disable-next-line no-console
    console.error(`[${context}] API Error ${ax.response.status}:`, {
      status: ax.response.status,
      data: ax.response.data,
      url: ax.config?.url,
    })
  } else if (ax?.request) {
    message = 'Network error. Please check your connection.'
    // eslint-disable-next-line no-console
    console.error(`[${context}] Network Error:`, ax.message)
  } else {
    message = error instanceof Error ? error.message : fallbackMessage
    // eslint-disable-next-line no-console
    console.error(`[${context}] Error:`, error)
  }

  if (!silent) {
    try {
      const notifications = useNotificationStore()
      notifications.showError(message)
    } catch (storeError) {
      // eslint-disable-next-line no-console
      console.error('Could not show notification:', storeError)
    }
  }

  return { success: false, error: message }
}

export function handleValidationError(
  errors: Record<string, unknown>,
  options: { silent?: boolean; context?: string } = {},
): ValidationErrorResult {
  const { silent = false, context = 'Validation' } = options

  // eslint-disable-next-line no-console
  console.warn(`[${context}] Validation errors:`, errors)

  if (!silent) {
    try {
      const notifications = useNotificationStore()
      const errorCount = Object.keys(errors).length
      notifications.showWarning(
        `Please fix ${errorCount} validation error${errorCount > 1 ? 's' : ''}`,
      )
    } catch (storeError) {
      // eslint-disable-next-line no-console
      console.error('Could not show notification:', storeError)
    }
  }

  return { success: false, errors }
}

export function withErrorHandling<TArgs extends unknown[], TResult>(
  fn: (...args: TArgs) => Promise<TResult>,
  options: ErrorHandlerOptions = {},
) {
  return async (...args: TArgs): Promise<TResult | ErrorResult> => {
    try {
      return await fn(...args)
    } catch (error) {
      return handleApiError(error, options)
    }
  }
}

export function showSuccess(message: string) {
  try {
    const notifications = useNotificationStore()
    notifications.showSuccess(message)
  } catch {
    // eslint-disable-next-line no-console
    console.log('Success:', message)
  }
}

export function showInfo(message: string) {
  try {
    const notifications = useNotificationStore()
    notifications.showInfo(message)
  } catch {
    // eslint-disable-next-line no-console
    console.log('Info:', message)
  }
}

export default {
  handleApiError,
  handleValidationError,
  withErrorHandling,
  showSuccess,
  showInfo,
}
