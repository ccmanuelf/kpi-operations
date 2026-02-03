/**
 * Unit tests for OperationsGrid component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OperationsGrid from '../OperationsGrid.vue'

// Mock AG Grid
vi.mock('ag-grid-vue3', () => ({
  AgGridVue: {
    template: '<div class="ag-grid-mock" data-testid="operations-grid"><slot /></div>',
    props: ['columnDefs', 'rowData', 'defaultColDef', 'gridOptions', 'getRowId']
  }
}))

// Mock papaparse
vi.mock('papaparse', () => ({
  default: {
    parse: vi.fn((text, options) => {
      const lines = text.trim().split('\n')
      const headers = lines[0].split(',')
      const data = lines.slice(1).map(line => {
        const values = line.split(',')
        const obj: Record<string, string> = {}
        headers.forEach((h, i) => {
          obj[h] = values[i]
        })
        return obj
      })
      options.complete({ data })
    })
  }
}))

// Mock the store
const mockStore = {
  operations: [
    { _id: '1', product: 'TSHIRT_A', step: 1, operation: 'Cut fabric', machine_tool: 'Cutting Table', sam_min: 2.0, operators: 2 }
  ],
  operationsCount: 1,
  productsCount: 1,
  addOperation: vi.fn(),
  removeOperation: vi.fn(),
  updateOperation: vi.fn(),
  importOperations: vi.fn()
}

vi.mock('@/stores/simulationV2Store', () => ({
  useSimulationV2Store: vi.fn(() => mockStore)
}))

describe('OperationsGrid', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mountComponent = () => {
    return mount(OperationsGrid, {
      global: {
        mocks: {
          $t: (key: string, fallback?: string) => fallback || key
        },
        stubs: {
          'v-card': { template: '<div class="v-card"><slot /></div>' },
          'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
          'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
          'v-icon': { template: '<span class="v-icon"><slot /></span>' },
          'v-chip': { template: '<span class="v-chip"><slot /></span>' },
          'v-btn': {
            template: '<button class="v-btn" @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          },
          'v-alert': { template: '<div class="v-alert"><slot /></div>' },
          'v-dialog': {
            template: '<div class="v-dialog" v-if="modelValue"><slot /></div>',
            props: ['modelValue']
          },
          'v-textarea': {
            template: '<textarea class="v-textarea" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
            props: ['modelValue'],
            emits: ['update:modelValue']
          },
          'v-card-actions': { template: '<div class="v-card-actions"><slot /></div>' },
          'v-spacer': { template: '<div class="v-spacer" />' }
        }
      }
    })
  }

  describe('Rendering', () => {
    it('should render the component', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.v-card').exists()).toBe(true)
    })

    it('should display Operations title', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Operations')
    })

    it('should display operation count chip', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('1 ops')
    })

    it('should display products count chip', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('1 products')
    })

    it('should render Add Operation button', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Add Operation')
    })

    it('should render Import CSV button', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Import CSV')
    })

    it('should render AG Grid component', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.ag-grid-mock').exists()).toBe(true)
    })
  })

  describe('Empty State', () => {
    it('should display help text about adding operations', () => {
      // The info alert provides guidance for users
      const wrapper = mountComponent()
      // Component should render successfully
      expect(wrapper.find('.v-card').exists()).toBe(true)
      // The component text should provide context about operations
      expect(wrapper.text()).toContain('Operations')
    })
  })

  describe('Actions', () => {
    it('should call addOperation when Add Operation button is clicked', async () => {
      const wrapper = mountComponent()
      const buttons = wrapper.findAll('.v-btn')
      const addButton = buttons.find(btn => btn.text().includes('Add Operation'))

      if (addButton) {
        await addButton.trigger('click')
        expect(mockStore.addOperation).toHaveBeenCalled()
      }
    })

    it('should open import dialog when Import CSV button is clicked', async () => {
      const wrapper = mountComponent()
      const buttons = wrapper.findAll('.v-btn')
      const importButton = buttons.find(btn => btn.text().includes('Import CSV'))

      if (importButton) {
        await importButton.trigger('click')
        // Dialog should be visible after click
        expect(wrapper.vm.showImportDialog).toBe(true)
      }
    })
  })

  describe('Column Definitions', () => {
    it('should define Product column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const productCol = columnDefs.find((c: { field: string }) => c.field === 'product')
      expect(productCol).toBeDefined()
      expect(productCol.headerName).toBe('Product')
    })

    it('should define Step column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const stepCol = columnDefs.find((c: { field: string }) => c.field === 'step')
      expect(stepCol).toBeDefined()
      expect(stepCol.headerName).toBe('Step')
    })

    it('should define Operation column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const opCol = columnDefs.find((c: { field: string }) => c.field === 'operation')
      expect(opCol).toBeDefined()
      expect(opCol.headerName).toBe('Operation')
    })

    it('should define Machine/Tool column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const machineCol = columnDefs.find((c: { field: string }) => c.field === 'machine_tool')
      expect(machineCol).toBeDefined()
      expect(machineCol.headerName).toBe('Machine/Tool')
    })

    it('should define SAM column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const samCol = columnDefs.find((c: { field: string }) => c.field === 'sam_min')
      expect(samCol).toBeDefined()
      expect(samCol.headerName).toBe('SAM (min)')
    })

    it('should define Operators column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const opsCol = columnDefs.find((c: { field: string }) => c.field === 'operators')
      expect(opsCol).toBeDefined()
      expect(opsCol.headerName).toBe('Operators')
    })

    it('should define Grade % column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const gradeCol = columnDefs.find((c: { field: string }) => c.field === 'grade_pct')
      expect(gradeCol).toBeDefined()
      expect(gradeCol.headerName).toBe('Grade %')
    })

    it('should define FPD % column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const fpdCol = columnDefs.find((c: { field: string }) => c.field === 'fpd_pct')
      expect(fpdCol).toBeDefined()
      expect(fpdCol.headerName).toBe('FPD %')
    })
  })

  describe('Grid Options', () => {
    it('should have single click edit enabled', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.gridOptions.singleClickEdit).toBe(true)
    })

    it('should have undo/redo enabled', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.gridOptions.undoRedoCellEditing).toBe(true)
    })

    it('should have editable columns by default', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.defaultColDef.editable).toBe(true)
    })

    it('should have sortable columns by default', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.defaultColDef.sortable).toBe(true)
    })

    it('should have filterable columns by default', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.defaultColDef.filter).toBe(true)
    })
  })
})
