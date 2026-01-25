/**
 * Vitest test setup file
 * Configures global mocks and test utilities
 */
import { vi } from 'vitest'
import { config } from '@vue/test-utils'

// Mock window.confirm
global.confirm = vi.fn(() => true)

// Mock window.URL.createObjectURL
global.URL.createObjectURL = vi.fn(() => 'mocked-url')
global.URL.revokeObjectURL = vi.fn()

// Mock CSS imports
vi.mock('vuetify/styles', () => ({}))

// Mock Vuetify components with stubs
config.global.stubs = {
  'v-card': { template: '<div class="v-card"><slot /></div>' },
  'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
  'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
  'v-btn': { template: '<button class="v-btn"><slot /></button>' },
  'v-icon': { template: '<span class="v-icon"><slot /></span>' },
  'v-file-input': {
    template: '<input type="file" class="v-file-input" />',
    props: ['modelValue', 'accept', 'label', 'loading'],
    emits: ['update:modelValue', 'change']
  },
  'v-alert': { template: '<div class="v-alert"><slot /></div>', props: ['type'] },
  'v-data-table': { template: '<table class="v-data-table"><slot /></table>', props: ['headers', 'items', 'loading'] },
  'v-row': { template: '<div class="v-row"><slot /></div>' },
  'v-col': { template: '<div class="v-col"><slot /></div>' },
  'v-progress-linear': { template: '<div class="v-progress-linear"><slot /></div>', props: ['modelValue', 'color', 'height'] },
  'v-chip': { template: '<span class="v-chip"><slot /></span>', props: ['color', 'size'] },
  'v-spacer': { template: '<div class="v-spacer"></div>' },
  'v-text-field': { template: '<input class="v-text-field" />', props: ['modelValue', 'type'] },
  'v-select': { template: '<select class="v-select"></select>', props: ['modelValue', 'items'] },
  'v-list': { template: '<ul class="v-list"><slot /></ul>' },
  'v-list-item': { template: '<li class="v-list-item"><slot /></li>' }
}

// Mock pinia for component tests
vi.mock('pinia', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    defineStore: actual.defineStore
  }
})
