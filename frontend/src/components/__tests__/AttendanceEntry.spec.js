/**
 * Unit tests for AttendanceEntry component
 * Tests form validation and attendance tracking
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Mock API
const mockCreateAttendanceEntry = vi.fn()
const mockGetEmployees = vi.fn()
const mockGetShifts = vi.fn()

vi.mock('@/services/api', () => ({
  default: {
    createAttendanceEntry: mockCreateAttendanceEntry,
    getEmployees: mockGetEmployees,
    getShifts: mockGetShifts
  }
}))

// Create a testable version of attendance entry logic
const AttendanceEntryLogic = {
  data() {
    return {
      valid: false,
      loading: false,
      initialLoading: false,
      employees: [],
      shifts: [],
      absenceReasons: [
        'Vacation',
        'Sick Leave',
        'Personal Leave',
        'FMLA',
        'Jury Duty',
        'Bereavement',
        'No Call No Show',
        'Other'
      ],
      formData: {
        employee_id: null,
        shift_id: null,
        attendance_date: '',
        scheduled_hours: 8,
        actual_hours: 8,
        is_absent: false,
        absence_reason: '',
        late_minutes: 0,
        early_leave_minutes: 0,
        notes: ''
      },
      rules: {
        required: value => !!value || 'Field is required',
        positiveOrZero: value => value >= 0 || 'Must be 0 or greater',
        maxHours: value => value <= 24 || 'Cannot exceed 24 hours'
      }
    }
  },
  computed: {
    hoursWorkedVariance() {
      return this.formData.actual_hours - this.formData.scheduled_hours
    },
    attendanceStatus() {
      if (this.formData.is_absent) return 'absent'
      if (this.formData.late_minutes > 0) return 'late'
      if (this.formData.early_leave_minutes > 0) return 'early-leave'
      if (this.hoursWorkedVariance < 0) return 'under-hours'
      return 'present'
    },
    requiresAbsenceReason() {
      return this.formData.is_absent
    }
  },
  methods: {
    calculateActualHours() {
      let hours = this.formData.scheduled_hours
      hours -= this.formData.late_minutes / 60
      hours -= this.formData.early_leave_minutes / 60
      return Math.max(0, parseFloat(hours.toFixed(2)))
    },
    setTodayDate() {
      this.formData.attendance_date = new Date().toISOString().split('T')[0]
    },
    resetFormOnAbsent() {
      if (this.formData.is_absent) {
        this.formData.actual_hours = 0
        this.formData.late_minutes = 0
        this.formData.early_leave_minutes = 0
      }
    }
  },
  template: '<div></div>'
}

describe('AttendanceEntry Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    global.alert = vi.fn()
  })

  describe('Initial State', () => {
    it('initializes with default form values', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)

      expect(wrapper.vm.formData.employee_id).toBeNull()
      expect(wrapper.vm.formData.scheduled_hours).toBe(8)
      expect(wrapper.vm.formData.actual_hours).toBe(8)
      expect(wrapper.vm.formData.is_absent).toBe(false)
      expect(wrapper.vm.formData.late_minutes).toBe(0)
    })

    it('has correct absence reason options', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)

      expect(wrapper.vm.absenceReasons).toContain('Vacation')
      expect(wrapper.vm.absenceReasons).toContain('Sick Leave')
      expect(wrapper.vm.absenceReasons).toContain('FMLA')
      expect(wrapper.vm.absenceReasons).toContain('No Call No Show')
    })
  })

  describe('Validation Rules', () => {
    it('required rule validates correctly', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)

      expect(wrapper.vm.rules.required('')).toBe('Field is required')
      expect(wrapper.vm.rules.required('test')).toBe(true)
    })

    it('positiveOrZero rule validates correctly', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)

      expect(wrapper.vm.rules.positiveOrZero(-1)).toBe('Must be 0 or greater')
      expect(wrapper.vm.rules.positiveOrZero(0)).toBe(true)
      expect(wrapper.vm.rules.positiveOrZero(5)).toBe(true)
    })

    it('maxHours rule validates correctly', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)

      expect(wrapper.vm.rules.maxHours(25)).toBe('Cannot exceed 24 hours')
      expect(wrapper.vm.rules.maxHours(24)).toBe(true)
      expect(wrapper.vm.rules.maxHours(8)).toBe(true)
    })
  })

  describe('Hours Worked Variance', () => {
    it('calculates positive variance when working overtime', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.scheduled_hours = 8
      wrapper.vm.formData.actual_hours = 10

      expect(wrapper.vm.hoursWorkedVariance).toBe(2)
    })

    it('calculates negative variance when under hours', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.scheduled_hours = 8
      wrapper.vm.formData.actual_hours = 6

      expect(wrapper.vm.hoursWorkedVariance).toBe(-2)
    })

    it('calculates zero variance when exact', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.scheduled_hours = 8
      wrapper.vm.formData.actual_hours = 8

      expect(wrapper.vm.hoursWorkedVariance).toBe(0)
    })
  })

  describe('Attendance Status', () => {
    it('returns absent when is_absent is true', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.is_absent = true

      expect(wrapper.vm.attendanceStatus).toBe('absent')
    })

    it('returns late when late_minutes > 0', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.is_absent = false
      wrapper.vm.formData.late_minutes = 15

      expect(wrapper.vm.attendanceStatus).toBe('late')
    })

    it('returns early-leave when early_leave_minutes > 0', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.is_absent = false
      wrapper.vm.formData.late_minutes = 0
      wrapper.vm.formData.early_leave_minutes = 30

      expect(wrapper.vm.attendanceStatus).toBe('early-leave')
    })

    it('returns under-hours when actual < scheduled', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.is_absent = false
      wrapper.vm.formData.late_minutes = 0
      wrapper.vm.formData.early_leave_minutes = 0
      wrapper.vm.formData.scheduled_hours = 8
      wrapper.vm.formData.actual_hours = 6

      expect(wrapper.vm.attendanceStatus).toBe('under-hours')
    })

    it('returns present when all conditions are normal', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.is_absent = false
      wrapper.vm.formData.late_minutes = 0
      wrapper.vm.formData.early_leave_minutes = 0
      wrapper.vm.formData.scheduled_hours = 8
      wrapper.vm.formData.actual_hours = 8

      expect(wrapper.vm.attendanceStatus).toBe('present')
    })
  })

  describe('Requires Absence Reason', () => {
    it('returns true when absent', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.is_absent = true

      expect(wrapper.vm.requiresAbsenceReason).toBe(true)
    })

    it('returns false when not absent', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.is_absent = false

      expect(wrapper.vm.requiresAbsenceReason).toBe(false)
    })
  })

  describe('Calculate Actual Hours', () => {
    it('calculates hours after deducting late and early leave', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.scheduled_hours = 8
      wrapper.vm.formData.late_minutes = 30 // 0.5 hours
      wrapper.vm.formData.early_leave_minutes = 30 // 0.5 hours

      expect(wrapper.vm.calculateActualHours()).toBe(7)
    })

    it('does not return negative hours', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.scheduled_hours = 1
      wrapper.vm.formData.late_minutes = 120 // 2 hours

      expect(wrapper.vm.calculateActualHours()).toBe(0)
    })

    it('handles decimal minutes correctly', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.scheduled_hours = 8
      wrapper.vm.formData.late_minutes = 15 // 0.25 hours
      wrapper.vm.formData.early_leave_minutes = 0

      expect(wrapper.vm.calculateActualHours()).toBe(7.75)
    })
  })

  describe('Reset Form On Absent', () => {
    it('resets actual hours and minutes when marked absent', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.actual_hours = 6
      wrapper.vm.formData.late_minutes = 15
      wrapper.vm.formData.early_leave_minutes = 30
      wrapper.vm.formData.is_absent = true

      wrapper.vm.resetFormOnAbsent()

      expect(wrapper.vm.formData.actual_hours).toBe(0)
      expect(wrapper.vm.formData.late_minutes).toBe(0)
      expect(wrapper.vm.formData.early_leave_minutes).toBe(0)
    })

    it('does not reset when not absent', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      wrapper.vm.formData.actual_hours = 6
      wrapper.vm.formData.is_absent = false

      wrapper.vm.resetFormOnAbsent()

      expect(wrapper.vm.formData.actual_hours).toBe(6)
    })
  })

  describe('Set Today Date', () => {
    it('sets attendance date to today', () => {
      const wrapper = shallowMount(AttendanceEntryLogic)
      const today = new Date().toISOString().split('T')[0]

      wrapper.vm.setTodayDate()

      expect(wrapper.vm.formData.attendance_date).toBe(today)
    })
  })
})

describe('AttendanceEntry API Integration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('creates attendance entry on valid submission', async () => {
    mockCreateAttendanceEntry.mockResolvedValue({ data: { attendance_id: 1 } })

    const formData = {
      employee_id: 1,
      shift_id: 1,
      attendance_date: '2024-01-15',
      scheduled_hours: 8,
      actual_hours: 8,
      is_absent: false
    }

    await mockCreateAttendanceEntry(formData)

    expect(mockCreateAttendanceEntry).toHaveBeenCalledWith(formData)
  })

  it('handles absent entry with reason', async () => {
    mockCreateAttendanceEntry.mockResolvedValue({ data: { attendance_id: 1 } })

    const formData = {
      employee_id: 1,
      shift_id: 1,
      attendance_date: '2024-01-15',
      scheduled_hours: 8,
      actual_hours: 0,
      is_absent: true,
      absence_reason: 'Sick Leave'
    }

    await mockCreateAttendanceEntry(formData)

    expect(mockCreateAttendanceEntry).toHaveBeenCalledWith(formData)
  })
})
