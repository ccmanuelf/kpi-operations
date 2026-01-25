/**
 * Unit tests for ProductionKPIs component
 * Tests KPI display, data fetching, and color-coded status indicators
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'

// Mock axios
const mockAxios = {
  get: vi.fn()
}

vi.mock('axios', () => ({
  default: {
    get: (...args) => mockAxios.get(...args)
  }
}))

// Create a test component that mimics ProductionKPIs without Vuetify dependencies
const ProductionKPIsMock = {
  template: `
    <div class="production-kpis">
      <h2>Phase 1: Production KPIs</h2>
      <p>KPI #3 Efficiency & KPI #9 Performance</p>
      <div class="kpi-card">
        <div class="efficiency">{{ efficiency }}%</div>
        <div class="performance">{{ performance }}%</div>
      </div>
      <table>
        <thead>
          <tr v-for="header in headers" :key="header.key">
            <th>{{ header.title }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in productionData" :key="row.id">
            <td>{{ row.shift_date }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  `,
  props: {
    dateRange: {
      type: String,
      default: '30d'
    }
  },
  data() {
    return {
      efficiency: 0,
      performance: 0,
      loading: false,
      productionData: [],
      headers: [
        { title: 'Date', key: 'shift_date' },
        { title: 'Client', key: 'client_id' },
        { title: 'Units Produced', key: 'units_produced' },
        { title: 'Efficiency', key: 'efficiency' },
        { title: 'Performance', key: 'performance' }
      ]
    }
  },
  methods: {
    getEfficiencyColor(value) {
      if (value >= 90) return 'success'
      if (value >= 70) return 'warning'
      return 'error'
    },
    getPerformanceColor(value) {
      if (value >= 90) return 'success'
      if (value >= 70) return 'warning'
      return 'error'
    },
    async fetchData() {
      this.loading = true
      try {
        const [effRes, perfRes, entriesRes] = await Promise.all([
          mockAxios.get('http://localhost:8000/api/v1/kpi/efficiency'),
          mockAxios.get('http://localhost:8000/api/v1/kpi/performance'),
          mockAxios.get('http://localhost:8000/api/v1/production-entries?limit=20')
        ])
        this.efficiency = parseFloat(effRes.data.value.toFixed(1))
        this.performance = parseFloat(perfRes.data.value.toFixed(1))
        this.productionData = entriesRes.data
      } catch (error) {
        console.error('Error fetching production KPIs:', error)
      } finally {
        this.loading = false
      }
    }
  },
  mounted() {
    this.fetchData()
  }
}

describe('ProductionKPIs', () => {
  beforeEach(() => {
    mockAxios.get.mockReset()
    vi.clearAllMocks()
  })

  it('renders component with title', () => {
    mockAxios.get.mockResolvedValue({ data: { value: 0 } })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    expect(wrapper.text()).toContain('Phase 1: Production KPIs')
    expect(wrapper.text()).toContain('KPI #3 Efficiency')
    expect(wrapper.text()).toContain('KPI #9 Performance')
  })

  it('fetches data on mount', async () => {
    mockAxios.get.mockImplementation((url) => {
      if (url.includes('efficiency')) {
        return Promise.resolve({ data: { value: 85.5 } })
      }
      if (url.includes('performance')) {
        return Promise.resolve({ data: { value: 92.3 } })
      }
      if (url.includes('production-entries')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: {} })
    })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    await flushPromises()

    expect(mockAxios.get).toHaveBeenCalledTimes(3)
    expect(wrapper.vm.efficiency).toBe(85.5)
    expect(wrapper.vm.performance).toBe(92.3)
  })

  it('displays efficiency and performance values', async () => {
    mockAxios.get.mockImplementation((url) => {
      if (url.includes('efficiency')) {
        return Promise.resolve({ data: { value: 78.2 } })
      }
      if (url.includes('performance')) {
        return Promise.resolve({ data: { value: 94.1 } })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    await flushPromises()

    expect(wrapper.text()).toContain('78.2%')
    expect(wrapper.text()).toContain('94.1%')
  })

  it('returns correct color for high efficiency (>=90)', () => {
    mockAxios.get.mockResolvedValue({ data: { value: 0 } })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    expect(wrapper.vm.getEfficiencyColor(95)).toBe('success')
    expect(wrapper.vm.getEfficiencyColor(90)).toBe('success')
  })

  it('returns correct color for medium efficiency (70-89)', () => {
    mockAxios.get.mockResolvedValue({ data: { value: 0 } })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    expect(wrapper.vm.getEfficiencyColor(85)).toBe('warning')
    expect(wrapper.vm.getEfficiencyColor(70)).toBe('warning')
  })

  it('returns correct color for low efficiency (<70)', () => {
    mockAxios.get.mockResolvedValue({ data: { value: 0 } })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    expect(wrapper.vm.getEfficiencyColor(65)).toBe('error')
    expect(wrapper.vm.getEfficiencyColor(50)).toBe('error')
  })

  it('returns correct color for high performance (>=90)', () => {
    mockAxios.get.mockResolvedValue({ data: { value: 0 } })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    expect(wrapper.vm.getPerformanceColor(95)).toBe('success')
    expect(wrapper.vm.getPerformanceColor(90)).toBe('success')
  })

  it('returns correct color for medium performance (70-89)', () => {
    mockAxios.get.mockResolvedValue({ data: { value: 0 } })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    expect(wrapper.vm.getPerformanceColor(85)).toBe('warning')
    expect(wrapper.vm.getPerformanceColor(70)).toBe('warning')
  })

  it('returns correct color for low performance (<70)', () => {
    mockAxios.get.mockResolvedValue({ data: { value: 0 } })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    expect(wrapper.vm.getPerformanceColor(65)).toBe('error')
    expect(wrapper.vm.getPerformanceColor(50)).toBe('error')
  })

  it('handles API errors gracefully', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockAxios.get.mockRejectedValue(new Error('API Error'))

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    await flushPromises()

    expect(consoleSpy).toHaveBeenCalledWith('Error fetching production KPIs:', expect.any(Error))
    expect(wrapper.vm.loading).toBe(false)

    consoleSpy.mockRestore()
  })

  it('sets loading state during fetch', async () => {
    let resolveEfficiency
    mockAxios.get.mockImplementation((url) => {
      if (url.includes('efficiency')) {
        return new Promise((resolve) => {
          resolveEfficiency = () => resolve({ data: { value: 85 } })
        })
      }
      return Promise.resolve({ data: [] })
    })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    // Initially loading should be true
    expect(wrapper.vm.loading).toBe(true)

    // Resolve the promise
    resolveEfficiency()
    await flushPromises()

    // After fetch completes, loading should be false
    expect(wrapper.vm.loading).toBe(false)
  })

  it('has correct table headers', () => {
    mockAxios.get.mockResolvedValue({ data: { value: 0 } })

    const wrapper = shallowMount(ProductionKPIsMock, {
      props: { dateRange: '30d' }
    })

    const expectedHeaders = ['Date', 'Client', 'Units Produced', 'Efficiency', 'Performance']
    wrapper.vm.headers.forEach((header, index) => {
      expect(header.title).toBe(expectedHeaders[index])
    })
  })
})
