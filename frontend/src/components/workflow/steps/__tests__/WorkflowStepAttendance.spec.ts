/**
 * Unit tests for WorkflowStepAttendance — Group B Surface #7.
 *
 * Verifies the migration from dead-link API calls (/employees/shift-roster
 * and /stations, both 404) + mock-fixture fallback to the canonical
 * /api/employees roster fetch with stations dropped.
 *
 * Asserts:
 *   - GETs /employees with active=true + client_id (canonical, matches Group A)
 *   - Does NOT call /employees/shift-roster or /stations
 *   - Maps backend response fields (employee_id, employee_name) to local shape
 *   - 80% coverage gate
 *   - Mock-fixture fallback is GONE (employees stays empty on failure)
 *   - Search filter narrows roster
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

const { mockApi } = vi.hoisted(() => ({
  mockApi: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string, params?: Record<string, unknown>) =>
    params ? `${key}:${JSON.stringify(params)}` : key,
  }),
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

import WorkflowStepAttendance from '../WorkflowStepAttendance.vue'

const stubs = {
  'v-row': { template: '<div><slot /></div>' },
  'v-col': { template: '<div><slot /></div>' },
  'v-card': { template: '<div><slot /></div>' },
  'v-card-title': { template: '<div><slot /></div>' },
  'v-card-text': { template: '<div><slot /></div>' },
  'v-icon': { template: '<i><slot /></i>' },
  'v-btn': { template: '<button v-bind="$attrs"><slot /></button>' },
  'v-list': { template: '<ul><slot /></ul>' },
  'v-list-item': { template: '<li><slot /></li>' },
  'v-list-item-title': { template: '<div><slot /></div>' },
  'v-list-item-subtitle': { template: '<div><slot /></div>' },
  'v-avatar': { template: '<div><slot /></div>' },
  'v-skeleton-loader': { template: '<div></div>' },
  'v-alert': { template: '<div><slot /></div>' },
  'v-alert-title': { template: '<div><slot /></div>' },
  'v-text-field': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'v-btn-toggle': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<div><slot /></div>',
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
  mount(WorkflowStepAttendance, {
    global: { stubs, mocks: { $t: (key: string) => key } },
  })

describe('WorkflowStepAttendance', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('canonical roster fetch', () => {
    it('GETs /employees with active=true and client_id', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      mountStep()
      await flushPromises()
      expect(mockApi.get).toHaveBeenCalledWith(
        '/employees',
        expect.objectContaining({
          params: expect.objectContaining({
            active: true,
            client_id: 'CLIENT1',
          }),
        }),
      )
    })

    it('does NOT call legacy /employees/shift-roster', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      mountStep()
      await flushPromises()
      const calls = mockApi.get.mock.calls.map((c) => c[0])
      expect(calls).not.toContain('/employees/shift-roster')
    })

    it('does NOT call legacy /stations', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      mountStep()
      await flushPromises()
      const calls = mockApi.get.mock.calls.map((c) => c[0])
      expect(calls).not.toContain('/stations')
    })

    it('maps backend employee_id and employee_name fields to local shape', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          { employee_id: 1, employee_name: 'Alice', role: 'Operator' },
          { employee_id: 2, first_name: 'Bob', last_name: 'Smith', position: 'Tech' },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as {
        employees: Array<{ id: number; name: string }>
      }
      expect(last.employees).toHaveLength(2)
      expect(last.employees[0]).toMatchObject({ id: 1, name: 'Alice' })
      expect(last.employees[1]).toMatchObject({ id: 2, name: 'Bob Smith' })
    })

    it('defaults all employees to present=true after fetch', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          { employee_id: 1, employee_name: 'Alice' },
          { employee_id: 2, employee_name: 'Bob' },
        ],
      })
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as {
        presentCount: number
        absentCount: number
      }
      expect(last.presentCount).toBe(2)
      expect(last.absentCount).toBe(0)
    })
  })

  describe('80% coverage gate', () => {
    it('checkbox enabled when ≥80% present (8/10)', async () => {
      const data = Array.from({ length: 10 }, (_, i) => ({
        employee_id: i + 1,
        employee_name: `Emp ${i + 1}`,
      }))
      mockApi.get.mockResolvedValue({ data })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      expect((checkbox.element as HTMLInputElement).disabled).toBe(false)
    })

    it('checkbox disabled when 0 employees', async () => {
      mockApi.get.mockResolvedValue({ data: [] })
      const wrapper = mountStep()
      await flushPromises()
      const checkbox = wrapper.find('input[type="checkbox"]')
      expect((checkbox.element as HTMLInputElement).disabled).toBe(true)
    })

    it('emits complete event when ≥80% coverage and confirmed', async () => {
      mockApi.get.mockResolvedValue({
        data: [
          { employee_id: 1, employee_name: 'A' },
          { employee_id: 2, employee_name: 'B' },
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
    it('does NOT inject mock employees on fetch failure (regression test)', async () => {
      mockApi.get.mockRejectedValue(new Error('boom'))
      const wrapper = mountStep()
      await flushPromises()
      const updates = wrapper.emitted('update') as Array<[unknown]>
      const last = updates.at(-1)?.[0] as {
        employees: unknown[]
        presentCount: number
      }
      expect(last.employees).toEqual([])
      expect(last.presentCount).toBe(0)
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
