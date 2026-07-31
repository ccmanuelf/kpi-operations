/**
 * Regression test for JobLineItems.vue's endpoint paths.
 *
 * Same double-`/api/`-prefix bug class as ISSUE-019
 * (calculationAssumptions.ts / metricResults.ts): the component called
 * `api.get('/api/work-orders/.../jobs')` etc. with a literal leading
 * `/api/` on top of the shared client's `/api/v1` baseURL, double-
 * prefixing every request (e.g. `/api/v1/api/work-orders/WO-1/jobs`),
 * which 404s and is silently swallowed into an empty jobs list by the
 * component's own catch block.
 *
 * JobLineItems.vue is a plain (non-TS) `<script setup>` SFC, so its
 * internal `loadJobs`/`loadWorkOrderRty` aren't reachable via wrapper.vm
 * — this drives them via their real triggers (mount for the `jobs` watch
 * with `{ immediate: true }`, a button click for RTY) and asserts on the
 * mocked `api.get` call arguments.
 */
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const { apiMock } = vi.hoisted(() => ({
  apiMock: {
    get: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (k: string) => k }),
}))
vi.mock('@/services/api', () => ({ default: apiMock }))

import JobLineItems from '../JobLineItems.vue'

describe('JobLineItems — endpoint paths', () => {
  it('loadJobs (fired on mount) calls the un-double-prefixed jobs endpoint', async () => {
    mount(JobLineItems, {
      props: { workOrderId: 'WO-1' },
      global: { mocks: { $t: (k: string) => k } },
    })
    await flushPromises()

    expect(apiMock.get).toHaveBeenCalledWith('/work-orders/WO-1/jobs')
    expect(apiMock.get).not.toHaveBeenCalledWith(expect.stringContaining('/api/work-orders'))
  })

  it('loadWorkOrderRty calls the un-double-prefixed rty endpoint', async () => {
    apiMock.get.mockClear()
    const wrapper = mount(JobLineItems, {
      props: { workOrderId: 'WO-2' },
      global: { mocks: { $t: (k: string) => k } },
    })
    await flushPromises()
    apiMock.get.mockClear()

    await wrapper.find('button.v-btn').trigger('click')
    await flushPromises()

    expect(apiMock.get).toHaveBeenCalledWith('/work-orders/WO-2/rty')
    expect(apiMock.get).not.toHaveBeenCalledWith(expect.stringContaining('/api/work-orders'))
  })
})
