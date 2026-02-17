/**
 * Unit tests for Capacity Planning Components
 * Tests: InstructionsPanel, DashboardInputsPanel, CapacityAnalysisPanel, ScenariosPanel
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key) => key
  })
}))

// Mock the capacityPlanningStore
const mockStore = {
  worksheets: {
    dashboardInputs: {
      data: {
        planning_horizon_days: 30,
        shortage_alert_days: 7,
        default_efficiency: 85,
        bottleneck_threshold: 90,
        auto_schedule_enabled: false
      },
      dirty: false
    },
    capacityAnalysis: {
      data: []
    },
    scenarios: {
      data: []
    },
    whatIfScenarios: {
      data: []
    },
    stockSnapshot: {
      data: [],
      dirty: false
    }
  },
  averageUtilization: 75,
  isRunningAnalysis: false,
  isCreatingScenario: false,
  updateDashboardInput: vi.fn(),
  runCapacityAnalysis: vi.fn(),
  createScenario: vi.fn(),
  deleteScenario: vi.fn(),
  runScenario: vi.fn(),
  addRow: vi.fn(),
  removeRow: vi.fn(),
  importData: vi.fn()
}

vi.mock('@/stores/capacityPlanningStore', () => ({
  useCapacityPlanningStore: () => mockStore
}))

// Additional Vuetify component stubs needed for capacity planning
const globalStubs = {
  'v-card': { template: '<div class="v-card"><slot /></div>' },
  'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
  'v-card-text': { template: '<div class="v-card-text"><slot /></div>' },
  'v-card-actions': { template: '<div class="v-card-actions"><slot /></div>' },
  'v-btn': { template: '<button class="v-btn" @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
  'v-icon': { template: '<span class="v-icon"><slot /></span>' },
  'v-row': { template: '<div class="v-row"><slot /></div>' },
  'v-col': { template: '<div class="v-col"><slot /></div>' },
  'v-spacer': { template: '<div class="v-spacer"></div>' },
  'v-chip': { template: '<span class="v-chip"><slot /></span>', props: ['color', 'size', 'variant'] },
  'v-alert': { template: '<div class="v-alert"><slot /></div>', props: ['type', 'variant'] },
  'v-expansion-panels': { template: '<div class="v-expansion-panels"><slot /></div>' },
  'v-expansion-panel': { template: '<div class="v-expansion-panel"><slot /></div>' },
  'v-expansion-panel-title': { template: '<div class="v-expansion-panel-title"><slot /></div>' },
  'v-expansion-panel-text': { template: '<div class="v-expansion-panel-text"><slot /></div>' },
  'v-list': { template: '<ul class="v-list"><slot /></ul>' },
  'v-list-item': { template: '<li class="v-list-item"><slot /><slot name="prepend" /></li>' },
  'v-list-item-title': { template: '<span class="v-list-item-title"><slot /></span>' },
  'v-list-item-subtitle': { template: '<span class="v-list-item-subtitle"><slot /></span>' },
  'v-avatar': { template: '<span class="v-avatar"><slot /></span>', props: ['size', 'color', 'variant'] },
  'v-text-field': { template: '<input class="v-text-field" />', props: ['modelValue', 'label', 'type'] },
  'v-select': { template: '<select class="v-select"></select>', props: ['modelValue', 'items'] },
  'v-slider': { template: '<div class="v-slider"><slot /><slot name="append" /></div>', props: ['modelValue', 'min', 'max'] },
  'v-switch': { template: '<div class="v-switch"></div>', props: ['modelValue', 'label'] },
  'v-dialog': { template: '<div class="v-dialog"><slot /></div>', props: ['modelValue'] },
  'v-data-table': { template: '<table class="v-data-table"><slot /><slot name="top" /></table>', props: ['headers', 'items'] },
  'v-progress-linear': { template: '<div class="v-progress-linear"><slot /></div>', props: ['modelValue', 'color'] },
  'v-checkbox': { template: '<input type="checkbox" class="v-checkbox" />', props: ['modelValue'] },
  'v-textarea': { template: '<textarea class="v-textarea"></textarea>', props: ['modelValue'] },
  'v-divider': { template: '<hr class="v-divider" />' }
}

// ============================================================
// InstructionsPanel
// ============================================================
describe('InstructionsPanel', () => {
  let InstructionsPanel

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    const mod = await import('../panels/InstructionsPanel.vue')
    InstructionsPanel = mod.default
  })

  it('renders the component title', () => {
    const wrapper = shallowMount(InstructionsPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('Capacity Planning Reference Guide')
  })

  it('renders all 12 calculation steps', () => {
    const wrapper = shallowMount(InstructionsPanel, {
      global: { stubs: globalStubs }
    })

    const html = wrapper.html()
    expect(html).toContain('Working Days')
    expect(html).toContain('Bottleneck Detection')
  })

  it('renders common pitfalls section', () => {
    const wrapper = shallowMount(InstructionsPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('Common Pitfalls')
    expect(wrapper.text()).toContain('Forgetting to exclude holidays')
  })

  it('renders key formulas section', () => {
    const wrapper = shallowMount(InstructionsPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('Key Formulas')
    expect(wrapper.text()).toContain('Net Capacity')
    expect(wrapper.text()).toContain('Utilization %')
  })

  it('displays 3 expansion panels', () => {
    const wrapper = shallowMount(InstructionsPanel, {
      global: { stubs: globalStubs }
    })

    const panels = wrapper.findAll('.v-expansion-panel')
    expect(panels).toHaveLength(3)
  })
})

// ============================================================
// DashboardInputsPanel
// ============================================================
describe('DashboardInputsPanel', () => {
  let DashboardInputsPanel

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockStore.worksheets.dashboardInputs.dirty = false
    const mod = await import('../panels/DashboardInputsPanel.vue')
    DashboardInputsPanel = mod.default
  })

  it('renders the Dashboard Inputs title', () => {
    const wrapper = shallowMount(DashboardInputsPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('Dashboard Inputs')
  })

  it('does not show unsaved changes chip when not dirty', () => {
    mockStore.worksheets.dashboardInputs.dirty = false

    const wrapper = shallowMount(DashboardInputsPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).not.toContain('Unsaved changes')
  })

  it('shows unsaved changes chip when dirty', () => {
    mockStore.worksheets.dashboardInputs.dirty = true

    const wrapper = shallowMount(DashboardInputsPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('Unsaved changes')
  })

  it('renders input fields for planning parameters', () => {
    const wrapper = shallowMount(DashboardInputsPanel, {
      global: { stubs: globalStubs }
    })

    const html = wrapper.html()
    expect(html).toContain('v-text-field')
    expect(html).toContain('v-slider')
    expect(html).toContain('v-switch')
  })
})

// ============================================================
// CapacityAnalysisPanel
// ============================================================
describe('CapacityAnalysisPanel', () => {
  let CapacityAnalysisPanel

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockStore.worksheets.capacityAnalysis.data = []
    const mod = await import('../panels/CapacityAnalysisPanel.vue')
    CapacityAnalysisPanel = mod.default
  })

  it('renders the Capacity Analysis title', () => {
    const wrapper = shallowMount(CapacityAnalysisPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('capacityPlanning.analysis.title')
  })

  it('shows empty state when no analysis data', () => {
    const wrapper = shallowMount(CapacityAnalysisPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('capacityPlanning.analysis.noResultsTitle')
  })

  it('shows Run Analysis button', () => {
    const wrapper = shallowMount(CapacityAnalysisPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('capacityPlanning.analysis.runAnalysis')
  })

  it('renders summary stats when analysis data is present', () => {
    mockStore.worksheets.capacityAnalysis.data = [
      { line_code: 'SEW-1', utilization_percent: 85, is_bottleneck: false, required_hours: 100, available_hours: 120 },
      { line_code: 'SEW-2', utilization_percent: 105, is_bottleneck: true, required_hours: 130, available_hours: 120 }
    ]

    const wrapper = shallowMount(CapacityAnalysisPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('capacityPlanning.analysis.avgUtilization')
    expect(wrapper.text()).toContain('capacityPlanning.analysis.linesAnalyzed')
    expect(wrapper.text()).toContain('capacityPlanning.analysis.bottlenecks')
  })
})

// ============================================================
// ScenariosPanel
// ============================================================
describe('ScenariosPanel', () => {
  let ScenariosPanel

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockStore.worksheets.scenarios.data = []
    const mod = await import('../panels/ScenariosPanel.vue')
    ScenariosPanel = mod.default
  })

  it('renders the What-If Scenarios title', () => {
    const wrapper = shallowMount(ScenariosPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('capacityPlanning.scenarios.title')
  })

  it('shows Create Scenario button', () => {
    const wrapper = shallowMount(ScenariosPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('capacityPlanning.scenarios.createScenario')
  })

  it('shows empty state when no scenarios exist', () => {
    const wrapper = shallowMount(ScenariosPanel, {
      global: { stubs: globalStubs }
    })

    expect(wrapper.text()).toContain('capacityPlanning.scenarios.noScenariosTitle')
  })
})
