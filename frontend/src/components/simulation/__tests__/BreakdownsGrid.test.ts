/**
 * Unit tests for BreakdownsGrid component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import BreakdownsGrid from '../BreakdownsGrid.vue'

// Mock AG Grid
vi.mock('ag-grid-vue3', () => ({
  AgGridVue: {
    template: '<div class="ag-grid-mock" data-testid="breakdowns-grid"><slot /></div>',
    props: ['columnDefs', 'rowData', 'defaultColDef', 'gridOptions', 'getRowId']
  }
}))

// Mock the store
const mockStore = {
  breakdowns: [],
  machineTools: ['Cutting Table', 'Sewing Machine', 'Pressing Station'],
  addBreakdown: vi.fn(),
  removeBreakdown: vi.fn(),
  updateBreakdown: vi.fn()
}

vi.mock('@/stores/simulationV2Store', () => ({
  useSimulationV2Store: vi.fn(() => mockStore)
}))

describe('BreakdownsGrid', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockStore.breakdowns = []
  })

  const mountComponent = () => {
    return mount(BreakdownsGrid, {
      global: {
        stubs: {
          'v-card': { template: '<div class="v-card"><slot /></div>' },
          'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
          'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
          'v-icon': { template: '<span class="v-icon"><slot /></span>' },
          'v-btn': {
            template: '<button class="v-btn" @click="$emit(\'click\')"><slot /></button>',
            emits: ['click']
          },
          'v-alert': { template: '<div class="v-alert"><slot /></div>', props: ['type'] },
          'v-dialog': {
            template: '<div class="v-dialog" v-if="modelValue"><slot /></div>',
            props: ['modelValue']
          },
          'v-list': { template: '<ul class="v-list"><slot /></ul>' },
          'v-list-item': { template: '<li class="v-list-item"><slot /></li>' },
          'v-list-item-title': { template: '<div class="v-list-item-title"><slot /></div>' },
          'v-checkbox': {
            template: '<input type="checkbox" class="v-checkbox" />',
            props: ['modelValue', 'value']
          },
          'v-text-field': {
            template: '<input class="v-text-field" :value="modelValue" />',
            props: ['modelValue', 'label', 'type']
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

    it('should display Equipment Breakdowns title', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Equipment Breakdowns')
    })

    it('should display Optional label', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Optional')
    })

    it('should render Add Breakdown Rule button', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Add Breakdown Rule')
    })

    it('should show info alert about breakdown configuration', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Configure probability of equipment breakdown')
    })
  })

  describe('Empty State', () => {
    it('should show empty state message when no breakdowns exist', () => {
      mockStore.breakdowns = []
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('No breakdown rules configured')
      expect(wrapper.text()).toContain('perfect equipment reliability')
    })

    it('should show check circle icon in empty state', () => {
      mockStore.breakdowns = []
      const wrapper = mountComponent()
      expect(wrapper.find('.v-icon').exists()).toBe(true)
    })

    it('should show Quick Add button when machine tools are available', () => {
      mockStore.breakdowns = []
      mockStore.machineTools = ['Cutting Table', 'Sewing Machine']
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Quick Add from Operations')
    })

    it('should show count of available machines in Quick Add button', () => {
      mockStore.breakdowns = []
      mockStore.machineTools = ['Cutting Table', 'Sewing Machine', 'Pressing']
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('3 machines')
    })
  })

  describe('With Breakdowns', () => {
    beforeEach(() => {
      mockStore.breakdowns = [
        { _id: '1', machine_tool: 'Cutting Table', breakdown_pct: 2.5 },
        { _id: '2', machine_tool: 'Sewing Machine', breakdown_pct: 1.0 }
      ]
    })

    it('should render AG Grid when breakdowns exist', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.ag-grid-mock').exists()).toBe(true)
    })

    it('should not show empty state when breakdowns exist', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).not.toContain('No breakdown rules configured')
    })
  })

  describe('Available Machine Tools', () => {
    it('should calculate available machine tools correctly', () => {
      mockStore.machineTools = ['Cutting Table', 'Sewing Machine', 'Pressing']
      mockStore.breakdowns = [
        { _id: '1', machine_tool: 'Cutting Table', breakdown_pct: 2.5 }
      ]
      const wrapper = mountComponent()
      const available = wrapper.vm.availableMachineTools
      expect(available).toEqual(['Sewing Machine', 'Pressing'])
    })

    it('should return all machines when no breakdowns configured', () => {
      mockStore.machineTools = ['Cutting Table', 'Sewing Machine']
      mockStore.breakdowns = []
      const wrapper = mountComponent()
      const available = wrapper.vm.availableMachineTools
      expect(available).toEqual(['Cutting Table', 'Sewing Machine'])
    })

    it('should return empty array when all machines have breakdown rules', () => {
      mockStore.machineTools = ['Cutting Table']
      mockStore.breakdowns = [
        { _id: '1', machine_tool: 'Cutting Table', breakdown_pct: 2.5 }
      ]
      const wrapper = mountComponent()
      const available = wrapper.vm.availableMachineTools
      expect(available).toEqual([])
    })
  })

  describe('Actions', () => {
    it('should call addBreakdown when Add Breakdown Rule button is clicked', async () => {
      const wrapper = mountComponent()
      const buttons = wrapper.findAll('.v-btn')
      const addButton = buttons.find(btn => btn.text().includes('Add Breakdown Rule'))

      if (addButton) {
        await addButton.trigger('click')
        expect(mockStore.addBreakdown).toHaveBeenCalled()
      }
    })

    it('should open quick add dialog when Quick Add button is clicked', async () => {
      mockStore.breakdowns = []
      mockStore.machineTools = ['Cutting Table']
      const wrapper = mountComponent()
      const buttons = wrapper.findAll('.v-btn')
      const quickAddButton = buttons.find(btn => btn.text().includes('Quick Add'))

      if (quickAddButton) {
        await quickAddButton.trigger('click')
        expect(wrapper.vm.showQuickAdd).toBe(true)
      }
    })
  })

  describe('Column Definitions', () => {
    it('should define Machine/Tool column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const machineCol = columnDefs.find((c: { field: string }) => c.field === 'machine_tool')
      expect(machineCol).toBeDefined()
      expect(machineCol.headerName).toBe('Machine/Tool')
    })

    it('should define Breakdown % column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const breakdownCol = columnDefs.find((c: { field: string }) => c.field === 'breakdown_pct')
      expect(breakdownCol).toBeDefined()
      expect(breakdownCol.headerName).toBe('Breakdown %')
    })

    it('should have actions column for row deletion', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const actionsCol = columnDefs.find((c: { field: string }) => c.field === 'actions')
      expect(actionsCol).toBeDefined()
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
  })

  describe('Default Values', () => {
    it('should have default breakdown percentage of 2.0', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.defaultBreakdownPct).toBe(2.0)
    })

    it('should have empty selected tools by default', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.selectedTools).toEqual([])
    })
  })
})
