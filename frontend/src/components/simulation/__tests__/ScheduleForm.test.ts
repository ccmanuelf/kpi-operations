/**
 * Unit tests for ScheduleForm component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ScheduleForm from '../ScheduleForm.vue'

// Mock the store
vi.mock('@/stores/simulationV2Store', () => ({
  useSimulationV2Store: vi.fn(() => ({
    schedule: {
      shifts_enabled: 1,
      shift1_hours: 8,
      shift2_hours: 0,
      shift3_hours: 0,
      work_days: 5,
      ot_enabled: false,
      weekday_ot_hours: 0,
      weekend_ot_days: 0,
      weekend_ot_hours: 0
    },
    dailyPlannedHours: 8
  }))
}))

describe('ScheduleForm', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const mountComponent = () => {
    return mount(ScheduleForm, {
      global: {
        stubs: {
          'v-card': { template: '<div class="v-card"><slot /></div>' },
          'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
          'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
          'v-icon': { template: '<span class="v-icon"><slot /></span>' },
          'v-row': { template: '<div class="v-row"><slot /></div>' },
          'v-col': { template: '<div class="v-col"><slot /></div>' },
          'v-slider': { template: '<input type="range" class="v-slider" />', props: ['modelValue', 'min', 'max', 'step'] },
          'v-switch': { template: '<input type="checkbox" class="v-switch" />', props: ['modelValue', 'label'] },
          'v-text-field': { template: '<input class="v-text-field" />', props: ['modelValue', 'label', 'type'] },
          'v-alert': { template: '<div class="v-alert"><slot /></div>', props: ['type'] }
        }
      }
    })
  }

  describe('Rendering', () => {
    it('should render the component', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.v-card').exists()).toBe(true)
    })

    it('should display Schedule Configuration title', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Schedule Configuration')
    })

    it('should display Shifts section', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Shifts')
    })

    it('should display Work Days section', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Work Days')
    })
  })

  describe('Shift Configuration', () => {
    it('should render shift configuration inputs', () => {
      const wrapper = mountComponent()
      // Check that shift-related text is present
      expect(wrapper.text()).toContain('Shifts')
    })
  })

  describe('Summary Display', () => {
    it('should display Daily Planned Hours', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Daily Planned Hours')
    })

    it('should display Weekly Base Hours', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Weekly Base Hours')
    })
  })
})
