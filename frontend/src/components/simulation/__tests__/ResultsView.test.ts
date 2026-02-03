/**
 * Unit tests for ResultsView component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ResultsView from '../ResultsView.vue'

// Mock date-fns
vi.mock('date-fns', () => ({
  format: vi.fn((date, formatStr) => '2025-01-15 10:30:00')
}))

// Create mock results object
const createMockResults = (overrides = {}) => ({
  daily_summary: {
    daily_throughput_pcs: 950,
    daily_demand_pcs: 1000,
    daily_coverage_pct: 95,
    total_shifts_per_day: 2,
    daily_planned_hours: 16,
    bundles_processed_per_day: 95,
    bundle_size_pcs: 10,
    avg_cycle_time_min: 15.5,
    avg_wip_pcs: 25
  },
  free_capacity: {
    daily_max_capacity_pcs: 1200,
    demand_usage_pct: 83.3,
    free_line_hours_per_day: 2.5,
    equivalent_free_operators_full_shift: 1.5
  },
  station_performance: [
    { product: 'TSHIRT_A', step: 1, operation: 'Cut fabric', machine_tool: 'Cutting Table', operators: 2, util_pct: 96, queue_wait_time_min: 2.5, is_bottleneck: true, is_donor: false },
    { product: 'TSHIRT_A', step: 2, operation: 'Sew seams', machine_tool: 'Sewing Machine', operators: 3, util_pct: 65, queue_wait_time_min: 0.5, is_bottleneck: false, is_donor: true }
  ],
  weekly_demand_capacity: [
    { product: 'TSHIRT_A', weekly_demand_pcs: 5000, max_weekly_capacity_pcs: 4750, demand_coverage_pct: 95, status: 'Tight' }
  ],
  per_product_summary: [
    { product: 'TSHIRT_A', bundle_size_pcs: 10, mix_share_pct: 100, daily_demand_pcs: 1000, daily_throughput_pcs: 950, daily_coverage_pct: 95, weekly_demand_pcs: 5000, weekly_throughput_pcs: 4750 }
  ],
  bundle_metrics: [
    { product: 'TSHIRT_A', bundle_size_pcs: 10, bundles_arriving_per_day: 100, avg_bundles_in_system: 5, max_bundles_in_system: 12, avg_bundle_cycle_time_min: 45 }
  ],
  rebalancing_suggestions: [
    { product: 'TSHIRT_A', step: 1, operation: 'Cut fabric', machine_tool: 'Cutting Table', operators_before: 2, operators_after: 3, util_before_pct: 96, util_after_pct: 64, role: 'Bottleneck', comment: 'Add 1 operator' }
  ],
  assumption_log: {
    simulation_engine_version: '2.0.0',
    configuration_mode: 'demand-driven',
    timestamp: '2025-01-15T10:30:00Z',
    formula_implementations: {
      'processing_time': 'SAM × (1 + Variability + FPD/100 + (100-Grade)/100)'
    },
    limitations_and_caveats: [
      'Setup times not modeled',
      'Assumes infinite raw materials'
    ]
  },
  simulation_duration_seconds: 1.25,
  ...overrides
})

describe('ResultsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mountComponent = (props = {}) => {
    return mount(ResultsView, {
      props: {
        modelValue: true,
        results: createMockResults(),
        ...props
      },
      global: {
        stubs: {
          'v-dialog': {
            template: '<div class="v-dialog" v-if="modelValue"><slot /></div>',
            props: ['modelValue', 'fullscreen', 'scrim', 'transition']
          },
          'v-card': { template: '<div class="v-card"><slot /></div>' },
          'v-toolbar': { template: '<div class="v-toolbar"><slot /></div>', props: ['dark', 'color'] },
          'v-toolbar-title': { template: '<span class="v-toolbar-title"><slot /></span>' },
          'v-toolbar-items': { template: '<div class="v-toolbar-items"><slot /></div>' },
          'v-btn': {
            template: '<button class="v-btn" @click="$emit(\'click\')"><slot /></button>',
            emits: ['click'],
            props: ['icon', 'variant']
          },
          'v-icon': { template: '<span class="v-icon"><slot /></span>' },
          'v-spacer': { template: '<div class="v-spacer" />' },
          'v-container': { template: '<div class="v-container"><slot /></div>', props: ['fluid'] },
          'v-row': { template: '<div class="v-row"><slot /></div>' },
          'v-col': { template: '<div class="v-col"><slot /></div>', props: ['cols', 'md'] },
          'v-alert': { template: '<div class="v-alert"><slot /></div>', props: ['type', 'variant'] },
          'v-tabs': { template: '<div class="v-tabs"><slot /></div>', props: ['modelValue', 'bgColor'] },
          'v-tab': { template: '<button class="v-tab"><slot /></button>', props: ['value'] },
          'v-window': { template: '<div class="v-window"><slot /></div>', props: ['modelValue'] },
          'v-window-item': { template: '<div class="v-window-item"><slot /></div>', props: ['value'] },
          'v-list': { template: '<ul class="v-list"><slot /></ul>', props: ['density'] },
          'v-list-item': { template: '<li class="v-list-item"><slot /></li>' },
          'v-list-item-title': { template: '<div class="v-list-item-title"><slot /></div>' },
          'v-list-item-subtitle': { template: '<div class="v-list-item-subtitle"><slot /></div>' },
          'v-chip': { template: '<span class="v-chip"><slot /></span>', props: ['color', 'variant', 'size'] },
          'v-data-table': { template: '<div class="v-data-table"><slot /></div>', props: ['headers', 'items', 'density', 'sortBy'] },
          'v-progress-linear': { template: '<div class="v-progress-linear"><slot /></div>', props: ['modelValue', 'color', 'height', 'rounded'] },
          'v-divider': { template: '<hr class="v-divider" />' },
          'v-card-title': { template: '<div class="v-card-title"><slot /></div>' },
          'v-card-text': { template: '<div class="v-card-text"><slot /></div>' }
        }
      }
    })
  }

  describe('Rendering', () => {
    it('should render the component when modelValue is true', () => {
      const wrapper = mountComponent()
      expect(wrapper.find('.v-dialog').exists()).toBe(true)
    })

    it('should not render when modelValue is false', () => {
      const wrapper = mountComponent({ modelValue: false })
      expect(wrapper.find('.v-dialog').exists()).toBe(false)
    })

    it('should display Simulation Results title', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Simulation Results')
    })

    it('should display Export to Excel button', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Export to Excel')
    })
  })

  describe('Summary Alert', () => {
    it('should display daily coverage percentage', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('95%')
    })

    it('should display throughput vs demand', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('950 pieces/day')
      expect(wrapper.text()).toContain('1000 demand')
    })

    it('should show success message when coverage >= 100%', () => {
      const results = createMockResults({
        daily_summary: { ...createMockResults().daily_summary, daily_coverage_pct: 105 }
      })
      const wrapper = mountComponent({ results })
      expect(wrapper.vm.summaryText).toBe('Demand can be fully met')
    })

    it('should show warning message when coverage >= 90% but < 100%', () => {
      const results = createMockResults({
        daily_summary: { ...createMockResults().daily_summary, daily_coverage_pct: 95 }
      })
      const wrapper = mountComponent({ results })
      expect(wrapper.vm.summaryText).toBe('Slight shortfall expected')
    })

    it('should show error message when coverage < 90%', () => {
      const results = createMockResults({
        daily_summary: { ...createMockResults().daily_summary, daily_coverage_pct: 80 }
      })
      const wrapper = mountComponent({ results })
      expect(wrapper.vm.summaryText).toBe('Significant shortfall - action needed')
    })
  })

  describe('Tabs', () => {
    it('should render Summary tab', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Summary')
    })

    it('should render Weekly Capacity tab', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Weekly Capacity')
    })

    it('should render Station Performance tab', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Station Performance')
    })

    it('should render Per Product tab', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Per Product')
    })

    it('should render Bundle Metrics tab', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Bundle Metrics')
    })

    it('should render Rebalancing tab', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Rebalancing')
    })

    it('should render Assumptions tab', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Assumptions')
    })
  })

  describe('Daily Summary', () => {
    it('should display shifts and hours information', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('2 shifts')
      expect(wrapper.text()).toContain('16h/day')
    })

    it('should display bundles processed per day', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('95 bundles/day')
    })

    it('should display average cycle time', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Avg cycle time')
      expect(wrapper.text()).toContain('15.5 min')
    })

    it('should display average WIP', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Avg WIP')
      expect(wrapper.text()).toContain('25 pieces')
    })
  })

  describe('Free Capacity', () => {
    it('should display max capacity', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Max capacity')
      expect(wrapper.text()).toContain('1200 pcs/day')
    })

    it('should display demand usage percentage', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Usage')
      expect(wrapper.text()).toContain('83.3%')
    })

    it('should display free line hours', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Free line hours')
      expect(wrapper.text()).toContain('2.5h/day')
    })
  })

  describe('Bottlenecks and Donors', () => {
    it('should identify bottleneck stations', () => {
      const wrapper = mountComponent()
      const bottlenecks = wrapper.vm.bottlenecks
      expect(bottlenecks.length).toBe(1)
      expect(bottlenecks[0].operation).toBe('Cut fabric')
    })

    it('should identify donor stations', () => {
      const wrapper = mountComponent()
      const donors = wrapper.vm.donors
      expect(donors.length).toBe(1)
      expect(donors[0].operation).toBe('Sew seams')
    })

    it('should display "No bottlenecks detected" when none exist', () => {
      const results = createMockResults({
        station_performance: [
          { ...createMockResults().station_performance[0], is_bottleneck: false }
        ]
      })
      const wrapper = mountComponent({ results })
      expect(wrapper.text()).toContain('No bottlenecks detected')
    })
  })

  describe('Helper Functions', () => {
    it('should return correct status color for OK', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.getStatusColor('OK')).toBe('success')
    })

    it('should return correct status color for Tight', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.getStatusColor('Tight')).toBe('warning')
    })

    it('should return correct status color for Shortfall', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.getStatusColor('Shortfall')).toBe('error')
    })

    it('should return correct utilization color for high utilization', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.getUtilColor(96)).toBe('error')
    })

    it('should return correct utilization color for medium utilization', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.getUtilColor(85)).toBe('warning')
    })

    it('should return correct utilization color for normal utilization', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.getUtilColor(70)).toBe('success')
    })

    it('should return correct utilization color for low utilization', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.getUtilColor(45)).toBe('info')
    })

    it('should return correct coverage color for full coverage', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.getCoverageColor(100)).toBe('success')
    })

    it('should return correct coverage color for near-full coverage', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.getCoverageColor(95)).toBe('warning')
    })

    it('should return correct coverage color for low coverage', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.getCoverageColor(80)).toBe('error')
    })
  })

  describe('Simulation Duration', () => {
    it('should display simulation duration', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('1.25 seconds')
    })
  })

  describe('Table Headers', () => {
    it('should define weekly capacity headers', () => {
      const wrapper = mountComponent()
      const headers = wrapper.vm.weeklyHeaders
      expect(headers.some((h: { key: string }) => h.key === 'product')).toBe(true)
      expect(headers.some((h: { key: string }) => h.key === 'weekly_demand_pcs')).toBe(true)
      expect(headers.some((h: { key: string }) => h.key === 'status')).toBe(true)
    })

    it('should define station performance headers', () => {
      const wrapper = mountComponent()
      const headers = wrapper.vm.stationHeaders
      expect(headers.some((h: { key: string }) => h.key === 'operation')).toBe(true)
      expect(headers.some((h: { key: string }) => h.key === 'util_pct')).toBe(true)
      expect(headers.some((h: { key: string }) => h.key === 'is_bottleneck')).toBe(true)
    })

    it('should define product summary headers', () => {
      const wrapper = mountComponent()
      const headers = wrapper.vm.productHeaders
      expect(headers.some((h: { key: string }) => h.key === 'daily_demand_pcs')).toBe(true)
      expect(headers.some((h: { key: string }) => h.key === 'daily_throughput_pcs')).toBe(true)
    })

    it('should define bundle metrics headers', () => {
      const wrapper = mountComponent()
      const headers = wrapper.vm.bundleHeaders
      expect(headers.some((h: { key: string }) => h.key === 'bundle_size_pcs')).toBe(true)
      expect(headers.some((h: { key: string }) => h.key === 'avg_bundle_cycle_time_min')).toBe(true)
    })

    it('should define rebalancing headers', () => {
      const wrapper = mountComponent()
      const headers = wrapper.vm.rebalanceHeaders
      expect(headers.some((h: { key: string }) => h.key === 'operators_before')).toBe(true)
      expect(headers.some((h: { key: string }) => h.key === 'operators_after')).toBe(true)
      expect(headers.some((h: { key: string }) => h.key === 'role')).toBe(true)
    })
  })

  describe('Dialog Controls', () => {
    it('should emit update:modelValue when close is called', async () => {
      const wrapper = mountComponent()
      wrapper.vm.close()
      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')![0]).toEqual([false])
    })

    it('should have summary as default active tab', () => {
      const wrapper = mountComponent()
      expect(wrapper.vm.activeTab).toBe('summary')
    })
  })

  describe('Rebalancing Suggestions', () => {
    it('should show success alert when no rebalancing needed', () => {
      const results = createMockResults({
        rebalancing_suggestions: []
      })
      const wrapper = mountComponent({ results })
      expect(wrapper.text()).toContain('No rebalancing needed')
      expect(wrapper.text()).toContain('line is well balanced')
    })
  })
})
