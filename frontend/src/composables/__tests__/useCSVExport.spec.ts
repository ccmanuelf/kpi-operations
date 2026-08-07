import { describe, it, expect, vi, beforeEach } from 'vitest'

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

      await downloadCSVByPath('/pivot/downtime/csv', { bucket: 'month' }, 'test.csv')

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

      await downloadCSV('production-entries', {})

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

      await downloadCSV('downtime-data', {})

      expect(notificationMock.showSuccess).toHaveBeenCalled()
    })
  })

  describe('success toast', () => {
    it('calls t(csv.downloadSuccess) with no params -- the locale string must not interpolate {type}', async () => {
      const { downloadCSVByPath } = useCSVExport()
      const blob = new Blob(['test data'], { type: 'text/csv' })

      apiMock.get.mockResolvedValueOnce({
        data: blob,
        headers: {},
      })

      await downloadCSVByPath('/pivot/downtime/csv', { bucket: 'month' }, 'test.csv')

      // The mocked i18n.global.t returns the bare key when called with no
      // params (see the vi.mock('@/i18n', ...) above); a stray {type}:...
      // suffix would mean the call site is still threading params it never
      // has, reproducing the unresolved-placeholder bug.
      expect(notificationMock.showSuccess).toHaveBeenCalledWith('csv.downloadSuccess')
    })
  })
})
