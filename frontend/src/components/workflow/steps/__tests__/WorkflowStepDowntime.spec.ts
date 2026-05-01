/**
 * Unit tests for WorkflowStepDowntime — Group B Surface #5.
 *
 * Verifies the migration from a write-with-forged-success step to a
 * read-only checkpoint. Specifically asserts:
 *   - "Needs attention" detection (rows without corrective_action)
 *   - Resolved detection (rows with corrective_action)
 *   - "Open Downtime Grid" link-out button exists
 *   - isValid gate (confirmed AND openCount === 0)
 *   - The forged-success-on-failure path is GONE (component no longer
 *     calls api.patch and the previous bug is structurally impossible).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    get: vi.fn(),
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

import WorkflowStepDowntime from '../WorkflowStepDowntime.vue'

const stubs = {
  'v-row': { template: '<div><slot /></div>' },
  'v-col': { template: '<div><slot /></div>' },
  'v-card': { template: '<div><slot /></div>' },
  'v-card-title': { template: '<div><slot /></div>' },
  'v-card-text': { template: '<div><slot /></div>' },
  'v-icon': { template: '<i><slot /></i>' },
  'v-chip': { template: '<span><slot /></span>' },
  'v-btn': { template: '<button v-bind="$attrs"><slot /></button>' },
  'v-list': { template: '<ul><slot /></ul>' },
  'v-list-item': { template: '<li><slot /></li>' },
  'v-list-item-title': { template: '<div><slot /></div>' },
  'v-list-item-subtitle': { template: '<div><slot /></div>' },
  'v-avatar': { template: '<div><slot /></div>' },
  'v-progress-linear': { template: '<div></div>' },
  'v-skeleton-loader': { template: '<div></div>' },
  'v-alert': { template: '<div><slot /></div>' },
  'v-checkbox': {
    props: ['modelValue', 'disabled'],
    emits: ['update:modelValue'],
    template:
      '<input type="checkbox" :checked="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', !modelValue)" />',
  },
  'v-tooltip': { template: '<div><slot name="activator" :props="{}" /></div>' },
  'v-spacer': { template: '<div></div>' },
}

const mountStep = () =>
  mount(WorkflowStepDowntime, {
    global: { stubs, mocks: { $t: (key: string) => key } },
  })

describe('WorkflowStepDowntime', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('read-only data load', () => {
    it('GETs /downtime with shift_date and client_id params', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      mountStep()
      await flushPromises()
      expect(mockApi.get).toHaveBeenCalledWith(
        '/downtime',
        expect.objectContaining({
          params: expect.objectContaining({
            shift_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
            client_id: 'CLIENT1',
          }),
        }),
      )
    })

    it('does NOT issue any PATCH requests on mount', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      mountStep()
      await flushPromises()
      expect(mockApi.patch).not.toHaveBeenCalled()
    })
  })

  describe('open vs. resolved classification', () => {
    it('treats rows missing corrective_action as open (needs attention)', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            downtime_entry_id: 'd1',
            downtime_reason: 'EQUIPMENT_FAILURE',
            downtime_duration_minutes: 30,
          },
          {
            downtime_entry_id: 'd2',
            downtime_reason: 'MAINTENANCE',
            downtime_duration_minutes: 15,
            corrective_action: 'Replaced gasket',
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as {
        openCount: number
        totalMinutes: number
      }
      expect(last.openCount).toBe(1)
      expect(last.totalMinutes).toBe(45)
    })

    it('treats rows with whitespace-only corrective_action as still open', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            downtime_entry_id: 'd1',
            downtime_reason: 'OTHER',
            downtime_duration_minutes: 10,
            corrective_action: '   ',
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as { openCount: number }
      expect(last.openCount).toBe(1)
    })

    it('treats rows with corrective_action as resolved', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            downtime_entry_id: 'd1',
            downtime_reason: 'OTHER',
            downtime_duration_minutes: 10,
            corrective_action: 'Done',
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as { openCount: number }
      expect(last.openCount).toBe(0)
    })
  })

  describe('isValid gate', () => {
    it('checkbox is disabled while openCount > 0', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            downtime_entry_id: 'd1',
            downtime_reason: 'OTHER',
            downtime_duration_minutes: 10,
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      expect((checkbox.element as HTMLInputElement).disabled).toBe(true)
    })

    it('isValid becomes true when openCount === 0 and confirmed=true', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            downtime_entry_id: 'd1',
            downtime_reason: 'OTHER',
            downtime_duration_minutes: 10,
            corrective_action: 'Done',
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      await checkbox.trigger('change')
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as { isValid: boolean }
      expect(last.isValid).toBe(true)
    })

    it('emits complete event when openCount=0 and confirm transitions to true', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          {
            downtime_entry_id: 'd1',
            downtime_reason: 'OTHER',
            downtime_duration_minutes: 10,
            corrective_action: 'Done',
          },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      await checkbox.trigger('change')
      expect(wrapper.emitted('complete')).toBeTruthy()
    })
  })

  describe('error handling', () => {
    it('does NOT forge resolved state on fetch failure (regression test)', async () => {
      mockApi.get.mockRejectedValue(new Error('boom'))
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as {
        openCount: number
        incidents: unknown[]
      }
      // No silent substitution of mock data; no fake "resolved" state.
      expect(last.incidents).toEqual([])
      expect(last.openCount).toBe(0)
    })

    it('still calls api.get on fetch failure path (no silent skip)', async () => {
      mockApi.get.mockRejectedValue(new Error('boom'))
      mountStep()
      await flushPromises()
      expect(mockApi.get).toHaveBeenCalledTimes(1)
    })
  })
})
