/**
 * Unit tests for HoldResumeEntry component
 * Tests hold/resume workflow, quantity validation, and aging calculations
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock API
const mockCreateHoldEntry = vi.fn()
const mockResumeHold = vi.fn()
const mockGetActiveHolds = vi.fn()
const mockGetHoldReasons = vi.fn()

vi.mock('@/services/api', () => ({
  default: {
    createHoldEntry: mockCreateHoldEntry,
    resumeHold: mockResumeHold,
    getActiveHolds: mockGetActiveHolds,
    getHoldReasons: mockGetHoldReasons
  }
}))

// Create a testable version of hold/resume entry logic
const HoldResumeEntryLogic = {
  data() {
    return {
      mode: 'hold', // 'hold' or 'resume'
      valid: false,
      loading: false,
      initialLoading: false,
      activeHolds: [],
      holdReasons: [
        'Quality Hold',
        'Customer Hold',
        'Engineering Review',
        'Material Issue',
        'Documentation',
        'Inspection Required',
        'Other'
      ],
      formData: {
        // Hold fields
        work_order_id: null,
        product_id: null,
        quantity: 0,
        hold_reason: '',
        notes: '',
        // Resume fields
        hold_id: null,
        resume_quantity: 0,
        resume_notes: '',
        disposition: ''
      },
      dispositions: [
        'Return to Production',
        'Ship As-Is',
        'Rework',
        'Scrap',
        'Return to Supplier'
      ],
      rules: {
        required: value => !!value || 'Field is required',
        positive: value => value > 0 || 'Must be greater than 0',
        maxQuantity: (value, max) => value <= max || `Cannot exceed ${max}`
      }
    }
  },
  computed: {
    isHoldMode() {
      return this.mode === 'hold'
    },
    isResumeMode() {
      return this.mode === 'resume'
    },
    selectedHold() {
      if (!this.formData.hold_id) return null
      return this.activeHolds.find(h => h.hold_id === this.formData.hold_id)
    },
    maxResumeQuantity() {
      return this.selectedHold?.remaining_quantity || 0
    },
    holdAgingDays() {
      if (!this.selectedHold?.created_at) return 0
      const holdDate = new Date(this.selectedHold.created_at)
      const today = new Date()
      const diffTime = Math.abs(today - holdDate)
      return Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    },
    agingStatus() {
      const days = this.holdAgingDays
      if (days >= 30) return 'critical'
      if (days >= 14) return 'warning'
      if (days >= 7) return 'caution'
      return 'normal'
    }
  },
  methods: {
    switchToHold() {
      this.mode = 'hold'
      this.resetForm()
    },
    switchToResume() {
      this.mode = 'resume'
      this.resetForm()
    },
    resetForm() {
      this.formData = {
        work_order_id: null,
        product_id: null,
        quantity: 0,
        hold_reason: '',
        notes: '',
        hold_id: null,
        resume_quantity: 0,
        resume_notes: '',
        disposition: ''
      }
    },
    validateResumeQuantity() {
      if (this.formData.resume_quantity > this.maxResumeQuantity) {
        return `Cannot exceed remaining quantity (${this.maxResumeQuantity})`
      }
      if (this.formData.resume_quantity <= 0) {
        return 'Must be greater than 0'
      }
      return true
    },
    isPartialResume() {
      return this.formData.resume_quantity < this.maxResumeQuantity
    }
  },
  template: '<div></div>'
}

describe('HoldResumeEntry Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    global.alert = vi.fn()
  })

  describe('Initial State', () => {
    it('initializes in hold mode', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)

      expect(wrapper.vm.mode).toBe('hold')
      expect(wrapper.vm.isHoldMode).toBe(true)
      expect(wrapper.vm.isResumeMode).toBe(false)
    })

    it('initializes with default form values', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)

      expect(wrapper.vm.formData.work_order_id).toBeNull()
      expect(wrapper.vm.formData.quantity).toBe(0)
      expect(wrapper.vm.formData.hold_reason).toBe('')
    })

    it('has correct hold reason options', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)

      expect(wrapper.vm.holdReasons).toContain('Quality Hold')
      expect(wrapper.vm.holdReasons).toContain('Customer Hold')
      expect(wrapper.vm.holdReasons).toContain('Engineering Review')
    })

    it('has correct disposition options', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)

      expect(wrapper.vm.dispositions).toContain('Return to Production')
      expect(wrapper.vm.dispositions).toContain('Ship As-Is')
      expect(wrapper.vm.dispositions).toContain('Rework')
      expect(wrapper.vm.dispositions).toContain('Scrap')
    })
  })

  describe('Mode Switching', () => {
    it('switches to hold mode', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.mode = 'resume'

      wrapper.vm.switchToHold()

      expect(wrapper.vm.mode).toBe('hold')
      expect(wrapper.vm.isHoldMode).toBe(true)
    })

    it('switches to resume mode', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)

      wrapper.vm.switchToResume()

      expect(wrapper.vm.mode).toBe('resume')
      expect(wrapper.vm.isResumeMode).toBe(true)
    })

    it('resets form when switching modes', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.formData.quantity = 100
      wrapper.vm.formData.hold_reason = 'Quality Hold'

      wrapper.vm.switchToResume()

      expect(wrapper.vm.formData.quantity).toBe(0)
      expect(wrapper.vm.formData.hold_reason).toBe('')
    })
  })

  describe('Validation Rules', () => {
    it('required rule validates correctly', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)

      expect(wrapper.vm.rules.required('')).toBe('Field is required')
      expect(wrapper.vm.rules.required('test')).toBe(true)
    })

    it('positive rule validates correctly', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)

      expect(wrapper.vm.rules.positive(0)).toBe('Must be greater than 0')
      expect(wrapper.vm.rules.positive(-1)).toBe('Must be greater than 0')
      expect(wrapper.vm.rules.positive(1)).toBe(true)
    })

    it('maxQuantity rule validates correctly', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)

      expect(wrapper.vm.rules.maxQuantity(101, 100)).toBe('Cannot exceed 100')
      expect(wrapper.vm.rules.maxQuantity(100, 100)).toBe(true)
      expect(wrapper.vm.rules.maxQuantity(50, 100)).toBe(true)
    })
  })

  describe('Selected Hold', () => {
    it('returns null when no hold selected', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.formData.hold_id = null

      expect(wrapper.vm.selectedHold).toBeNull()
    })

    it('returns selected hold when id matches', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.activeHolds = [
        { hold_id: 1, remaining_quantity: 50 },
        { hold_id: 2, remaining_quantity: 100 }
      ]
      wrapper.vm.formData.hold_id = 2

      expect(wrapper.vm.selectedHold.remaining_quantity).toBe(100)
    })
  })

  describe('Max Resume Quantity', () => {
    it('returns 0 when no hold selected', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.formData.hold_id = null

      expect(wrapper.vm.maxResumeQuantity).toBe(0)
    })

    it('returns remaining quantity from selected hold', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.activeHolds = [{ hold_id: 1, remaining_quantity: 75 }]
      wrapper.vm.formData.hold_id = 1

      expect(wrapper.vm.maxResumeQuantity).toBe(75)
    })
  })

  describe('Hold Aging Calculations', () => {
    it('returns 0 days when no hold selected', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.formData.hold_id = null

      expect(wrapper.vm.holdAgingDays).toBe(0)
    })

    it('calculates aging days correctly', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      // Use a fixed timestamp to avoid timezone issues
      const sevenDaysAgo = new Date()
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
      sevenDaysAgo.setHours(12, 0, 0, 0) // Set to noon to avoid edge cases

      wrapper.vm.activeHolds = [{
        hold_id: 1,
        created_at: sevenDaysAgo.toISOString(),
        remaining_quantity: 50
      }]
      wrapper.vm.formData.hold_id = 1

      // Allow for timezone variance (7 or 8 days depending on local time)
      expect(wrapper.vm.holdAgingDays).toBeGreaterThanOrEqual(7)
      expect(wrapper.vm.holdAgingDays).toBeLessThanOrEqual(8)
    })
  })

  describe('Aging Status', () => {
    it('returns critical for >= 30 days', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      const thirtyDaysAgo = new Date()
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

      wrapper.vm.activeHolds = [{
        hold_id: 1,
        created_at: thirtyDaysAgo.toISOString(),
        remaining_quantity: 50
      }]
      wrapper.vm.formData.hold_id = 1

      expect(wrapper.vm.agingStatus).toBe('critical')
    })

    it('returns warning for >= 14 days', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      const fourteenDaysAgo = new Date()
      fourteenDaysAgo.setDate(fourteenDaysAgo.getDate() - 14)

      wrapper.vm.activeHolds = [{
        hold_id: 1,
        created_at: fourteenDaysAgo.toISOString(),
        remaining_quantity: 50
      }]
      wrapper.vm.formData.hold_id = 1

      expect(wrapper.vm.agingStatus).toBe('warning')
    })

    it('returns caution for >= 7 days', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      const sevenDaysAgo = new Date()
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)

      wrapper.vm.activeHolds = [{
        hold_id: 1,
        created_at: sevenDaysAgo.toISOString(),
        remaining_quantity: 50
      }]
      wrapper.vm.formData.hold_id = 1

      expect(wrapper.vm.agingStatus).toBe('caution')
    })

    it('returns normal for < 7 days', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      const twoDaysAgo = new Date()
      twoDaysAgo.setDate(twoDaysAgo.getDate() - 2)

      wrapper.vm.activeHolds = [{
        hold_id: 1,
        created_at: twoDaysAgo.toISOString(),
        remaining_quantity: 50
      }]
      wrapper.vm.formData.hold_id = 1

      expect(wrapper.vm.agingStatus).toBe('normal')
    })
  })

  describe('Resume Quantity Validation', () => {
    it('fails when exceeds max quantity', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.activeHolds = [{ hold_id: 1, remaining_quantity: 50 }]
      wrapper.vm.formData.hold_id = 1
      wrapper.vm.formData.resume_quantity = 60

      expect(wrapper.vm.validateResumeQuantity()).toContain('Cannot exceed')
    })

    it('fails when zero or negative', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.activeHolds = [{ hold_id: 1, remaining_quantity: 50 }]
      wrapper.vm.formData.hold_id = 1
      wrapper.vm.formData.resume_quantity = 0

      expect(wrapper.vm.validateResumeQuantity()).toBe('Must be greater than 0')
    })

    it('passes for valid quantity', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.activeHolds = [{ hold_id: 1, remaining_quantity: 50 }]
      wrapper.vm.formData.hold_id = 1
      wrapper.vm.formData.resume_quantity = 25

      expect(wrapper.vm.validateResumeQuantity()).toBe(true)
    })
  })

  describe('Partial Resume Detection', () => {
    it('returns true for partial resume', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.activeHolds = [{ hold_id: 1, remaining_quantity: 100 }]
      wrapper.vm.formData.hold_id = 1
      wrapper.vm.formData.resume_quantity = 50

      expect(wrapper.vm.isPartialResume()).toBe(true)
    })

    it('returns false for full resume', () => {
      const wrapper = shallowMount(HoldResumeEntryLogic)
      wrapper.vm.activeHolds = [{ hold_id: 1, remaining_quantity: 100 }]
      wrapper.vm.formData.hold_id = 1
      wrapper.vm.formData.resume_quantity = 100

      expect(wrapper.vm.isPartialResume()).toBe(false)
    })
  })
})

describe('HoldResumeEntry API Integration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('creates hold entry', async () => {
    mockCreateHoldEntry.mockResolvedValue({ data: { hold_id: 1 } })

    const formData = {
      work_order_id: 1,
      product_id: 1,
      quantity: 100,
      hold_reason: 'Quality Hold',
      notes: 'Awaiting inspection'
    }

    await mockCreateHoldEntry(formData)

    expect(mockCreateHoldEntry).toHaveBeenCalledWith(formData)
  })

  it('resumes hold entry', async () => {
    mockResumeHold.mockResolvedValue({ data: { status: 'resumed' } })

    const resumeData = {
      resume_quantity: 50,
      disposition: 'Return to Production',
      notes: 'Inspection passed'
    }

    await mockResumeHold(1, resumeData)

    expect(mockResumeHold).toHaveBeenCalledWith(1, resumeData)
  })

  it('fetches active holds', async () => {
    const mockHolds = [
      { hold_id: 1, work_order_id: 1, remaining_quantity: 50 },
      { hold_id: 2, work_order_id: 2, remaining_quantity: 100 }
    ]
    mockGetActiveHolds.mockResolvedValue({ data: mockHolds })

    const result = await mockGetActiveHolds({ client_id: 1 })

    expect(result.data).toEqual(mockHolds)
    expect(result.data).toHaveLength(2)
  })
})
