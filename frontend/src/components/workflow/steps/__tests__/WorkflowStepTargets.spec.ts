/**
 * Unit tests for WorkflowStepTargets — Group G Surface #17.
 *
 * Verifies the migration from broken-endpoint mock-fallback to a
 * canonical read-only checkpoint. Asserts:
 *   - GETs canonical /work-orders with client_id (not the legacy
 *     /work-orders/shift-queue)
 *   - Maps WorkOrderResponse fields (work_order_id, style_model,
 *     planned_quantity, actual_quantity, planned_ship_date) into
 *     the display shape
 *   - Computes progress = actual / planned * 100
 *   - Does NOT call the dead /materials/availability endpoint
 *   - Does NOT inject mock work orders on fetch failure
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    get: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/services/api', () => ({ default: mockApi }))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ user: { client_id_assigned: 'CLIENT1' } }),
}))

vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => ({ selectedClient: null }),
}))

vi.mock('@/stores/notificationStore', () => ({
  useNotificationStore: () => ({ show: vi.fn() }),
}))

import WorkflowStepTargets from '../WorkflowStepTargets.vue'

const stubs = {
  'v-row': { template: '<div><slot /></div>' },
  'v-col': { template: '<div><slot /></div>' },
  'v-card': { template: '<div><slot /></div>' },
  'v-card-title': { template: '<div><slot /></div>' },
  'v-card-text': { template: '<div><slot /></div>' },
  'v-icon': { template: '<i><slot /></i>' },
  'v-btn': { template: '<button v-bind="$attrs"><slot /></button>' },
  'v-skeleton-loader': { template: '<div></div>' },
  'v-alert': { template: '<div><slot /></div>' },
  'v-data-table': { template: '<table><slot /></table>' },
  'v-progress-linear': { template: '<div></div>' },
  'v-textarea': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
  },
  'v-checkbox': {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<input type="checkbox" :checked="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', !modelValue)" />',
  },
  'v-spacer': { template: '<div></div>' },
}

const mountStep = () =>
  mount(WorkflowStepTargets, {
    global: { stubs, mocks: { $t: (key: string) => key } },
  })

describe('WorkflowStepTargets', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('canonical work-orders fetch', () => {
    it('GETs /work-orders with client_id', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      mountStep()
      await flushPromises()
      expect(mockApi.get).toHaveBeenCalledWith(
        '/work-orders',
        expect.objectContaining({
          params: expect.objectContaining({ client_id: 'CLIENT1' }),
        }),
      )
    })

    it('does NOT call legacy /work-orders/shift-queue', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      mountStep()
      await flushPromises()
      const calls = mockApi.get.mock.calls.map((c) => c[0])
      expect(calls).not.toContain('/work-orders/shift-queue')
    })

    it('does NOT call legacy /materials/availability', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      mountStep()
      await flushPromises()
      const calls = mockApi.get.mock.calls.map((c) => c[0])
      expect(calls).not.toContain('/materials/availability')
    })
  })

  describe('field mapping', () => {
    it('maps WorkOrderResponse fields to display shape', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            work_order_id: 'WO-1',
            style_model: 'STYLE-A',
            planned_quantity: 100,
            actual_quantity: 25,
            planned_ship_date: '2026-05-10',
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as {
        workOrders: Array<{
          id: string
          product: string
          targetQuantity: number
          completedQuantity: number
          progress: number
        }>
      }
      expect(last.workOrders[0]).toMatchObject({
        id: 'WO-1',
        product: 'STYLE-A',
        targetQuantity: 100,
        completedQuantity: 25,
        progress: 25,
      })
    })

    it('computes progress = actual / planned * 100', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            work_order_id: 'WO-1',
            planned_quantity: 200,
            actual_quantity: 50,
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const last = (wrapper.emitted('update') as Array<[unknown]>).at(-1)?.[0] as {
        workOrders: Array<{ progress: number }>
      }
      expect(last.workOrders[0].progress).toBe(25)
    })

    it('handles zero planned_quantity without division-by-zero', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            work_order_id: 'WO-1',
            planned_quantity: 0,
            actual_quantity: 0,
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const last = (wrapper.emitted('update') as Array<[unknown]>).at(-1)?.[0] as {
        workOrders: Array<{ progress: number }>
      }
      expect(last.workOrders[0].progress).toBe(0)
    })

    it('falls back through planned_ship_date / expected_date / required_date', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            work_order_id: 'WO-1',
            planned_ship_date: null,
            expected_date: '2026-06-01',
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const last = (wrapper.emitted('update') as Array<[unknown]>).at(-1)?.[0] as {
        workOrders: Array<{ dueDate: string | null }>
      }
      expect(last.workOrders[0].dueDate).toBe('2026-06-01')
    })
  })

  describe('aggregations', () => {
    it('totalUnits sums (target - completed) clamped to 0', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          { work_order_id: 'WO-1', planned_quantity: 100, actual_quantity: 30 },
          { work_order_id: 'WO-2', planned_quantity: 50, actual_quantity: 20 },
          { work_order_id: 'WO-3', planned_quantity: 5, actual_quantity: 10 }, // over-production
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const last = (wrapper.emitted('update') as Array<[unknown]>).at(-1)?.[0] as {
        totalUnits: number
      }
      // (100-30) + (50-20) + max(0, 5-10) = 70 + 30 + 0
      expect(last.totalUnits).toBe(100)
    })
  })

  describe('error handling', () => {
    it('does NOT inject mock work orders on fetch failure (regression test)', async () => {
      mockApi.get.mockRejectedValue(new Error('boom'))
      const wrapper = mountStep()
      await flushPromises()
      const last = (wrapper.emitted('update') as Array<[unknown]>).at(-1)?.[0] as {
        workOrders: unknown[]
      }
      expect(last.workOrders).toEqual([])
    })
  })

  describe('isValid gate', () => {
    it('isValid becomes true when confirmed=true', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      await checkbox.trigger('change')
      const last = (wrapper.emitted('update') as Array<[unknown]>).at(-1)?.[0] as {
        isValid: boolean
      }
      expect(last.isValid).toBe(true)
    })

    it('emits complete event when confirm transitions to true', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      await checkbox.trigger('change')
      expect(wrapper.emitted('complete')).toBeTruthy()
    })
  })
})
