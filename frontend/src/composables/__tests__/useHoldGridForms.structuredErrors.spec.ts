/**
 * The hold approval actions go out over a raw `fetch`, so the axios response
 * interceptor never sees them — a structured 409/422 body has to be flattened
 * inside the composable or the operator gets `Error: [object Object]`.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { computed, ref } from 'vue'

vi.mock('vue-i18n', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-i18n')>()),
  useI18n: () => ({ t: (key: string) => key }),
}))
vi.mock('@/stores/authStore', () => ({ useAuthStore: () => ({ user: null }) }))
vi.mock('@/stores/kpi', () => ({ useKPIStore: () => ({ selectedClient: 'CLIENT001' }) }))

import { useHoldGridForms } from '../useHoldGridForms'
import { withSetup } from '../../test/composable-test-utils'

const showSnackbar = vi.fn()

const buildHarness = () =>
  withSetup(() =>
    useHoldGridForms({
      gridRef: ref(null),
      unsavedChanges: ref(new Set<string | number>()),
      saving: ref(false),
      workOrders: computed(() => []),
      kpiStore: {
        deleteHoldEntry: vi.fn(),
        createHoldEntry: vi.fn(),
        updateHoldEntry: vi.fn(),
        fetchHoldEntries: vi.fn().mockResolvedValue(undefined),
      },
      applyFilters: vi.fn(),
      showSnackbar,
    }),
  )

const respondWith = (detail: unknown) => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail }) }),
  )
}

describe('useHoldGridForms — approval errors', () => {
  beforeEach(() => {
    showSnackbar.mockReset()
    // The request builds an Authorization header from the bare `localStorage`
    // global, which this environment does not provide.
    vi.stubGlobal('localStorage', { getItem: () => 'test-token' })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('flattens a structured hidden_parents body', async () => {
    respondWith({
      message: 'Cannot reference a deleted record: WORK_ORDER WO-0002.',
      hidden_parents: [{ table: 'WORK_ORDER', id: 'WO-0002' }],
    })

    await buildHarness().approveHold({ hold_entry_id: 7 } as never)

    expect(showSnackbar).toHaveBeenCalledWith(
      'common.error: Cannot reference a deleted record: Work order WO-0002. ' +
        'It has been deleted and is no longer available.',
      'error',
    )
  })

  it('leaves a plain string detail alone', async () => {
    respondWith('Hold entry not found')

    await buildHarness().approveHold({ hold_entry_id: 7 } as never)

    expect(showSnackbar).toHaveBeenCalledWith('common.error: Hold entry not found', 'error')
  })
})
