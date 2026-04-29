/**
 * Unit tests for Error Handler
 * Tests centralized error handling and notification integration
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import {
  handleApiError,
  handleValidationError,
  withErrorHandling,
  showSuccess,
  showInfo
} from '../errorHandler'

// Mock notification store
const mockShowError = vi.fn()
const mockShowWarning = vi.fn()
const mockShowSuccess = vi.fn()
const mockShowInfo = vi.fn()

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: vi.fn(() => ({
    showError: mockShowError,
    showWarning: mockShowWarning,
    showSuccess: mockShowSuccess,
    showInfo: mockShowInfo
  }))
}))

describe('Error Handler', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('handleApiError', () => {
    it('extracts error message from response.data.detail', () => {
      const error = {
        response: {
          status: 400,
          data: { detail: 'Validation failed' },
          config: { url: '/api/test' }
        }
      }
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const result = handleApiError(error, { context: 'Test' })

      expect(result.success).toBe(false)
      expect(result.error).toBe('Validation failed')
      expect(mockShowError).toHaveBeenCalledWith('Validation failed')
      consoleSpy.mockRestore()
    })

    it('extracts error message from response.data.message', () => {
      const error = {
        response: {
          status: 500,
          data: { message: 'Server error occurred' },
          config: { url: '/api/test' }
        }
      }
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const result = handleApiError(error, { context: 'Test' })

      expect(result.error).toBe('Server error occurred')
      consoleSpy.mockRestore()
    })

    it('uses fallback message when no specific error provided', () => {
      const error = {
        response: {
          status: 500,
          data: {},
          config: { url: '/api/test' }
        }
      }
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const result = handleApiError(error, {
        fallbackMessage: 'Custom fallback'
      })

      expect(result.error).toBe('Custom fallback')
      consoleSpy.mockRestore()
    })

    it('handles network errors with request but no response', () => {
      const error = {
        request: {},
        message: 'Network Error'
      }
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const result = handleApiError(error)

      expect(result.error).toBe('Network error. Please check your connection.')
      consoleSpy.mockRestore()
    })

    it('handles generic errors', () => {
      const error = new Error('Something went wrong')
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const result = handleApiError(error)

      expect(result.error).toBe('Something went wrong')
      consoleSpy.mockRestore()
    })

    it('does not show notification in silent mode', () => {
      const error = {
        response: {
          status: 400,
          data: { detail: 'Error' },
          config: {}
        }
      }
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      handleApiError(error, { silent: true })

      expect(mockShowError).not.toHaveBeenCalled()
      consoleSpy.mockRestore()
    })

    it('logs detailed error information', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const error = {
        response: {
          status: 400,
          data: { detail: 'Error' }
        },
        config: { url: '/api/test' }
      }

      handleApiError(error, { context: 'TestContext' })

      expect(consoleSpy).toHaveBeenCalledWith(
        '[TestContext] API Error 400:',
        expect.objectContaining({
          status: 400,
          data: { detail: 'Error' },
          url: '/api/test'
        })
      )
      consoleSpy.mockRestore()
    })
  })

  describe('handleValidationError', () => {
    it('returns errors object', () => {
      const errors = {
        email: 'Invalid email',
        password: 'Too short'
      }
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      const result = handleValidationError(errors)

      expect(result.success).toBe(false)
      expect(result.errors).toEqual(errors)
      consoleSpy.mockRestore()
    })

    it('shows warning notification with error count', () => {
      const errors = {
        field1: 'Error 1',
        field2: 'Error 2',
        field3: 'Error 3'
      }
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      handleValidationError(errors)

      expect(mockShowWarning).toHaveBeenCalledWith('Please fix 3 validation errors')
      consoleSpy.mockRestore()
    })

    it('uses singular for single error', () => {
      const errors = { field1: 'Error 1' }
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      handleValidationError(errors)

      expect(mockShowWarning).toHaveBeenCalledWith('Please fix 1 validation error')
      consoleSpy.mockRestore()
    })

    it('does not show notification in silent mode', () => {
      const errors = { field1: 'Error 1' }
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      handleValidationError(errors, { silent: true })

      expect(mockShowWarning).not.toHaveBeenCalled()
      consoleSpy.mockRestore()
    })
  })

  describe('withErrorHandling', () => {
    it('returns result on success', async () => {
      const asyncFn = vi.fn().mockResolvedValue({ success: true, data: 'test' })
      const wrapped = withErrorHandling(asyncFn)

      const result = await wrapped('arg1', 'arg2')

      expect(result).toEqual({ success: true, data: 'test' })
      expect(asyncFn).toHaveBeenCalledWith('arg1', 'arg2')
    })

    it('handles errors and returns error result', async () => {
      const error = {
        response: {
          status: 500,
          data: { detail: 'Server error' },
          config: {}
        }
      }
      const asyncFn = vi.fn().mockRejectedValue(error)
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const wrapped = withErrorHandling(asyncFn, { context: 'Test' })

      const result = await wrapped()

      expect(result.success).toBe(false)
      expect(result.error).toBe('Server error')
      consoleSpy.mockRestore()
    })

    it('passes options to error handler', async () => {
      const error = new Error('Test error')
      const asyncFn = vi.fn().mockRejectedValue(error)
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const wrapped = withErrorHandling(asyncFn, { silent: true })

      await wrapped()

      expect(mockShowError).not.toHaveBeenCalled()
      consoleSpy.mockRestore()
    })
  })

  describe('showSuccess', () => {
    it('shows success notification', () => {
      showSuccess('Operation completed')

      expect(mockShowSuccess).toHaveBeenCalledWith('Operation completed')
    })

    it('logs to console if store unavailable', () => {
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
      mockShowSuccess.mockImplementation(() => {
        throw new Error('Store not available')
      })

      showSuccess('Test message')

      expect(consoleSpy).toHaveBeenCalledWith('Success:', 'Test message')
      consoleSpy.mockRestore()
    })
  })

  describe('showInfo', () => {
    it('shows info notification', () => {
      showInfo('Information message')

      expect(mockShowInfo).toHaveBeenCalledWith('Information message')
    })

    it('logs to console if store unavailable', () => {
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {})
      mockShowInfo.mockImplementation(() => {
        throw new Error('Store not available')
      })

      showInfo('Test message')

      expect(consoleSpy).toHaveBeenCalledWith('Info:', 'Test message')
      consoleSpy.mockRestore()
    })
  })
})
