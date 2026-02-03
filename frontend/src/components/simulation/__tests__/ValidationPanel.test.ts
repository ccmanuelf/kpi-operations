/**
 * Unit tests for ValidationPanel component
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ValidationPanel from '../ValidationPanel.vue'

// Create a fresh pinia for each test
const createTestPinia = () => {
  const pinia = createPinia()
  setActivePinia(pinia)
  return pinia
}

describe('ValidationPanel', () => {
  const mountComponent = (props = {}) => {
    return mount(ValidationPanel, {
      props,
      global: {
        plugins: [createTestPinia()],
        stubs: {
          'v-card': { template: '<div class="v-card"><slot /></div>' },
          'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
          'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
          'v-icon': { template: '<span class="v-icon"><slot /></span>' },
          'v-spacer': { template: '<div class="v-spacer" />' },
          'v-chip': { template: '<span class="v-chip"><slot /></span>' },
          'v-list': { template: '<ul class="v-list"><slot /></ul>' },
          'v-list-item': { template: '<li class="v-list-item"><slot /></li>' },
          'v-list-item-title': { template: '<div class="v-list-item-title"><slot /></div>' },
          'v-expansion-panels': { template: '<div class="v-expansion-panels"><slot /></div>' },
          'v-expansion-panel': { template: '<div class="v-expansion-panel"><slot /></div>' },
          'v-expansion-panel-title': { template: '<div class="v-expansion-panel-title"><slot /></div>' },
          'v-expansion-panel-text': { template: '<div class="v-expansion-panel-text"><slot /></div>' },
          'v-alert': { template: '<div class="v-alert"><slot /></div>' }
        }
      }
    })
  }

  describe('Rendering', () => {
    it('should not render when report is null', () => {
      const wrapper = mountComponent({ report: null })
      expect(wrapper.find('.v-card').exists()).toBe(false)
    })

    it('should render when report is provided', () => {
      const report = {
        is_valid: true,
        errors: [],
        warnings: [],
        info: [],
        products_count: 2,
        operations_count: 5,
        machine_tools_count: 3
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.find('.v-card').exists()).toBe(true)
    })

    it('should display "Validation Passed" when valid', () => {
      const report = {
        is_valid: true,
        errors: [],
        warnings: [],
        info: [],
        products_count: 2,
        operations_count: 5,
        machine_tools_count: 3
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).toContain('Validation')
      expect(wrapper.text()).toContain('Passed')
    })

    it('should display "Validation Failed" when not valid', () => {
      const report = {
        is_valid: false,
        errors: [{ message: 'Error 1', recommendation: 'Fix it' }],
        warnings: [],
        info: [],
        products_count: 2,
        operations_count: 5,
        machine_tools_count: 3
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).toContain('Validation')
      expect(wrapper.text()).toContain('Failed')
    })
  })

  describe('Counts Display', () => {
    it('should display products count', () => {
      const report = {
        is_valid: true,
        errors: [],
        warnings: [],
        info: [],
        products_count: 3,
        operations_count: 10,
        machine_tools_count: 5
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).toContain('3 products')
    })

    it('should display operations count', () => {
      const report = {
        is_valid: true,
        errors: [],
        warnings: [],
        info: [],
        products_count: 2,
        operations_count: 10,
        machine_tools_count: 5
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).toContain('10 operations')
    })

    it('should display machines count', () => {
      const report = {
        is_valid: true,
        errors: [],
        warnings: [],
        info: [],
        products_count: 2,
        operations_count: 5,
        machine_tools_count: 8
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).toContain('8 machines')
    })
  })

  describe('Errors Display', () => {
    it('should display errors section when errors exist', () => {
      const report = {
        is_valid: false,
        errors: [
          { message: 'Missing product', recommendation: 'Add a product', product: 'A' },
          { message: 'Invalid step', recommendation: 'Fix step number' }
        ],
        warnings: [],
        info: [],
        products_count: 1,
        operations_count: 2,
        machine_tools_count: 1
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).toContain('Errors (2)')
      expect(wrapper.text()).toContain('Must fix before running')
    })

    it('should display error messages', () => {
      const report = {
        is_valid: false,
        errors: [
          { message: 'Test error message', recommendation: 'Test recommendation' }
        ],
        warnings: [],
        info: [],
        products_count: 1,
        operations_count: 1,
        machine_tools_count: 1
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).toContain('Test error message')
    })

    it('should not display errors section when no errors', () => {
      const report = {
        is_valid: true,
        errors: [],
        warnings: [],
        info: [],
        products_count: 1,
        operations_count: 1,
        machine_tools_count: 1
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).not.toContain('Errors (')
    })
  })

  describe('Warnings Display', () => {
    it('should display warnings section when warnings exist', () => {
      const report = {
        is_valid: true,
        errors: [],
        warnings: [
          { message: 'Low efficiency', recommendation: 'Consider adding operators' }
        ],
        info: [],
        products_count: 1,
        operations_count: 1,
        machine_tools_count: 1
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).toContain('Warnings (1)')
    })
  })

  describe('Info Display', () => {
    it('should display info section when info exists', () => {
      const report = {
        is_valid: true,
        errors: [],
        warnings: [],
        info: [
          { message: 'Default value used' }
        ],
        products_count: 1,
        operations_count: 1,
        machine_tools_count: 1
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).toContain('Information (1)')
    })
  })

  describe('Success State', () => {
    it('should show success alert when valid with no warnings', () => {
      const report = {
        is_valid: true,
        errors: [],
        warnings: [],
        info: [],
        products_count: 1,
        operations_count: 1,
        machine_tools_count: 1
      }
      const wrapper = mountComponent({ report })
      expect(wrapper.text()).toContain('Configuration is valid')
      expect(wrapper.text()).toContain('Ready to run simulation')
    })
  })
})
