import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the api module BEFORE importing the composable.
const getMock = vi.fn()
const postMock = vi.fn()
vi.mock('@/services/api', () => ({
  default: { get: (...a: unknown[]) => getMock(...a), post: (...a: unknown[]) => postMock(...a) },
}))
// vue-i18n: return the key so assertions are stable.
vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (k: string) => k }) }))

import { useKPIReports } from '@/composables/useKPIReports'

describe('useKPIReports endpoint wiring', () => {
  const snackbar = vi.fn()
  beforeEach(() => {
    getMock.mockReset(); postMock.mockReset(); snackbar.mockReset()
    getMock.mockResolvedValue({ data: new Blob(['x']) })
    postMock.mockResolvedValue({ data: {} })
    // jsdom lacks URL.createObjectURL used by the blob-download helper.
    // @ts-expect-error test shim
    global.URL.createObjectURL = vi.fn(() => 'blob:x')
    // @ts-expect-error test shim
    global.URL.revokeObjectURL = vi.fn()
  })

  const client = () => 'DEMO-PIECE'
  const range = () => [new Date('2026-06-01'), new Date('2026-06-30')]

  it('downloadPDF calls the comprehensive PDF endpoint', async () => {
    const r = useKPIReports(snackbar, client, range)
    await r.downloadPDF()
    expect(getMock).toHaveBeenCalledTimes(1)
    expect(getMock.mock.calls[0][0]).toContain('/reports/comprehensive/pdf')
    expect(getMock.mock.calls[0][0]).toContain('client_id=DEMO-PIECE')
  })

  it('downloadExcel calls the comprehensive Excel endpoint', async () => {
    const r = useKPIReports(snackbar, client, range)
    await r.downloadExcel()
    expect(getMock.mock.calls[0][0]).toContain('/reports/comprehensive/excel')
  })

  it('sendEmailReport posts to send-manual when a client is selected', async () => {
    const r = useKPIReports(snackbar, client, range)
    r.emailRecipients.value = ['a@b.com']
    r.emailFormValid.value = true
    await r.sendEmailReport()
    expect(postMock).toHaveBeenCalledTimes(1)
    expect(postMock.mock.calls[0][0]).toBe('/reports/send-manual')
    expect(postMock.mock.calls[0][1]).toMatchObject({
      client_id: 'DEMO-PIECE', recipient_emails: ['a@b.com'],
    })
  })

  it('sendEmailReport short-circuits with no API call when no client is selected', async () => {
    const r = useKPIReports(snackbar, () => null, range)
    r.emailRecipients.value = ['a@b.com']
    r.emailFormValid.value = true
    await r.sendEmailReport()
    expect(postMock).not.toHaveBeenCalled()
    expect(snackbar).toHaveBeenCalledWith('success.pleaseSelectClient', 'warning')
  })
})
