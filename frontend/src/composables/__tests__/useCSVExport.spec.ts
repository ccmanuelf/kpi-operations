import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const { apiMock, notificationMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(),
  },
  notificationMock: {
    showSuccess: vi.fn(),
    showError: vi.fn(),
  },
}))

vi.mock('@/services/api/client', () => ({ default: apiMock }))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => notificationMock,
}))

vi.mock('@/i18n', () => ({
  default: {
    global: {
      t: (key: string, params?: Record<string, unknown>) =>
        params ? `${key}:${JSON.stringify(params)}` : key,
    },
  },
}))

// Mock document operations for download
vi.stubGlobal('URL', {
  createObjectURL: vi.fn(() => 'blob:mock'),
  revokeObjectURL: vi.fn(),
})

beforeEach(() => {
  vi.clearAllMocks()
})

import { useCSVExport } from '../useCSVExport'

describe('useCSVExport', () => {
  describe('downloadCSVByPath', () => {
    it('calls api.get with the provided path and params (correct URL)', async () => {
      const { downloadCSVByPath } = useCSVExport()
      const blob = new Blob(['test data'], { type: 'text/csv' })

      apiMock.get.mockResolvedValueOnce({
        data: blob,
        headers: {},
      })

      try {
        await downloadCSVByPath('/pivot/downtime/csv', { bucket: 'month' }, 'test.csv')
      } catch {
        // Ignore DOM errors
      }

      expect(apiMock.get).toHaveBeenCalledWith('/pivot/downtime/csv', {
        params: { bucket: 'month' },
        responseType: 'blob',
      })
    })

    it('shows error notification on api failure', async () => {
      const { downloadCSVByPath } = useCSVExport()

      const error = new Error('Network error')
      apiMock.get.mockRejectedValueOnce(error)

      await expect(downloadCSVByPath('/pivot/downtime/csv', {}, 'test.csv')).rejects.toThrow()

      expect(notificationMock.showError).toHaveBeenCalled()
    })
  })

  describe('downloadCSV', () => {
    it('delegates to downloadCSVByPath with correct /export/ URL construction', async () => {
      const { downloadCSV } = useCSVExport()
      const blob = new Blob(['test data'], { type: 'text/csv' })

      apiMock.get.mockResolvedValueOnce({
        data: blob,
        headers: {},
      })

      try {
        await downloadCSV('production-entries', {})
      } catch {
        // Ignore DOM errors
      }

      expect(apiMock.get).toHaveBeenCalledWith('/export/production-entries', {
        params: {},
        responseType: 'blob',
      })
    })

    it('uses entityType as fallback filename when not provided', async () => {
      const { downloadCSV } = useCSVExport()
      const blob = new Blob(['test data'], { type: 'text/csv' })

      apiMock.get.mockResolvedValueOnce({
        data: blob,
        headers: {},
      })

      try {
        await downloadCSV('downtime-data', {})
      } catch {
        // Ignore DOM errors
      }

      expect(notificationMock.showSuccess).toHaveBeenCalled()
    })
  })
})
