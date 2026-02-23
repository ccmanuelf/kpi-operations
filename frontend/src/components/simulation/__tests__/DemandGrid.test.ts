/**
 * Unit tests for DemandGrid component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DemandGrid from '../DemandGrid.vue'

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key })
}))

// Mock AG Grid
vi.mock('ag-grid-vue3', () => ({
  AgGridVue: {
    template: '<div class="ag-grid-mock" data-testid="demand-grid"><slot /></div>',
    props: ['columnDefs', 'rowData', 'defaultColDef', 'gridOptions', 'getRowId']
  }
}))

// Mock the store
const mockStore = {
  demands: [
    { _id: '1', product: 'TSHIRT_A', bundle_size: 10, daily_demand: 100, weekly_demand: 500, mix_share_pct: 50 }
  ],
  products: ['TSHIRT_A', 'TSHIRT_B'],
  mode: 'demand-driven',
  totalDemand: 1000,
  horizonDays: 5,
  totalMixPercent: 100,
  addDemand: vi.fn(),
  removeDemand: vi.fn(),
  updateDemand: vi.fn()
}

vi.mock('@/stores/simulationV2Store', () => ({
  useSimulationV2Store: vi.fn(() => mockStore)
}))

describe('DemandGrid', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockStore.mode = 'demand-driven'
    mockStore.demands = [
      { _id: '1', product: 'TSHIRT_A', bundle_size: 10, daily_demand: 100, weekly_demand: 500, mix_share_pct: 50 }
    ]
  })

  const mountComponent = () => {
    return mount(DemandGrid, {
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
          'v-row': { template: '<div class="v-row"><slot /></div>' },
          'v-col': { template: '<div class="v-col"><slot /></div>' },
          'v-select': {
            template: '<select class="v-select"><option v-for="i in items" :key="i.value" :value="i.value">{{i.title}}</option></select>',
            props: ['modelValue', 'items', 'label']
          },
          'v-text-field': {
            template: '<input class="v-text-field" :value="modelValue" />',
            props: ['modelValue', 'label', 'type']
          }
        }
      }
    })
  }

  describe('Rendering', () => {
    it('should render the component', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.v-card').exists()).toBe(true)
    })

    it('should display Demand Configuration title', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('simulationDemand.title')
    })

    it('should render Add Product Demand button', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('simulationDemand.addProductDemand')
    })

    it('should render AG Grid component', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.ag-grid-mock').exists()).toBe(true)
    })

    it('should render demand mode selector', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.v-select').exists()).toBe(true)
    })
  })

  describe('Empty State', () => {
    it('should show info alert when no demands exist', () => {
      mockStore.demands = []
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('simulationDemand.emptyDemand')
    })

    it('should show auto-fill button when products exist but no demands', () => {
      mockStore.demands = []
      mockStore.products = ['TSHIRT_A', 'TSHIRT_B']
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('simulationDemand.autoFill')
    })
  })

  describe('Demand-Driven Mode', () => {
    beforeEach(() => {
      mockStore.mode = 'demand-driven'
    })

    it('should display daily demand column in demand-driven mode', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const dailyCol = columnDefs.find((c: { field: string }) => c.field === 'daily_demand')
      expect(dailyCol).toBeDefined()
      expect(dailyCol.headerName).toBe('simulationDemand.dailyDemand')
    })

    it('should display weekly demand column in demand-driven mode', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const weeklyCol = columnDefs.find((c: { field: string }) => c.field === 'weekly_demand')
      expect(weeklyCol).toBeDefined()
      expect(weeklyCol.headerName).toBe('simulationDemand.weeklyDemand')
    })
  })

  describe('Mix-Driven Mode', () => {
    beforeEach(() => {
      mockStore.mode = 'mix-driven'
    })

    it('should display mix share column in mix-driven mode', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const mixCol = columnDefs.find((c: { field: string }) => c.field === 'mix_share_pct')
      expect(mixCol).toBeDefined()
      expect(mixCol.headerName).toBe('simulationDemand.mixShare')
    })

    it('should not display daily demand column in mix-driven mode', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const dailyCol = columnDefs.find((c: { field: string }) => c.field === 'daily_demand')
      expect(dailyCol).toBeUndefined()
    })
  })

  describe('Mix Percentage Validation', () => {
    it('should show warning when mix percentages do not sum to 100', () => {
      mockStore.mode = 'mix-driven'
      mockStore.totalMixPercent = 90
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('simulationDemand.mixWarning')
    })
  })

  describe('Actions', () => {
    it('should call addDemand when Add Product Demand button is clicked', async () => {
      const wrapper = mountComponent()
      const buttons = wrapper.findAll('.v-btn')
      const addButton = buttons.find(btn => btn.text().includes('simulationDemand.addProductDemand'))

      if (addButton) {
        await addButton.trigger('click')
        expect(mockStore.addDemand).toHaveBeenCalled()
      }
    })
  })

  describe('Column Definitions', () => {
    it('should define Product column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const productCol = columnDefs.find((c: { field: string }) => c.field === 'product')
      expect(productCol).toBeDefined()
      expect(productCol.headerName).toBe('simulationV2.operations.product')
    })

    it('should define Bundle Size column', () => {
      const wrapper = mountComponent()
      const columnDefs = wrapper.vm.columnDefs
      const bundleCol = columnDefs.find((c: { field: string }) => c.field === 'bundle_size')
      expect(bundleCol).toBeDefined()
      expect(bundleCol.headerName).toBe('simulationDemand.bundleSize')
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
})
