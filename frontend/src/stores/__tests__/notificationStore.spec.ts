/**
 * Unit tests for Notification Store
 * Tests notification display, history management, and convenience methods
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useNotificationStore } from '../notificationStore'

describe('Notification Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('Initial State', () => {
    it('initializes with empty notifications array', () => {
      const store = useNotificationStore()

      expect(store.notifications).toEqual([])
    })

    it('initializes snackbar with default values', () => {
      const store = useNotificationStore()

      expect(store.snackbar.show).toBe(false)
      expect(store.snackbar.message).toBe('')
      expect(store.snackbar.color).toBe('info')
      expect(store.snackbar.timeout).toBe(4000)
    })
  })

  describe('show() Method', () => {
    it('shows notification with correct message', () => {
      const store = useNotificationStore()

      store.show({ message: 'Test message' })

      expect(store.snackbar.show).toBe(true)
      expect(store.snackbar.message).toBe('Test message')
    })

    it('sets correct color for success type', () => {
      const store = useNotificationStore()

      store.show({ message: 'Success', type: 'success' })

      expect(store.snackbar.color).toBe('success')
    })

    it('sets correct color for error type', () => {
      const store = useNotificationStore()

      store.show({ message: 'Error', type: 'error' })

      expect(store.snackbar.color).toBe('error')
    })

    it('sets correct color for warning type', () => {
      const store = useNotificationStore()

      store.show({ message: 'Warning', type: 'warning' })

      expect(store.snackbar.color).toBe('warning')
    })

    it('uses custom timeout when provided', () => {
      const store = useNotificationStore()

      store.show({ message: 'Test', timeout: 10000 })

      expect(store.snackbar.timeout).toBe(10000)
    })

    it('adds notification to history with timestamp', () => {
      const store = useNotificationStore()

      store.show({ message: 'Test message', type: 'info' })

      expect(store.notifications).toHaveLength(1)
      expect(store.notifications[0].message).toBe('Test message')
      expect(store.notifications[0].type).toBe('info')
      expect(store.notifications[0].timestamp).toBeDefined()
      expect(store.notifications[0].id).toBe(1)
    })

    it('increments notification IDs', () => {
      const store = useNotificationStore()

      store.show({ message: 'First' })
      store.show({ message: 'Second' })
      store.show({ message: 'Third' })

      expect(store.notifications[0].id).toBe(3)
      expect(store.notifications[1].id).toBe(2)
      expect(store.notifications[2].id).toBe(1)
    })

    it('limits notification history to 50 items', () => {
      const store = useNotificationStore()

      // Add 60 notifications
      for (let i = 0; i < 60; i++) {
        store.show({ message: `Message ${i}` })
      }

      expect(store.notifications).toHaveLength(50)
    })

    it('keeps most recent notifications when limiting', () => {
      const store = useNotificationStore()

      for (let i = 0; i < 55; i++) {
        store.show({ message: `Message ${i}` })
      }

      // Most recent should be at index 0
      expect(store.notifications[0].message).toBe('Message 54')
    })
  })

  describe('Convenience Methods', () => {
    it('showSuccess shows success notification', () => {
      const store = useNotificationStore()

      store.showSuccess('Operation successful')

      expect(store.snackbar.color).toBe('success')
      expect(store.snackbar.message).toBe('Operation successful')
    })

    it('showError shows error notification with longer timeout', () => {
      const store = useNotificationStore()

      store.showError('Something went wrong')

      expect(store.snackbar.color).toBe('error')
      expect(store.snackbar.message).toBe('Something went wrong')
      expect(store.snackbar.timeout).toBe(6000)
    })

    it('showWarning shows warning notification', () => {
      const store = useNotificationStore()

      store.showWarning('Please check your input')

      expect(store.snackbar.color).toBe('warning')
      expect(store.snackbar.message).toBe('Please check your input')
    })

    it('showInfo shows info notification', () => {
      const store = useNotificationStore()

      store.showInfo('Here is some information')

      expect(store.snackbar.color).toBe('info')
      expect(store.snackbar.message).toBe('Here is some information')
    })
  })

  describe('hide() Method', () => {
    it('hides the snackbar', () => {
      const store = useNotificationStore()
      store.show({ message: 'Test' })

      store.hide()

      expect(store.snackbar.show).toBe(false)
    })
  })

  describe('clearHistory() Method', () => {
    it('clears all notifications from history', () => {
      const store = useNotificationStore()
      store.show({ message: 'Test 1' })
      store.show({ message: 'Test 2' })
      store.show({ message: 'Test 3' })

      store.clearHistory()

      expect(store.notifications).toEqual([])
    })
  })

  describe('Type Mapping', () => {
    it('defaults to info color for unknown type', () => {
      const store = useNotificationStore()

      store.show({ message: 'Test', type: 'unknown' })

      expect(store.snackbar.color).toBe('info')
    })

    it('defaults to info type when not provided', () => {
      const store = useNotificationStore()

      store.show({ message: 'Test' })

      expect(store.snackbar.color).toBe('info')
    })
  })
})
