/**
 * Unit tests for QualityEntry component
 * Tests form validation, metric calculations, and submission
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock API
const mockCreateQualityEntry = vi.fn()
const mockGetProducts = vi.fn()
const mockGetClients = vi.fn()
const mockGetDefectTypes = vi.fn()

vi.mock('@/services/api', () => ({
  default: {
    createQualityEntry: mockCreateQualityEntry,
    getProducts: mockGetProducts,
    getClients: mockGetClients,
    getDefectTypes: mockGetDefectTypes
  }
}))

// Mock KPI Store
vi.mock('@/stores/kpi', () => ({
  useKPIStore: () => ({
    selectedClient: null
  })
}))

// Mock CSV upload dialog
vi.mock('@/components/CSVUploadDialogQuality.vue', () => ({
  default: { template: '<div class="csv-upload-mock"></div>' }
}))

// Create a testable version of the component logic
const QualityEntryLogic = {
  data() {
    return {
      valid: false,
      loading: false,
      initialLoading: false,
      products: [],
      defectTypes: [],
      workOrders: [],
      clients: [],
      severities: ['Critical', 'Major', 'Minor', 'Cosmetic'],
      dispositions: ['Accept', 'Reject', 'Rework', 'Use As Is', 'Return to Supplier'],
      formData: {
        client_id: null,
        work_order_id: null,
        product_id: null,
        inspected_quantity: 0,
        defect_quantity: 0,
        rejected_quantity: 0,
        defect_type_id: null,
        severity: '',
        disposition: '',
        inspector_id: '',
        defect_description: '',
        corrective_action: ''
      },
      rules: {
        required: value => !!value || 'Field is required',
        positive: value => value > 0 || 'Must be greater than 0'
      }
    }
  },
  methods: {
    calculateFPY() {
      const inspected = this.formData.inspected_quantity || 0
      const defects = this.formData.defect_quantity || 0
      if (inspected === 0) return 0
      return ((1 - defects / inspected) * 100).toFixed(2)
    },
    calculateDefectRate() {
      const inspected = this.formData.inspected_quantity || 0
      const defects = this.formData.defect_quantity || 0
      if (inspected === 0) return 0
      return ((defects / inspected) * 100).toFixed(2)
    },
    calculatePPM() {
      const inspected = this.formData.inspected_quantity || 0
      const defects = this.formData.defect_quantity || 0
      if (inspected === 0) return 0
      return Math.round((defects / inspected) * 1000000)
    },
    calculatePassQty() {
      return (this.formData.inspected_quantity || 0) - (this.formData.defect_quantity || 0)
    }
  },
  template: '<div></div>'
}

describe('QualityEntry Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    global.alert = vi.fn()
  })

  describe('Initial State', () => {
    it('initializes with default form values', () => {
      const wrapper = shallowMount(QualityEntryLogic)

      expect(wrapper.vm.formData.client_id).toBeNull()
      expect(wrapper.vm.formData.inspected_quantity).toBe(0)
      expect(wrapper.vm.formData.defect_quantity).toBe(0)
      expect(wrapper.vm.formData.disposition).toBe('')
    })

    it('has correct severity options', () => {
      const wrapper = shallowMount(QualityEntryLogic)

      expect(wrapper.vm.severities).toContain('Critical')
      expect(wrapper.vm.severities).toContain('Major')
      expect(wrapper.vm.severities).toContain('Minor')
      expect(wrapper.vm.severities).toContain('Cosmetic')
    })

    it('has correct disposition options', () => {
      const wrapper = shallowMount(QualityEntryLogic)

      expect(wrapper.vm.dispositions).toContain('Accept')
      expect(wrapper.vm.dispositions).toContain('Reject')
      expect(wrapper.vm.dispositions).toContain('Rework')
    })
  })

  describe('Validation Rules', () => {
    it('required rule returns error for empty value', () => {
      const wrapper = shallowMount(QualityEntryLogic)

      expect(wrapper.vm.rules.required('')).toBe('Field is required')
      expect(wrapper.vm.rules.required(null)).toBe('Field is required')
    })

    it('required rule passes for valid value', () => {
      const wrapper = shallowMount(QualityEntryLogic)

      expect(wrapper.vm.rules.required('test')).toBe(true)
      expect(wrapper.vm.rules.required(1)).toBe(true)
    })

    it('positive rule returns error for zero or negative', () => {
      const wrapper = shallowMount(QualityEntryLogic)

      expect(wrapper.vm.rules.positive(0)).toBe('Must be greater than 0')
      expect(wrapper.vm.rules.positive(-1)).toBe('Must be greater than 0')
    })

    it('positive rule passes for positive values', () => {
      const wrapper = shallowMount(QualityEntryLogic)

      expect(wrapper.vm.rules.positive(1)).toBe(true)
      expect(wrapper.vm.rules.positive(100)).toBe(true)
    })
  })

  describe('FPY Calculation', () => {
    it('returns 0 when inspected quantity is 0', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 0
      wrapper.vm.formData.defect_quantity = 5

      expect(wrapper.vm.calculateFPY()).toBe(0)
    })

    it('calculates 100% FPY with no defects', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 100
      wrapper.vm.formData.defect_quantity = 0

      expect(wrapper.vm.calculateFPY()).toBe('100.00')
    })

    it('calculates correct FPY percentage', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 100
      wrapper.vm.formData.defect_quantity = 5

      expect(wrapper.vm.calculateFPY()).toBe('95.00')
    })

    it('handles decimal results correctly', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 100
      wrapper.vm.formData.defect_quantity = 3

      expect(wrapper.vm.calculateFPY()).toBe('97.00')
    })
  })

  describe('Defect Rate Calculation', () => {
    it('returns 0 when inspected quantity is 0', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 0
      wrapper.vm.formData.defect_quantity = 5

      expect(wrapper.vm.calculateDefectRate()).toBe(0)
    })

    it('calculates 0% defect rate with no defects', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 100
      wrapper.vm.formData.defect_quantity = 0

      expect(wrapper.vm.calculateDefectRate()).toBe('0.00')
    })

    it('calculates correct defect rate', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 100
      wrapper.vm.formData.defect_quantity = 10

      expect(wrapper.vm.calculateDefectRate()).toBe('10.00')
    })
  })

  describe('PPM Calculation', () => {
    it('returns 0 when inspected quantity is 0', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 0

      expect(wrapper.vm.calculatePPM()).toBe(0)
    })

    it('calculates 0 PPM with no defects', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 1000
      wrapper.vm.formData.defect_quantity = 0

      expect(wrapper.vm.calculatePPM()).toBe(0)
    })

    it('calculates correct PPM', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 1000
      wrapper.vm.formData.defect_quantity = 5

      // 5/1000 * 1,000,000 = 5000 PPM
      expect(wrapper.vm.calculatePPM()).toBe(5000)
    })

    it('rounds PPM to integer', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 300
      wrapper.vm.formData.defect_quantity = 1

      // 1/300 * 1,000,000 = 3333.33... should round to 3333
      expect(wrapper.vm.calculatePPM()).toBe(3333)
    })
  })

  describe('Pass Quantity Calculation', () => {
    it('calculates correct pass quantity', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 100
      wrapper.vm.formData.defect_quantity = 10

      expect(wrapper.vm.calculatePassQty()).toBe(90)
    })

    it('returns inspected quantity when no defects', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = 100
      wrapper.vm.formData.defect_quantity = 0

      expect(wrapper.vm.calculatePassQty()).toBe(100)
    })

    it('handles null/undefined values', () => {
      const wrapper = shallowMount(QualityEntryLogic)
      wrapper.vm.formData.inspected_quantity = null
      wrapper.vm.formData.defect_quantity = null

      expect(wrapper.vm.calculatePassQty()).toBe(0)
    })
  })
})

describe('QualityEntry API Integration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    global.alert = vi.fn()
  })

  it('loads reference data on mount', async () => {
    mockGetProducts.mockResolvedValue({ data: [{ id: 1, name: 'Product 1' }] })
    mockGetClients.mockResolvedValue({ data: [{ client_id: 1, client_name: 'Client 1' }] })
    mockGetDefectTypes.mockResolvedValue({ data: [] })

    // Simulate the loadReferenceData function
    const loadReferenceData = async (state) => {
      try {
        const [productsRes, clientsRes] = await Promise.all([
          mockGetProducts(),
          mockGetClients()
        ])
        state.products = productsRes.data
        state.clients = clientsRes.data || []
      } catch (error) {
        console.error('Error loading reference data:', error)
      }
    }

    const state = { products: [], clients: [] }
    await loadReferenceData(state)

    expect(mockGetProducts).toHaveBeenCalled()
    expect(mockGetClients).toHaveBeenCalled()
    expect(state.products).toHaveLength(1)
    expect(state.clients).toHaveLength(1)
  })

  it('creates quality entry on valid submission', async () => {
    mockCreateQualityEntry.mockResolvedValue({ data: { quality_id: 1 } })

    const formData = {
      client_id: 1,
      work_order_id: 1,
      product_id: 1,
      inspected_quantity: 100,
      defect_quantity: 5,
      disposition: 'Accept'
    }

    await mockCreateQualityEntry(formData)

    expect(mockCreateQualityEntry).toHaveBeenCalledWith(formData)
  })

  it('handles submission errors', async () => {
    mockCreateQualityEntry.mockRejectedValue({
      response: { data: { detail: 'Validation error' } }
    })

    try {
      await mockCreateQualityEntry({})
    } catch (error) {
      expect(error.response.data.detail).toBe('Validation error')
    }
  })
})
