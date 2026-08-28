/**
 * Unit tests for useWorkOrderForms' delete path.
 *
 * The work-order delete dialog is the one surface that can host markup (the
 * four grid deletes use window.confirm), so a refused delete has to reach it
 * as per-blocker rows and not only as the flattened snackbar sentence.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

const { mockApi, notifications } = vi.hoisted(() => ({
  mockApi: { deleteWorkOrder: vi.fn() },
  notifications: { showError: vi.fn(), showSuccess: vi.fn() },
}))

vi.mock('@/services/api', () => ({ default: mockApi }))
vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => notifications,
}))
// Only useI18n is replaced: `@/i18n` (which the label formatter reads) still
// needs the real createI18n, so the labels resolve from the shipped bundles.
vi.mock('vue-i18n', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key }),
}))

import { useWorkOrderForms } from '../useWorkOrderForms'
import { normalizeStructuredDetail } from '@/services/api/structuredErrors'
import { withSetup } from '../../test/composable-test-utils'

const WORK_ORDER = { work_order_id: 'WO-0002' } as never

/** An axios-shaped 409 put through the real interceptor helper, so the test
 *  never hand-builds the post-interceptor error shape. */
const refusedDelete = () => {
  const error = {
    response: {
      status: 409,
      data: {
        detail: {
          message: 'Cannot delete this WORK_ORDER record while other records still reference it.',
          blocked_by: [
            { table: 'JOB', count: 1 },
            { table: 'PRODUCTION_ENTRY', count: 4 },
          ],
        },
      },
    },
  }
  normalizeStructuredDetail(error)
  return error
}

const buildHarness = () =>
  withSetup(() => useWorkOrderForms(async () => {}, (s: string) => s))

describe('useWorkOrderForms — refused delete', () => {
  beforeEach(() => {
    mockApi.deleteWorkOrder.mockReset()
    notifications.showError.mockReset()
    notifications.showSuccess.mockReset()
  })

  it('exposes one localized row per blocker and keeps the dialog open', async () => {
    mockApi.deleteWorkOrder.mockRejectedValue(refusedDelete())
    const forms = buildHarness()

    forms.confirmDelete(WORK_ORDER)
    await forms.deleteWorkOrder()
    await flushPromises()

    expect(forms.deleteBlockers.value).toEqual([
      { table: 'JOB', count: 1, label: 'Job' },
      { table: 'PRODUCTION_ENTRY', count: 4, label: 'Production entries' },
    ])
    expect(forms.deleteDialog.value).toBe(true)
  })

  it('stays silent in the snackbar, because the dialog lists the blockers itself', async () => {
    mockApi.deleteWorkOrder.mockRejectedValue(refusedDelete())
    const forms = buildHarness()

    forms.confirmDelete(WORK_ORDER)
    await forms.deleteWorkOrder()
    await flushPromises()

    // The interceptor's flattened sentence names the same four entities the
    // open dialog is already listing; firing both puts the same information on
    // screen twice, in two different shapes.
    expect(notifications.showError).not.toHaveBeenCalled()
  })

  it('still shows a snackbar for a failure the dialog cannot explain', async () => {
    mockApi.deleteWorkOrder.mockRejectedValue({
      response: { status: 500, data: { detail: 'Internal Server Error' } },
    })
    const forms = buildHarness()

    forms.confirmDelete(WORK_ORDER)
    await forms.deleteWorkOrder()
    await flushPromises()

    // No blockers means nothing renders in the dialog, so suppressing the
    // snackbar here would lose the failure entirely.
    expect(forms.deleteBlockers.value).toEqual([])
    expect(notifications.showError).toHaveBeenCalledWith('Internal Server Error')
  })

  it('clears stale blockers when the dialog is reopened', async () => {
    mockApi.deleteWorkOrder.mockRejectedValue(refusedDelete())
    const forms = buildHarness()

    forms.confirmDelete(WORK_ORDER)
    await forms.deleteWorkOrder()
    await flushPromises()
    forms.confirmDelete(WORK_ORDER)

    expect(forms.deleteBlockers.value).toEqual([])
  })

  it('leaves the list empty when the delete succeeds', async () => {
    mockApi.deleteWorkOrder.mockResolvedValue({})
    const forms = buildHarness()

    forms.confirmDelete(WORK_ORDER)
    await forms.deleteWorkOrder()
    await flushPromises()

    expect(forms.deleteBlockers.value).toEqual([])
    expect(forms.deleteDialog.value).toBe(false)
  })
})
