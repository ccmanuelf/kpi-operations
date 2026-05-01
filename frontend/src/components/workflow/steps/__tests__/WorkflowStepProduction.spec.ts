/**
 * Unit tests for WorkflowStepProduction — Group B Surface #6.
 *
 * Verifies the migration from a write step (POST /production-entries to a
 * non-existent endpoint) to a read-only checkpoint. Asserts:
 *   - GETs /production with start_date/end_date params + client_id
 *   - Aggregates by work_order_id (entry_count + units_produced + defect_count)
 *   - canConfirm gate: at least one entry must exist
 *   - No POST/PUT/PATCH calls
 *   - Mock-fixture fallback path is GONE (entries stays empty on failure)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
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

import WorkflowStepProduction from '../WorkflowStepProduction.vue'

const stubs = {
  'v-row': { template: '<div><slot /></div>' },
  'v-col': { template: '<div><slot /></div>' },
  'v-card': { template: '<div><slot /></div>' },
  'v-card-title': { template: '<div><slot /></div>' },
  'v-card-text': { template: '<div><slot /></div>' },
  'v-icon': { template: '<i><slot /></i>' },
  'v-btn': { template: '<button v-bind="$attrs"><slot /></button>' },
  'v-data-table': { template: '<table><slot /></table>' },
  'v-skeleton-loader': { template: '<div></div>' },
  'v-alert': { template: '<div><slot /></div>' },
  'v-chip': { template: '<span><slot /></span>' },
  'v-checkbox': {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<input type="checkbox" :checked="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', !modelValue)" />',
  },
  'v-spacer': { template: '<div></div>' },
}

const mountStep = () =>
  mount(WorkflowStepProduction, {
    global: { stubs, mocks: { $t: (key: string) => key } },
  })

describe('WorkflowStepProduction', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('read-only data load', () => {
    it('GETs /production with start_date and end_date params', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      mountStep()
      await flushPromises()
      expect(mockApi.get).toHaveBeenCalledWith(
        '/production',
        expect.objectContaining({
          params: expect.objectContaining({
            start_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
            end_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
            client_id: 'CLIENT1',
          }),
        }),
      )
    })

    it('does NOT issue any POST/PUT/PATCH on mount', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      mountStep()
      await flushPromises()
      expect(mockApi.post).not.toHaveBeenCalled()
      expect(mockApi.put).not.toHaveBeenCalled()
      expect(mockApi.patch).not.toHaveBeenCalled()
    })
  })

  describe('aggregation by work order', () => {
    it('groups entries by work_order_id and sums units_produced + defect_count', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            production_entry_id: 'p1',
            work_order_id: 'WO-001',
            units_produced: 100,
            defect_count: 2,
          },
          {
            production_entry_id: 'p2',
            work_order_id: 'WO-001',
            units_produced: 50,
            defect_count: 0,
          },
          {
            production_entry_id: 'p3',
            work_order_id: 'WO-002',
            units_produced: 30,
            defect_count: 1,
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as {
        totalProduced: number
        totalDefects: number
        workOrdersCount: number
      }
      expect(last.totalProduced).toBe(180)
      expect(last.totalDefects).toBe(3)
      expect(last.workOrdersCount).toBe(2)
    })

    it('handles entries with missing work_order_id (groups under "—")', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          { production_entry_id: 'p1', units_produced: 100 },
          { production_entry_id: 'p2', units_produced: 50 },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as { workOrdersCount: number }
      expect(last.workOrdersCount).toBe(1)
    })
  })

  describe('canConfirm gate', () => {
    it('checkbox disabled when no entries exist', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      expect((checkbox.element as HTMLInputElement).disabled).toBe(true)
    })

    it('checkbox enabled when ≥1 entry exists', async () => {
      mockApi.get.mockResolvedValue({
        data: [{ production_entry_id: 'p1', units_produced: 10 }],
      })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      expect((checkbox.element as HTMLInputElement).disabled).toBe(false)
    })

    it('isValid becomes true when entries exist AND confirmed', async () => {
      mockApi.get.mockResolvedValue({
        data: [{ production_entry_id: 'p1', units_produced: 10 }],
      })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      await checkbox.trigger('change')
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as { isValid: boolean }
      expect(last.isValid).toBe(true)
    })

    it('emits complete event when entries exist and confirm transitions to true', async () => {
      mockApi.get.mockResolvedValue({
        data: [{ production_entry_id: 'p1', units_produced: 10 }],
      })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      await checkbox.trigger('change')
      expect(wrapper.emitted('complete')).toBeTruthy()
    })
  })

  describe('error handling', () => {
    it('does NOT inject mock work orders on fetch failure (regression test)', async () => {
      mockApi.get.mockRejectedValue(new Error('boom'))
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as {
        entries: unknown[]
        workOrdersCount: number
      }
      expect(last.entries).toEqual([])
      expect(last.workOrdersCount).toBe(0)
    })

    it('checkbox stays disabled on fetch failure', async () => {
      mockApi.get.mockRejectedValue(new Error('boom'))
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      expect((checkbox.element as HTMLInputElement).disabled).toBe(true)
    })
  })
})
