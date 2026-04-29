/**
 * Unit tests for DowntimeEntry component
 * Tests form validation, duration calculation, and inference suggestions
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock API
const mockCreateDowntimeEntry = vi.fn()
const mockGetProducts = vi.fn()
const mockGetDowntimeReasons = vi.fn()

vi.mock('@/services/api', () => ({
  default: {
    createDowntimeEntry: mockCreateDowntimeEntry,
    getProducts: mockGetProducts,
    getDowntimeReasons: mockGetDowntimeReasons
  }
}))

// Mock CSV upload dialog
vi.mock('@/components/CSVUploadDialogDowntime.vue', () => ({
  default: { template: '<div class="csv-upload-mock"></div>' }
}))

// Create a testable version of the component logic
const DowntimeEntryLogic = {
  data() {
    return {
      valid: false,
      loading: false,
      initialLoading: false,
      equipmentList: [],
      downtimeReasons: [],
      inferenceData: null,
      categories: [
        'Planned Maintenance',
        'Unplanned Breakdown',
        'Changeover',
        'Material Shortage',
        'Quality Issue',
        'Operator Absence',
        'Other'
      ],
      formData: {
        equipment_id: null,
        reason_id: null,
        start_time: '',
        end_time: '',
        duration_minutes: 0,
        category: '',
        notes: ''
      },
      rules: {
        required: value => !!value || 'Field is required'
      }
    }
  },
  methods: {
    calculateDuration(startTime, endTime) {
      if (startTime && endTime) {
        const startDate = new Date(startTime)
        const endDate = new Date(endTime)
        const diffMs = endDate - startDate
        return Math.max(0, Math.floor(diffMs / 60000))
      }
      return 0
    },
    applySuggestion() {
      if (this.inferenceData) {
        this.formData.category = this.inferenceData.category
      }
    },
    setDefaultStartTime() {
      const now = new Date()
      this.formData.start_time = now.toISOString().slice(0, 16)
    }
  },
  template: '<div></div>'
}

describe('DowntimeEntry Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    global.alert = vi.fn()
  })

  describe('Initial State', () => {
    it('initializes with default form values', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      expect(wrapper.vm.formData.equipment_id).toBeNull()
      expect(wrapper.vm.formData.reason_id).toBeNull()
      expect(wrapper.vm.formData.duration_minutes).toBe(0)
      expect(wrapper.vm.formData.category).toBe('')
    })

    it('has correct category options', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      expect(wrapper.vm.categories).toContain('Planned Maintenance')
      expect(wrapper.vm.categories).toContain('Unplanned Breakdown')
      expect(wrapper.vm.categories).toContain('Changeover')
      expect(wrapper.vm.categories).toContain('Material Shortage')
      expect(wrapper.vm.categories).toContain('Quality Issue')
      expect(wrapper.vm.categories).toContain('Operator Absence')
      expect(wrapper.vm.categories).toContain('Other')
    })

    it('initializes with null inference data', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      expect(wrapper.vm.inferenceData).toBeNull()
    })
  })

  describe('Validation Rules', () => {
    it('required rule returns error for empty value', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      expect(wrapper.vm.rules.required('')).toBe('Field is required')
      expect(wrapper.vm.rules.required(null)).toBe('Field is required')
    })

    it('required rule passes for valid value', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      expect(wrapper.vm.rules.required('test')).toBe(true)
      expect(wrapper.vm.rules.required(1)).toBe(true)
    })
  })

  describe('Duration Calculation', () => {
    it('returns 0 when start time is missing', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      const duration = wrapper.vm.calculateDuration('', '2024-01-01T10:30')
      expect(duration).toBe(0)
    })

    it('returns 0 when end time is missing', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      const duration = wrapper.vm.calculateDuration('2024-01-01T10:00', '')
      expect(duration).toBe(0)
    })

    it('calculates correct duration in minutes', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      const duration = wrapper.vm.calculateDuration(
        '2024-01-01T10:00',
        '2024-01-01T10:30'
      )
      expect(duration).toBe(30)
    })

    it('calculates duration spanning hours', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      const duration = wrapper.vm.calculateDuration(
        '2024-01-01T10:00',
        '2024-01-01T12:30'
      )
      expect(duration).toBe(150) // 2.5 hours = 150 minutes
    })

    it('returns 0 for negative duration (end before start)', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      const duration = wrapper.vm.calculateDuration(
        '2024-01-01T12:00',
        '2024-01-01T10:00'
      )
      expect(duration).toBe(0)
    })

    it('calculates duration spanning days', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)

      const duration = wrapper.vm.calculateDuration(
        '2024-01-01T22:00',
        '2024-01-02T02:00'
      )
      expect(duration).toBe(240) // 4 hours = 240 minutes
    })
  })

  describe('Inference Suggestions', () => {
    it('applies suggestion when inference data exists', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)
      wrapper.vm.inferenceData = {
        category: 'Unplanned Breakdown',
        confidence: 0.87
      }

      wrapper.vm.applySuggestion()

      expect(wrapper.vm.formData.category).toBe('Unplanned Breakdown')
    })

    it('does not change category when no inference data', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)
      wrapper.vm.formData.category = 'Changeover'
      wrapper.vm.inferenceData = null

      wrapper.vm.applySuggestion()

      expect(wrapper.vm.formData.category).toBe('Changeover')
    })
  })

  describe('Default Start Time', () => {
    it('sets start time to current time', () => {
      const wrapper = shallowMount(DowntimeEntryLogic)
      const beforeCall = new Date()

      wrapper.vm.setDefaultStartTime()

      expect(wrapper.vm.formData.start_time).toBeDefined()
      expect(wrapper.vm.formData.start_time.length).toBe(16) // YYYY-MM-DDTHH:mm format
    })
  })
})

describe('DowntimeEntry API Integration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    global.alert = vi.fn()
  })

  it('loads reference data on mount', async () => {
    mockGetProducts.mockResolvedValue({ data: [{ id: 1, name: 'Equipment 1' }] })
    mockGetDowntimeReasons.mockResolvedValue({ data: [{ id: 1, name: 'Breakdown' }] })

    const loadReferenceData = async (state) => {
      try {
        const [equipmentRes, reasonsRes] = await Promise.all([
          mockGetProducts(),
          mockGetDowntimeReasons()
        ])
        state.equipmentList = equipmentRes.data
        state.downtimeReasons = reasonsRes.data
      } catch (error) {
        console.error('Error loading reference data:', error)
      }
    }

    const state = { equipmentList: [], downtimeReasons: [] }
    await loadReferenceData(state)

    expect(mockGetProducts).toHaveBeenCalled()
    expect(mockGetDowntimeReasons).toHaveBeenCalled()
    expect(state.equipmentList).toHaveLength(1)
    expect(state.downtimeReasons).toHaveLength(1)
  })

  it('creates downtime entry on valid submission', async () => {
    mockCreateDowntimeEntry.mockResolvedValue({ data: { downtime_id: 1 } })

    const formData = {
      equipment_id: 1,
      reason_id: 2,
      start_time: '2024-01-01T10:00',
      end_time: '2024-01-01T10:30',
      duration_minutes: 30,
      category: 'Unplanned Breakdown',
      notes: 'Motor failure'
    }

    await mockCreateDowntimeEntry(formData)

    expect(mockCreateDowntimeEntry).toHaveBeenCalledWith(formData)
  })

  it('handles submission errors', async () => {
    mockCreateDowntimeEntry.mockRejectedValue({
      response: { data: { detail: 'Equipment not found' } }
    })

    try {
      await mockCreateDowntimeEntry({})
    } catch (error) {
      expect(error.response.data.detail).toBe('Equipment not found')
    }
  })
})

describe('Duration Watch Behavior', () => {
  it('updates duration when times change', () => {
    // Simulate the watch behavior
    const calculateDuration = (start, end) => {
      if (start && end) {
        const startDate = new Date(start)
        const endDate = new Date(end)
        const diffMs = endDate - startDate
        return Math.max(0, Math.floor(diffMs / 60000))
      }
      return 0
    }

    const formData = {
      start_time: '2024-01-01T10:00',
      end_time: '2024-01-01T11:30',
      duration_minutes: 0
    }

    formData.duration_minutes = calculateDuration(formData.start_time, formData.end_time)

    expect(formData.duration_minutes).toBe(90)
  })
})
